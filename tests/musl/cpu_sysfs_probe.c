/* The kernel's CPU sysfs tree and affinity calls from a static musl program.
 * `cpu-sysfs-probe` checks, as root:
 *
 * - tree: /sys/devices/system/cpu holds kernel_max ("15"), possible = present,
 *   online within present, offline = present minus online, one cpuN/ per
 *   present CPU (BusyBox `nproc --all` counts them), cpu0/ without online and
 *   cpuN/online ("1" or "0", matching online) for N >= 1;
 * - affinity: sched_getaffinity names exactly the online CPUs in one native
 *   word, sysconf(_SC_NPROCESSORS_ONLN) counts them, a length below one word
 *   or not a word multiple is EINVAL, sched_getcpu() is online; pinning to
 *   each online CPU in turn moves the thread there (getcpu), a mask of no
 *   present CPU is EINVAL, and the full mask comes back;
 * - negatives: cpu0/online is ENOENT for O_WRONLY and EACCES with O_CREAT,
 *   opening `online` for writing is EACCES, a write of "x" to cpuN/online is
 *   EINVAL, more than a page is E2BIG, and uid 1000 (a forked child) reads
 *   the tree but gets EACCES opening cpuN/online for writing;
 * - no-op: writing the current state of cpuN/online succeeds with its count.
 *
 * The probe never takes a CPU offline. Prints exactly one line:
 *
 *   CPU_SYSFS_PASS arch=<arch> present=<n> online=<n> nproc_all=<n> sysconf=<n> affinity_bytes=<n> pinned=<n> negatives=<n>
 *   CPU_SYSFS_FAIL arch=<arch> reason=<token> errno=<n>
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
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
#elif defined(__powerpc__)
#define PROBE_ARCH "ppc"
#else
#error "unknown probe architecture"
#endif

#define ROOT "/sys/devices/system/cpu"
#define MAX_CPUS 16

/* Integer-only output, so every profile links without the floating-point
   formatter (mips64 binary128, ppc soft float); one write per line. */
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

static void put_number(struct line *out, long value)
{
    char digits[24];
    size_t count = 0;
    unsigned long magnitude = value < 0 ? 0UL - (unsigned long)value : (unsigned long)value;
    if (value < 0)
        put(out, "-");
    do
        digits[count++] = (char)('0' + magnitude % 10);
    while (magnitude /= 10);
    while (count && out->size + 1 < sizeof out->text)
        out->text[out->size++] = digits[--count];
}

static void emit(struct line *out)
{
    out->text[out->size++] = '\n';
    const char *text = out->text;
    size_t size = out->size;
    while (size)
    {
        const ssize_t written = write(1, text, size);
        if (written <= 0)
            return;
        text += written;
        size -= (size_t)written;
    }
}

static int fail(const char *reason)
{
    const long error = errno;
    struct line out = {{0}, 0};
    put(&out, "CPU_SYSFS_FAIL arch=" PROBE_ARCH " reason=");
    put(&out, reason);
    put(&out, " errno=");
    put_number(&out, error);
    emit(&out);
    return 1;
}

/* ROOT "/" name, or ROOT "/cpuN/online" when name is null. */
static void sys_path(char *path, const char *name, int cpu)
{
    struct line out = {{0}, 0};
    put(&out, ROOT "/");
    if (name)
        put(&out, name);
    else
    {
        put(&out, "cpu");
        put_number(&out, cpu);
        put(&out, "/online");
    }
    out.text[out.size] = 0;
    memcpy(path, out.text, out.size + 1);
}

#define CHECK(condition, reason) do { if (!(condition)) return fail(reason); } while (0)

static int read_text(const char *path, char *buffer, size_t size)
{
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    ssize_t total = 0, got;
    while ((got = read(fd, buffer + total, size - 1 - (size_t)total)) > 0) total += got;
    int saved = errno;
    close(fd);
    errno = saved;
    if (got < 0) return -1;
    buffer[total] = 0;
    return (int)total;
}

