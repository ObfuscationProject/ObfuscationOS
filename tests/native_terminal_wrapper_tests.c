/* Hosted native terminal marshalling; no host terminal or process is changed. */
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <ok/syscall.h>
#include <ok/uapi/termios.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>

static long selected, words[3], response;
static unsigned calls;
static pid_t copied, expected_group;
static int pointer_bad, written_lock;
static struct ok_termios kernel_termios, written_termios;
static uint32_t kernel_ptn;
int errno;

/* Plays the kernel side of each request: copy-out, copy-in or nothing. */
long ok_syscall3(long number, long fd, long request, long argument)
{
    ++calls;
    selected = number; words[0] = fd; words[1] = request; words[2] = argument;
    if (response < 0 || number != (long)OK_SYS_IOCTL) return response;
    switch ((uint32_t)request) {
    case OK_TIOCGPGRP:
    case OK_TIOCGSID:
        *(pid_t *)argument = copied;
        break;
    case OK_TIOCSPGRP:
        if (*(pid_t *)argument != expected_group) pointer_bad = 1;
        break;
    case OK_TCGETS:
        memcpy((void *)argument, &kernel_termios, sizeof(kernel_termios));
        break;
    case OK_TCSETS:
    case OK_TCSETSW:
    case OK_TCSETSF:
        memcpy(&written_termios, (const void *)argument, sizeof(written_termios));
        break;
    case OK_TIOCGPTN:
        *(uint32_t *)argument = kernel_ptn;
        break;
    case OK_TIOCSPTLCK:
        written_lock = *(int *)argument;
        break;
    default:
        break;
    }
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
        struct ok_termios buffer = {0};
        const uint32_t request = pointer_requests[index];
        expected_group = 0;
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

static int same_termios(const struct termios *left, const struct ok_termios *right)
{
    return !memcmp(left, right, sizeof(*right));
}

static int attributes(unsigned *cases)
{
    /* struct termios is struct ok_termios and every name is the UAPI value. */
    CHECK(sizeof(struct termios) == sizeof(struct ok_termios) && NCCS == OK_NCCS);
    CHECK(offsetof(struct termios, c_line) == 16 && offsetof(struct termios, c_cc) == 17);
    CHECK(VMIN == OK_VMIN && VTIME == OK_VTIME && VINTR == OK_VINTR && VSUSP == OK_VSUSP && VEOL2 == OK_VEOL2);
    CHECK(ICRNL == OK_ICRNL && IXON == OK_IXON && OPOST == OK_OPOST && ONLCR == OK_ONLCR);
    CHECK(ECHO == OK_ECHO && ICANON == OK_ICANON && ISIG == OK_ISIG && TOSTOP == OK_TOSTOP);
    CHECK(CBAUD == OK_CBAUD && B38400 == OK_B38400 && B115200 == OK_B115200 && CS8 == OK_CS8);
    CHECK(TCIFLUSH == OK_TCIFLUSH && TCOFLUSH == OK_TCOFLUSH && TCIOFLUSH == OK_TCIOFLUSH);
    CHECK(TCSANOW == 0 && TCSADRAIN == 1 && TCSAFLUSH == 2);
    const struct ok_termios pts = {
        OK_ICRNL | OK_IXON, OK_OPOST | OK_ONLCR, OK_B38400 | OK_CS8 | OK_CREAD,
        OK_ISIG | OK_ICANON | OK_ECHO | OK_ECHOE | OK_ECHOK | OK_ECHOCTL | OK_ECHOKE | OK_IEXTEN, 0,
        {3, 28, 127, 21, 4, 0, 1, 0, 17, 19, 26, 0, 18, 15, 23, 22, 0, 0, 0},
    };
    struct termios value;

    kernel_termios = pts; response = 0; calls = 0;
    memset(&value, 0xa5, sizeof(value));
    CHECK(!tcgetattr(6, &value) && calls == 1 && selected == OK_SYS_IOCTL && words[0] == 6);
    CHECK((uint32_t)words[1] == OK_TCGETS && words[2] == (long)&value && same_termios(&value, &pts));
    response = -OK_ENOTTY; errno = 0;
    CHECK(tcgetattr(6, &value) == -1 && errno == ENOTTY);
    response = 0;
    *cases += 2;

    const int actions[] = {TCSANOW, TCSADRAIN, TCSAFLUSH};
    const uint32_t settings[] = {OK_TCSETS, OK_TCSETSW, OK_TCSETSF};
    for (unsigned index = 0; index < 3; ++index) {
        memcpy(&value, &pts, sizeof(value));
        value.c_lflag &= ~(tcflag_t)ECHO;
        value.c_cc[VMIN] = (cc_t)(index + 2);
        memset(&written_termios, 0, sizeof(written_termios)); calls = 0;
        CHECK(!tcsetattr(7, actions[index], &value) && calls == 1 && words[0] == 7);
        CHECK((uint32_t)words[1] == settings[index] && words[2] == (long)&value);
        CHECK(same_termios(&value, &written_termios));
        response = -OK_EIO; errno = 0;
        CHECK(tcsetattr(7, actions[index], &value) == -1 && errno == EIO);
        response = 0;
        ++*cases;
    }
    const int bad_actions[] = {-1, 3, (int)OK_TCSETS};
    for (unsigned index = 0; index < 3; ++index) {
        calls = 0; errno = 0;
        CHECK(tcsetattr(7, bad_actions[index], &value) == -1 && errno == EINVAL && !calls);
        ++*cases;
    }

    const int queues[] = {TCIFLUSH, TCOFLUSH, TCIOFLUSH};
    for (unsigned index = 0; index < 3; ++index) {
        calls = 0;
        CHECK(!tcflush(8, queues[index]) && calls == 1 && words[0] == 8);
        CHECK((uint32_t)words[1] == OK_TCFLSH && words[2] == queues[index]);
        ++*cases;
    }
    response = -OK_EINVAL; errno = 0;
    CHECK(tcflush(8, 3) == -1 && errno == EINVAL && words[2] == 3);
    response = 0; calls = 0;
    CHECK(!tcdrain(9) && calls == 1 && (uint32_t)words[1] == OK_TCSBRK && words[2] == 1 && words[0] == 9);
    response = -OK_EINTR; errno = 0;
    CHECK(tcdrain(9) == -1 && errno == EINTR);
    response = 0;
    *cases += 3;

    /* cfmakeraw of the pts defaults is the kernel's raw-pair termios. */
    memcpy(&value, &pts, sizeof(value));
    value.c_iflag |= IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | IUTF8;
    value.c_cflag = (value.c_cflag & ~CSIZE) | CS7 | PARENB;
    value.c_lflag |= ECHONL | TOSTOP;
    value.c_cc[VMIN] = 0; value.c_cc[VTIME] = 5;
    calls = 0;
    cfmakeraw(&value);
    CHECK(!calls && value.c_iflag == IUTF8 && value.c_oflag == ONLCR);
    CHECK(value.c_cflag == (B38400 | CS8 | CREAD));
    CHECK(value.c_lflag == (ECHOE | ECHOK | ECHOCTL | ECHOKE | TOSTOP));
    CHECK(value.c_cc[VMIN] == 1 && value.c_cc[VTIME] == 0 && value.c_cc[VINTR] == 3);
    ++*cases;

    /* Speeds are CBAUD codes; the input speed is the output speed. */
    memcpy(&value, &pts, sizeof(value));
    value.c_cflag |= CIBAUD & (B9600 << OK_IBSHIFT);
    const tcflag_t others = value.c_cflag & ~CBAUD;
    CHECK(cfgetospeed(&value) == B38400 && cfgetispeed(&value) == B38400);
    CHECK(!cfsetospeed(&value, B115200) && cfgetospeed(&value) == B115200 &&
          cfgetispeed(&value) == B115200 && (value.c_cflag & ~CBAUD) == others);
    CHECK(!cfsetispeed(&value, 0) && cfgetospeed(&value) == B115200);
    CHECK(!cfsetispeed(&value, B9600) && cfgetospeed(&value) == B9600 && (value.c_cflag & ~CBAUD) == others);
    CHECK(!cfsetospeed(&value, B0) && cfgetospeed(&value) == B0);
    const speed_t bad_speeds[] = {115200, CBAUD + 1, CIBAUD, 0x80000000U};
    for (unsigned index = 0; index < 4; ++index) {
        const tcflag_t before = value.c_cflag;
        errno = 0;
        CHECK(cfsetospeed(&value, bad_speeds[index]) == -1 && errno == EINVAL && value.c_cflag == before);
        errno = 0;
        CHECK(cfsetispeed(&value, bad_speeds[index]) == -1 && errno == EINVAL && value.c_cflag == before);
    }
    CHECK(!calls);
    *cases += 2;
    return 0;
}

static int pseudo_terminals(unsigned *cases)
{
    /* isatty probes with TCGETS and reports ENOTTY unless fd is bad. */
    response = 0; calls = 0;
    CHECK(isatty(11) == 1 && calls == 1 && words[0] == 11 && (uint32_t)words[1] == OK_TCGETS && words[2]);
    const long errors[] = {OK_ENOTTY, OK_EBADF, OK_EIO, OK_EACCES, OK_EFAULT};
    const int reported[] = {ENOTTY, EBADF, ENOTTY, ENOTTY, ENOTTY};
    for (unsigned index = 0; index < 5; ++index) {
        response = -errors[index]; errno = 0;
        CHECK(isatty(11) == 0 && errno == reported[index]);
        ++*cases;
    }

    /* posix_openpt opens /dev/ptmx with the caller's flags, O_NOCTTY included. */
    CHECK(O_NOCTTY == OK_O_NOCTTY && O_NOCTTY == 0x0100);
    const int flags[] = {O_RDWR | O_NOCTTY, O_RDWR | O_NOCTTY | O_CLOEXEC, O_RDWR};
    for (unsigned index = 0; index < 3; ++index) {
        response = 12; calls = 0;
        CHECK(posix_openpt(flags[index]) == 12 && calls == 1 && selected == OK_SYS_OPEN);
        CHECK(!strcmp((const char *)words[0], "/dev/ptmx") && words[1] == flags[index] && !words[2]);
        ++*cases;
    }
    response = 13;
    CHECK(open("/dev/pts/3", O_RDWR | O_NOCTTY) == 13 && selected == OK_SYS_OPEN &&
          !strcmp((const char *)words[0], "/dev/pts/3") && words[1] == (OK_O_RDWR | OK_O_NOCTTY));
    response = -OK_ENOSPC; errno = 0;
    CHECK(posix_openpt(O_RDWR | O_NOCTTY) == -1 && errno == EAGAIN);
    response = -OK_EACCES; errno = 0;
    CHECK(posix_openpt(O_RDWR) == -1 && errno == EACCES);
    *cases += 3;

    /* grantpt and unlockpt act on ptmx masters only: ENOTTY becomes EINVAL. */
    response = 0; calls = 0; kernel_ptn = 2;
    CHECK(!grantpt(14) && calls == 1 && words[0] == 14 && (uint32_t)words[1] == OK_TIOCGPTN && words[2]);
    written_lock = -7; calls = 0;
    CHECK(!unlockpt(15) && calls == 1 && words[0] == 15 && (uint32_t)words[1] == OK_TIOCSPTLCK &&
          words[2] && written_lock == 0);
    const long master_errors[] = {OK_ENOTTY, OK_EBADF, OK_EIO};
    const int master_reported[] = {EINVAL, EBADF, EIO};
    for (unsigned index = 0; index < 3; ++index) {
        response = -master_errors[index]; errno = 0;
        CHECK(grantpt(14) == -1 && errno == master_reported[index]);
        errno = 0;
        CHECK(unlockpt(15) == -1 && errno == master_reported[index]);
        ++*cases;
    }
    response = 0;
    *cases += 2;

    /* ptsname_r formats /dev/pts/<TIOCGPTN> and never writes past size. */
    const uint32_t numbers[] = {0, 3, 7, 10, 4294967295U};
    const char *const names[] = {"/dev/pts/0", "/dev/pts/3", "/dev/pts/7", "/dev/pts/10", "/dev/pts/4294967295"};
    for (unsigned index = 0; index < 5; ++index) {
        char buffer[24];
        const size_t need = strlen(names[index]) + 1;
        kernel_ptn = numbers[index];
        memset(buffer, 'x', sizeof(buffer)); calls = 0;
        CHECK(!ptsname_r(16, buffer, need) && calls == 1 && words[0] == 16);
        CHECK((uint32_t)words[1] == OK_TIOCGPTN && words[2] && !strcmp(buffer, names[index]));
        CHECK(buffer[need] == 'x');
        memset(buffer, 'x', sizeof(buffer)); errno = 0;
        CHECK(ptsname_r(16, buffer, need - 1) == ERANGE && errno == ERANGE && buffer[0] == 'x');
        CHECK(ptsname_r(16, NULL, 0) == ERANGE);
        CHECK(!strcmp(ptsname(16), names[index]));
        ++*cases;
    }
    response = -OK_ENOTTY; errno = 0;
    char unused[24] = "unchanged";
    CHECK(ptsname_r(17, unused, sizeof(unused)) == ENOTTY && !strcmp(unused, "unchanged"));
    errno = 0;
    CHECK(ptsname(17) == NULL && errno == ENOTTY);
    response = -OK_EBADF; errno = 0;
    CHECK(ptsname(17) == NULL && errno == EBADF);
    response = 0;
    *cases += 3;
    return 0;
}

int main(void)
{
    _Static_assert(sizeof(pid_t) == 4, "four-byte native terminal PID");
    _Static_assert(OK_NATIVE_CONSOLE_CONTROL_VERSION == 2, "terminal contract version");
    unsigned cases = 0;
    int line;
    if ((line = requests(&cases)) || (line = sessions(&cases)) || (line = attributes(&cases)) ||
        (line = pseudo_terminals(&cases)))
        return line;
    printf("NATIVE_TERMINAL_WRAPPER_PASS long_bits=%u cases=%u host_mock_only=1\n",
           (unsigned)(sizeof(long) * 8), cases);
    return 0;
}
