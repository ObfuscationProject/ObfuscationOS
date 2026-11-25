#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>

_Static_assert(sizeof(struct termios) == sizeof(struct ok_termios), "native termios size");
_Static_assert(offsetof(struct termios, c_lflag) == offsetof(struct ok_termios, c_lflag) &&
               offsetof(struct termios, c_line) == offsetof(struct ok_termios, c_line) &&
               offsetof(struct termios, c_cc) == offsetof(struct ok_termios, c_cc),
               "native termios layout");

int tcgetattr(int fd, struct termios *attributes)
{
    return ioctl(fd, TCGETS, (void *)attributes) < 0 ? -1 : 0;
}

int tcsetattr(int fd, int action, const struct termios *attributes)
{
    unsigned long request;
    switch (action) {
    case TCSANOW:
        request = TCSETS;
        break;
    case TCSADRAIN:
        request = TCSETSW;
        break;
    case TCSAFLUSH:
        request = TCSETSF;
        break;
    default:
        errno = EINVAL;
        return -1;
    }
    return ioctl(fd, request, (void *)attributes) < 0 ? -1 : 0;
}

int tcflush(int fd, int queue)
{
    return ioctl(fd, TCFLSH, queue) < 0 ? -1 : 0;
}

/* A nonzero TCSBRK argument waits for output without sending a break. */
int tcdrain(int fd)
{
    return ioctl(fd, TCSBRK, 1) < 0 ? -1 : 0;
}

void cfmakeraw(struct termios *attributes)
{
    attributes->c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON);
    attributes->c_oflag &= ~OPOST;
    attributes->c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    attributes->c_cflag &= ~(CSIZE | PARENB);
    attributes->c_cflag |= CS8;
    attributes->c_cc[VMIN] = 1;
    attributes->c_cc[VTIME] = 0;
}

speed_t cfgetospeed(const struct termios *attributes)
{
    return attributes->c_cflag & CBAUD;
}

speed_t cfgetispeed(const struct termios *attributes)
{
    return cfgetospeed(attributes);
}

int cfsetospeed(struct termios *attributes, speed_t speed)
{
    if (speed & ~CBAUD) {
        errno = EINVAL;
        return -1;
    }
    attributes->c_cflag = (attributes->c_cflag & ~CBAUD) | speed;
    return 0;
}

/* Input speed 0 means "same as output"; any other value sets both. */
int cfsetispeed(struct termios *attributes, speed_t speed)
{
    return speed ? cfsetospeed(attributes, speed) : 0;
}

int isatty(int fd)
{
    struct termios attributes;
    if (!tcgetattr(fd, &attributes))
        return 1;
    if (errno != EBADF)
        errno = ENOTTY;
    return 0;
}

int posix_openpt(int flags)
{
    const int fd = open("/dev/ptmx", flags);
    /* The kernel reports a full PTY table as ENOSPC; POSIX names it EAGAIN. */
    if (fd < 0 && errno == ENOSPC)
        errno = EAGAIN;
    return fd;
}

/* The kernel already gives the slave to the opener's euid:egid with mode
 * 0620, so grantpt only checks that fd is a ptmx master. */
int grantpt(int fd)
{
    uint32_t number;
    if (ioctl(fd, TIOCGPTN, (void *)&number) < 0) {
        if (errno == ENOTTY)
            errno = EINVAL;
        return -1;
    }
    return 0;
}

int unlockpt(int fd)
{
    int lock = 0;
    if (ioctl(fd, TIOCSPTLCK, (void *)&lock) < 0) {
        if (errno == ENOTTY)
            errno = EINVAL;
        return -1;
    }
    return 0;
}

int ptsname_r(int fd, char *buffer, size_t size)
{
    static const char prefix[] = "/dev/pts/";
    uint32_t number;
    if (ioctl(fd, TIOCGPTN, (void *)&number) < 0)
        return errno;
    char digits[10];
    size_t count = 0;
    do {
        digits[count++] = (char)('0' + number % 10U);
        number /= 10U;
    } while (number);
    if (!buffer || size < sizeof(prefix) + count) {
        errno = ERANGE;
        return ERANGE;
    }
    size_t used = 0;
    for (; prefix[used]; ++used)
        buffer[used] = prefix[used];
    while (count)
        buffer[used++] = digits[--count];
    buffer[used] = '\0';
    return 0;
}

char *ptsname(int fd)
{
    static char name[sizeof("/dev/pts/4294967295")];
    const int error = ptsname_r(fd, name, sizeof(name));
    if (error) {
        errno = error;
        return NULL;
    }
    return name;
}
