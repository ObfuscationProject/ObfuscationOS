/* Hosted native terminal marshalling; no host terminal or process is changed. */
#include <errno.h>
#include <ok/syscall.h>
#include <sys/ioctl.h>
#include <unistd.h>

static long selected, words[3], response;
static pid_t copied, expected_group;
static int pointer_bad;
int errno;

long ok_syscall3(long number, long fd, long request, long argument)
{
    selected = number; words[0] = fd; words[1] = request; words[2] = argument;
    if (response < 0) return response;
    if ((uint32_t)request == TIOCGPGRP || (uint32_t)request == TIOCGSID)
        *(pid_t *)argument = copied;
    else if ((uint32_t)request == TIOCSPGRP && *(pid_t *)argument != expected_group)
        pointer_bad = 1;
    return response;
}
long ok_syscall_ret(long result)
{
    if (result < 0 && result >= -4095) { errno = (int)-result; return -1; }
    return result;
}
#define CHECK(value) do { if (!(value)) return __LINE__; } while (0)
int main(void)
{
    _Static_assert(sizeof(pid_t) == 4, "four-byte native terminal PID");
    _Static_assert(OK_NATIVE_CONSOLE_CONTROL_VERSION == 1, "terminal contract version");
    int (*entry)(int, unsigned long, ...) = ioctl;
    response = 0; errno = 73;
    CHECK(!entry(0, TIOCSCTTY, 0) && selected == OK_SYS_IOCTL &&
          words[0] == 0 && words[1] == TIOCSCTTY && !words[2] && errno == 73);
    CHECK(!ioctl(2, TIOCSCTTY, -1) && words[2] == -1);
    copied = 29;
    CHECK(tcgetpgrp(4) == 29 && words[0] == 4 && words[1] == TIOCGPGRP);
    copied = 17;
    CHECK(tcgetsid(5) == 17 && words[0] == 5 && words[1] == TIOCGSID);
    expected_group = 101;
    CHECK(!tcsetpgrp(7, expected_group) && words[0] == 7 && words[1] == TIOCSPGRP && !pointer_bad);
    struct { pid_t value; uint32_t guard; } output = {0, 0xa5b6c7d8U};
    copied = 0x12345678;
    CHECK(!ioctl(8, TIOCGSID, (void *)&output.value) && words[2] == (long)&output.value &&
          output.value == copied && output.guard == 0xa5b6c7d8U);
#if __SIZEOF_LONG__ == 8
    unsigned long high_request = (1UL << 32) | TIOCGPGRP;
    CHECK(!ioctl(9, high_request, (void *)&output.value) &&
          (unsigned long)words[1] == high_request && output.value == copied);
#endif
    response = -OK_ENOTTY; errno = 0;
    CHECK(ioctl(9, 0x1234UL) == -1 && errno == ENOTTY && !words[2]);
    response = -OK_EFAULT; errno = 0;
    CHECK(ioctl(9, TIOCGSID, (void *)0) == -1 && errno == EFAULT && !words[2]);
    response = -OK_EIO; errno = 0;
    CHECK(tcgetpgrp(10) == -1 && errno == EIO);
    response = -OK_EACCES; errno = 0;
    CHECK(tcgetsid(11) == -1 && errno == EACCES);
    response = -OK_ESRCH; errno = 0;
    CHECK(tcsetpgrp(12, 999) == -1 && errno == ESRCH);
    return 0;
}
