/* Concurrent filesystem, socket and fork stress for SMP bring-up (kernel
 * WT2.1). `smp-stress [workers [rounds]]` forks the workers together and
 * releases them at once; each round of each worker
 *
 * - writes a known pattern to a new file in its own directory, fsyncs it,
 *   renames it in place, reopens it, reads it back, checks it and unlinks it;
 * - writes a second file, fsyncs it, renames it into the one directory every
 *   worker shares, reads it back there and unlinks it, so the workers race
 *   updates of one directory;
 * - ping-pongs MESSAGES messages of varying size with a forked child over an
 *   AF_UNIX stream socketpair, the child answering each with a transform the
 *   worker checks, then reaps the child;
 * - forks a child that execs this program (even rounds) or exits directly (odd
 *   rounds) with a status computed from the worker and round, and checks it;
 * - starts a thread that keeps writing and checking its own pages while the
 *   worker maps, write-protects and unmaps others, so the address space the
 *   thread runs in on another CPU changes under it (TLB shootdown).
 *
 * Each worker sends its counts, or where its first check failed, through one
 * pipe all workers share and exits 0 only if every check held. The parent reaps and checks
 * every worker and prints exactly one line:
 *
 *   SMP_STRESS_PASS arch=<arch> workers=W rounds=R files=<n> messages=<n> forks=<n> seconds=<s>
 *   SMP_STRESS_FAIL arch=<arch> reason=<token>
 *
 * files counts the files written and verified, messages the verified round
 * trips and forks every child the workers reaped (socket peers and exec/exit
 * children). Output is integer-only so every profile, mips64 included, links
 * it without the quad-float formatter. Which CPU ran what is the kernel's
 * OK_SMP_CPUS report, not this probe's. */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#if defined(__i386__)
#define PROBE_ARCH "i386"
#elif defined(__x86_64__)
#define PROBE_ARCH "x86_64"
#elif defined(__arm__)
#define PROBE_ARCH "arm32"
#elif defined(__aarch64__)
#define PROBE_ARCH "aarch64"
#elif defined(__riscv) && __riscv_xlen == 32
#define PROBE_ARCH "rv32"
#elif defined(__riscv) && __riscv_xlen == 64
#define PROBE_ARCH "rv64"
#elif defined(__mips64)
#define PROBE_ARCH "mips64"
#elif defined(__mips__)
#define PROBE_ARCH "mips"
#elif defined(__loongarch64)
#define PROBE_ARCH "loongarch64"
#elif defined(__powerpc__) || defined(__PPC__)
#define PROBE_ARCH "ppc"
#else
#error "Unsupported SMP stress profile"
#endif

/* The kernel has 16 stream buffers system-wide: a pipe takes one and a
   socketpair two. The gate, the record channel and one socketpair per worker
   leave two for the rest of the system. The parent, the workers and one child
   per worker stay well inside the kernel's 64 native processes. */
#define DEFAULT_WORKERS 6
#define MAX_WORKERS 6
#define DEFAULT_ROUNDS 40
#define MAX_ROUNDS 10000
#define MESSAGES 4
#define MAX_FILE 6144
#define MAX_MESSAGE 768
#define SELF "/bin/smp-stress"

/* One per worker, written once to its pipe before it exits. */
struct record
{
    uint32_t worker, rounds, files, messages, forks;
    uint32_t failed, round, line, error;
};

struct line
{
    char text[256];
    size_t size;
};

static void put(struct line *out, const char *text)
{
    while (*text && out->size + 1 < sizeof out->text)
        out->text[out->size++] = *text++;
}

static void put_number(struct line *out, uint64_t value)
{
    char digits[21];
    size_t count = 0;
    do
        digits[count++] = (char)('0' + value % 10);
    while (value /= 10);
    while (count && out->size + 1 < sizeof out->text)
        out->text[out->size++] = digits[--count];
}

/* One write, so the result line is never split around kernel output. */
static void emit(struct line *out)
{
    out->text[out->size++] = '\n';
    const char *text = out->text;
    size_t size = out->size;
    while (size)
    {
        const ssize_t written = write(1, text, size);
        if (written < 0 && errno == EINTR)
            continue;
        if (written <= 0)
            _exit(2);
        text += written;
        size -= (size_t)written;
    }
}

