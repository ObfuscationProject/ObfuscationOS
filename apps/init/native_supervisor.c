#include "native_supervisor.h"
#include "native_supervisor_protocol.h"
#include "native_manifest_load.h"
#include "native_control.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

struct ns_channel {
    struct ns_exec_channel exec;
    int exec_fd, ready_fd;
    unsigned exec_published : 1;
    unsigned ready : 1;
    unsigned notified : 1;
#ifdef OK_NATIVE_CONSOLE_LEASE
    uint32_t console_epoch;
#endif
};

struct ns_runtime {
    struct service_graph graph;
    struct nc_lifecycle lifecycle;
    struct { uid_t uid; gid_t gid; } identities[SG_CAPACITY];
    struct ns_channel channels[SG_CAPACITY];
#ifdef OK_NATIVE_INIT_CONTROL
    struct native_control control;
#endif
    uint64_t now;
    int clock_seen;
    int terminal_error;
};

static int ns_now(struct ns_runtime *runtime)
{
    struct timespec clock;
    uint64_t value;
    if (clock_gettime(CLOCK_MONOTONIC, &clock) < 0) return -1;
    if (ns_clock_value(clock.tv_sec, clock.tv_nsec, &value) ||
        (runtime->clock_seen && value < runtime->now)) { errno = EOVERFLOW; return -1; }
    runtime->now = value;
    runtime->clock_seen = 1;
    return 0;
}

static int ns_quiesce_budget(struct ns_runtime *runtime)
{
    if (ns_now(runtime) < 0) return -1;
    if (runtime->lifecycle.requested && (!runtime->lifecycle.completed || runtime->lifecycle.power_requested) &&
        runtime->now >= runtime->lifecycle.deadline_ms) { errno = EIO; return -1; }
    return 0;
}

static int ns_append(char *buffer, size_t capacity, size_t *size, const char *text)
{
    size_t length = strlen(text);
    if (length > capacity - *size) return -1;
    memcpy(buffer + *size, text, length);
    *size += length;
    return 0;
}

static int ns_event(struct ns_runtime *runtime, struct sg_token token,
                    const char *event, int error, int status)
{
    char record[384], number[21];
    size_t size = 0;
    const struct service_graph *graph = &runtime->graph;
    unsigned index = token.index;
#define NS_TEXT(value) do { if (ns_append(record, sizeof(record), &size, value)) { errno = EOVERFLOW; return -1; } } while (0)
#define NS_NUMBER(value) do { ns_decimal(number, (uint64_t)(value)); NS_TEXT(number); } while (0)
    NS_TEXT("NATIVE_PID1 scope=hardware profile=");
    NS_TEXT(graph->count == 1 && graph->specs[0].mode == SG_SIMPLE && !graph->specs[0].dependencies
        ? "direct-child-v1" : "dependency-graph-v1");
    NS_TEXT(" event="); NS_TEXT(event);
    NS_TEXT(" service="); NS_TEXT(index < graph->count ? graph->specs[index].name : "none");
    NS_TEXT(" pid="); NS_NUMBER(token.pid > 0 ? token.pid : 0);
    NS_TEXT(" generation="); NS_NUMBER(token.generation);
    NS_TEXT(" time_ms="); NS_NUMBER(runtime->now);
    NS_TEXT(" next_ms="); NS_NUMBER(index < graph->count ? graph->services[index].next_ms : 0);
    NS_TEXT(" errno="); NS_NUMBER(error > 0 ? error : 0);
    NS_TEXT(" status="); NS_NUMBER(status >= 0 ? status : 0);
    NS_TEXT("\n");
#undef NS_NUMBER
#undef NS_TEXT
    /* Refuse a new success record after the absolute lifecycle deadline, but
     * leave one attempt available for the terminal diagnostic itself. */
    if (runtime->lifecycle.requested && strcmp(event, "fatal-hold") && ns_quiesce_budget(runtime) < 0) return -1;
    ssize_t count;
    do {
        count = write(STDOUT_FILENO, record, size);
        if (count < 0 && errno == EINTR && ns_quiesce_budget(runtime) < 0) return -1;
    } while (count < 0 && errno == EINTR);
    if (count == (ssize_t)size) return 0;
    if (count >= 0) errno = EIO;
    return -1;
}

