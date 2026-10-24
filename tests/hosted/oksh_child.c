#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    if (argc < 2) return 2;
    if (!strcmp(argv[1], "both")) {
        if (write(1, "stdout\n", 7) != 7 || write(2, "stderr\n", 7) != 7) return 3;
    } else if (!strcmp(argv[1], "emit")) {
        size_t remaining = (size_t)strtoul(argv[2], 0, 10);
        char data[4096]; memset(data, 'x', sizeof(data));
        while (remaining) {
            size_t count = remaining < sizeof(data) ? remaining : sizeof(data);
            ssize_t written = write(1, data, count);
            if (written < 0) { if (errno == EINTR) continue; return 3; }
            remaining -= (size_t)written;
        }
    } else if (!strcmp(argv[1], "touch")) {
        FILE *file = fopen(argv[2], "w");
        if (!file) return 3;
        fclose(file);
    } else if (!strcmp(argv[1], "identity")) {
        /* Capture the real hosted process group after the shell launch gate. */
        for (int fd = 3; fd < 64; ++fd)
            if (fcntl(fd, F_GETFD) >= 0) return 125;
        int fd = open(argv[2], O_WRONLY | O_CREAT | O_APPEND, 0600);
        if (fd < 0) return 3;
        int result = dprintf(fd, "CHILD %ld %ld %ld %ld\n", (long)getpid(),
                             (long)getppid(), (long)getsid(0), (long)getpgrp());
        close(fd);
        if (result < 0) return 3;
    } else if (!strcmp(argv[1], "status")) return atoi(argv[2]);
    else if (!strcmp(argv[1], "signal")) raise(SIGTERM);
    else return 2;
    return 0;
}
