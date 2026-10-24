#include "service_graph.h"
#include "service_manifest_load.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

struct channel {
    struct sg_token token;
    int exec_fd, ready_fd;
    unsigned exec_bytes;
    unsigned char exec_error[sizeof(int)];
};

static volatile sig_atomic_t stop_requested;
static void stop(int number) { (void)number; stop_requested = 1; }

static void emit(const struct service_graph *graph, const char *kind, struct sg_token token, long value)
{
    char buffer[224];
    const char *name = token.index < graph->count ? graph->specs[token.index].name : "init";
    int size = snprintf(buffer, sizeof(buffer),
        "SERVICE_EVENT kind=%s name=%s generation=%llu pid=%d value=%ld\n",
        kind, name, (unsigned long long)token.generation, token.pid, value);
    if (size > 0 && (size_t)size < sizeof(buffer)) (void)write(1, buffer, (size_t)size);
}

static struct sg_token init_token(void) { return (struct sg_token){SG_CAPACITY, 0, 1}; }

static int now_ms(uint64_t *result)
{
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC, &time) || time.tv_sec < 0 || time.tv_nsec < 0 ||
        time.tv_nsec >= 1000000000L || (uint64_t)time.tv_sec > UINT64_MAX / 1000) return -1;
    uint64_t whole = (uint64_t)time.tv_sec * 1000, part = (uint64_t)time.tv_nsec / 1000000;
    if (UINT64_MAX - whole < part) return -1;
    *result = whole + part;
    return 0;
}

static void close_channel(struct channel *channel)
{
    if (channel->exec_fd >= 0) close(channel->exec_fd);
    if (channel->ready_fd >= 0) close(channel->ready_fd);
    channel->exec_fd = channel->ready_fd = -1;
}

static void channel_failure(struct service_graph *graph, struct channel *channel, uint64_t now, int error)
{
    emit(graph, "channel-failed", channel->token, error);
    (void)sg_fail(graph, channel->token, now);
    close_channel(channel);
}

/* Complete exec status before publishing a oneshot's zero exit. */
static int inspect_channel(struct service_graph *graph, struct channel *channel)
{
    if (!sg_matches(graph, channel->token)) { close_channel(channel); return 0; }
    uint64_t now;
    enum sg_phase before = graph->services[channel->token.index].phase;
    if (channel->exec_fd >= 0) {
        for (;;) {
            ssize_t got = read(channel->exec_fd, channel->exec_error + channel->exec_bytes,
                               sizeof(int) - channel->exec_bytes);
            int read_error = errno;
            if (now_ms(&now)) return -1;
            if (got > 0) {
                channel->exec_bytes += (unsigned)got;
                if (channel->exec_bytes == sizeof(int)) {
                    int error;
                    memcpy(&error, channel->exec_error, sizeof(error));
                    emit(graph, "exec-failed", channel->token, error);
                    (void)sg_fail(graph, channel->token, now);
                    close_channel(channel);
                    return 0;
                }
                continue;
            }
            if (got == 0) {
                close(channel->exec_fd); channel->exec_fd = -1;
                if (channel->exec_bytes) { channel_failure(graph, channel, now, EPROTO); return 0; }
                if (graph->services[channel->token.index].phase == SG_STARTING) {
                    if (sg_exec(graph, channel->token, 1, now)) {
                        channel_failure(graph, channel, now, EPROTO); return 0;
                    }
                    emit(graph, "exec", channel->token, 0);
                }
                break;
            }
            if (read_error == EINTR) continue;
            if (read_error != EAGAIN) { channel_failure(graph, channel, now, read_error); return 0; }
            break;
        }
    }
    if (channel->ready_fd >= 0) {
        unsigned char message[2];
        ssize_t got;
        do { got = read(channel->ready_fd, message, sizeof(message)); } while (got < 0 && errno == EINTR);
        int read_error = errno;
        if (now_ms(&now)) return -1;
        if (got > 0) {
            if (got != 1 || message[0] != 'R' || sg_ack(graph, channel->token, now)) {
                channel_failure(graph, channel, now, EPROTO); return 0;
            }
            emit(graph, "notify", channel->token, 0);
        } else if (got == 0) {
            close(channel->ready_fd); channel->ready_fd = -1;
            const struct sg_service *service = &graph->services[channel->token.index];
            if (!service->ready_ack && (service->phase == SG_STARTING || service->phase == SG_READY)) {
                channel_failure(graph, channel, now, EPROTO); return 0;
            }
        } else if (read_error != EAGAIN) { channel_failure(graph, channel, now, read_error); return 0; }
    }
    if (before != SG_READY && graph->services[channel->token.index].phase == SG_READY)
        emit(graph, "ready", channel->token, graph->specs[channel->token.index].mode);
    return 0;
}