static int ns_close(int *owner)
{
    if (*owner < 0) return 0;
    int fd = *owner;
    *owner = -1;
    return close(fd);
}

#ifdef OK_NATIVE_CONSOLE_LEASE
#include "native_console_gate.h"
#endif

static int ns_close_channel(struct ns_channel *channel)
{
    int first = ns_close(&channel->exec_fd), saved = errno;
    int second = ns_close(&channel->ready_fd);
    if (first < 0) { errno = saved; return -1; }
    return second;
}

static int ns_init(struct ns_runtime *runtime, const struct service_manifest *manifest)
{
    *runtime = (struct ns_runtime){0};
#ifdef OK_NATIVE_INIT_CONTROL
    nc_reset(&runtime->control);
#endif
    for (unsigned i = 0; i < SG_CAPACITY; ++i)
        runtime->channels[i] = (struct ns_channel){.exec_fd = -1, .ready_fd = -1};
    if (sm_bind(manifest, &runtime->graph)) { errno = EINVAL; return -1; }
    for (unsigned i = 0; i < manifest->count; ++i) {
        runtime->identities[i].uid = (uid_t)manifest->records[i].uid;
        runtime->identities[i].gid = (gid_t)manifest->records[i].gid;
    }
    return ns_now(runtime);
}

static int ns_drain_exec(struct ns_runtime *runtime, struct ns_channel *channel)
{
    if (channel->exec_fd < 0) return 0;
    unsigned char bytes[sizeof(int) + 1];
    for (;;) {
        if (ns_quiesce_budget(runtime) < 0) return -1;
        ssize_t count = read(channel->exec_fd, bytes, sizeof(bytes));
        if (count < 0) {
            if (errno == EINTR) continue;
            if (errno == EAGAIN) return 0;
            return -1;
        }
        if (count) {
            ns_channel_bytes(&channel->exec, bytes, (size_t)count);
            if (channel->exec.state == NS_EXEC_BROKEN) { errno = EIO; return -1; }
            continue;
        }
        ns_channel_eof(&channel->exec);
        if (ns_close(&channel->exec_fd) < 0) return -1;
        if (channel->exec.state == NS_EXEC_BROKEN) { errno = EIO; return -1; }
        return 0;
    }
}

static void ns_child_error(int descriptor, int error)
{
    unsigned char *bytes = (unsigned char *)&error;
    size_t offset = 0;
    while (offset < sizeof(error)) {
        ssize_t count = write(descriptor, bytes + offset, sizeof(error) - offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) break;
        offset += (size_t)count;
    }
    _Exit(127);
}

static void ns_environment(char *out, const char *prefix, uint64_t value)
{
    char number[21];
    strcpy(out, prefix);
    ns_decimal(number, value);
    strcpy(out + strlen(prefix), number);
}

static int ns_launch_failed(struct ns_runtime *runtime, struct sg_token token, int error)
{
    if (ns_now(runtime) < 0 || sg_launch_failed(&runtime->graph, token, runtime->now)) return -1;
    return ns_event(runtime, token, "launch-failed", error, 0);
}

/* Only the fork child mutates credentials; every saved identity is retired. */
static int ns_child_identity(uid_t uid, gid_t gid)
{
    uid_t real_uid, effective_uid, saved_uid;
    gid_t real_gid, effective_gid, saved_gid;
    if (setresgid(gid, gid, gid) < 0 || setresuid(uid, uid, uid) < 0 ||
        getresgid(&real_gid, &effective_gid, &saved_gid) < 0 ||
        getresuid(&real_uid, &effective_uid, &saved_uid) < 0) return -1;
    if (real_gid != gid || effective_gid != gid || saved_gid != gid ||
        real_uid != uid || effective_uid != uid || saved_uid != uid) {
        errno = EPERM;
        return -1;
    }
    return 0;
}