/* A cpulist ("0-3,5\n", "\n") as a mask; -1 when it is not one. */
static long parse_list(const char *text)
{
    long mask = 0;
    const char *p = text;
    if (*p == '\n') return p[1] ? -1 : 0;
    for (;;) {
        char *end;
        long first = strtol(p, &end, 10), last = first;
        if (end == p || first < 0 || first >= MAX_CPUS) return -1;
        p = end;
        if (*p == '-') {
            last = strtol(p + 1, &end, 10);
            if (end == p + 1 || last < first || last >= MAX_CPUS) return -1;
            p = end;
        }
        for (long cpu = first; cpu <= last; ++cpu) mask |= 1L << cpu;
        if (*p == ',') { ++p; continue; }
        return *p == '\n' && !p[1] ? mask : -1;
    }
}

static long read_list(const char *name)
{
    char path[96], text[64];
    sys_path(path, name, 0);
    if (read_text(path, text, sizeof text) < 0) return -2;
    return parse_list(text);
}

static int count(long mask)
{
    int total = 0;
    for (; mask; mask &= mask - 1) ++total;
    return total;
}

static long current_affinity(void)
{
    cpu_set_t set;
    CPU_ZERO(&set);
    if (sched_getaffinity(0, sizeof set, &set) != 0) return -1;
    long mask = 0;
    for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu)
        if (CPU_ISSET(cpu, &set)) {
            if (cpu >= MAX_CPUS) return -1;
            mask |= 1L << cpu;
        }
    return mask;
}

static int pin(long mask)
{
    cpu_set_t set;
    CPU_ZERO(&set);
    for (int cpu = 0; cpu < MAX_CPUS; ++cpu)
        if (mask & (1L << cpu)) CPU_SET(cpu, &set);
    return sched_setaffinity(0, sizeof set, &set);
}

/* Opens `path` with `flags` and expects failure with `expected`. */
static int refused(const char *path, int flags, int expected)
{
    int fd = open(path, flags, 0644);
    if (fd >= 0) {
        close(fd);
        errno = 0;
        return 0;
    }
    return errno == expected;
}