static int install_signals(void)
{
    struct sigaction action = {0};
    action.sa_handler = stop;
    sigset_t mask;
    return sigemptyset(&action.sa_mask) || sigemptyset(&mask) || sigaddset(&mask, SIGTERM) ||
        sigaddset(&mask, SIGINT) || sigaction(SIGTERM, &action, 0) || sigaction(SIGINT, &action, 0) ||
        sigprocmask(SIG_UNBLOCK, &mask, 0) ? -1 : 0;
}

static int pending_stop(void)
{
    sigset_t pending;
    if (sigpending(&pending)) return -1;
    int term = sigismember(&pending, SIGTERM), interrupt = sigismember(&pending, SIGINT);
    if (term < 0 || interrupt < 0) return -1;
    if (term || interrupt) stop_requested = 1;
    return stop_requested;
}

static int restore_mask(const sigset_t *previous, int result, int error)
{
    if (sigprocmask(SIG_SETMASK, previous, 0)) return -2;
    if (error) errno = error;
    return result;
}

/* Fork is the launch commit point; parent publishes before restoring stop signals. */
static int launch(struct service_graph *graph, struct channel *channels, struct sg_action action)
{
    sigset_t blocked, previous;
    if (sigemptyset(&blocked) || sigaddset(&blocked, SIGTERM) || sigaddset(&blocked, SIGINT) ||
        sigprocmask(SIG_BLOCK, &blocked, &previous)) return -2;
    int pending = pending_stop();
    if (pending < 0) return restore_mask(&previous, -2, errno);
    if (pending) return restore_mask(&previous, 1, 0);
    int error_pipe[2], ready_pipe[2] = {-1, -1};
    if (pipe2(error_pipe, O_CLOEXEC | O_NONBLOCK)) return restore_mask(&previous, -1, errno);
    if (graph->specs[action.token.index].mode == SG_NOTIFY && pipe2(ready_pipe, O_CLOEXEC | O_NONBLOCK)) {
        int error = errno; close(error_pipe[0]); close(error_pipe[1]);
        return restore_mask(&previous, -1, error);
    }
    pending = pending_stop();
    if (pending < 0 || pending) {
        int error = pending < 0 ? errno : 0;
        close(error_pipe[0]); close(error_pipe[1]);
        if (ready_pipe[0] >= 0) { close(ready_pipe[0]); close(ready_pipe[1]); }
        return restore_mask(&previous, pending < 0 ? -2 : 1, error);
    }
    pid_t child = fork();
    if (child < 0) {
        int error = errno; close(error_pipe[0]); close(error_pipe[1]);
        if (ready_pipe[0] >= 0) { close(ready_pipe[0]); close(ready_pipe[1]); }
        return restore_mask(&previous, -1, error);
    }
    if (child == 0) {
        close(error_pipe[0]);
        if (ready_pipe[0] >= 0) close(ready_pipe[0]);
        for (unsigned i = 0; i < graph->count; ++i) close_channel(&channels[i]);
        struct sigaction action_default = {0};
        action_default.sa_handler = SIG_DFL;
        int error = 0;
        if (sigemptyset(&action_default.sa_mask) || sigaction(SIGTERM, &action_default, 0) ||
            sigaction(SIGINT, &action_default, 0) ||
            (ready_pipe[1] >= 0 && fcntl(ready_pipe[1], F_SETFD, 0)) ||
            sigprocmask(SIG_SETMASK, &previous, 0)) error = errno;
        if (!error) {
            char descriptor[48], generation[64], name[64], attempt[64];
            const struct sg_spec *spec = &graph->specs[action.token.index];
            snprintf(descriptor, sizeof(descriptor), "OK_SERVICE_READY_FD=%d", ready_pipe[1]);
            snprintf(generation, sizeof(generation), "OK_SERVICE_GENERATION=%llu", (unsigned long long)action.token.generation);
            snprintf(name, sizeof(name), "OK_SERVICE_NAME=%s", spec->name);
            snprintf(attempt, sizeof(attempt), "OK_SERVICE_ATTEMPT=%u", graph->services[action.token.index].launches + 1);
            char *const argv[] = {(char *)spec->executable, 0};
            char *const envp[] = {"PATH=/bin", "HOME=/", "TERM=vt100", descriptor, generation, name, attempt, 0};
            execve(spec->executable, argv, envp);
            error = errno;
        }
        (void)write(error_pipe[1], &error, sizeof(error));
        _Exit(127);
    }
    close(error_pipe[1]);
    if (ready_pipe[1] >= 0) close(ready_pipe[1]);
    uint64_t committed_ms;
    if (now_ms(&committed_ms) || sg_launched(graph, action.token, child, committed_ms)) {
        close(error_pipe[0]);
        if (ready_pipe[0] >= 0) close(ready_pipe[0]);
        (void)kill(child, SIGKILL);
        int status;
        pid_t reaped;
        do { reaped = waitpid(child, &status, 0); } while (reaped < 0 && errno == EINTR);
        return restore_mask(&previous, -2, EPROTO);
    }
    struct channel *channel = &channels[action.token.index];
    close_channel(channel);
    *channel = (struct channel){.token = sg_token(graph, action.token.index),
        .exec_fd = error_pipe[0], .ready_fd = ready_pipe[0]};
    emit(graph, "launch", channel->token, graph->services[action.token.index].launches);
    return restore_mask(&previous, 0, 0);
}