/* Fork commits ownership. No fallible post-fork step may discard the child PID. */
static int ns_launch(struct ns_runtime *runtime, struct sg_action action)
{
    unsigned index = action.token.index;
    int error_pipe[2], ready_pipe[2] = {-1, -1};
    if (pipe2(error_pipe, O_CLOEXEC | O_NONBLOCK) < 0)
        return ns_launch_failed(runtime, action.token, errno);
    if (runtime->graph.specs[index].mode == SG_NOTIFY && pipe2(ready_pipe, O_CLOEXEC | O_NONBLOCK) < 0) {
        int error = errno;
        int reader = close(error_pipe[0]), writer = close(error_pipe[1]);
        if (reader < 0 || writer < 0) { errno = EIO; return -1; }
        return ns_launch_failed(runtime, action.token, error);
    }
#ifdef OK_NATIVE_CONSOLE_LEASE
    struct ns_console_gate gate;
    if (ns_console_gate_prepare(&gate, !strcmp(runtime->graph.specs[index].name, "console")) < 0) {
        int error = errno;
        int reader = close(error_pipe[0]), writer = close(error_pipe[1]);
        int ready_reader = ns_close(&ready_pipe[0]), ready_writer = ns_close(&ready_pipe[1]);
        if (reader < 0 || writer < 0 || ready_reader < 0 || ready_writer < 0) { errno = EIO; return -1; }
        return ns_launch_failed(runtime, action.token, error);
    }
#endif
    pid_t pid = fork();
    if (pid < 0) {
        int error = errno;
        int reader = close(error_pipe[0]), writer = close(error_pipe[1]);
        int ready_reader = ns_close(&ready_pipe[0]), ready_writer = ns_close(&ready_pipe[1]);
#ifdef OK_NATIVE_CONSOLE_LEASE
        if (ns_console_gate_close(&gate) < 0) { errno = EIO; return -1; }
#endif
        if (reader < 0 || writer < 0 || ready_reader < 0 || ready_writer < 0) { errno = EIO; return -1; }
        return ns_launch_failed(runtime, action.token, error);
    }
    if (!pid) {
#ifdef OK_NATIVE_INIT_CONTROL
        if (nc_close(&runtime->control) < 0) ns_child_error(error_pipe[1], errno);
#endif
        if (close(error_pipe[0]) < 0 || ns_close(&ready_pipe[0]) < 0) ns_child_error(error_pipe[1], errno);
        for (unsigned i = 0; i < runtime->graph.count; ++i)
            if (ns_close_channel(&runtime->channels[i]) < 0) ns_child_error(error_pipe[1], errno);
#ifdef OK_NATIVE_CONSOLE_LEASE
        uint32_t console_epoch = 0;
        if (ns_console_gate_child(&gate, &console_epoch) < 0) ns_child_error(error_pipe[1], errno);
#endif
        if (ready_pipe[1] >= 0 && fcntl(ready_pipe[1], F_SETFD, 0) < 0) ns_child_error(error_pipe[1], errno);
        if (ns_child_identity(runtime->identities[index].uid, runtime->identities[index].gid) < 0)
            ns_child_error(error_pipe[1], errno);
        char generation[64], name[64] = "OK_SERVICE_NAME=", attempt[64], ready[64] = "OK_SERVICE_READY_FD=-1";
        ns_environment(generation, "OK_SERVICE_GENERATION=", action.token.generation);
        ns_environment(attempt, "OK_SERVICE_ATTEMPT=", runtime->graph.services[index].launches + 1);
        if (ready_pipe[1] >= 0) ns_environment(ready, "OK_SERVICE_READY_FD=", (unsigned)ready_pipe[1]);
        strcpy(name + sizeof("OK_SERVICE_NAME=") - 1, runtime->graph.specs[index].name);
#ifdef OK_NATIVE_CONSOLE_LEASE
        char console[64];
        ns_environment(console, "OK_CONSOLE_EPOCH=", console_epoch);
        char *env[] = {"PATH=/bin", "HOME=/", "TERM=vt100", generation, name, attempt, ready, console, 0};
#else
        char *env[] = {"PATH=/bin", "HOME=/", "TERM=vt100", generation, name, attempt, ready, 0};
#endif
        char *argv[] = {(char *)runtime->graph.specs[index].executable, 0};
        execve(argv[0], argv, env);
        ns_child_error(error_pipe[1], errno);
    }
    /* The reserved graph slot and original time were validated before fork. */
    if (sg_launched(&runtime->graph, action.token, pid, runtime->now)) {
        /* This invariant is impossible without local corruption. Keep ownership. */
        runtime->graph.services[index].pid = pid;
        runtime->graph.services[index].phase = SG_FAILED;
        runtime->graph.failed = 1;
        runtime->channels[index] = (struct ns_channel){.exec_fd = error_pipe[0], .ready_fd = ready_pipe[0]};
        (void)close(error_pipe[1]);
        (void)ns_close(&ready_pipe[1]);
#ifdef OK_NATIVE_CONSOLE_LEASE
        (void)ns_console_gate_close(&gate);
#endif
        errno = EIO;
        return -1;
    }
    runtime->channels[index] = (struct ns_channel){.exec_fd = error_pipe[0], .ready_fd = ready_pipe[0]};
    int writer = close(error_pipe[1]), ready_writer = ns_close(&ready_pipe[1]);
#ifdef OK_NATIVE_CONSOLE_LEASE
    int gate_error = 0;
    if (writer >= 0 && ready_writer >= 0 && ns_console_gate_parent(&gate, pid, &runtime->channels[index].console_epoch) < 0)
        gate_error = errno;
    if (ns_console_gate_close(&gate) < 0 && !gate_error) gate_error = errno;
    if (gate_error) { errno = gate_error; return -1; }
#endif
    if (writer < 0 || ready_writer < 0 || ns_now(runtime) < 0) return -1;
    runtime->graph.services[index].launched_ms = runtime->now;
    runtime->lifecycle.children = NC_CHILDREN_UNKNOWN;
    return ns_event(runtime, sg_token(&runtime->graph, index), "launch", 0, 0);
}