static __attribute__((noreturn)) void fail(const char *reason, uint64_t detail)
{
    struct line out = {{0}, 0};
    put(&out, "SMP_STRESS_FAIL arch=" PROBE_ARCH " reason=");
    put(&out, reason);
    put(&out, "-");
    put_number(&out, detail);
    put(&out, " errno=");
    put_number(&out, (uint64_t)errno);
    emit(&out);
    _exit(1);
}

static int64_t monotonic(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t))
        return -1;
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

static int parse(const char *text, long low, long high, long *value)
{
    long result = 0;
    if (!*text)
        return -1;
    for (; *text; ++text)
    {
        if (*text < '0' || *text > '9' || result > high)
            return -1;
        result = result * 10 + (*text - '0');
    }
    if (result < low || result > high)
        return -1;
    *value = result;
    return 0;
}

static int write_all(int fd, const unsigned char *bytes, size_t size)
{
    while (size)
    {
        const ssize_t step = write(fd, bytes, size);
        if (step < 0 && errno == EINTR)
            continue;
        if (step <= 0)
            return -1;
        bytes += step;
        size -= (size_t)step;
    }
    return 0;
}

/* 0 once `size` bytes arrived, 1 on end of file before any byte, -1 otherwise. */
static int read_all(int fd, unsigned char *bytes, size_t size)
{
    size_t got = 0;
    while (got < size)
    {
        const ssize_t step = read(fd, bytes + got, size - got);
        if (step < 0 && errno == EINTR)
            continue;
        if (step == 0 && got == 0)
            return 1;
        if (step <= 0)
            return -1;
        got += (size_t)step;
    }
    return 0;
}

static pid_t reap(pid_t child, int *status)
{
    pid_t got;
    while ((got = waitpid(child, status, 0)) < 0 && errno == EINTR) {}
    return got;
}

static unsigned char pattern(unsigned seed, size_t at)
{
    return (unsigned char)((seed * 131u + at * 7u + (at >> 8) * 13u) & 0xffu);
}

static void name_into(char *out, const char *prefix, unsigned a, char separator, unsigned b)
{
    struct line text = {{0}, 0};
    put(&text, prefix);
    put_number(&text, a);
    if (separator)
    {
        text.text[text.size++] = separator;
        put_number(&text, b);
    }
    text.text[text.size] = 0;
    memcpy(out, text.text, text.size + 1);
}

static void join(char *out, const char *directory, const char *name)
{
    struct line text = {{0}, 0};
    put(&text, directory);
    put(&text, "/");
    put(&text, name);
    text.text[text.size] = 0;
    memcpy(out, text.text, text.size + 1);
}

static struct record result;
static int record_fd = -1;
static unsigned char buffer[MAX_FILE], readback[MAX_FILE];

static __attribute__((noreturn)) void finish(void)
{
    if (write_all(record_fd, (const unsigned char *)&result, sizeof result))
        _exit(3);
    _exit(result.failed ? 1 : 0);
}

#define CHECK(condition) do { if (!(condition)) { result.failed = 1; result.line = __LINE__; \
    result.error = (uint32_t)errno; finish(); } } while (0)

/* Write, fsync, rename `from` to `to`, reopen, check and unlink. */
static void file_cycle(const char *from, const char *to, unsigned seed, size_t size)
{
    for (size_t i = 0; i < size; ++i)
        buffer[i] = pattern(seed, i);
    int fd = open(from, O_WRONLY | O_CREAT | O_EXCL, 0644);
    CHECK(fd >= 0);
    /* Two writes, so the file is extended within one open. */
    CHECK(write_all(fd, buffer, size / 2) == 0);
    CHECK(write_all(fd, buffer + size / 2, size - size / 2) == 0);
    CHECK(fsync(fd) == 0);
    CHECK(close(fd) == 0);
    CHECK(rename(from, to) == 0);
    errno = 0;
    CHECK(open(from, O_RDONLY) < 0 && errno == ENOENT);
    /* stat is refused on mounts without a qualified stat policy; the size
       comes from the file offset instead. */
    fd = open(to, O_RDONLY);
    CHECK(fd >= 0);
    CHECK(lseek(fd, 0, SEEK_END) == (off_t)size && lseek(fd, 0, SEEK_SET) == 0);
    memset(readback, 0, size);
    CHECK(read_all(fd, readback, size) == 0);
    CHECK(memcmp(readback, buffer, size) == 0);
    unsigned char extra;
    CHECK(read(fd, &extra, 1) == 0);
    CHECK(close(fd) == 0);
    CHECK(unlink(to) == 0);
    errno = 0;
    CHECK(open(to, O_RDONLY) < 0 && errno == ENOENT);
    ++result.files;
}

