#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <setjmp.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static pid_t fake_getpid(void);
static int fake_clock_gettime(clockid_t clock, struct timespec *value);
static pid_t fake_waitpid(pid_t pid, int *status, int options);
static int fake_pipe2(int descriptors[2], int flags);
static pid_t fake_fork(void);
static int fake_close(int descriptor);
static ssize_t fake_write(int descriptor, const void *data, size_t length);
static int fake_nanosleep(const struct timespec *request, struct timespec *remaining);
static int fake_kill(pid_t pid, int signal_number);

#define main reviewed_pid1_main
#define getpid fake_getpid
#define clock_gettime fake_clock_gettime
#define waitpid fake_waitpid
#define pipe2 fake_pipe2
#define fork fake_fork
#define close fake_close
#define write fake_write
#define nanosleep fake_nanosleep
#define kill fake_kill
#include "../apps/init/pid1.c"
#undef main

static jmp_buf done;
static unsigned forks;
static int inject_at_pipe;
static int inject_at_fork;
static char output[512];
static size_t used;

static pid_t fake_getpid(void) { return 1; }
static int fake_clock_gettime(clockid_t clock, struct timespec *value)
{ (void)clock; value->tv_sec = 0; value->tv_nsec = 0; return 0; }
static pid_t fake_waitpid(pid_t pid, int *status, int options)
{
    (void)pid; (void)status; (void)options;
    assert(raise(SIGTERM) == 0);  /* A TERM arrives after the loop checked the flag. */
    errno = ECHILD;
    return -1;
}
static int fake_pipe2(int descriptors[2], int flags)
{
    (void)flags;
    descriptors[0] = 10;
    descriptors[1] = 11;
    if (inject_at_pipe)
        raise(SIGTERM);
    return 0;
}
static pid_t fake_fork(void)
{
    forks++;
    if (inject_at_fork)
        raise(SIGTERM);
    return 42;
}
static int fake_close(int descriptor) { (void)descriptor; return 0; }
static ssize_t fake_write(int descriptor, const void *data, size_t length)
{
    (void)descriptor;
    assert(used + length < sizeof(output));
    memcpy(output + used, data, length);
    used += length;
    output[used] = 0;
    return (ssize_t)length;
}
static int fake_nanosleep(const struct timespec *request, struct timespec *remaining)
{ (void)request; (void)remaining; longjmp(done, 1); }
static int fake_kill(pid_t pid, int signal_number)
{ (void)pid; (void)signal_number; return 0; }

int main(void)
{
    sigset_t startup_block, startup_previous, current_mask;
    assert(sigemptyset(&startup_block) == 0);
    assert(sigaddset(&startup_block, SIGTERM) == 0);
    assert(sigprocmask(SIG_BLOCK, &startup_block, &startup_previous) == 0);
    if (setjmp(done) == 0)
        (void)reviewed_pid1_main();
    assert(sigprocmask(SIG_BLOCK, 0, &current_mask) == 0);
    assert(sigismember(&current_mask, SIGTERM) == 0);
    assert(stop_requested == 1);
    assert(forks == 0);
    assert(strstr(output, "PID1_EVENT kind=launch") == 0);
    struct pid1_policy policy;
    pid1_policy_init(&policy);
    int error_read = -1;
    stop_requested = 0;
    inject_at_pipe = 1;
    assert(launch(&policy, 0, &error_read) == 1);
    assert(stop_requested == 1 && forks == 0 && policy.service_pid == 0);
    inject_at_pipe = 0;
    stop_requested = 0;
    inject_at_fork = 1;
    assert(launch(&policy, 0, &error_read) == 0);
    assert(stop_requested == 1 && forks == 1 && policy.service_pid == 42);
    sigset_t inherited_block, old_mask;
    assert(sigemptyset(&inherited_block) == 0);
    assert(sigaddset(&inherited_block, SIGTERM) == 0);
    assert(sigprocmask(SIG_BLOCK, &inherited_block, &old_mask) == 0);
    stop_requested = 0;
    forks = 0;
    inject_at_fork = 0;
    inject_at_pipe = 1;
    pid1_policy_init(&policy);
    assert(launch(&policy, 0, &error_read) == 1);
    assert(stop_requested == 1 && forks == 0 && policy.service_pid == 0);
    assert(sigprocmask(SIG_SETMASK, &old_mask, 0) == 0);
    assert(sigprocmask(SIG_SETMASK, &startup_previous, 0) == 0);
    puts("PID1_SIGNAL_LAUNCH_PASS precommit=cancel postcommit=stop inherited-mask=stop boot-mask=clear");
    return 0;
}
