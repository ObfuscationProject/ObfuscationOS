#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <inttypes.h>
#include <limits.h>
#include <linux/capability.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* This executable is an initramfs PID1 for a disposable x86_64 Linux guest. */
_Static_assert(SYS_clock_settime == 227, "x86_64 reference syscall");
_Static_assert(sizeof(struct timespec) == 16, "x86_64 Linux timespec layout");
#define NS INT64_C(1000000000)
#define SET_LIMIT INT64_C(8277292036)
static unsigned rejected;

static void fail(const char *operation)
{
    printf("JBD2_NATIVE_FAIL linux-clock-set operation=%s errno=%d\n", operation, errno);
    _exit(111);
}

static int64_t clock_ns(clockid_t clock)
{
    struct timespec value;
    if (syscall(SYS_clock_gettime, clock, &value) || value.tv_sec < 0 || value.tv_sec >= SET_LIMIT ||
        value.tv_nsec < 0 || value.tv_nsec >= NS) fail("clock sample");
    return (int64_t)value.tv_sec * NS + value.tv_nsec;
}

static unsigned has_time_capability(void)
{
    struct __user_cap_header_struct header = {_LINUX_CAPABILITY_VERSION_3, 0};
    struct __user_cap_data_struct bits[2] = {{0}};
    if (syscall(SYS_capget, &header, bits)) fail("capget");
    return (bits[CAP_SYS_TIME / 32].effective >> (CAP_SYS_TIME % 32)) & 1;
}

struct setting { int64_t seconds, fraction, before, after; };

static void verify_set(const char *name, struct setting value)
{
    const int64_t c = clock_ns(CLOCK_MONOTONIC);
    const int64_t real = clock_ns(CLOCK_REALTIME);
    const int64_t d = clock_ns(CLOCK_MONOTONIC);
    const int64_t target = value.seconds * NS + value.fraction;
    if (value.before > value.after || value.after > c || c > d ||
        real < target + c - value.after || real > target + d - value.before) fail("set elapsed bracket");
    printf("LINUX_CLOCK_SET_SAMPLE case=%s target=%" PRId64 " before=%" PRId64 " after=%" PRId64
           " read_before=%" PRId64 " realtime=%" PRId64 " read_after=%" PRId64 "\n",
           name, target, value.before, value.after, c, real, d);
}

static struct setting set_value(const char *name, int64_t seconds, int64_t fraction)
{
    const struct timespec request = {.tv_sec = seconds, .tv_nsec = fraction};
    struct setting value = {seconds, fraction, clock_ns(CLOCK_MONOTONIC), 0};
    if (syscall(SYS_clock_settime, CLOCK_REALTIME, &request)) fail(name);
    value.after = clock_ns(CLOCK_MONOTONIC);
    verify_set(name, value);
    return value;
}

static void expect_error(const char *name, long identity, const struct timespec *request, int expected)
{
    const int64_t b = clock_ns(CLOCK_MONOTONIC);
    const int64_t first = clock_ns(CLOCK_REALTIME);
    const int64_t c = clock_ns(CLOCK_MONOTONIC);
    errno = 0;
    const long result = syscall(SYS_clock_settime, identity, request);
    const int actual = errno;
    const int64_t d = clock_ns(CLOCK_MONOTONIC);
    const int64_t second = clock_ns(CLOCK_REALTIME);
    const int64_t e = clock_ns(CLOCK_MONOTONIC);
    if (result != -1 || actual != expected || b > c || c > d || d > e ||
        second - first < d - c || second - first > e - b) fail(name);
    ++rejected;
    printf("LINUX_CLOCK_SET_ERROR case=%s errno=%d before=%" PRId64 " first=%" PRId64
           " first_after=%" PRId64 " second_before=%" PRId64 " second=%" PRId64
           " after=%" PRId64 "\n", name, actual, b, first, c, d, second, e);
}

static void shared_child_setting(void)
{
    int descriptors[2];
    if (pipe(descriptors)) fail("shared pipe");
    const pid_t child = fork();
    if (child < 0) fail("shared fork");
    if (!child) {
        close(descriptors[0]);
        const struct setting result = set_value("child-global", INT64_C(2214176530), 789012345);
        if (write(descriptors[1], &result, sizeof result) != sizeof result) fail("shared write");
        _exit(0);
    }
    close(descriptors[1]);
    struct setting result;
    if (read(descriptors[0], &result, sizeof result) != sizeof result || close(descriptors[0])) fail("shared read");
    int status;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status)) fail("shared child status");
    verify_set("parent-observes-child", result);
}