static size_t message_size(unsigned seed, unsigned index)
{
    return 1 + (seed * 37u + index * 211u) % MAX_MESSAGE;
}

static unsigned char answer(unsigned char byte, unsigned index)
{
    return (unsigned char)(byte ^ (0x5au + index));
}

/* The socket peer: answer every message with its transform until EOF. */
static __attribute__((noreturn)) void peer(int fd, unsigned seed)
{
    unsigned char message[MAX_MESSAGE];
    for (unsigned index = 0; index < MESSAGES; ++index)
    {
        const size_t size = message_size(seed, index);
        if (read_all(fd, message, size))
            _exit(40);
        for (size_t i = 0; i < size; ++i)
        {
            if (message[i] != pattern(seed + index, i))
                _exit(41);
            message[i] = answer(message[i], index);
        }
        if (write_all(fd, message, size))
            _exit(42);
    }
    unsigned char extra;
    if (read_all(fd, &extra, 1) != 1)
        _exit(43);
    _exit(close(fd) == 0 ? 0 : 44);
}

static void socket_cycle(unsigned seed)
{
    int pair[2];
    CHECK(socketpair(AF_UNIX, SOCK_STREAM, 0, pair) == 0);
    const pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        close(record_fd);
        close(pair[0]);
        peer(pair[1], seed);
    }
    CHECK(close(pair[1]) == 0);
    unsigned char message[MAX_MESSAGE], reply[MAX_MESSAGE];
    for (unsigned index = 0; index < MESSAGES; ++index)
    {
        const size_t size = message_size(seed, index);
        for (size_t i = 0; i < size; ++i)
            message[i] = pattern(seed + index, i);
        CHECK(write_all(pair[0], message, size) == 0);
        CHECK(read_all(pair[0], reply, size) == 0);
        for (size_t i = 0; i < size; ++i)
            CHECK(reply[i] == answer(message[i], index));
        ++result.messages;
    }
    /* The peer exits 0 only once it reads end of file after the last message. */
    CHECK(close(pair[0]) == 0);
    int status = 0;
    CHECK(reap(child, &status) == child);
    CHECK(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    ++result.forks;
}

static void fork_cycle(const char *self, unsigned worker, unsigned round)
{
    const unsigned expected = 1 + (worker * 7u + round * 3u) % 200u;
    char code[12];
    name_into(code, "", expected, 0, 0);
    const pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        close(record_fd);
        if (round % 2)
            _exit((int)expected);
        execl(self, self, "--exit", code, (char *)0);
        _exit(250);
    }
    int status = 0;
    CHECK(reap(child, &status) == child);
    CHECK(WIFEXITED(status) && WEXITSTATUS(status) == expected);
    ++result.forks;
}

struct toucher
{
    unsigned char *pages;
    size_t size;
    unsigned seed;
    int stop, bad;
    unsigned long passes;
};

static void *touch(void *opaque)
{
    struct toucher *t = opaque;
    while (!__atomic_load_n(&t->stop, __ATOMIC_ACQUIRE))
    {
        const unsigned long pass = __atomic_load_n(&t->passes, __ATOMIC_RELAXED);
        for (size_t i = 0; i < t->size; i += 64)
            t->pages[i] = pattern(t->seed + (unsigned)pass, i);
        for (size_t i = 0; i < t->size; i += 64)
            if (t->pages[i] != pattern(t->seed + (unsigned)pass, i))
                __atomic_store_n(&t->bad, 1, __ATOMIC_RELEASE);
        __atomic_store_n(&t->passes, pass + 1, __ATOMIC_RELEASE);
    }
    return 0;
}

