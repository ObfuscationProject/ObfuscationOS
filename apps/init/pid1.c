#include "pid1_policy.h"

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifdef OK_PID1_TEST_GUEST
#define PID1_SERVICE_PATH "/bin/pid1-service"
#else
#define PID1_SERVICE_PATH "/bin/oksh"
#endif

static volatile sig_atomic_t stop_requested;

static void request_stop(int signal_number)
{
    (void)signal_number;
    stop_requested = 1;
}

static void emit(const char *event, int pid, long value)
{
    char buffer[128];
    int length = snprintf(buffer, sizeof(buffer),
                          "PID1_EVENT kind=%s pid=%d value=%ld\n", event, pid, value);
    if (length > 0 && (size_t)length < sizeof(buffer))
        (void)write(STDOUT_FILENO, buffer, (size_t)length);
}

static int monotonic_ms(uint64_t *result)
{
    struct timespec current;
    if (clock_gettime(CLOCK_MONOTONIC, &current) != 0 || current.tv_sec < 0 ||
        current.tv_nsec < 0 || current.tv_nsec >= 1000000000L ||
        (uint64_t)current.tv_sec > UINT64_MAX / 1000)
        return -1;
    uint64_t whole_ms = (uint64_t)current.tv_sec * 1000;
    uint64_t fractional_ms = (uint64_t)current.tv_nsec / 1000000;
    if (whole_ms > UINT64_MAX - fractional_ms)
        return -1;
    *result = whole_ms + fractional_ms;
    return 0;
}

static void idle(void)
{
    const struct timespec delay = { .tv_sec = 0, .tv_nsec = 10000000L };
    (void)nanosleep(&delay, 0);
}

static int install_signals(void)
{
    struct sigaction action = {0};
    sigset_t stop_signals;
    action.sa_handler = request_stop;
    if (sigemptyset(&action.sa_mask) != 0 ||
        sigemptyset(&stop_signals) != 0 ||
        sigaddset(&stop_signals, SIGTERM) != 0 ||
        sigaddset(&stop_signals, SIGINT) != 0 ||
        sigaction(SIGTERM, &action, 0) != 0 ||
        sigaction(SIGINT, &action, 0) != 0 ||
        sigprocmask(SIG_UNBLOCK, &stop_signals, 0) != 0)
        return -1;
    return 0;
}

static void decimal(unsigned value, char digits[16])
{
    char reverse[16];
    unsigned used = 0;
    do {
        reverse[used++] = (char)('0' + value % 10);
        value /= 10;
    } while (value && used < sizeof(reverse));
    for (unsigned i = 0; i < used; ++i)
        digits[i] = reverse[used - i - 1];
    digits[used] = 0;
}

/* Record a pending stop even if the inherited mask would keep it blocked. */
static int stop_pending(void)
{
    sigset_t pending;
    if (sigpending(&pending) != 0)
        return -1;
    int term = sigismember(&pending, SIGTERM);
    int interrupt = sigismember(&pending, SIGINT);
    if (term < 0 || interrupt < 0)
        return -1;
    if (term || interrupt)
        stop_requested = 1;
    return term || interrupt;
}

/* Restore the old signal mask and preserve the launch error when applicable. */
static int finish_launch(const sigset_t *previous, int outcome, int saved_errno)
{
    if (sigprocmask(SIG_SETMASK, previous, 0) != 0)
        return -2;
    if (saved_errno)
        errno = saved_errno;
    return outcome;
}

/* Returns 0 when published, 1 when canceled, -1 on launch error, -2 on mask error. */
static int launch(struct pid1_policy *policy, uint64_t now_ms, int *error_read)
{
    sigset_t blocked, previous;
    if (sigemptyset(&blocked) != 0 || sigaddset(&blocked, SIGTERM) != 0 ||
        sigaddset(&blocked, SIGINT) != 0 ||
        sigprocmask(SIG_BLOCK, &blocked, &previous) != 0)
        return -2;
    int pending = stop_pending();
    if (pending < 0)
        return finish_launch(&previous, -2, errno);
    if (stop_requested || pending)
        return finish_launch(&previous, 1, 0);
    int error_pipe[2];
    if (pipe2(error_pipe, O_CLOEXEC | O_NONBLOCK) != 0)
        return finish_launch(&previous, -1, errno);
    pending = stop_pending();
    if (pending < 0 || stop_requested || pending) {
        int error = pending < 0 ? errno : 0;
        close(error_pipe[0]);
        close(error_pipe[1]);
        return finish_launch(&previous, pending < 0 ? -2 : 1, error);
    }
    /* Fork is the commit point. A later stop is delivered after publication. */
    pid_t child = fork();
    if (child < 0) {
        int error = errno;
        close(error_pipe[0]);
        close(error_pipe[1]);
        return finish_launch(&previous, -1, error);
    }
    if (child == 0) {
        close(error_pipe[0]);
        struct sigaction action = {0};
        action.sa_handler = SIG_DFL;
        sigemptyset(&action.sa_mask);
        sigaction(SIGTERM, &action, 0);
        sigaction(SIGINT, &action, 0);
        if (sigprocmask(SIG_SETMASK, &previous, 0) != 0) {
            int error = errno;
            (void)write(error_pipe[1], &error, sizeof(error));
            _Exit(127);
        }
        char attempt[16];
        decimal(policy->launches + 1, attempt);
        char *const argv[] = { (char *)PID1_SERVICE_PATH, (char *)"--pid1-attempt",
                               attempt, 0 };
        char *const envp[] = { (char *)"PATH=/bin", (char *)"HOME=/",
                               (char *)"TERM=vt100", 0 };
        execve(PID1_SERVICE_PATH, argv, envp);
        int error = errno;
        (void)write(error_pipe[1], &error, sizeof(error));
        _Exit(127);
    }
    close(error_pipe[1]);
    *error_read = error_pipe[0];
    pid1_policy_launched(policy, child, now_ms);
    emit("launch", child, policy->launches);
    return finish_launch(&previous, 0, 0);
}

