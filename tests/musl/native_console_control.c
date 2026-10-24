#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

_Static_assert(sizeof(pid_t) == 4, "the console ioctl PID wire is four bytes");

/* This Linux-personality probe is explicitly packaged by the qualifier only. */
static int fail(unsigned code)
{
    char line[128];
    int size = snprintf(line, sizeof(line), "\nNATIVE_CONSOLE_LINUX_FAIL pid=%d code=%u\n", getpid(), code);
    if (size > 0 && size < (int)sizeof(line)) (void)write(2, line, (size_t)size);
    return (int)code;
}

static int byte(int fd, char expected)
{
    struct pollfd descriptor = {fd, POLLIN, 0};
    if (poll(&descriptor, 1, 5000) != 1 || !(descriptor.revents & POLLIN) ||
        (descriptor.revents & (POLLERR | POLLNVAL))) return -1;
    char value = 0;
    return read(fd, &value, 1) == 1 && value == expected ? 0 : -1;
}

static int waited(pid_t child)
{
    int status = 0;
    return waitpid(child, &status, 0) == child && WIFEXITED(status) && !WEXITSTATUS(status) ? 0 : -1;
}

int main(int argc, char **argv)
{
    (void)argv;
    const pid_t pid = getpid(), sid = getsid(0), group = getpgrp(), parent = getppid();
    char line[256];
    if (argc != 1 || pid <= 1 || parent != sid || group != pid || group == sid ||
        getuid() || geteuid() || getgid() || getegid() ||
        tcgetsid(0) != sid || tcgetsid(1) != sid || tcgetsid(2) != sid || tcgetpgrp(0) != group)
        return fail(1);
    int size = snprintf(line, sizeof(line),
        "\nNATIVE_CONSOLE_LINUX_IDS pid=%d ppid=%d sid=%d pgid=%d tty_sid=%d fg=%d uid=0\n",
        pid, parent, sid, group, tcgetsid(0), tcgetpgrp(0));
    if (size <= 0 || size >= (int)sizeof(line) || write(2, line, (size_t)size) != size) return fail(2);
    errno = 0;
    if (ioctl(0, TIOCSCTTY, 1) != -1 || errno != EOPNOTSUPP) return fail(3);
    errno = 0;
    if (ioctl(0, TIOCSCTTY, 0) != -1 || errno != EPERM) return fail(4);

    int stop[2], ready[2], selected[2];
    if (pipe(stop) || pipe(ready) || pipe(selected)) return fail(5);
    pid_t controller = fork();
    if (controller < 0) return fail(6);
    if (!controller) {
        close(stop[1]); close(ready[0]); close(selected[0]); close(selected[1]);
        if (setpgid(0, 0) || getpgrp() != getpid() || tcgetsid(0) != sid ||
            write(ready[1], "C", 1) != 1 || close(ready[1]) || byte(stop[0], 'X')) _Exit(fail(7));
        close(stop[0]); _Exit(0);
    }
    close(stop[0]); close(ready[1]);
    if (byte(ready[0], 'C') || close(ready[0]) || getpgid(controller) != controller) return fail(8);
    pid_t reader = fork();
    if (reader < 0) return fail(9);
    if (!reader) {
        close(stop[1]); close(selected[0]);
        if (tcgetpgrp(0) != group || getpgrp() != group || getsid(0) != sid) _Exit(fail(10));
        int count = snprintf(line, sizeof(line),
            "\nNATIVE_CONSOLE_LINUX_READY pid=%d ppid=%d sid=%d pgid=%d wait=select armed=unproven\n",
            getpid(), getppid(), getsid(0), getpgrp());
        if (count <= 0 || count >= (int)sizeof(line) || write(2, line, (size_t)count) != count ||
            write(selected[1], "A", 1) != 1) _Exit(fail(11));
        fd_set reads, exceptions;
        FD_ZERO(&reads); FD_ZERO(&exceptions); FD_SET(0, &reads); FD_SET(0, &exceptions);
        struct timeval timeout = {5, 0};
        errno = 0;
        if (select(1, &reads, 0, &exceptions, &timeout) != 1 || !FD_ISSET(0, &reads) ||
            FD_ISSET(0, &exceptions)) _Exit(fail(12));
        char input = 0;
        errno = 0;
        if (read(0, &input, 1) != -1 || errno != EIO || tcgetpgrp(0) != controller ||
            tcgetsid(0) != sid || write(selected[1], "S", 1) != 1) _Exit(fail(13));
        close(selected[1]); _Exit(0);
    }
    close(selected[1]);
    if (byte(selected[0], 'A')) return fail(14);
    /* The exact armed ticket is checked separately by the hosted runtime test.
     * No console input is injected during this guest pre-syscall window. */
    const struct timespec delay = {0, 100000000};
    if (nanosleep(&delay, 0) || setgid(1000) || setuid(1000) ||
        getuid() != 1000 || geteuid() != 1000 || getgid() != 1000 || getegid() != 1000 ||
        tcsetpgrp(0, controller) || tcgetpgrp(0) != controller || tcgetsid(0) != sid) return fail(15);
    char input = 0;
    struct iovec vector = {&input, 1};
    errno = 0;
    if (read(0, &input, 1) != -1 || errno != EIO) return fail(16);
    errno = 0;
    if (readv(0, &vector, 1) != -1 || errno != EIO) return fail(17);
    struct pollfd console = {0, POLLIN, 0};
    if (poll(&console, 1, 0) != 1 || console.revents != POLLERR ||
        byte(selected[0], 'S') || close(selected[0]) || waited(reader)) return fail(18);
    if (tcsetpgrp(0, group) || tcgetpgrp(0) != group || tcgetsid(0) != sid ||
        write(stop[1], "X", 1) != 1 || close(stop[1]) || waited(controller)) return fail(19);
    size = snprintf(line, sizeof(line),
        "\nNATIVE_CONSOLE_LINUX_PASS pid=%d sid=%d pgid=%d reader=%d controller=%d uid=1000 "
        "select=readable read=EIO readv=EIO poll=ERR reclaim=pass pid_bytes=4\n",
        pid, sid, group, reader, controller);
    return size <= 0 || size >= (int)sizeof(line) || write(2, line, (size_t)size) != size ? fail(20) : 0;
}
