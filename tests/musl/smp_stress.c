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
 * - forks a child that starts a thread spinning in user mode, preferably on
 *   another CPU, and then execs this program (rounds 0 and 2 mod 4), exits
 *   directly (round 1 mod 4) with a status computed from the worker and
 *   round, or is killed by the worker with SIGKILL (round 3 mod 4), and
 *   checks the status; the exec, the exit and the kill each end a thread
 *   group whose other thread may run on another CPU (the kernel's group
 *   quiesce, OK_SMP_WAKE group_waits and frozen_skips);
 * - starts a thread that keeps writing and checking its own pages while the
 *   worker maps, write-protects and unmaps others, so the address space the
 *   thread runs in on another CPU changes under it (TLB shootdown);
 * - on the RAM filesystem (/run): creates a file, looks it up, renames it
 *   into a directory every worker shares, looks up both names, appends to it
 *   with O_APPEND, checks its size and unlinks it (metadata);
 * - ping-pongs PINGS bytes with a forked child over two pipes (pipes);
 * - opens a PTY pair through /dev/ptmx, sets the slave raw and echoes a
 *   message from the master to the slave and an answer back (ptys);
 * - opens an AF_INET datagram socket, binds it to an ephemeral port, sends a
 *   few datagrams to the static link peer (each is sent, or queued, or
 *   ENOBUFS when the kernel's transmit backlog is full) and closes it (udp);
 *   a boot without a NIC refuses the socket, counted as udp_nolink.
 *
 * Each worker sends its counts, or where its first check failed, through one
 * pipe all workers share and exits 0 only if every check held. The parent reaps and checks
 * every worker and prints exactly one line (`smp-stress W R hotplug` also runs
 * the user CPU hotplug controller described above controller() and adds its
 * counts; its pinned children are announced by SMP_STRESS_PINNED lines and
 * online writes that failed with EIO by SMP_STRESS_ONLINE_EIO lines):
 *
 *   SMP_STRESS_PASS arch=<arch> workers=W rounds=R files=<n> messages=<n> forks=<n> seconds=<s>
 *                   metadata=<n> pipes=<n> ptys=<n> udp=<n> udp_nolink=<n>
 *                   [hotplug_cycles=<n> pinned=<n> racing=<n> killed=<n> killed_filed=<n> refusals=<n>]
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
#include <signal.h>
#include <stdlib.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <termios.h>
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
#define PINGS 16
#define RAM_ROOT "/run"
#define MAX_FILE 6144
#define MAX_MESSAGE 768
#define SELF "/bin/smp-stress"

/* One per worker, written once to its pipe before it exits. */
struct record
{
    uint32_t worker, rounds, files, messages, forks;
    uint32_t failed, round, line, error;
    uint32_t metadata, pipes, ptys, udp, udp_nolink;
};

struct line
{
    char text[512];
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

/* The fork cycle's child: a second thread that spins in user mode, placed
   away from the child's own CPU when the affinity allows. `ready` (shared
   with the worker) is set once it ran. */
static volatile uint32_t *ready;
static unsigned long spun;

static void *spin(void *opaque)
{
    (void)opaque;
    for (;;)
        __atomic_add_fetch(&spun, 1, __ATOMIC_RELAXED);
    return 0;
}

static void start_spinner(void)
{
    pthread_t thread;
    cpu_set_t away;
    CPU_ZERO(&away);
    const int self = sched_getcpu();
    if (!sched_getaffinity(0, sizeof away, &away) && self >= 0 && CPU_COUNT(&away) > 1)
        CPU_CLR(self, &away);
    if (pthread_create(&thread, 0, spin, 0))
        _exit(249);
    /* Best effort: the thread stays wherever the kernel put it otherwise. */
    (void)pthread_setaffinity_np(thread, sizeof away, &away);
    /* A bounded wait for the first spin: the group then has a thread that
       may be in user mode on another CPU when it execs, exits or dies. */
    for (unsigned wait = 0; wait < 100000 && !__atomic_load_n(&spun, __ATOMIC_RELAXED); ++wait)
        sched_yield();
    __atomic_store_n(ready, 1, __ATOMIC_RELEASE);
}

static void fork_cycle(const char *self, unsigned worker, unsigned round)
{
    const unsigned expected = 1 + (worker * 7u + round * 3u) % 200u;
    char code[12];
    name_into(code, "", expected, 0, 0);
    __atomic_store_n(ready, 0, __ATOMIC_RELEASE);
    const pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        close(record_fd);
        start_spinner();
        if (round % 4 == 3)
            for (;;)
                __atomic_add_fetch(&spun, 1, __ATOMIC_RELAXED);
        if (round % 4 == 1)
            _exit((int)expected);
        execl(self, self, "--exit", code, (char *)0);
        _exit(250);
    }
    int status = 0;
    if (round % 4 == 3)
    {
        while (!__atomic_load_n(ready, __ATOMIC_ACQUIRE))
            sched_yield();
        CHECK(kill(child, SIGKILL) == 0);
    }
    CHECK(reap(child, &status) == child);
    if (round % 4 == 3)
        CHECK(WIFSIGNALED(status) && WTERMSIG(status) == SIGKILL);
    else
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

/* The size of `path` from its end-of-file offset; -1 when it cannot be opened. */
static off_t file_size(const char *path)
{
    const int fd = open(path, O_RDONLY);
    if (fd < 0)
        return -1;
    const off_t size = lseek(fd, 0, SEEK_END);
    close(fd);
    return size;
}

/* RAM filesystem metadata: create, look up, rename into the shared
   directory, look up both names, O_APPEND, unlink (kernel WP5:
   ram_topology, the namespace gate shared, Node::append). */
static void metadata_cycle(const char *own, const char *shared, unsigned index, unsigned round, unsigned seed)
{
    char name[32], from[96], to[96];
    name_into(name, "m", round, 0, 0);
    join(from, own, name);
    name_into(name, "m", index, '-', round);
    join(to, shared, name);
    const size_t size = 1 + seed % 3000;
    for (size_t i = 0; i < size; ++i)
        buffer[i] = pattern(seed + 7, i);
    int fd = open(from, O_WRONLY | O_CREAT | O_EXCL, 0640);
    CHECK(fd >= 0);
    CHECK(write_all(fd, buffer, size) == 0);
    CHECK(close(fd) == 0);
    /* stat is refused here too (no qualified stat policy on the RAM mount):
       lookups are opens, sizes are end-of-file offsets. */
    CHECK(file_size(from) == (off_t)size);
    CHECK(rename(from, to) == 0);
    errno = 0;
    CHECK(open(from, O_RDONLY) < 0 && errno == ENOENT);
    CHECK(file_size(to) == (off_t)size);
    fd = open(to, O_WRONLY | O_APPEND);
    CHECK(fd >= 0);
    CHECK(write_all(fd, buffer, 16) == 0);
    CHECK(close(fd) == 0);
    CHECK(file_size(to) == (off_t)(size + 16));
    CHECK(unlink(to) == 0);
    errno = 0;
    CHECK(open(to, O_RDONLY) < 0 && errno == ENOENT);
    ++result.metadata;
}

/* Pipe ping-pong: PINGS bytes down to a forked child, each answered + 1 up. */
static void pipe_cycle(unsigned seed)
{
    int down[2], up[2];
    CHECK(pipe(down) == 0);
    CHECK(pipe(up) == 0);
    const pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        close(record_fd);
        close(down[1]);
        close(up[0]);
        unsigned char byte;
        for (unsigned i = 0; i < PINGS; ++i)
        {
            if (read_all(down[0], &byte, 1))
                _exit(50);
            byte = (unsigned char)(byte + 1);
            if (write_all(up[1], &byte, 1))
                _exit(51);
        }
        if (read_all(down[0], &byte, 1) != 1)
            _exit(52);
        _exit(0);
    }
    CHECK(close(down[0]) == 0 && close(up[1]) == 0);
    for (unsigned i = 0; i < PINGS; ++i)
    {
        const unsigned char sent = pattern(seed, i);
        unsigned char back = 0;
        CHECK(write_all(down[1], &sent, 1) == 0);
        CHECK(read_all(up[0], &back, 1) == 0 && back == (unsigned char)(sent + 1));
    }
    CHECK(close(down[1]) == 0);
    int status = 0;
    CHECK(reap(child, &status) == child);
    CHECK(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    CHECK(close(up[0]) == 0);
    ++result.pipes;
}

/* PTY echo: master to raw slave and an answer back (kernel WP5: the tty
   lock, prepare/copy/commit reads). A full pair table is retried. */
static void pty_cycle(unsigned seed)
{
    int master = -1;
    for (unsigned attempt = 0; attempt < 1000 && master < 0; ++attempt)
    {
        master = posix_openpt(O_RDWR | O_NOCTTY);
        if (master < 0)
        {
            CHECK(errno == ENOSPC || errno == EAGAIN);
            sched_yield();
        }
    }
    CHECK(master >= 0);
    CHECK(grantpt(master) == 0 && unlockpt(master) == 0);
    const char *path = ptsname(master);
    CHECK(path != 0);
    const int slave = open(path, O_RDWR | O_NOCTTY);
    CHECK(slave >= 0);
    struct termios mode;
    CHECK(tcgetattr(slave, &mode) == 0);
    cfmakeraw(&mode);
    CHECK(tcsetattr(slave, TCSANOW, &mode) == 0);
    unsigned char out[32], in[32];
    const size_t size = 1 + seed % sizeof out;
    for (size_t i = 0; i < size; ++i)
        out[i] = pattern(seed + 3, i);
    CHECK(write_all(master, out, size) == 0);
    CHECK(read_all(slave, in, size) == 0 && memcmp(in, out, size) == 0);
    for (size_t i = 0; i < size; ++i)
        out[i] = answer(in[i], 1);
    CHECK(write_all(slave, out, size) == 0);
    CHECK(read_all(master, in, size) == 0 && memcmp(in, out, size) == 0);
    CHECK(close(slave) == 0 && close(master) == 0);
    ++result.ptys;
}

/* A datagram socket's admission, ephemeral bind, sends to the static link
   peer and close (kernel WP5: try-transmit under net_stack, ENOBUFS). */
static void udp_cycle(unsigned seed)
{
    const int fd = socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (fd < 0)
    {
        /* No NIC in this boot: the link cannot start. */
        CHECK(errno == ENODEV || errno == ENXIO || errno == EIO || errno == ENETDOWN || errno == ENOENT);
        ++result.udp_nolink;
        return;
    }
    struct sockaddr_in local = {0};
    local.sin_family = AF_INET;
    local.sin_addr.s_addr = htonl(INADDR_ANY);
    CHECK(bind(fd, (const struct sockaddr *)&local, sizeof local) == 0);
    socklen_t length = sizeof local;
    CHECK(getsockname(fd, (struct sockaddr *)&local, &length) == 0 && local.sin_port != 0);
    struct sockaddr_in peer = {0};
    peer.sin_family = AF_INET;
    peer.sin_port = htons(9);
    peer.sin_addr.s_addr = htonl(0xc0000201u);
    unsigned char payload[64];
    const size_t size = 1 + seed % sizeof payload;
    for (size_t i = 0; i < size; ++i)
        payload[i] = pattern(seed, i);
    for (unsigned i = 0; i < 4; ++i)
    {
        const ssize_t sent = sendto(fd, payload, size, 0, (const struct sockaddr *)&peer, sizeof peer);
        CHECK(sent == (ssize_t)size || (sent < 0 && errno == ENOBUFS));
    }
    CHECK(close(fd) == 0);
    ++result.udp;
}

static __attribute__((noreturn)) void worker(const char *self, const char *base, unsigned index,
                                             unsigned rounds, int gate)
{
    result.worker = index;
    char own[64], shared[64], name[32], from[96], to[96], ram_base[64], ram_own[64], ram_shared[64];
    join(shared, base, "shared");
    name_into(name, "w", index, 0, 0);
    join(own, base, name);
    CHECK(mkdir(own, 0755) == 0);
    ready = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    CHECK(ready != MAP_FAILED);
    /* The parent made /run/<base name> and its shared directory. */
    join(ram_base, RAM_ROOT, base + 5);
    join(ram_shared, ram_base, "shared");
    join(ram_own, ram_base, name);
    CHECK(mkdir(ram_own, 0755) == 0);
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
        metadata_cycle(ram_own, ram_shared, index, round, seed);
        pipe_cycle(seed);
        pty_cycle(seed);
        udp_cycle(seed);
        result.rounds = round + 1;
    }
    CHECK(rmdir(own) == 0);
    CHECK(rmdir(ram_own) == 0);
    finish();
}

/* User CPU hotplug (smp-stress W R hotplug): a controller process cycles every
 * present secondary CPU offline and online again through
 * /sys/devices/system/cpu/cpuN/online while the workers run, until the parent
 * creates the stop file and at least two full cycles ran. Each cycle checks,
 * while CPU N is offline, that cpuN/online reads 0, the online list excludes
 * N and the offline list names it, sched_getaffinity counts the online CPUs
 * as sysconf(_SC_NPROCESSORS_ONLN) does, and no sched_getcpu() reports N. On
 * top, per secondary and cycle in turn:
 *
 * - pinned: a child pinned to N runs on N; N goes offline and the child keeps
 *   running elsewhere with its affinity reset (the kernel names it in an
 *   OK_SMP_AFFINITY_BROKEN line; the controller prints SMP_STRESS_PINNED);
 * - racing: two children write the same value to cpuN/online at once; each
 *   write succeeds or is EBUSY (or, writing "1", EIO as below), never
 *   anything else, and one succeeds or failed with EIO;
 * - killed: children writing "0" get SIGKILL (kill_writer), possibly while
 *   they wait in the uninterruptible hotplug wait, until one died after its
 *   request was filed; with three or more CPUs also writers of "0" and of
 *   "1" (to an offline N) killed right after they announced their write
 *   through shared memory, at varied points of their uninterruptible wait
 *   (kill_waiting); the CPU stays usable either way;
 * - otherwise the cycle writes directly or, every other time, runs the
 *   distribution's /bin/chcpu -d and -e.
 *
 * The direct writes of the pinned and plain cycles rotate through write(),
 * writev() (digit and newline in two vectors) and pwrite(), each of which
 * waits for the service; the controller stops only after every one took a
 * CPU offline and back.
 *
 * Writing "1" may fail with EIO, as on Linux when a CPU does not come up:
 * under host load an x86 restart's clock handshake can find no round tight
 * enough, or the CPU misses its start timeout. The CPU then reads offline;
 * the controller announces each such write (SMP_STRESS_ONLINE_EIO) and
 * writes "1" again, at most ONLINE_RETRIES times in a row. Any other error,
 * an EIO that left the CPU online and an EIO writing "0" fail the probe; the
 * runner accepts each announced EIO only against a kernel OK_SMP_HOTPLUG_FAIL
 * line that names a timing reason for that CPU.
 *
 * Before the first cycle it checks the refusals: cpu0/online is ENOENT
 * (O_WRONLY) and EACCES (O_CREAT), `online` opened for writing is EACCES,
 * "x" is EINVAL and uid 1000 gets EACCES. Its record: rounds = cycles, files =
 * pinned children that survived, messages = racing pairs, forks = kills that
 * landed, round = refusals checked and, as it passed, error = kills whose
 * request was filed (the CPU went offline although its writer died). */
#define CPU_ROOT "/sys/devices/system/cpu"
#define MAX_CPUS 16

static long cpu_list(const char *name)
{
    char path[64], text[64];
    join(path, CPU_ROOT, name);
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        return -1;
    ssize_t got = read(fd, text, sizeof text - 1);
    close(fd);
    if (got <= 0)
        return -1;
    text[got] = 0;
    long mask = 0;
    const char *p = text;
    if (*p == '\n')
        return 0;
    for (;;)
    {
        long first = 0, last;
        if (*p < '0' || *p > '9')
            return -1;
        while (*p >= '0' && *p <= '9')
            first = first * 10 + (*p++ - '0');
        last = first;
        if (*p == '-')
        {
            last = 0;
            ++p;
            while (*p >= '0' && *p <= '9')
                last = last * 10 + (*p++ - '0');
        }
        if (first > last || last >= MAX_CPUS)
            return -1;
        for (long cpu = first; cpu <= last; ++cpu)
            mask |= 1L << cpu;
        if (*p == ',')
        {
            ++p;
            continue;
        }
        return *p == '\n' ? mask : -1;
    }
}

static void online_path(char *path, unsigned cpu)
{
    char name[16];
    name_into(name, "cpu", cpu, 0, 0);
    join(path, CPU_ROOT, name);
    join(path, path, "online");
}

/* One write of `value` to cpuN/online: 0 on success, else errno. `method`
   0 is write(); 1 is writev() with the digit and the newline in two
   vectors; 2 is pwrite() at offset 0. */
static int set_cpu_via(unsigned cpu, char value, unsigned method)
{
    char path[64];
    online_path(path, cpu);
    int fd = open(path, O_WRONLY);
    if (fd < 0)
        return errno ? errno : EIO;
    char text[2] = {value, '\n'};
    struct iovec parts[2] = {{&text[0], 1}, {&text[1], 1}};
    const ssize_t wrote = method == 1 ? writev(fd, parts, 2) : method == 2 ? pwrite(fd, text, 2, 0)
                                                                          : write(fd, text, 2);
    const int error = wrote == 2 ? 0 : wrote < 0 ? errno : EIO;
    close(fd);
    return error;
}

static int set_cpu(unsigned cpu, char value)
{
    return set_cpu_via(cpu, value, 0);
}

/* cpuN/online's digit, or -1. */
static int cpu_state(unsigned cpu)
{
    char path[64], text[4];
    online_path(path, cpu);
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        return -1;
    const ssize_t got = read(fd, text, sizeof text);
    close(fd);
    return got == 2 && text[1] == '\n' && (text[0] == '0' || text[0] == '1') ? text[0] - '0' : -1;
}

/* Consecutive EIO online failures accepted at one site before the probe fails. */
#define ONLINE_RETRIES 8

/* An online write of `cpu` failed with EIO and left it offline. */
static void say_online_eio(unsigned cpu, const char *site)
{
    struct line out = {{0}, 0};
    put(&out, "SMP_STRESS_ONLINE_EIO cpu=");
    put_number(&out, cpu);
    put(&out, " site=");
    put(&out, site);
    emit(&out);
}

/* Writes "1" through `method` (set_cpu_via); an EIO that left the CPU
   offline is announced and written again. Returns 0 or the last error. */
static int online_via(unsigned cpu, unsigned method, const char *site)
{
    for (int failed = 0;; ++failed)
    {
        const int error = set_cpu_via(cpu, '1', method);
        if (error != EIO || failed == ONLINE_RETRIES || cpu_state(cpu) != 0)
            return error;
        say_online_eio(cpu, site);
    }
}

static long affinity(void)
{
    cpu_set_t set;
    CPU_ZERO(&set);
    if (sched_getaffinity(0, sizeof set, &set))
        return -1;
    long mask = 0;
    for (int cpu = 0; cpu < MAX_CPUS; ++cpu)
        if (CPU_ISSET(cpu, &set))
            mask |= 1L << cpu;
    return CPU_COUNT(&set) == __builtin_popcountl(mask) ? mask : -1;
}

static int pin(long mask)
{
    cpu_set_t set;
    CPU_ZERO(&set);
    for (int cpu = 0; cpu < MAX_CPUS; ++cpu)
        if (mask & (1L << cpu))
            CPU_SET(cpu, &set);
    return sched_setaffinity(0, sizeof set, &set);
}

/* Bring `cpu` online again, retrying while a killed writer's request still runs. */
static int restore_cpu(unsigned cpu)
{
    for (int attempt = 0, failed = 0; attempt < 400; ++attempt)
    {
        const int state = cpu_state(cpu);
        if (state == 1)
            return 0;
        const int error = state == 0 ? set_cpu(cpu, '1') : EBUSY;
        if (!error)
            return 0;
        if (error == EIO && failed < ONLINE_RETRIES && cpu_state(cpu) == 0)
        {
            say_online_eio(cpu, "restore");
            ++failed;
            continue;
        }
        if (error != EBUSY)
            return error;
        const struct timespec pause = {0, 10000000};
        nanosleep(&pause, 0);
    }
    return EBUSY;
}

/* While `cpu` is offline: the files, the affinity and getcpu agree. */
static void check_offline(unsigned cpu)
{
    const long online = cpu_list("online"), offline = cpu_list("offline"), present = cpu_list("present");
    CHECK(cpu_state(cpu) == 0);
    CHECK(online > 0 && !(online & (1L << cpu)) && offline >= 0 && (offline & (1L << cpu)));
    CHECK(offline == (present & ~online));
    const long allowed = affinity();
    CHECK(allowed == online && sysconf(_SC_NPROCESSORS_ONLN) == __builtin_popcountl(online));
    for (int sample = 0; sample < 32; ++sample)
    {
        const int here = sched_getcpu();
        CHECK(here >= 0 && here != (int)cpu && (online & (1L << here)));
        sched_yield();
    }
}

/* Exit codes of a racing writer: 0 written, 1 EBUSY, 3 EIO, 2 anything else. */
static __attribute__((noreturn)) void racer(unsigned cpu, char value)
{
    const int error = set_cpu(cpu, value);
    _exit(error == 0 ? 0 : error == EBUSY ? 1 : error == EIO ? 3 : 2);
}

/* A child pinned to `cpu` until its affinity breaks; exits 0 if it kept running. */
static __attribute__((noreturn)) void pinned_child(unsigned cpu, const char *flag)
{
    if (pin(1L << cpu) || affinity() != (1L << cpu))
        _exit(2);
    sched_yield();
    if (sched_getcpu() != (int)cpu)
        _exit(3);
    const int fd = open(flag, O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (fd < 0)
        _exit(4);
    close(fd);
    /* User-mode work on its CPU until the offline resets the mask. */
    volatile unsigned long spin = 0;
    long now = affinity();
    /* While the CPU leaves, its last calls on it see no online CPU allowed. */
    for (unsigned long rounds = 0; now == (1L << cpu) || now == 0; ++rounds, now = affinity())
    {
        for (int i = 0; i < 20000; ++i)
            spin = spin + (unsigned long)i;
        if (rounds > 2000000)
            _exit(5);
    }
    /* Reset to every CPU; it now runs on an online one. */
    const long online = cpu_list("online");
    const int here = sched_getcpu();
    _exit(now == online && here >= 0 && here != (int)cpu ? 0 : 6);
}

/* Runs /bin/chcpu OPTION CPU; its exit status, or -1. Its standard error
   goes to `errors` (NUL-terminated) when given, else to the console. */
static int chcpu_into(const char *option, unsigned cpu, char *errors, size_t size)
{
    char number[16];
    name_into(number, "", cpu, 0, 0);
    int pipe_fds[2] = {-1, -1};
    if (errors && pipe(pipe_fds))
        return -1;
    const pid_t child = fork();
    if (child < 0)
    {
        if (errors)
            close(pipe_fds[0]), close(pipe_fds[1]);
        return -1;
    }
    if (child == 0)
    {
        if (errors && (dup2(pipe_fds[1], 2) != 2 || close(pipe_fds[0]) || close(pipe_fds[1])))
            _exit(126);
        char *const argv[] = {"/bin/chcpu", (char *)option, number, 0};
        char *const envp[] = {0};
        execve(argv[0], argv, envp);
        _exit(127);
    }
    if (errors)
    {
        close(pipe_fds[1]);
        size_t got = 0;
        for (;;)
        {
            const ssize_t part = read(pipe_fds[0], errors + got, size - 1 - got);
            if (part < 0 && errno == EINTR)
                continue;
            if (part <= 0)
                break;
            got += (size_t)part;
            if (got == size - 1)
                break;
        }
        errors[got] = 0;
        close(pipe_fds[0]);
    }
    int status = 0;
    if (reap(child, &status) != child || !WIFEXITED(status))
        return -1;
    return WEXITSTATUS(status);
}

static int chcpu(const char *option, unsigned cpu)
{
    return chcpu_into(option, cpu, 0, 0);
}

/* chcpu -e CPU; a failure whose only message is the EIO of a CPU that did
   not come up (and left it offline) is announced and run again. */
static int chcpu_enable(unsigned cpu)
{
    for (int failed = 0;; ++failed)
    {
        char errors[128], number[16];
        const int status = chcpu_into("-e", cpu, errors, sizeof errors);
        name_into(number, "", cpu, 0, 0);
        struct line expected = {{0}, 0};
        put(&expected, "chcpu: CPU ");
        put(&expected, number);
        put(&expected, " enable failed: I/O error\n");
        expected.text[expected.size] = 0;
        if (status != 1 || strcmp(errors, expected.text) || failed == ONLINE_RETRIES || cpu_state(cpu) != 0)
        {
            if (status && errors[0])
            {
                /* What chcpu said, for the console. */
                struct line out = {{0}, 0};
                put(&out, "SMP_STRESS_CHCPU ");
                put(&out, errors);
                if (out.size && out.text[out.size - 1] == '\n')
                    --out.size;
                emit(&out);
            }
            return status;
        }
        say_online_eio(cpu, "chcpu");
    }
}

/* SIGKILL to a child writing "0" to cpuN/online, then N online again.
   mode 0: right away, before or while it files its request. mode 1: once
   the CPU reads offline, the controller and the writer sharing CPU 0, which
   serves the request between their steps: the writer holds a result it has
   not consumed when the kill lands. mode 2: once the CPU reads offline, from
   any CPU: with three or more CPUs the kill can land while CPU 0 still
   stops N and the writer waits. A killed writer whose CPU still went
   offline had filed its request (result.error counts them). With two CPUs
   only mode 1 can find one: the controller never runs while CPU 0 stops
   the other CPU. */
static void kill_writer(unsigned cpu, unsigned mode)
{
    const long present = cpu_list("present");
    if (mode == 1)
        CHECK(pin(1) == 0);
    const pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
        racer(cpu, '0');
    int status = 0;
    pid_t gone = 0;
    if (mode == 0)
        for (unsigned spin = 0; spin < (unsigned)result.forks % 4 * 3; ++spin)
            sched_yield();
    else
        for (int poll = 0; poll < 20000 && !gone && cpu_state(cpu) == 1; ++poll)
        {
            /* From other CPUs a short sleep per poll keeps the kernel lock
               free for the stop; on CPU 0 the stop runs between steps. */
            if (mode == 2)
            {
                const struct timespec pause = {0, 500000};
                nanosleep(&pause, 0);
            }
            gone = waitpid(child, &status, WNOHANG);
        }
    if (!gone)
    {
        kill(child, SIGKILL);
        gone = reap(child, &status);
    }
    CHECK(gone == child);
    if (WIFSIGNALED(status))
    {
        CHECK(WTERMSIG(status) == SIGKILL);
        ++result.forks;
        for (int wait = 0; wait < 200 && cpu_state(cpu) == 1; ++wait)
            sched_yield();
        result.error += cpu_state(cpu) != 1;
    }
    else
        CHECK(WIFEXITED(status) && WEXITSTATUS(status) <= 1);
    if (mode == 1)
        CHECK(pin(present) == 0);
    const int error = restore_cpu(cpu);
    errno = error;
    CHECK(error == 0 && cpu_state(cpu) == 1);
}

/* Shared with kill_waiting's writer: set just before its write. */
static volatile uint32_t *announce;

/* With three or more CPUs: SIGKILL to a child writing `value` ('0' stops N,
   '1' restarts it after the controller took it offline) as soon as it
   announced its write through shared memory, after `spins` rounds of user
   work, so that the kill lands while the writer waits uninterruptibly:
   before CPU 0 takes its request (dropped_waiting), or while CPU 0 runs it
   (abandoned). Returns 1 when the kill landed before the writer exited; N
   is online again on return. */
static int kill_waiting(unsigned cpu, char value, unsigned spins)
{
    if (value == '1')
        CHECK(set_cpu(cpu, '0') == 0);
    *announce = 0;
    const pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        char path[64];
        online_path(path, cpu);
        const int fd = open(path, O_WRONLY);
        if (fd < 0)
            _exit(2);
        const char text[2] = {value, '\n'};
        *announce = 1;
        const ssize_t wrote = write(fd, text, 2);
        _exit(wrote == 2 ? 0 : wrote < 0 && errno == EBUSY ? 1 : wrote < 0 && errno == EIO && value == '1' ? 3 : 2);
    }
    /* No system call until the kill: the writer runs on another CPU. */
    for (unsigned long wait = 0; !*announce && wait < 2000000000ul; ++wait)
        ;
    volatile unsigned long work = 0;
    for (unsigned i = 0; i < spins; ++i)
        work = work + i;
    kill(child, SIGKILL);
    int status = 0;
    CHECK(reap(child, &status) == child);
    int killed = 0;
    if (WIFSIGNALED(status))
    {
        CHECK(WTERMSIG(status) == SIGKILL);
        ++result.forks;
        killed = 1;
    }
    else if (WIFEXITED(status) && WEXITSTATUS(status) == 3)
    {
        /* Its "1" failed with EIO before the kill: the CPU did not come up. */
        CHECK(cpu_state(cpu) == 0);
        say_online_eio(cpu, "waiting");
    }
    else
        CHECK(WIFEXITED(status) && WEXITSTATUS(status) <= 1);
    const int error = restore_cpu(cpu);
    errno = error;
    CHECK(error == 0 && cpu_state(cpu) == 1);
    return killed;
}

static void say_pinned(pid_t pid, unsigned cpu)
{
    struct line out = {{0}, 0};
    put(&out, "SMP_STRESS_PINNED pid=");
    put_number(&out, (uint64_t)pid);
    put(&out, " cpu=");
    put_number(&out, cpu);
    emit(&out);
}

static void refusals(unsigned secondary)
{
    errno = 0;
    CHECK(open(CPU_ROOT "/cpu0/online", O_WRONLY) < 0 && errno == ENOENT);
    errno = 0;
    CHECK(open(CPU_ROOT "/cpu0/online", O_WRONLY | O_CREAT | O_TRUNC, 0644) < 0 && errno == EACCES);
    errno = 0;
    CHECK(open(CPU_ROOT "/online", O_WRONLY) < 0 && errno == EACCES);
    char path[64];
    online_path(path, secondary);
    int fd = open(path, O_WRONLY);
    CHECK(fd >= 0);
    errno = 0;
    CHECK(write(fd, "x", 1) < 0 && errno == EINVAL);
    close(fd);
    const pid_t user = fork();
    CHECK(user >= 0);
    if (user == 0)
    {
        if (setgid(1000) || setuid(1000))
            _exit(2);
        errno = 0;
        _exit(open(path, O_WRONLY) < 0 && errno == EACCES ? 0 : 3);
    }
    int status = 0;
    CHECK(reap(user, &status) == user && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    result.round = 5;
}

static __attribute__((noreturn)) void controller(const char *base, const char *stop, unsigned index)
{
    result.worker = index;
    const long present = cpu_list("present");
    CHECK(present > 1 && cpu_list("online") == present);
    const long secondaries = present & ~1L;
    unsigned first = 1;
    while (!(secondaries & (1L << first)))
        ++first;
    refusals(first);
    unsigned cycle = 0, scenario = 0, kills = 0, chcpu_runs = 0, plain = 0, method = 0, methods = 0;
    unsigned waits = 0;
    announce = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    CHECK(announce != MAP_FAILED);
    for (;; ++cycle)
    {
        /* Every write method took a CPU offline and back at least once. */
        if (cycle >= 2 && scenario >= 4 && chcpu_runs && methods == 7 && access(stop, F_OK) == 0)
            break;
        CHECK(cycle < 10000);
        for (unsigned cpu = 1; cpu < MAX_CPUS; ++cpu)
        {
            if (!(secondaries & (1L << cpu)))
                continue;
            const unsigned kind = scenario++ % 4;
            if (kind == 1)
            {
                /* Pinned: the child's only CPU goes offline under it. */
                char flag[64], name[32];
                name_into(name, "pinned-", cycle, '-', cpu);
                join(flag, base, name);
                const pid_t child = fork();
                CHECK(child >= 0);
                if (child == 0)
                    pinned_child(cpu, flag);
                for (int wait = 0; access(flag, F_OK) != 0; ++wait)
                {
                    int status;
                    CHECK(wait < 100000 && waitpid(child, &status, WNOHANG) == 0);
                    sched_yield();
                }
                say_pinned(child, cpu);
                CHECK(set_cpu_via(cpu, '0', method % 3) == 0);
                check_offline(cpu);
                int status = 0;
                CHECK(reap(child, &status) == child && WIFEXITED(status));
                errno = (int)WEXITSTATUS(status);
                CHECK(WEXITSTATUS(status) == 0);
                CHECK(unlink(flag) == 0);
                ++result.files;
            }
            else if (kind == 2)
            {
                /* Racing: two writers of the same value, each way. */
                for (char value = '0'; value <= '1'; ++value)
                {
                    pid_t racers[2];
                    for (int i = 0; i < 2; ++i)
                    {
                        racers[i] = fork();
                        CHECK(racers[i] >= 0);
                        if (racers[i] == 0)
                            racer(cpu, value);
                    }
                    int written = 0, failed = 0;
                    for (int i = 0; i < 2; ++i)
                    {
                        int status = 0;
                        CHECK(reap(racers[i], &status) == racers[i] && WIFEXITED(status));
                        errno = (int)WEXITSTATUS(status);
                        CHECK(WEXITSTATUS(status) <= 1 || (value == '1' && WEXITSTATUS(status) == 3));
                        written += WEXITSTATUS(status) == 0;
                        failed += WEXITSTATUS(status) == 3;
                    }
                    for (int i = 0; i < failed; ++i)
                        say_online_eio(cpu, "racer");
                    if (failed && !written)
                    {
                        /* Nothing brought it up: it still reads offline. */
                        CHECK(cpu_state(cpu) == 0);
                        errno = online_via(cpu, 0, "racer");
                        CHECK(errno == 0);
                    }
                    CHECK((written >= 1 || failed >= 1) && cpu_state(cpu) == value - '0');
                    if (value == '0')
                        check_offline(cpu);
                }
                ++result.messages;
                continue;
            }
            else if (kind == 3)
            {
                /* Killed: SIGKILL writers, maybe in their uninterruptible
                   wait, until one died after filing its request. */
                unsigned attempts = 0;
                do
                    kill_writer(cpu, kills++ % 3);
                while (!result.error && ++attempts < 32);
                /* With three or more CPUs, kills aimed at writers in their
                   uninterruptible wait, stopping or restarting N, landing
                   at varied points of it. */
                static const unsigned spins[] = {0, 1000, 10000, 100000};
                if (__builtin_popcountl(present) >= 3)
                    for (unsigned attempt = 0; attempt < 4; ++attempt, ++waits)
                        kill_waiting(cpu, waits % 2 ? '1' : '0', spins[waits / 2 % 4]);
                continue;
            }
            else if (plain++ % 2)
            {
                /* The distribution's chcpu, as an administrator runs it. */
                CHECK(chcpu("-d", cpu) == 0);
                check_offline(cpu);
                CHECK(chcpu_enable(cpu) == 0 && cpu_state(cpu) == 1);
                CHECK(cpu_list("online") & (1L << cpu));
                ++chcpu_runs;
                continue;
            }
            else
            {
                CHECK(set_cpu_via(cpu, '0', method % 3) == 0);
                check_offline(cpu);
            }
            CHECK(online_via(cpu, method % 3, "plain") == 0 && cpu_state(cpu) == 1);
            CHECK(cpu_list("online") & (1L << cpu));
            methods |= 1u << (method++ % 3);
        }
    }
    CHECK(cpu_list("online") == present && affinity() == present);
    result.rounds = cycle;
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
    const int hotplug = argc == 4 && !strcmp(argv[3], "hotplug");
    if ((argc > 3 && !hotplug) || (argc > 1 && parse(argv[1], 1, MAX_WORKERS, &workers)) ||
        (argc > 2 && parse(argv[2], 1, MAX_ROUNDS, &rounds)))
    {
        errno = EINVAL;
        fail("usage", 0);
    }
    const char *self = argc > 0 && argv[0][0] == '/' ? argv[0] : SELF;

    char base[64], shared[64], name[32], ram_base[64], ram_shared[64];
    name_into(name, "/tmp/smp-stress-", (unsigned)getpid(), 0, 0);
    memcpy(base, name, strlen(name) + 1);
    join(shared, base, "shared");
    if (mkdir(base, 0755) || mkdir(shared, 0755))
        fail("mkdir", 0);
    /* The same names on the RAM filesystem for the metadata cycles. */
    join(ram_base, RAM_ROOT, base + 5);
    join(ram_shared, ram_base, "shared");
    if (mkdir(ram_base, 0755) || mkdir(ram_shared, 0755))
        fail("mkdir-run", 0);

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
    /* The hotplug controller reports through the same channel, as one more record. */
    char stop[64];
    join(stop, base, "stop");
    pid_t control = 0;
    if (hotplug)
    {
        control = fork();
        if (control < 0)
            fail("fork", (uint64_t)workers);
        if (control == 0)
        {
            close(gate[0]);
            close(gate[1]);
            close(channel[0]);
            record_fd = channel[1];
            controller(base, stop, (unsigned)workers);
        }
    }
    close(gate[0]);
    close(gate[1]);
    close(channel[1]);

    int statuses[MAX_WORKERS] = {0}, reaped[MAX_WORKERS] = {0}, received[MAX_WORKERS + 1] = {0};
    for (long i = 0; i < workers; ++i)
        reaped[i] = reap(children[i], &statuses[i]) == children[i];
    int control_status = 0;
    if (hotplug)
    {
        const int marker = open(stop, O_WRONLY | O_CREAT | O_EXCL, 0644);
        if (marker < 0)
            fail("stop", 0);
        close(marker);
        if (reap(control, &control_status) != control)
            fail("reap-controller", 0);
    }
    struct record reports[MAX_WORKERS + 1];
    for (;;)
    {
        struct record report;
        const int got = read_all(channel[0], (unsigned char *)&report, sizeof report);
        if (got == 1)
            break;
        if (got || report.worker >= (uint32_t)workers + (hotplug ? 1u : 0u) || received[report.worker])
            fail("record", got ? 0 : report.worker);
        reports[report.worker] = report;
        received[report.worker] = 1;
    }
    close(channel[0]);
    if (hotplug)
    {
        const struct record control_report = reports[workers];
        if (!received[workers] || control_report.failed || !WIFEXITED(control_status) ||
            WEXITSTATUS(control_status) != 0)
        {
            struct line out = {{0}, 0};
            put(&out, "SMP_STRESS_FAIL arch=" PROBE_ARCH " reason=hotplug-line-");
            put_number(&out, received[workers] ? control_report.line : 0);
            put(&out, "-errno-");
            put_number(&out, received[workers] ? control_report.error : 0);
            put(&out, "-status-");
            put_number(&out, (uint64_t)control_status);
            emit(&out);
            return 1;
        }
        if (unlink(stop))
            fail("unlink-stop", 0);
    }

    uint64_t files = 0, messages = 0, forks = 0, metadata = 0, pipes = 0, ptys = 0, udp = 0, udp_nolink = 0;
    long failed = -1;
    struct record first = {0};
    for (long i = 0; i < workers; ++i)
    {
        const int status = statuses[i];
        const struct record report = reports[i];
        const int good = reaped[i] && WIFEXITED(status) && WEXITSTATUS(status) == 0 && received[i] &&
                         !report.failed && report.rounds == (uint32_t)rounds &&
                         report.files == 2 * (uint32_t)rounds && report.messages == MESSAGES * (uint32_t)rounds &&
                         report.forks == 2 * (uint32_t)rounds && report.metadata == (uint32_t)rounds &&
                         report.pipes == (uint32_t)rounds && report.ptys == (uint32_t)rounds &&
                         report.udp + report.udp_nolink == (uint32_t)rounds;
        if (!good && failed < 0)
        {
            failed = i;
            first = received[i] ? report : (struct record){(uint32_t)i, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0};
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
            metadata += report.metadata;
            pipes += report.pipes;
            ptys += report.ptys;
            udp += report.udp;
            udp_nolink += report.udp_nolink;
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
    if (rmdir(shared) || rmdir(base) || rmdir(ram_shared) || rmdir(ram_base))
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
    put(&out, " metadata=");
    put_number(&out, metadata);
    put(&out, " pipes=");
    put_number(&out, pipes);
    put(&out, " ptys=");
    put_number(&out, ptys);
    put(&out, " udp=");
    put_number(&out, udp);
    put(&out, " udp_nolink=");
    put_number(&out, udp_nolink);
    if (hotplug)
    {
        const struct record control_report = reports[workers];
        put(&out, " hotplug_cycles=");
        put_number(&out, control_report.rounds);
        put(&out, " pinned=");
        put_number(&out, control_report.files);
        put(&out, " racing=");
        put_number(&out, control_report.messages);
        put(&out, " killed=");
        put_number(&out, control_report.forks);
        put(&out, " killed_filed=");
        put_number(&out, control_report.error);
        put(&out, " refusals=");
        put_number(&out, control_report.round);
    }
    emit(&out);
    return 0;
}