static void inspect_exec_pipe(int *error_read)
{
    if (*error_read < 0)
        return;
    int error = 0;
    ssize_t got = read(*error_read, &error, sizeof(error));
    if (got == (ssize_t)sizeof(error))
        emit("exec-failed", 0, error);
    if (got == 0 || got > 0 || (got < 0 && errno != EAGAIN && errno != EINTR)) {
        close(*error_read);
        *error_read = -1;
    }
}

int main(void)
{
    if (getpid() != 1 || install_signals() != 0) {
        emit("init-invalid", (int)getpid(), errno);
        return 1;
    }
    emit("init", 1, 0);
    struct pid1_policy policy;
    pid1_policy_init(&policy);
    int error_read = -1;
    for (;;) {
        uint64_t now_ms;
        if (monotonic_ms(&now_ms) != 0) {
            emit("clock-failed", 1, errno);
            return 2;
        }
        if (stop_requested && policy.phase != PID1_STOPPING &&
            policy.phase != PID1_STOPPED) {
            pid1_policy_shutdown(&policy, now_ms);
            emit("shutdown", policy.service_pid, 0);
            if (policy.service_pid > 0 && kill(policy.service_pid, SIGTERM) != 0 && errno != ESRCH)
                emit("term-failed", policy.service_pid, errno);
        }
        int children_remaining = 0;
        for (;;) {
            int status = 0;
            pid_t child = waitpid(-1, &status, WNOHANG);
            if (child > 0) {
                int service = pid1_policy_reaped(&policy, child, now_ms);
                emit(service ? "reap-service" : "reap-other", child, status);
                if (service && error_read >= 0) {
                    /* The exited child has closed the writer; consume an exec error before closing. */
                    inspect_exec_pipe(&error_read);
                }
                if (service && error_read >= 0) {
                    close(error_read);
                    error_read = -1;
                }
                continue;
            }
            if (child < 0 && errno == EINTR)
                continue;
            if (child < 0 && errno != ECHILD) {
                emit("wait-failed", 1, errno);
                return 3;
            }
            if (child < 0 && policy.service_pid > 0) {
                emit("service-lost", policy.service_pid, ECHILD);
                return 4;
            }
            children_remaining = child == 0;
            break;
        }
        inspect_exec_pipe(&error_read);
        if (policy.phase == PID1_STOPPED) {
            if (children_remaining) {
                if (now_ms >= policy.stop_started_ms &&
                    now_ms - policy.stop_started_ms >=
                        PID1_STOP_TERM_MS + PID1_STOP_KILL_MS) {
                    emit("orphan-timeout", 1, 0);
                    return 6;
                }
                idle();
                continue;
            }
            emit("stopped", 1, policy.forced_stops);
#ifdef OK_PID1_TEST_GUEST
            if (policy.launches == 3 && policy.other_exits == 1 &&
                policy.forced_stops == 0) {
                const char marker[] = "PID1_NATIVE_PASS pid=1 restarts=2 other=1 shutdown=clean\n";
                (void)write(STDOUT_FILENO, marker, sizeof(marker) - 1);
            }
#endif
            return 0;
        }
        if (pid1_policy_force_due(&policy, now_ms)) {
            if (kill(policy.service_pid, SIGKILL) != 0 && errno != ESRCH)
                emit("kill-failed", policy.service_pid, errno);
            pid1_policy_force_sent(&policy);
            emit("force-stop", policy.service_pid, 0);
        }
        if (pid1_policy_stop_expired(&policy, now_ms)) {
            emit("stop-timeout", policy.service_pid, 0);
            return 5;
        }
        if (pid1_policy_launch_due(&policy, now_ms)) {
            int outcome = launch(&policy, now_ms, &error_read);
            if (outcome == -2) {
                emit("signal-mask-failed", 1, errno);
                return 7;
            }
            if (outcome < 0) {
                emit("launch-failed", 0, errno);
                policy.next_launch_ms = pid1_saturating_add(now_ms, PID1_COOLDOWN_MS);
            }
        }
        idle();
    }
}
