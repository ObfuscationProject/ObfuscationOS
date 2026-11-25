/* Hosted native terminal marshalling; no host terminal or process is changed. */
#include <errno.h>
#include <ok/syscall.h>
#include <ok/uapi/termios.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <unistd.h>

static long selected, words[3], response;
static unsigned calls;
static pid_t copied, expected_group;
static int pointer_bad;
int errno;

long ok_syscall3(long number, long fd, long request, long argument)
{
    ++calls;
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
/* The exit status alone could wrap to 0, so the runner also needs the marker. */
#define CHECK(value) do { if (!(value)) { fprintf(stderr, "line %d: %s\n", __LINE__, #value); return __LINE__; } } while (0)

static const uint32_t pointer_requests[] = {
    OK_TCGETS, OK_TCSETS, OK_TCSETSW, OK_TCSETSF, OK_TIOCGPGRP, OK_TIOCSPGRP, OK_TIOCGWINSZ,
    OK_TIOCSWINSZ, OK_FIONREAD, OK_TIOCGSID, OK_TIOCGPTN, OK_TIOCSPTLCK,
};
static const uint32_t scalar_requests[] = {OK_TIOCSCTTY, OK_TCSBRK, OK_TCFLSH};
static const uint32_t argumentless_requests[] = {OK_TIOCNOTTY, 0x1234U, OK_TIOCGPTN + 1U};

static int requests(unsigned *cases)
{
    /* Every public request name is the UAPI value. */
    CHECK(TCGETS == OK_TCGETS && TCSETS == OK_TCSETS && TCSETSW == OK_TCSETSW && TCSETSF == OK_TCSETSF);
    CHECK(TCSBRK == OK_TCSBRK && TCFLSH == OK_TCFLSH && TIOCSCTTY == OK_TIOCSCTTY);
    CHECK(TIOCGPGRP == OK_TIOCGPGRP && TIOCSPGRP == OK_TIOCSPGRP && TIOCGSID == OK_TIOCGSID);
    CHECK(TIOCGWINSZ == OK_TIOCGWINSZ && TIOCSWINSZ == OK_TIOCSWINSZ && FIONREAD == OK_FIONREAD);
    CHECK(TIOCNOTTY == OK_TIOCNOTTY && TIOCGPTN == OK_TIOCGPTN && TIOCSPTLCK == OK_TIOCSPTLCK);
    CHECK(sizeof(struct winsize) == sizeof(struct ok_winsize));
    response = 0;
    /* A pointer request forwards the caller's address, never a copy or 0. */
    for (unsigned index = 0; index < sizeof(pointer_requests) / sizeof(pointer_requests[0]); ++index) {
        struct ok_termios buffer;
        const uint32_t request = pointer_requests[index];
        expected_group = 0;
        *(pid_t *)(void *)&buffer = 0;
        calls = 0; errno = 61;
        CHECK(!ioctl(20 + (int)index, request, (void *)&buffer) && calls == 1 && errno == 61);
        CHECK(selected == OK_SYS_IOCTL && words[0] == 20 + (long)index);
        CHECK((uint32_t)words[1] == request && words[2] == (long)&buffer);
        ++*cases;
    }
    /* A scalar request forwards the int value, sign-extended to the word. */
    const int values[] = {0, 1, 2, -1, 0x7fffffff};
    for (unsigned index = 0; index < sizeof(scalar_requests) / sizeof(scalar_requests[0]); ++index)
        for (unsigned value = 0; value < sizeof(values) / sizeof(values[0]); ++value) {
            calls = 0;
            CHECK(!ioctl(3, scalar_requests[index], values[value]) && calls == 1);
            CHECK((uint32_t)words[1] == scalar_requests[index] && words[2] == (long)values[value]);
            ++*cases;
        }
    /* TIOCNOTTY and unknown requests never read an optional argument. */
    for (unsigned index = 0; index < sizeof(argumentless_requests) / sizeof(argumentless_requests[0]); ++index) {
        int ignored = 0;
        CHECK(!ioctl(4, argumentless_requests[index], (void *)&ignored));
        CHECK((uint32_t)words[1] == argumentless_requests[index] && !words[2]);
        CHECK(!ioctl(4, argumentless_requests[index]) && !words[2]);
        ++*cases;
    }
    /* Kernel errors map to -1 and errno for every request shape. */
    const long errors[] = {OK_EBADF, OK_ENOTTY, OK_EFAULT, OK_EINVAL, OK_EIO, OK_EPERM};
    for (unsigned index = 0; index < sizeof(errors) / sizeof(errors[0]); ++index) {
        struct ok_termios buffer;
        response = -errors[index]; errno = 0;
        CHECK(ioctl(5, TCGETS, (void *)&buffer) == -1 && errno == errors[index] && words[2] == (long)&buffer);
        errno = 0;
        CHECK(ioctl(5, TCFLSH, 2) == -1 && errno == errors[index] && words[2] == 2);
        errno = 0;
        CHECK(ioctl(5, TIOCNOTTY) == -1 && errno == errors[index] && !words[2]);
        ++*cases;
    }
    response = 0;
    return 0;
}

static int sessions(unsigned *cases)
{
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
    response = 0;
    *cases += 12;
    return 0;
}

int main(void)
{
    _Static_assert(sizeof(pid_t) == 4, "four-byte native terminal PID");
    _Static_assert(OK_NATIVE_CONSOLE_CONTROL_VERSION == 2, "terminal contract version");
    unsigned cases = 0;
    int line;
    if ((line = requests(&cases)) || (line = sessions(&cases)))
        return line;
    printf("NATIVE_TERMINAL_WRAPPER_PASS long_bits=%u cases=%u host_mock_only=1\n",
           (unsigned)(sizeof(long) * 8), cases);
    return 0;
}
