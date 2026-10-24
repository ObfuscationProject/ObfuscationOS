#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stop_requested;

static void stop(int signal_number)
{
    (void)signal_number;
    stop_requested = 1;
}

static void mark_pid(const char *kind, int number)
{
    char buffer[128];
    int length = snprintf(buffer, sizeof(buffer),
                          "PID1_SERVICE_%s attempt=%d pid=%ld\n",
                          kind, number, (long)getpid());
    if (length > 0 && (size_t)length < sizeof(buffer))
        (void)write(STDOUT_FILENO, buffer, (size_t)length);
}

static void pause_briefly(void)
{
    const struct timespec delay = { .tv_sec = 0, .tv_nsec = 10000000L };
    (void)nanosleep(&delay, 0);
}

int main(int argc, char **argv)
{
    if (argc != 3 || strcmp(argv[1], "--pid1-attempt") != 0 ||
        getppid() != 1 || getpid() <= 1)
        return 91;
    int attempt = atoi(argv[2]);
    if (attempt == 1 || attempt == 2) {
        mark_pid("CRASH", attempt);
        _Exit(42);
    }
    if (attempt != 3)
        return 92;
    int report[2];
    if (pipe(report) != 0)
        return 93;
    pid_t intermediate = fork();
    if (intermediate < 0)
        return 94;
    if (intermediate == 0) {
        close(report[0]);
        pid_t orphan = fork();
        if (orphan < 0)
            _Exit(95);
        if (orphan > 0)
            _Exit(0);
        for (int tries = 0; tries < 300 && getppid() != 1; ++tries)
            pause_briefly();
        if (getppid() != 1)
            _Exit(96);
        char marker[128];
        int length = snprintf(marker, sizeof(marker),
                              "PID1_ORPHAN_PASS pid=%ld ppid=%ld\n",
                              (long)getpid(), (long)getppid());
        if (length > 0 && (size_t)length < sizeof(marker))
            (void)write(STDOUT_FILENO, marker, (size_t)length);
        (void)write(report[1], "O", 1);
        close(report[1]);
        _Exit(17);
    }
    close(report[1]);
    int status;
    if (waitpid(intermediate, &status, 0) != intermediate ||
        !WIFEXITED(status) || WEXITSTATUS(status) != 0)
        return 97;
    char acknowledgment = 0;
    if (read(report[0], &acknowledgment, 1) != 1 || acknowledgment != 'O')
        return 98;
    close(report[0]);
    for (int i = 0; i < 20; ++i)
        pause_briefly();
    struct sigaction action = {0};
    action.sa_handler = stop;
    if (sigemptyset(&action.sa_mask) != 0 || sigaction(SIGTERM, &action, 0) != 0 ||
        kill(1, SIGTERM) != 0)
        return 99;
    for (int tries = 0; tries < 300 && !stop_requested; ++tries)
        pause_briefly();
    if (!stop_requested)
        return 100;
    mark_pid("STOP", attempt);
    return 0;
}