int main(void)
{
#ifdef OK_SERVICE_GRAPH_TEST
    const struct sg_spec specs[] = {
        {"setup", "/bin/service-graph-child", 0, SG_ONESHOT},
        {"upstream", "/bin/service-graph-child", 1, SG_NOTIFY},
        {"downstream", "/bin/service-graph-child", 2, SG_NOTIFY}
    };
#else
    const struct sg_spec specs[] = {{"console", "/bin/oksh", 0, SG_SIMPLE}};
#endif
    struct service_graph graph = {0};
#ifdef OK_SERVICE_GRAPH_TEST
    if (sg_init(&graph, specs, sizeof(specs) / sizeof(specs[0]))) return 1;
#else
    static struct service_manifest manifest;
    int configuration = sm_load(&manifest);
    if (configuration < 0) { emit(&graph, "config-invalid", init_token(), errno); return 13; }
    if (configuration == SM_CONFIG_MISSING) {
        if (sg_init(&graph, specs, sizeof(specs) / sizeof(specs[0]))) return 1;
    } else if (sm_bind(&manifest, &graph)) {
        emit(&graph, "config-invalid", init_token(), EINVAL); return 13;
    }
#endif
    if (getpid() != 1 || install_signals()) { emit(&graph, "init-invalid", init_token(), errno); return 2; }
    struct channel channels[SG_CAPACITY];
    for (unsigned i = 0; i < SG_CAPACITY; ++i) channels[i] = (struct channel){.exec_fd = -1, .ready_fd = -1};
    emit(&graph, "init", init_token(), graph.count);
    uint64_t orphan_wait_ms = 0;
    int orphan_wait_started = 0;
    for (;;) {
        uint64_t now;
        if (now_ms(&now)) { emit(&graph, "clock-failed", init_token(), errno); return 3; }
        if (stop_requested && !graph.stopping) {
            sg_shutdown(&graph, now);
            emit(&graph, "shutdown", init_token(), 0);
        }
        for (unsigned i = 0; i < graph.count; ++i)
            if (inspect_channel(&graph, &channels[i])) { emit(&graph, "clock-failed", init_token(), errno); return 3; }
        int remaining = 0;
        for (;;) {
            int status;
            pid_t child = waitpid(-1, &status, WNOHANG);
            if (child > 0) {
                unsigned index = graph.count;
                for (unsigned i = 0; i < graph.count; ++i) if (graph.services[i].pid == child) { index = i; break; }
                struct sg_token token = index < graph.count ? sg_token(&graph, index) : (struct sg_token){SG_CAPACITY, 0, child};
                if (index < graph.count && inspect_channel(&graph, &channels[index])) {
                    emit(&graph, "clock-failed", init_token(), errno); return 3;
                }
                if (now_ms(&now)) { emit(&graph, "clock-failed", init_token(), errno); return 3; }
                int service = sg_reaped(&graph, child, WIFEXITED(status) && WEXITSTATUS(status) == 0, now);
                emit(&graph, service >= 0 ? "reap-service" : "reap-other", token, status);
                if (index < graph.count) {
                    close_channel(&channels[index]);
                    if (graph.services[index].phase == SG_READY)
                        emit(&graph, "ready", token, SG_ONESHOT);
                }
                continue;
            }
            if (child < 0 && errno == EINTR) continue;
            if (child < 0 && errno != ECHILD) { emit(&graph, "wait-failed", init_token(), errno); return 4; }
            if (child < 0)
                for (unsigned i = 0; i < graph.count; ++i)
                    if (graph.services[i].pid > 0) { emit(&graph, "service-lost", sg_token(&graph, i), ECHILD); return 5; }
            remaining = child == 0;
            break;
        }
        for (unsigned step = 0; step < 2 * SG_CAPACITY; ++step) {
            if (now_ms(&now)) { emit(&graph, "clock-failed", init_token(), errno); return 3; }
            struct sg_action action = sg_next(&graph, now);
            if (action.kind == SG_NONE) break;
            if (action.kind == SG_TIMEOUT) { emit(&graph, "stop-timeout", action.token, 0); return 6; }
            if (action.kind == SG_LAUNCH) {
                int result = launch(&graph, channels, action);
                if (result == -2) { emit(&graph, "launch-publication-failed", init_token(), errno); return 7; }
                if (result < 0) {
                    emit(&graph, "launch-failed", action.token, errno);
                    if (now_ms(&now)) { emit(&graph, "clock-failed", init_token(), errno); return 3; }
                    (void)sg_launch_failed(&graph, action.token, now);
                }
                if (result > 0 || stop_requested) break;
            } else {
                int signal_number = action.kind == SG_TERM ? SIGTERM : SIGKILL;
                emit(&graph, action.kind == SG_TERM ? "term" : "kill", action.token, graph.services[action.token.index].reason);
                if (now_ms(&now)) { emit(&graph, "clock-failed", init_token(), errno); return 3; }
                if (!sg_time_budget(now, action.kind == SG_TERM ? PID1_STOP_TERM_MS + PID1_STOP_KILL_MS : PID1_STOP_KILL_MS)) {
                    emit(&graph, "deadline-overflow", action.token, 0); return 9;
                }
                if (kill(action.token.pid, signal_number) && errno != ESRCH) {
                    emit(&graph, "signal-failed", action.token, errno); return 8;
                }
                if (now_ms(&now)) { emit(&graph, "clock-failed", init_token(), errno); return 3; }
                if (sg_signaled(&graph, action, now)) { emit(&graph, "signal-publication-failed", action.token, 0); return 9; }
                close_channel(&channels[action.token.index]);
            }
        }
        for (unsigned i = 0; i < graph.count; ++i)
            if (graph.services[i].phase == SG_FAILED) { emit(&graph, "policy-failed", sg_token(&graph, i), 0); return 10; }
        if (sg_stopped(&graph)) {
            if (!remaining) {
                emit(&graph, "stopped", init_token(), graph.other_exits);
#ifdef OK_SERVICE_GRAPH_TEST
                if (graph.services[0].launches == 1 && graph.services[1].launches == 2 &&
                    graph.services[2].launches == 2 && graph.other_exits == 1) {
                    const char marker[] = "SERVICE_GRAPH_NATIVE_PASS pid=1 setup=1 upstream=2 downstream=2 other=1 shutdown=ordered\n";
                    (void)write(1, marker, sizeof(marker) - 1);
                } else return 11;
#endif
                return 0;
            }
            if (now_ms(&now)) { emit(&graph, "clock-failed", init_token(), errno); return 3; }
            if (!orphan_wait_started) { orphan_wait_started = 1; orphan_wait_ms = now; }
            if (now >= orphan_wait_ms && now - orphan_wait_ms >= PID1_STOP_TERM_MS + PID1_STOP_KILL_MS) {
                emit(&graph, "orphan-timeout", init_token(), 0); return 12;
            }
        }
        const struct timespec delay = {.tv_sec = 0, .tv_nsec = 10000000L};
        (void)nanosleep(&delay, 0);
    }
}
