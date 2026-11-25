#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int record(const char *path, const char *event)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (fd < 0) return -1;
    int result = dprintf(fd, "%s %ld %ld\n", event, (long)getpid(), (long)getpgrp());
    close(fd);
    return result;
}

static int wait_file(const char *path)
{
    for (int i = 0; i < 1000 && access(path, F_OK) != 0; ++i) usleep(10000);
    return access(path, F_OK) == 0 ? 0 : 4;
}

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
    } else if (!strcmp(argv[1], "stop") && (argc == 4 || argc == 5)) {
        /* Stop like a job sent SIGTSTP; SIGSTOP also works in an orphaned group. */
        for (int stops = argc == 5 ? atoi(argv[4]) : 1; stops > 0; --stops) {
            if (record(argv[2], "STOP") < 0) return 3;
            raise(SIGSTOP);
            if (record(argv[2], "CONT") < 0) return 3;
        }
        return atoi(argv[3]);
    } else if (!strcmp(argv[1], "stop-wait") && argc == 4) {
        if (record(argv[2], "STOP") < 0) return 3;
        raise(SIGSTOP);
        if (record(argv[2], "CONT") < 0) return 3;
        return wait_file(argv[3]);
    } else if (!strcmp(argv[1], "wait-file") && argc == 3) {
        return wait_file(argv[2]);
    } else if (!strcmp(argv[1], "drain") && argc == 3) {
        char buffer[256];
        long total = 0;
        for (;;) {
            ssize_t count = read(0, buffer, sizeof(buffer));
            if (count < 0 && errno == EINTR) continue;
            if (count <= 0) break;
            total += count;
        }
        int fd = open(argv[2], O_WRONLY | O_CREAT | O_APPEND, 0600);
        if (fd < 0 || dprintf(fd, "STDIN %ld\n", total) < 0) return 3;
        close(fd);
    } else if (!strcmp(argv[1], "inspect") && argc == 3) {
        /* Report what the shell handed over: standard input and which of the
         * signals the interactive shell ignores are still ignored. */
        static const struct { int number; const char *name; } signals[] = {
            {SIGINT, "INT"}, {SIGQUIT, "QUIT"}, {SIGTSTP, "TSTP"}, {SIGTTIN, "TTIN"}, {SIGTTOU, "TTOU"}};
        char input[256], ignored[64] = "";
        ssize_t length = readlink("/proc/self/fd/0", input, sizeof(input) - 1);
        if (length < 0) return 3;
        input[length] = '\0';
        for (size_t i = 0; i < sizeof(signals) / sizeof(signals[0]); ++i) {
            struct sigaction action;
            if (sigaction(signals[i].number, NULL, &action) < 0) return 3;
            if (action.sa_handler != SIG_IGN) continue;
            if (ignored[0]) strcat(ignored, ",");
            strcat(ignored, signals[i].name);
        }
        int fd = open(argv[2], O_WRONLY | O_CREAT | O_APPEND, 0600);
        if (fd < 0 || dprintf(fd, "INPUT %s\nIGNORED %s\n", input, ignored[0] ? ignored : "-") < 0) return 3;
        close(fd);
    } else if (!strcmp(argv[1], "status")) return atoi(argv[2]);
    else if (!strcmp(argv[1], "signal")) raise(SIGTERM);
    else return 2;
    return 0;
}