int main(void)
{
    char text[64];
    int negatives = 0;

    /* The tree. */
    CHECK(read_text(ROOT "/kernel_max", text, sizeof text) == 3 && !strcmp(text, "15\n"), "kernel-max");
    long present = read_list("present"), possible = read_list("possible");
    long online = read_list("online"), offline = read_list("offline");
    CHECK(present > 0 && (present & 1), "present");
    CHECK(possible == present, "possible");
    CHECK(online > 0 && (online & 1) && (online & ~present) == 0, "online");
    CHECK(offline == (present & ~online), "offline");
    DIR *directory = opendir(ROOT);
    CHECK(directory, "opendir");
    long listed = 0;
    for (struct dirent *entry; (entry = readdir(directory));) {
        const char *name = entry->d_name;
        if (strncmp(name, "cpu", 3) || name[3] < '0' || name[3] > '9') continue;
        char *end;
        long cpu = strtol(name + 3, &end, 10);
        if (*end || cpu >= MAX_CPUS) { closedir(directory); return fail("cpu-entry"); }
        listed |= 1L << cpu;
    }
    closedir(directory);
    CHECK(listed == present, "nproc-all");
    struct stat status;
    CHECK(stat(ROOT "/cpu0", &status) == 0 && S_ISDIR(status.st_mode), "cpu0-directory");
    CHECK(stat(ROOT "/cpu0/online", &status) != 0 && errno == ENOENT, "cpu0-online-present");
    for (int cpu = 1; cpu < MAX_CPUS; ++cpu) {
        char path[96];
        sys_path(path, 0, cpu);
        if (!(present & (1L << cpu))) {
            CHECK(stat(path, &status) != 0, "absent-cpu-online");
            continue;
        }
        CHECK(stat(path, &status) == 0 && S_ISREG(status.st_mode) && (status.st_mode & 0777) == 0644 &&
              status.st_uid == 0, "cpu-online-mode");
        CHECK(read_text(path, text, sizeof text) == 2, "cpu-online-read");
        CHECK(text[0] == ((online & (1L << cpu)) ? '1' : '0') && text[1] == '\n', "cpu-online-state");
    }

    /* Affinity. */
    long word = sizeof(long);
    unsigned char raw[128];
    memset(raw, 0xa5, sizeof raw);
    long bytes = syscall(SYS_sched_getaffinity, 0, sizeof raw, raw);
    CHECK(bytes == word, "affinity-bytes");
    CHECK(syscall(SYS_sched_getaffinity, 0, 3, raw) == -1 && errno == EINVAL, "affinity-length");
    CHECK(current_affinity() == online, "affinity-online");
    long configured = sysconf(_SC_NPROCESSORS_ONLN);
    CHECK(configured == count(online), "sysconf-online");
    int here = sched_getcpu();
    CHECK(here >= 0 && here < MAX_CPUS && (online & (1L << here)), "getcpu");
    int pinned = 0;
    for (int cpu = 0; cpu < MAX_CPUS; ++cpu) {
        if (!(online & (1L << cpu))) continue;
        CHECK(pin(1L << cpu) == 0, "pin");
        CHECK(current_affinity() == (1L << cpu), "pinned-affinity");
        /* The thread leaves for its CPU before its next user entry. */
        sched_yield();
        CHECK(sched_getcpu() == cpu, "pinned-getcpu");
        ++pinned;
    }
    if (count(present) < MAX_CPUS) {
        long absent = ~present & ((1L << MAX_CPUS) - 1);
        long lowest = absent & -absent;
        CHECK(pin(lowest) == -1 && errno == EINVAL, "pin-absent");
        ++negatives;
    }
    CHECK(pin(present) == 0 && current_affinity() == online, "unpin");

    /* Negative opens and writes. */
    CHECK(refused(ROOT "/cpu0/online", O_WRONLY, ENOENT), "cpu0-online-wronly");
    CHECK(refused(ROOT "/cpu0/online", O_WRONLY | O_CREAT | O_TRUNC, EACCES), "cpu0-online-creat");
    CHECK(refused(ROOT "/online", O_WRONLY, EACCES), "online-wronly");
    CHECK(refused(ROOT "/online", O_RDWR, EACCES), "online-rdwr");
    CHECK(refused(ROOT "/kernel_max", O_WRONLY | O_TRUNC, EACCES), "kernel-max-wronly");
    negatives += 5;
    int secondary = 0;
    for (int cpu = 1; cpu < MAX_CPUS && !secondary; ++cpu)
        if (present & (1L << cpu)) secondary = cpu;
    if (secondary) {
        char path[96];
        sys_path(path, 0, secondary);
        int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644); /* As a shell redirection. */
        CHECK(fd >= 0, "cpu-online-open");
        CHECK(write(fd, "x", 1) == -1 && errno == EINVAL, "write-invalid");
        static char page[4097];
        memset(page, '1', sizeof page);
        CHECK(write(fd, page, sizeof page) == -1 && errno == E2BIG, "write-too-big");
        const char *same = (online & (1L << secondary)) ? "1\n" : "0\n";
        CHECK(write(fd, same, 2) == 2, "write-noop");
        CHECK(pwrite(fd, same, 1, 0) == 1, "pwrite-noop");
        close(fd);
        negatives += 2;
        /* uid 1000 reads the tree but may not write. */
        pid_t child = fork();
        CHECK(child >= 0, "fork");
        if (child == 0) {
            if (setgid(1000) || setuid(1000)) _exit(2);
            char state[8];
            if (read_text(path, state, sizeof state) != 2) _exit(3);
            _exit(refused(path, O_WRONLY, EACCES) ? 0 : 4);
        }
        int wstatus = 0;
        CHECK(waitpid(child, &wstatus, 0) == child && WIFEXITED(wstatus), "user-wait");
        errno = 0;
        CHECK(WEXITSTATUS(wstatus) == 0, WEXITSTATUS(wstatus) == 4 ? "user-write-allowed" : "user-setup");
        ++negatives;
    }
    struct line out = {{0}, 0};
    put(&out, "CPU_SYSFS_PASS arch=" PROBE_ARCH " present=");
    put_number(&out, count(present));
    put(&out, " online=");
    put_number(&out, count(online));
    put(&out, " nproc_all=");
    put_number(&out, count(listed));
    put(&out, " sysconf=");
    put_number(&out, configured);
    put(&out, " affinity_bytes=");
    put_number(&out, bytes);
    put(&out, " pinned=");
    put_number(&out, pinned);
    put(&out, " negatives=");
    put_number(&out, negatives);
    emit(&out);
    return 0;
}