static int ns_publish_exec(struct ns_runtime *runtime, unsigned index)
{
    sg_settle(&runtime->graph, runtime->now);
    struct ns_channel *channel = &runtime->channels[index];
    struct sg_service *service = &runtime->graph.services[index];
    if (channel->exec_published || channel->exec.state == NS_PENDING || service->phase != SG_STARTING) return 0;
    int success = channel->exec.state == NS_EXEC_CLOSED;
    if (sg_exec(&runtime->graph, sg_token(&runtime->graph, index), success, runtime->now)) {
        errno = EIO; return -1;
    }
    channel->exec_published = 1;
    return success ? 0 : ns_event(runtime, sg_token(&runtime->graph, index), "exec-failed", channel->exec.error, 0);
}

static int ns_drain_ready(struct ns_runtime *runtime, unsigned index)
{
    struct ns_channel *channel = &runtime->channels[index];
    if (channel->ready_fd < 0) return 0;
    unsigned char message[2];
    ssize_t count;
    do {
        if (ns_quiesce_budget(runtime) < 0) return -1;
        count = read(channel->ready_fd, message, sizeof(message));
    } while (count < 0 && errno == EINTR);
    if (count < 0 && errno == EAGAIN) return 0;
    if (count < 0) return -1;
    if (count == 1 && message[0] == 'R' && !channel->notified) {
        if (sg_ack(&runtime->graph, sg_token(&runtime->graph, index), runtime->now)) { errno = EIO; return -1; }
        channel->notified = 1;
        return 0;
    }
    if (ns_close(&channel->ready_fd) < 0) return -1;
    if (count == 0 && channel->notified) return 0;
    if (sg_fail(&runtime->graph, sg_token(&runtime->graph, index), runtime->now)) { errno = EIO; return -1; }
    return ns_event(runtime, sg_token(&runtime->graph, index), "notify-failed", EIO, 0);
}

