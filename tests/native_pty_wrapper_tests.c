#include <ok/pty.h>
#include <ok/syscall.h>
#include <stdlib.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>

#define CHECK(condition) do { if (!(condition)) { fprintf(stderr, "%d: %s\n", __LINE__, #condition); abort(); } } while (0)

static long captured[7], raw_return;
static unsigned calls, returns;
long ok_syscall6(long number, long a0, long a1, long a2, long a3, long a4, long a5)
{
    ++calls;
    captured[0] = number; captured[1] = a0; captured[2] = a1;
    captured[3] = a2; captured[4] = a3; captured[5] = a4; captured[6] = a5;
    return raw_return;
}
long ok_syscall_ret(long result)
{
    ++returns;
    if (result < 0) { errno = (int)-result; return -1; }
    return result;
}
int main(void)
{
    int descriptors[2] = {-1, -1};
    const uint32_t flags[] = {0, OK_PTY_NONBLOCK, OK_PTY_CLOEXEC,
        OK_PTY_NONBLOCK | OK_PTY_CLOEXEC, UINT32_MAX};
    unsigned cases = 0;
    for (unsigned index = 0; index < sizeof(flags) / sizeof(flags[0]); ++index)
        for (unsigned error = 0; error <= 14; error += 14)
        {
            raw_return = -(long)error; errno = 0;
            const int result = ok_pty_pair(descriptors, flags[index]);
            CHECK(result == (error ? -1 : 0));
            CHECK(errno == (int)error && captured[0] == OK_SYS_PTY_PAIR);
            CHECK(captured[1] == (long)descriptors && (uint32_t)captured[2] == flags[index]);
            for (unsigned slot = 3; slot < 7; ++slot) CHECK(captured[slot] == 0);
            CHECK(descriptors[0] == -1 && descriptors[1] == -1);
            ++cases;
        }
    raw_return = -14;
    CHECK(ok_pty_pair(NULL, 0) == -1 && captured[1] == 0);
    ++cases;
    CHECK(calls == cases && returns == cases && sizeof(int) == 4 && CHAR_BIT == 8);
    printf("NATIVE_PTY_WRAPPER_PASS cases=%u host_mock_only=1\n", cases);
}