static void wait_passes(struct toucher *t, unsigned long passes)
{
    while (__atomic_load_n(&t->passes, __ATOMIC_ACQUIRE) < passes)
        sched_yield();
}

static void vm_cycle(unsigned seed)
{
    enum { PAGE = 4096, SIZE = 4 * PAGE, CHANGES = 6 };
    unsigned char *own = mmap(0, SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(own != MAP_FAILED);
    struct toucher t = {own, SIZE, seed, 0, 0, 0};
    pthread_t thread;
    CHECK(pthread_create(&thread, 0, touch, &t) == 0);
    wait_passes(&t, 1);
    for (unsigned change = 0; change < CHANGES; ++change)
    {
        unsigned char *other = mmap(0, SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        CHECK(other != MAP_FAILED);
        for (size_t i = 0; i < SIZE; i += PAGE)
            other[i] = pattern(seed + change, i);
        CHECK(mprotect(other, SIZE, PROT_READ) == 0);
        for (size_t i = 0; i < SIZE; i += PAGE)
            CHECK(other[i] == pattern(seed + change, i));
        CHECK(munmap(other, SIZE) == 0);
    }
    /* The thread went on writing its pages across every change. */
    wait_passes(&t, __atomic_load_n(&t.passes, __ATOMIC_ACQUIRE) + 1);
    __atomic_store_n(&t.stop, 1, __ATOMIC_RELEASE);
    CHECK(pthread_join(thread, 0) == 0);
    CHECK(!__atomic_load_n(&t.bad, __ATOMIC_ACQUIRE));
    CHECK(munmap(own, SIZE) == 0);
}

static __attribute__((noreturn)) void worker(const char *self, const char *base, unsigned index,
                                             unsigned rounds, int gate)
{
    result.worker = index;
    char own[64], shared[64], name[32], from[96], to[96];
    join(shared, base, "shared");
    name_into(name, "w", index, 0, 0);
    join(own, base, name);
    CHECK(mkdir(own, 0755) == 0);
    /* Every worker leaves the gate together, once the parent closes it. */
    unsigned char byte;
    CHECK(read_all(gate, &byte, 1) == 1);
    CHECK(close(gate) == 0);
    for (unsigned round = 0; round < rounds; ++round)
    {
        result.round = round;
        const unsigned seed = index * 1000003u + round * 7919u;
        name_into(name, "a", round, 0, 0);
        join(from, own, name);
        name_into(name, "b", round, 0, 0);
        join(to, own, name);
        file_cycle(from, to, seed, 512 + (seed % (MAX_FILE - 512)));

        name_into(name, "x", round, 0, 0);
        join(from, own, name);
        name_into(name, "w", index, '-', round);
        join(to, shared, name);
        file_cycle(from, to, seed + 1, 64 + (seed % 2000));

        socket_cycle(seed);
        fork_cycle(self, index, round);
        vm_cycle(seed);
        result.rounds = round + 1;
    }
    CHECK(rmdir(own) == 0);
    finish();
}

int main(int argc, char **argv)
{
    long value;
    if (argc == 3 && !strcmp(argv[1], "--exit"))
    {
        if (parse(argv[2], 1, 255, &value))
            _exit(251);
        _exit((int)value);
    }
    long workers = DEFAULT_WORKERS, rounds = DEFAULT_ROUNDS;
    if (argc > 3 || (argc > 1 && parse(argv[1], 1, MAX_WORKERS, &workers)) ||
        (argc > 2 && parse(argv[2], 1, MAX_ROUNDS, &rounds)))
    {
        errno = EINVAL;
        fail("usage", 0);
    }
    const char *self = argc > 0 && argv[0][0] == '/' ? argv[0] : SELF;

    char base[64], shared[64], name[32];
    name_into(name, "/tmp/smp-stress-", (unsigned)getpid(), 0, 0);
    memcpy(base, name, strlen(name) + 1);
    join(shared, base, "shared");
    if (mkdir(base, 0755) || mkdir(shared, 0755))
        fail("mkdir", 0);

    /* The gate releases the workers together; every worker writes its one
       record to the shared channel, in whatever order they finish. */
    int gate[2], channel[2];
    if (pipe(gate) || pipe(channel))
        fail("pipe", 0);
    pid_t children[MAX_WORKERS];
    const int64_t began = monotonic();
    for (long i = 0; i < workers; ++i)
    {
        children[i] = fork();
        if (children[i] < 0)
            fail("fork", (uint64_t)i);
        if (children[i] == 0)
        {
            close(gate[1]);
            close(channel[0]);
            record_fd = channel[1];
            worker(self, base, (unsigned)i, (unsigned)rounds, gate[0]);
        }
    }
    close(gate[0]);
    close(gate[1]);
    close(channel[1]);

    int statuses[MAX_WORKERS] = {0}, reaped[MAX_WORKERS] = {0}, received[MAX_WORKERS] = {0};
    for (long i = 0; i < workers; ++i)
        reaped[i] = reap(children[i], &statuses[i]) == children[i];
    struct record reports[MAX_WORKERS];
    for (;;)
    {
        struct record report;
        const int got = read_all(channel[0], (unsigned char *)&report, sizeof report);
        if (got == 1)
            break;
        if (got || report.worker >= (uint32_t)workers || received[report.worker])
            fail("record", got ? 0 : report.worker);
        reports[report.worker] = report;
        received[report.worker] = 1;
    }
    close(channel[0]);

    uint64_t files = 0, messages = 0, forks = 0;
    long failed = -1;
    struct record first = {0};
    for (long i = 0; i < workers; ++i)
    {
        const int status = statuses[i];
        const struct record report = reports[i];
        const int good = reaped[i] && WIFEXITED(status) && WEXITSTATUS(status) == 0 && received[i] &&
                         !report.failed && report.rounds == (uint32_t)rounds &&
                         report.files == 2 * (uint32_t)rounds && report.messages == MESSAGES * (uint32_t)rounds &&
                         report.forks == 2 * (uint32_t)rounds;
        if (!good && failed < 0)
        {
            failed = i;
            first = received[i] ? report : (struct record){(uint32_t)i, 0, 0, 0, 0, 1, 0, 0, 0};
            if (!reaped[i])
                first.line = 30000u;
            else if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
                first.line = first.line ? first.line : (WIFEXITED(status) ? 10000u + WEXITSTATUS(status)
                                                                          : 20000u + WTERMSIG(status));
        }
        if (received[i])
        {
            files += report.files;
            messages += report.messages;
            forks += report.forks;
        }
    }
    const int64_t ended = monotonic();
    if (failed >= 0)
    {
        struct line out = {{0}, 0};
        put(&out, "SMP_STRESS_FAIL arch=" PROBE_ARCH " reason=worker-");
        put_number(&out, (uint64_t)failed);
        put(&out, "-round-");
        put_number(&out, first.round);
        put(&out, "-line-");
        put_number(&out, first.line);
        put(&out, "-errno-");
        put_number(&out, first.error);
        emit(&out);
        return 1;
    }
    if (rmdir(shared) || rmdir(base))
        fail("rmdir", 0);
    if (began < 0 || ended < began)
        fail("clock", 0);
    const uint64_t milliseconds = (uint64_t)(ended - began) / 1000000u;
    struct line out = {{0}, 0};
    put(&out, "SMP_STRESS_PASS arch=" PROBE_ARCH " workers=");
    put_number(&out, (uint64_t)workers);
    put(&out, " rounds=");
    put_number(&out, (uint64_t)rounds);
    put(&out, " files=");
    put_number(&out, files);
    put(&out, " messages=");
    put_number(&out, messages);
    put(&out, " forks=");
    put_number(&out, forks);
    put(&out, " seconds=");
    put_number(&out, milliseconds / 1000u);
    put(&out, ".");
    put_number(&out, milliseconds / 100u % 10u);
    put_number(&out, milliseconds / 10u % 10u);
    put_number(&out, milliseconds % 10u);
    emit(&out);
    return 0;
}