/* Reap before publishing live readiness; a dead simple service is never ready. */
static int ns_collect(struct ns_runtime *runtime)
{
    /* No observation from an earlier launch or reap can prove current emptiness. */
    runtime->lifecycle.children = NC_CHILDREN_UNKNOWN;
    for (unsigned i = 0; i < runtime->graph.count; ++i)
        if (ns_drain_exec(runtime, &runtime->channels[i]) < 0) return -1;
    for (;;) {
        if (ns_quiesce_budget(runtime) < 0) return -1;
        int status = 0;
        pid_t pid = waitpid(-1, &status, WNOHANG);
        if (pid < 0) {
            if (errno == EINTR) continue;
            if (errno != ECHILD) return -1;
            for (unsigned i = 0; i < runtime->graph.count; ++i)
                if (runtime->graph.services[i].pid) { errno = EIO; return -1; }
            runtime->lifecycle.children = NC_CHILDREN_EMPTY;
            break;
        }
        if (!pid) { runtime->lifecycle.children = NC_CHILDREN_LIVE; break; }
        if (ns_now(runtime) < 0) return -1;
        unsigned index = runtime->graph.count;
        for (unsigned i = 0; i < runtime->graph.count; ++i)
            if (runtime->graph.services[i].pid == pid) { index = i; break; }
        if (index == runtime->graph.count) {
            if (runtime->graph.other_exits == ~0u) { errno = EOVERFLOW; return -1; }
            (void)sg_reaped(&runtime->graph, pid, 0, runtime->now);
            if (ns_event(runtime, (struct sg_token){index, 0, pid}, "other-child", 0, status) < 0) return -1;
            continue;
        }
        struct ns_channel *channel = &runtime->channels[index];
        struct sg_token token = sg_token(&runtime->graph, index);
        if (ns_drain_exec(runtime, channel) < 0) return -1;
        if (channel->exec.state == NS_PENDING) { errno = EIO; return -1; }
        if (ns_publish_exec(runtime, index) < 0) return -1;
        int error = channel->exec.state == NS_EXEC_ERROR ? channel->exec.error : 0;
        int clean = WIFEXITED(status) && WEXITSTATUS(status) == 0;
        if (sg_reaped(&runtime->graph, pid, clean, runtime->now) != (int)index) { errno = EIO; return -1; }
        if (ns_close_channel(channel) < 0) return -1;
#ifdef OK_NATIVE_CONSOLE_LEASE
        channel->console_epoch = 0; /* The kernel revokes before publishing death. */
#endif
        if (ns_event(runtime, token, "reap", error, WIFEXITED(status) ? WEXITSTATUS(status) : 128) < 0) return -1;
        if (runtime->graph.services[index].phase == SG_READY) {
            if (ns_event(runtime, token, "oneshot-ready", 0, 0) < 0) return -1;
        } else if (!runtime->graph.stopping &&
                   ns_event(runtime, sg_token(&runtime->graph, index), "restart", error, 0) < 0) return -1;
    }
    for (unsigned i = 0; i < runtime->graph.count; ++i) {
        if (ns_now(runtime) < 0 || ns_publish_exec(runtime, i) < 0) return -1;
        struct sg_service *service = &runtime->graph.services[i];
        if (service->phase == SG_STARTING || service->phase == SG_READY) {
            if (ns_drain_ready(runtime, i) < 0) return -1;
            if (service->phase == SG_READY && service->pid && !runtime->channels[i].ready) {
                const char *event = runtime->graph.specs[i].mode == SG_NOTIFY ? "notify-ready" : "simple-ready";
                if (ns_event(runtime, sg_token(&runtime->graph, i), event, 0, 0) < 0) return -1;
                runtime->channels[i].ready = 1;
            }
        }
    }
    return 0;
}

