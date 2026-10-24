/* Actual static-musl syscall/timeout/copy probe; no pthread or SMP claim. */
#include <errno.h>
#include <stdint.h>
#include "../probe_output.h"
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define CHECK(x) do { if (!(x)) { probe_failure("FUTEX_FAIL", __LINE__, errno); } } while (0)
static uint32_t word = 7;
struct old_time { long seconds, nanoseconds; };
struct new_time { int64_t seconds, nanoseconds; };
static long futex(long nr, const void *address, int operation, uint32_t expected, const void *timeout)
{
    return syscall(nr, address, operation, expected, timeout, 0, 0);
}
static int64_t nanos(struct timespec t) { return (int64_t)t.tv_sec*1000000000+t.tv_nsec; }
static void probe(long nr, int wide)
{
    struct old_time old = {0, 0};
    struct new_time modern = {0, 0};
    void *timeout = wide ? (void *)&modern : (void *)&old;
    CHECK(futex(nr, &word, 128, 8, 0) == -1 && errno == EAGAIN);
    CHECK(futex(nr, &word, 128, 8, timeout) == -1 && errno == EAGAIN);
    CHECK(futex(nr, &word, 128, 7, timeout) == -1 && errno == ETIMEDOUT);
    CHECK(futex(nr, (char *)&word+1, 128, 7, (void *)1) == -1 && errno == EFAULT);
    old.nanoseconds = modern.nanoseconds = 1000000000;
    CHECK(futex(nr, &word, 128, 8, timeout) == -1 && errno == EINVAL);
    old.seconds = modern.seconds = -1;
    old.nanoseconds = modern.nanoseconds = 0;
    CHECK(futex(nr, &word, 128, 8, timeout) == -1 && errno == EINVAL);
    old.seconds = modern.seconds = 0;
    old.nanoseconds = modern.nanoseconds = 10000000;
    struct timespec before, after;
    CHECK(clock_gettime(CLOCK_MONOTONIC, &before) == 0);
    CHECK(futex(nr, &word, 128, 7, timeout) == -1 && errno == ETIMEDOUT);
    CHECK(clock_gettime(CLOCK_MONOTONIC, &after) == 0 && nanos(after)-nanos(before) >= 10000000);
    CHECK(futex(nr, &word, 129, 1, (void *)1) == 0);
    CHECK(futex(nr, 0, 129, 0, (void *)1) == 0);
    CHECK(futex(nr, (void *)4, 129, 0xffffffffU, 0) == 0);
    CHECK(futex(nr, (char *)&word+1, 129, 1, 0) == -1 && errno == EINVAL);
    CHECK(futex(nr, 0, 128, 7, 0) == -1 && errno == EFAULT);
    CHECK(futex(nr, &word, 0, 8, 0) == -1 && errno == EAGAIN);
    CHECK(futex(nr, &word, 137, 7, 0) == -1 && errno == ENOSYS);
    void *page = mmap(0, 4096, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    CHECK(page != MAP_FAILED);
    CHECK(mprotect(page, 4096, PROT_NONE) == 0);
    CHECK(futex(nr, page, 129, 1, 0) == 0);
    CHECK(futex(nr, page, 128, 7, 0) == -1 && errno == EFAULT);
    CHECK(munmap(page, 4096) == 0 && futex(nr, page, 129, 1, 0) == 0);
    int channel[2]; CHECK(pipe(channel) == 0);
    pid_t child = fork(); CHECK(child >= 0);
    if (!child)
    {
        CHECK(close(channel[0]) == 0 && write(channel[1], "x", 1) == 1);
        CHECK(futex(nr, &word, 128, 7, timeout) == -1 && errno == ETIMEDOUT);
        _exit(0);
    }
    CHECK(close(channel[1]) == 0);
    char byte = 0; CHECK(read(channel[0], &byte, 1) == 1 && byte == 'x');
    CHECK(futex(nr, &word, 129, 1, 0) == 0);
    int status = -1;
    CHECK(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    CHECK(close(channel[0]) == 0);
}
int main(void)
{
#ifdef SYS_futex_time64
    probe(SYS_futex, sizeof(long) == 8 || SYS_futex == SYS_futex_time64);
    if (SYS_futex_time64 != SYS_futex) probe(SYS_futex_time64, 1);
#else
    probe(SYS_futex, sizeof(long) == 8);
#endif
    probe_text("OK_MUSL_PRIVATE_FUTEX mismatch=pass timeout=pass layouts=pass copies=pass wake_empty=pass fork_key=pass unsupported=pass\n");
    return 0;
}