static void unprivileged_child(void)
{
    const pid_t child = fork();
    if (child < 0) fail("denial fork");
    if (!child) {
        if (setgroups(0, NULL) || setgid(1000) || setuid(1000) ||
            getuid() != 1000 || geteuid() != 1000 || getgid() != 1000 || getegid() != 1000 || has_time_capability())
            fail("drop credentials");
        puts("LINUX_CLOCK_SET_CREDENTIALS role=child uid=1000 euid=1000 gid=1000 egid=1000 cap_sys_time=0");
        const struct timespec valid = {1709210096, 123};
        const struct timespec negative = {-1, 0};
        const struct timespec bad_ns = {100, 1000000000};
        const struct timespec limit = {SET_LIMIT, 0};
        const struct timespec floor = {0, 0};
        expect_error("user-valid", CLOCK_REALTIME, &valid, EPERM);
        expect_error("user-id-null", CLOCK_MONOTONIC, NULL, EINVAL);
        expect_error("user-null", CLOCK_REALTIME, NULL, EFAULT);
        expect_error("user-negative-seconds", CLOCK_REALTIME, &negative, EINVAL);
        expect_error("user-nanoseconds", CLOCK_REALTIME, &bad_ns, EINVAL);
        expect_error("user-upper-range", CLOCK_REALTIME, &limit, EINVAL);
        expect_error("user-floor-permission-first", CLOCK_REALTIME, &floor, EPERM);
        puts("LINUX_CLOCK_SET_DENIAL_PASS cases=7 credentials=actual unchanged=elapsed-brackets");
        _exit(0);
    }
    int status;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status)) fail("denial child status");
}

int main(void)
{
    /* Refuse ordinary host invocation before any setter can execute. */
    if (getpid() != 1) return 125;
    mkdir("/dev", 0755);
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, "") && errno != EBUSY) fail("devtmpfs");
    mknod("/dev/console", S_IFCHR | 0600, makedev(5, 1));
    const int console = open("/dev/console", O_RDWR);
    if (console < 0 || dup2(console, 0) < 0 || dup2(console, 1) < 0 || dup2(console, 2) < 0) fail("console");
    setvbuf(stdout, NULL, _IONBF, 0);
    struct utsname version;
    if (uname(&version) || getuid() || geteuid() || !has_time_capability()) fail("root admission");
    printf("LINUX_CLOCK_SET_BEGIN release=%s version=%s machine=%s\n", version.release, version.version, version.machine);
    puts("LINUX_CLOCK_SET_CREDENTIALS role=parent uid=0 euid=0 cap_sys_time=1");
    set_value("ordinary", INT64_C(1709210100), 123456789);
    set_value("backwards", INT64_C(1709210096), 234567890);
    set_value("time2040", INT64_C(2214176523), 345678901);
    const struct timespec valid = {1709210096, 123};
    const struct timespec negative = {-1, 0};
    const struct timespec negative_ns = {100, -1};
    const struct timespec high_ns = {100, 1000000000};
    const struct timespec wide_ns = {100, INT64_C(1) << 32};
    const struct timespec limit = {SET_LIMIT, 0};
    const struct timespec floor = {0, 0};
    expect_error("root-monotonic-null", CLOCK_MONOTONIC, NULL, EINVAL);
    expect_error("root-invalid-id-null", INT_MAX, NULL, EINVAL);
    expect_error("root-narrowed-id-null", (INT64_C(1) << 32) | CLOCK_MONOTONIC, NULL, EINVAL);
    expect_error("root-null", CLOCK_REALTIME, NULL, EFAULT);
    expect_error("root-unmapped", CLOCK_REALTIME, (const struct timespec *)(uintptr_t)1, EFAULT);
    expect_error("root-negative-seconds", CLOCK_REALTIME, &negative, EINVAL);
    expect_error("root-negative-nanoseconds", CLOCK_REALTIME, &negative_ns, EINVAL);
    expect_error("root-high-nanoseconds", CLOCK_REALTIME, &high_ns, EINVAL);
    expect_error("root-wide-nanoseconds", CLOCK_REALTIME, &wide_ns, EINVAL);
    expect_error("root-upper-range", CLOCK_REALTIME, &limit, EINVAL);
    expect_error("root-monotonic-floor", CLOCK_REALTIME, &floor, EINVAL);
    if (rejected != 11) fail("root count");
    /* The low32 clockid_t value is zero; x86 syscall argument narrowing applies. */
    const int64_t before = clock_ns(CLOCK_MONOTONIC);
    if (syscall(SYS_clock_settime, INT64_C(1) << 32, &valid)) fail("narrowed-zero identity");
    verify_set("narrowed-realtime", (struct setting){valid.tv_sec, valid.tv_nsec, before, clock_ns(CLOCK_MONOTONIC)});
    shared_child_setting();
    unprivileged_child();
    puts("LINUX_CLOCK_SET_PASS root_sets=5 observations=6 root_errors=11 user_errors=7 shared=pass monotonic=pass credentials=actual");
    for (;;) pause();
}