static int ns_quiesce_progress(struct ns_runtime *runtime)
{
    struct nc_lifecycle *lifecycle = &runtime->lifecycle;
    const struct sg_token owner = {SG_CAPACITY, 0, 1};
    if (!lifecycle->requested) return 0;
    if (ns_now(runtime) < 0) return -1;
    if (runtime->graph.failed || !runtime->graph.stopping ||
        (!lifecycle->completed && runtime->now >= lifecycle->deadline_ms)) { errno = EIO; return -1; }
    if (!lifecycle->announced) {
        if (ns_event(runtime, owner, "quiesce-started", 0, 0) < 0) return -1;
        lifecycle->announced = 1;
    }
    if (!sg_stopped(&runtime->graph)) return 0;
    if (!lifecycle->graph_stopped) {
        if (ns_event(runtime, owner, "graph-stopped", 0, 0) < 0) return -1;
        lifecycle->graph_stopped = 1;
    }
    if (lifecycle->completed) {
        if (lifecycle->children != NC_CHILDREN_EMPTY) { errno = EIO; return -1; }
        return 0;
    }
    /* A stopped graph says nothing about adopted descendants. Reset and drain
     * again after the graph boundary, accepting only a fresh actual ECHILD. */
    if (ns_collect(runtime) < 0) return -1;
    if (lifecycle->children != NC_CHILDREN_EMPTY) return 0;
    if (ns_now(runtime) < 0) return -1;
    if (runtime->now >= lifecycle->deadline_ms) { errno = EIO; return -1; }
    if (ns_event(runtime, owner, "quiesced", 0, 0) < 0) return -1;
    lifecycle->completed = 1;
    return 0;
}

static int ns_lifecycle_progress(struct ns_runtime *runtime)
{
    if (ns_quiesce_progress(runtime) < 0) return -1;
#ifdef OK_NATIVE_INIT_CONTROL
    struct nc_lifecycle *lifecycle = &runtime->lifecycle;
    if (lifecycle->power_requested && lifecycle->completed) {
        /* No earlier cached observation proves emptiness at the commit boundary. */
        if (ns_collect(runtime) < 0) return -1;
        if (lifecycle->children != NC_CHILDREN_EMPTY || !sg_stopped(&runtime->graph)) { errno = EIO; return -1; }
        for (unsigned i = 0; i < SG_CAPACITY; ++i)
            if (ns_quiesce_budget(runtime) < 0 || ns_close_channel(&runtime->channels[i]) < 0) return -1;
        if (ns_quiesce_budget(runtime) < 0 || nc_close(&runtime->control) < 0 || ns_quiesce_budget(runtime) < 0)
            return -1;
        if (nc_commit_power(lifecycle) < 0) return -1;
        lifecycle->power_committed = 1;
        return 1; /* Queued only. Never return to ordinary supervision. */
    }
#endif
    return 0;
}

static int ns_advance(struct ns_runtime *runtime)
{
    if (ns_now(runtime) < 0 || ns_collect(runtime) < 0) return -1;
    int progress = ns_lifecycle_progress(runtime);
    if (progress) return progress;
#ifdef OK_NATIVE_INIT_CONTROL
    if (nc_step(&runtime->control, &runtime->graph, &runtime->lifecycle, runtime->now) < 0) {
        int error = errno;
        if (runtime->lifecycle.power_requested) { errno = error; return -1; }
        (void)nc_close(&runtime->control);
        if (ns_event(runtime, (struct sg_token){SG_CAPACITY, 0, 1}, "control-disabled", error, 0) < 0) return -1;
    }
#endif
    progress = ns_lifecycle_progress(runtime);
    if (progress) return progress;
    for (unsigned step = 0; step < 2 * SG_CAPACITY; ++step) {
        if (ns_now(runtime) < 0) return -1;
        struct sg_action action = sg_next(&runtime->graph, runtime->now);
        if (action.kind == SG_NONE)
            return runtime->graph.failed ? (errno = EIO, -1) : ns_lifecycle_progress(runtime);
        if (action.kind == SG_TIMEOUT) { errno = EIO; return -1; }
        if (action.kind == SG_LAUNCH) {
            if (ns_launch(runtime, action) < 0) return -1;
            continue;
        }
        if (!sg_time_budget(runtime->now, action.kind == SG_TERM
            ? PID1_STOP_TERM_MS + PID1_STOP_KILL_MS : PID1_STOP_KILL_MS)) { errno = EOVERFLOW; return -1; }
        int signal_number = action.kind == SG_TERM ? SIGTERM : SIGKILL;
        if (kill(action.token.pid, signal_number) < 0 && errno != ESRCH) return -1;
        if (ns_now(runtime) < 0 || sg_signaled(&runtime->graph, action, runtime->now)) return -1;
        if (ns_close(&runtime->channels[action.token.index].ready_fd) < 0) return -1;
        if (ns_event(runtime, action.token, action.kind == SG_TERM ? "term" : "kill", 0,
                     runtime->graph.services[action.token.index].reason) < 0) return -1;
    }
    return ns_lifecycle_progress(runtime);
}

