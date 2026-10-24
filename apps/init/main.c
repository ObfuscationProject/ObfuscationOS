#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#include <time.h>
#include "native_supervisor.h"

#ifdef OK_USERLAND_SELFTEST
static void marker(const char *record)
{
    size_t length = strlen(record);
    if (write(1, record, length) != (ssize_t)length) _Exit(2);
}
static int launch(const char *path, char *const argv[])
{
    pid_t pid = fork();
    if (pid < 0)
        return -1;
    if (pid == 0)
    {
        char *env[] = {"PATH=/bin", 0};
        execve(path, argv, env);
        perror(path);
        _Exit(127);
    }
    int status = 0;
    // Acceptance may deliberately orphan grandchildren. PID 1 must reap those
    // children while waiting for the requested program, just as the supervisor
    // does after acceptance; otherwise the process table fills during the test.
    for (;;) {
        pid_t completed = waitpid(-1, &status, 0);
        if (completed == pid) break;
        if (completed < 0 && errno != EINTR) return -1;
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128;
}
#endif

int main(void)
{
#ifdef OK_USERLAND_SELFTEST
    puts("ObfuscationOS: /init entered user mode");
    struct timespec before, after, delay = {0, 20000000};
    if (clock_gettime(CLOCK_MONOTONIC, &before) != 0 || nanosleep(&delay, 0) != 0 ||
        clock_gettime(CLOCK_MONOTONIC, &after) != 0 ||
        (after.tv_sec - before.tv_sec) * 1000000000 + after.tv_nsec - before.tv_nsec < delay.tv_nsec)
    {
        marker("OK_USERLAND scope=hardware acceptance=FAIL sole-sleeper\n");
        return 1;
    }
    puts("OK_SLEEP_NATIVE scope=hardware sole_sleeper=pass");
    char *check[] = {"posix-check", 0};
    if (launch("/bin/posix-check", check) != 0)
    {
        marker("OK_USERLAND scope=hardware acceptance=FAIL\n");
        return 1;
    }
#ifdef OK_NATIVE_UDP_PROBE
    char *udp_probe[] = {"udp-probe", 0};
    if (launch("/bin/udp-probe", udp_probe) != 0)
    {
        marker("OK_NATIVE_UDP scope=hardware acceptance=FAIL\n");
        return 1;
    }
#endif
    char *script[] = {"oksh", "-c", "hello | cat", 0};
    if (launch("/bin/oksh", script) != 0)
    {
        marker("OK_USERLAND scope=hardware shell_pipeline=FAIL\n");
        return 1;
    }
    marker("OK_USERLAND scope=hardware acceptance=pass shell_pipeline=pass\n");
#else
    puts("ObfuscationOS");
#endif
    return native_supervisor_run();
}
