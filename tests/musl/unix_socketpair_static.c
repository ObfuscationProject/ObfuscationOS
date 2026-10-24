#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

static int exactly(int fd, char *bytes, unsigned count)
{
    unsigned got = 0;
    while (got < count)
    {
        ssize_t step = read(fd, bytes + got, count - got);
        if (step < 0 && errno == EINTR) continue;
        if (step <= 0) return -1;
        got += (unsigned)step;
    }
    return 0;
}

int main(void)
{
    int flags[2];
    if (socketpair(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0, flags) != 0) _Exit(80);
    if (!(fcntl(flags[0], F_GETFL) & O_NONBLOCK) || !(fcntl(flags[1], F_GETFD) & FD_CLOEXEC)) _Exit(81);
    char byte;
    errno = 0;
    if (read(flags[0], &byte, 1) != -1 || errno != EAGAIN) _Exit(82);
    close(flags[0]);
    close(flags[1]);

    int pair[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, pair) != 0) _Exit(83);
    pid_t child = fork();
    if (child < 0) _Exit(84);
    if (child == 0)
    {
        close(pair[0]);
        int inherited = dup(pair[1]);
        if (inherited < 0 || close(pair[1]) != 0) _Exit(85);
        char request[4];
        if (exactly(inherited, request, sizeof request) ||
            request[0] != 'p' || request[1] != 'i' || request[2] != 'n' || request[3] != 'g') _Exit(86);
        if (write(inherited, "pong", 4) != 4 || close(inherited) != 0) _Exit(87);
        _Exit(0);
    }
    close(pair[1]);
    if (write(pair[0], "ping", 4) != 4) _Exit(88);
    char response[4];
    if (exactly(pair[0], response, sizeof response) ||
        response[0] != 'p' || response[1] != 'o' || response[2] != 'n' || response[3] != 'g') _Exit(89);
    if (read(pair[0], &byte, 1) != 0) _Exit(90);
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status) != 0) _Exit(91);
    if (close(pair[0]) != 0) _Exit(92);
    static const char record[] = "OK_STATIC_UNIX_SOCKETPAIR fork=pass duplex=pass nonblock=pass eof=pass\n";
    if (write(1, record, sizeof record - 1) != sizeof record - 1) _Exit(93);
    return 0;
}