static int ns_step(struct ns_runtime *runtime)
{
    if (runtime->terminal_error) { errno = runtime->terminal_error; return -1; }
    if (runtime->lifecycle.power_committed) return 1;
    int result = ns_advance(runtime);
    if (result < 0 && runtime->lifecycle.power_requested) {
        runtime->terminal_error = errno ? errno : EIO;
        runtime->lifecycle.failed = 1;
        errno = runtime->terminal_error;
    }
    return result;
}

static void ns_hold(struct ns_runtime *runtime, int error)
{
    runtime->lifecycle.completed = 0;
    if (runtime->lifecycle.power_requested) {
        runtime->lifecycle.failed = 1;
        runtime->terminal_error = error ? error : EIO;
    }
    (void)ns_event(runtime, (struct sg_token){SG_CAPACITY, 0, 1}, "fatal-hold", error, 0);
    for (unsigned i = 0; i < runtime->graph.count; ++i) {
#ifdef OK_NATIVE_CONSOLE_LEASE
        if (runtime->channels[i].console_epoch)
            (void)ok_console_revoke(runtime->channels[i].console_epoch);
#endif
        (void)ns_close_channel(&runtime->channels[i]);
    }
#ifdef OK_NATIVE_INIT_CONTROL
    (void)nc_close(&runtime->control);
#endif
    for (;;) {
        int status;
        while (waitpid(-1, &status, WNOHANG) > 0) {}
        struct timespec pause = {0, 100000000};
        (void)nanosleep(&pause, 0);
    }
}

static _Noreturn void ns_park(void)
{
    /* COMMIT acknowledged a queued boundary. The kernel owns retirement; if
     * execution continues, keep PID1 alive without reopening any admission. */
    for (;;) {
        struct timespec pause = {0, 100000000};
        (void)nanosleep(&pause, 0);
    }
}

int native_supervisor_run(void)
{
    if (getpid() != 1) return 1;
    struct ns_runtime runtime = {0};
#ifdef OK_NATIVE_INIT_CONTROL
    nc_reset(&runtime.control);
#endif
    struct service_manifest manifest;
    int loaded = ns_manifest_load(&manifest);
    if (loaded < 0) ns_hold(&runtime, errno);
    if (loaded == NS_CONFIG_MISSING) {
#ifdef OK_NATIVE_CONSOLE_LOGIN
        static const char fallback[] = "OK_SERVICE_MANIFEST 2\nservice console simple /bin/login - 0 0\n";
#else
        static const char fallback[] = "OK_SERVICE_MANIFEST 1\nservice console simple /bin/oksh -\n";
#endif
        if (sm_parse(&manifest, fallback, sizeof(fallback) - 1)) ns_hold(&runtime, EINVAL);
    }
    if (ns_init(&runtime, &manifest) < 0) ns_hold(&runtime, errno);
#ifdef OK_NATIVE_INIT_CONTROL
    int control_error = nc_open(&runtime.control) < 0 ? errno : 0;
    if (ns_event(&runtime, (struct sg_token){SG_CAPACITY, 0, 1},
        control_error ? "control-unavailable" : "control-enabled", control_error, 0) < 0) ns_hold(&runtime, EIO);
#endif
    if (ns_event(&runtime, sg_token(&runtime.graph, 0),
        loaded == NS_CONFIG_MISSING ? "default-console" : "configured-console", 0, 0) < 0) ns_hold(&runtime, EIO);
    for (;;) {
        int progress = ns_step(&runtime);
        if (progress < 0) ns_hold(&runtime, errno);
        if (progress > 0) ns_park();
        struct timespec pause = {0, 10000000};
        if (nanosleep(&pause, 0) < 0 && errno != EINTR) ns_hold(&runtime, errno);
    }
}
