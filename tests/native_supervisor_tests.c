#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

enum { TEST_FDS = 64 };
struct test_pipe { unsigned char bytes[16]; size_t size, offset, chunk; int again, interrupted; };
static struct test_pipe descriptors[TEST_FDS];
static unsigned forks, pipes, closes, waits, reads, signals, event_write_calls;
static int pipe_error, fork_error, close_error, wait_error, read_error, clock_error, signal_error;
static int write_error, write_partial, next_fd, next_pid;
static int wait_empty, wait_repeated_error;
static unsigned wait_advance_ms, read_advance_ms, write_advance_ms, close_advance_ms;
static struct { int pid, status; } reap_queue[16];
static unsigned reap_begin, reap_end;
static struct { int pid, number; } signal_calls[32];
static struct timespec clock_value;
static char events[32768];
static size_t event_size;
static int child_mode, child_error, child_status, child_execs, identity_fault, identity_mismatch;
static unsigned char child_error_bytes[sizeof(int)];
static size_t child_error_size, child_trace_size;
static char child_trace[64];
static uid_t child_uids[3];
static gid_t child_gids[3];
static jmp_buf child_return;

static void trace_child(char operation)
{
    assert(child_mode && child_trace_size + 1 < sizeof(child_trace));
    child_trace[child_trace_size++] = operation; child_trace[child_trace_size] = 0;
}

static int fake_clock(clockid_t id, struct timespec *out)
{ assert(id == CLOCK_MONOTONIC); if (clock_error) { errno = clock_error; return -1; } *out = clock_value; return 0; }
static int fake_pipe(int ends[2], int flags)
{
    ++pipes; assert(flags == (O_CLOEXEC | O_NONBLOCK));
    if (pipe_error) { errno = pipe_error; return -1; }
    assert(next_fd + 1 < TEST_FDS); ends[0] = next_fd++; ends[1] = next_fd++; return 0;
}
static pid_t fake_fork(void)
{ ++forks; if (fork_error) { errno = fork_error; return -1; } return child_mode ? 0 : next_pid++; }
static int fake_close(int fd)
{
    assert(fd >= 3 && fd < TEST_FDS); ++closes;
    uint64_t advanced = (uint64_t)clock_value.tv_nsec + (uint64_t)close_advance_ms * 1000000;
    clock_value.tv_sec += (time_t)(advanced / 1000000000);
    clock_value.tv_nsec = (long)(advanced % 1000000000);
    if (child_mode) trace_child('C');
    if (close_error) { errno = close_error; return -1; } return 0;
}
static ssize_t fake_read(int fd, void *out, size_t capacity)
{
    assert(fd >= 3 && fd < TEST_FDS); ++reads;
    uint64_t advanced = (uint64_t)clock_value.tv_nsec + (uint64_t)read_advance_ms * 1000000;
    clock_value.tv_sec += (time_t)(advanced / 1000000000);
    clock_value.tv_nsec = (long)(advanced % 1000000000);
    struct test_pipe *pipe = &descriptors[fd];
    if (pipe->interrupted) { pipe->interrupted = 0; errno = EINTR; return -1; }
    if (read_error) { errno = read_error; return -1; }
    if (pipe->again) { errno = EAGAIN; return -1; }
    size_t count = pipe->size - pipe->offset;
    if (pipe->chunk && count > pipe->chunk) count = pipe->chunk;
    if (count > capacity) count = capacity;
    memcpy(out, pipe->bytes + pipe->offset, count); pipe->offset += count; return (ssize_t)count;
}
static pid_t fake_wait(pid_t pid, int *status, int flags)
{
    assert(pid == -1 && flags == WNOHANG); ++waits;
    uint64_t advanced = (uint64_t)clock_value.tv_nsec + (uint64_t)wait_advance_ms * 1000000;
    clock_value.tv_sec += (time_t)(advanced / 1000000000);
    clock_value.tv_nsec = (long)(advanced % 1000000000);
    if (wait_repeated_error) { errno = wait_repeated_error; return -1; }
    if (wait_error) { int error = wait_error; wait_error = 0; errno = error; return -1; }
    if (reap_begin == reap_end) { if (wait_empty) { errno = ECHILD; return -1; } return 0; }
    *status = reap_queue[reap_begin].status; return reap_queue[reap_begin++].pid;
}
static int fake_kill(pid_t pid, int number)
{
    assert(signals < 32); signal_calls[signals].pid = pid; signal_calls[signals++].number = number;
    if (signal_error) { errno = signal_error; return -1; } return 0;
}
static ssize_t fake_write(int fd, const void *in, size_t size)
{
    if (child_mode) {
        assert(fd == 4 && size <= sizeof(int) - child_error_size);
        trace_child('W'); memcpy(child_error_bytes + child_error_size, in, size); child_error_size += size;
        return (ssize_t)size;
    }
    assert(fd == STDOUT_FILENO);
    ++event_write_calls;
    uint64_t advanced = (uint64_t)clock_value.tv_nsec + (uint64_t)write_advance_ms * 1000000;
    clock_value.tv_sec += (time_t)(advanced / 1000000000);
    clock_value.tv_nsec = (long)(advanced % 1000000000);
    if (write_error) { errno = write_error; return -1; }
    if (write_partial && size) --size;
    assert(size <= sizeof(events) - event_size - 1);
    memcpy(events + event_size, in, size); event_size += size; events[event_size] = 0;
    return (ssize_t)size;
}
static int fake_fcntl(int fd, int command, ...)
{ assert(fd == 6 && command == F_SETFD); trace_child('F'); return 0; }
static int fake_setresgid(gid_t real, gid_t effective, gid_t saved)
{
    trace_child('G');
    if (identity_fault == 1) { errno = EACCES; return -1; }
    child_gids[0] = real; child_gids[1] = effective; child_gids[2] = saved; return 0;
}
static int fake_setresuid(uid_t real, uid_t effective, uid_t saved)
{
    trace_child('U');
    if (identity_fault == 2) { errno = EACCES; return -1; }
    child_uids[0] = real; child_uids[1] = effective; child_uids[2] = saved; return 0;
}
static int fake_getresgid(gid_t *real, gid_t *effective, gid_t *saved)
{
    trace_child('g');
    if (identity_fault == 3) { errno = EIO; return -1; }
    *real = child_gids[0] + (identity_mismatch == 1);
    *effective = child_gids[1] + (identity_mismatch == 2);
    *saved = child_gids[2] + (identity_mismatch == 3); return 0;
}
static int fake_getresuid(uid_t *real, uid_t *effective, uid_t *saved)
{
    trace_child('u');
    if (identity_fault == 4) { errno = EIO; return -1; }
    *real = child_uids[0] + (identity_mismatch == 4);
    *effective = child_uids[1] + (identity_mismatch == 5);
    *saved = child_uids[2] + (identity_mismatch == 6); return 0;
}
static int fake_execve(const char *path, char *const argv[], char *const environment[])
{
    trace_child('X'); ++child_execs;
    assert(!strcmp(path, "/bin/oksh") && !strcmp(argv[0], path) && !argv[1] && environment[0]);
    errno = ENOENT; return -1;
}
static _Noreturn void fake_exit(int status)
{
    trace_child('E'); child_status = status;
    assert(child_error_size == sizeof(int)); memcpy(&child_error, child_error_bytes, sizeof(int));
    longjmp(child_return, 1);
}

#define clock_gettime fake_clock
#define pipe2 fake_pipe
#define fork fake_fork
#define close fake_close
#define read fake_read
#define waitpid fake_wait
#define write fake_write
#define kill fake_kill
#define fcntl fake_fcntl
#define setresgid fake_setresgid
#define setresuid fake_setresuid
#define getresgid fake_getresgid
#define getresuid fake_getresuid
#define execve fake_execve
#define _Exit fake_exit
#include "../apps/init/native_supervisor.c"
#undef clock_gettime
#undef pipe2
#undef fork
#undef close
#undef read
#undef waitpid
#undef write
#undef kill
#undef fcntl
#undef setresgid
#undef setresuid
#undef getresgid
#undef getresuid
#undef execve
#undef _Exit

static struct service_manifest manifest;
static struct ns_runtime actor_config(const char *configuration)
{
    forks = pipes = closes = waits = reads = signals = event_write_calls = 0;
    pipe_error = fork_error = close_error = wait_error = read_error = clock_error = signal_error = 0;
    write_error = write_partial = 0; next_pid = 9; next_fd = 3; reap_begin = reap_end = 0;
    wait_empty = wait_repeated_error = 0; wait_advance_ms = read_advance_ms = write_advance_ms = close_advance_ms = 0;
    event_size = 0; memset(events, 0, sizeof(events)); memset(descriptors, 0, sizeof(descriptors));
    clock_value = (struct timespec){1, 0};
    child_mode = child_error = child_status = child_execs = identity_fault = identity_mismatch = 0;
    child_error_size = child_trace_size = 0; memset(child_trace, 0, sizeof(child_trace));
    memset(child_uids, 0, sizeof(child_uids)); memset(child_gids, 0, sizeof(child_gids));
    assert(!sm_parse(&manifest, configuration, strlen(configuration)));
    struct ns_runtime runtime; assert(!ns_init(&runtime, &manifest)); return runtime;
}
static struct ns_runtime actor(void)
{ return actor_config("OK_SERVICE_MANIFEST 1\nservice console simple /bin/oksh -\n"); }
static void time_ms(unsigned value)
{ clock_value = (struct timespec){value / 1000, (long)(value % 1000) * 1000000}; }
static void reap(int pid, int status)
{ assert(reap_end < 16); reap_queue[reap_end].pid = pid; reap_queue[reap_end++].status = status; }
static int launch_next(struct ns_runtime *runtime, unsigned index)
{
    struct sg_action action = sg_next(&runtime->graph, runtime->now);
    assert(action.kind == SG_LAUNCH && action.token.index == index);
    int result = ns_launch(runtime, action);
    if (!result && runtime->channels[index].ready_fd >= 0)
        descriptors[runtime->channels[index].ready_fd].again = 1;
    return result;
}

/* Retains the previous single-console channel, reap and error controls. */
static void channels_and_reaping(void)
{
    struct ns_runtime runtime = actor();
    assert(!launch_next(&runtime, 0) && forks == 1 && closes == 1 && runtime.channels[0].exec_fd == 3);
    reap(9, 127 << 8); assert(!ns_collect(&runtime));
    assert(strstr(events, "event=reap service=console pid=9 generation=1") && !strstr(events, "simple-ready"));
    assert(runtime.graph.services[0].pid == 0 && runtime.graph.services[0].next_ms == 1050 && closes == 2);
    runtime = actor(); assert(!launch_next(&runtime, 0));
    int error = ENOENT; memcpy(descriptors[3].bytes, &error, sizeof(error));
    descriptors[3].size = sizeof(error); descriptors[3].chunk = 1; descriptors[3].interrupted = 1;
    reap(9, 127 << 8); assert(!ns_collect(&runtime));
    assert(runtime.channels[0].exec.state == NS_EXEC_ERROR && runtime.channels[0].exec.error == ENOENT);
    assert(!strstr(events, "simple-ready") && strstr(events, "errno=2 status=127") && closes == 2 && reads >= 6);
    runtime = actor(); assert(!launch_next(&runtime, 0)); descriptors[3].size = 1; reap(9, 127 << 8);
    assert(ns_collect(&runtime) < 0 && errno == EIO && !strstr(events, "simple-ready") && !strstr(events, "event=reap"));
    assert(waits == 0 && runtime.graph.services[0].pid == 9);
    runtime = actor(); assert(!launch_next(&runtime, 0)); descriptors[3].size = sizeof(int) + 1;
    assert(ns_collect(&runtime) < 0 && errno == EIO && !strstr(events, "simple-ready"));
    runtime = actor(); assert(!launch_next(&runtime, 0)); descriptors[3].again = 1;
    assert(!ns_collect(&runtime) && !runtime.channels[0].ready && runtime.channels[0].exec_fd == 3);
    descriptors[3].again = 0; assert(!ns_collect(&runtime) && runtime.channels[0].ready && closes == 2);
    assert(strstr(events, "\nNATIVE_PID1 scope=hardware profile=direct-child-v1 event=simple-ready"));
    assert(!ns_collect(&runtime) && closes == 2);
    runtime = actor(); assert(!launch_next(&runtime, 0)); wait_error = EIO;
    assert(ns_collect(&runtime) < 0 && errno == EIO && !strstr(events, "simple-ready"));
    runtime = actor(); assert(!launch_next(&runtime, 0)); wait_error = ECHILD;
    assert(ns_collect(&runtime) < 0 && !strstr(events, "simple-ready"));
    runtime = actor(); assert(!launch_next(&runtime, 0)); read_error = EBADF;
    assert(ns_collect(&runtime) < 0 && errno == EBADF && waits == 0 && !strstr(events, "simple-ready"));
    runtime = actor(); assert(!launch_next(&runtime, 0)); wait_error = EINTR;
    assert(!ns_collect(&runtime) && runtime.channels[0].ready && waits == 2);
    runtime = actor(); assert(!launch_next(&runtime, 0)); reap(10, 0);
    assert(!ns_collect(&runtime) && runtime.graph.other_exits == 1 && runtime.graph.services[0].pid == 9);
}

static void launch_failures(void)
{
    struct ns_runtime runtime = actor(); pipe_error = EMFILE;
    assert(!launch_next(&runtime, 0) && !forks && !closes && !runtime.graph.services[0].launches);
    assert(runtime.graph.services[0].next_ms == 1050 && strstr(events, "event=launch-failed") && strstr(events, "errno=24"));
    runtime = actor(); fork_error = EAGAIN;
    assert(!launch_next(&runtime, 0) && forks == 1 && closes == 2 && !runtime.graph.services[0].pid);
    assert(runtime.graph.services[0].next_ms == 1050 && strstr(events, "errno=11"));
    runtime = actor(); close_error = EIO;
    assert(launch_next(&runtime, 0) < 0 && runtime.graph.services[0].pid == 9);
    assert(sg_next(&runtime.graph, UINT64_MAX).kind != SG_LAUNCH && forks == 1);
    runtime = actor(); clock_error = EIO;
    assert(launch_next(&runtime, 0) < 0 && runtime.graph.services[0].pid == 9);
    runtime = actor(); write_partial = 1;
    assert(launch_next(&runtime, 0) < 0 && errno == EIO && runtime.graph.services[0].pid == 9);
    runtime = actor(); write_error = EPIPE;
    assert(launch_next(&runtime, 0) < 0 && errno == EPIPE && runtime.graph.services[0].pid == 9);
    runtime = actor(); runtime.graph.services[0].launches = ~0u;
    assert(ns_step(&runtime) < 0 && !pipes && !forks);
    runtime = actor(); runtime.graph.services[0].generation = UINT64_MAX;
    assert(ns_step(&runtime) < 0 && !pipes && !forks);
    runtime = actor(); assert(!launch_next(&runtime, 0)); runtime.graph.other_exits = ~0u; reap(20, 0);
    assert(ns_collect(&runtime) < 0 && errno == EOVERFLOW && runtime.graph.other_exits == ~0u);
}

/* This intercepts the actual child branch. It never changes hosted credentials. */
static void child_identity_case(const char *configuration, int fault, int mismatch,
                                const char *trace, int error, unsigned execs)
{
    struct ns_runtime runtime = actor_config(configuration);
    identity_fault = fault; identity_mismatch = mismatch; child_mode = 1;
    if (!setjmp(child_return)) {
        (void)launch_next(&runtime, 0);
        assert(!"fork child returned without exit");
    }
    child_mode = 0;
    assert(child_status == 127 && child_error == error && child_execs == (int)execs);
    assert(!strcmp(child_trace, trace));
}

static void permanent_child_identities(void)
{
    static const char selected[] = "OK_SERVICE_MANIFEST 2\nservice console notify /bin/oksh - 1001 2002\n";
    child_identity_case(selected, 0, 0, "CCFGUguXWE", ENOENT, 1);
    for (unsigned i = 0; i < 3; ++i) assert(child_uids[i] == 1001 && child_gids[i] == 2002);
    static const char *traces[] = {"", "CCFGWE", "CCFGUWE", "CCFGUgWE", "CCFGUguWE"};
    for (int fault = 1; fault <= 4; ++fault)
        child_identity_case(selected, fault, 0, traces[fault], fault < 3 ? EACCES : EIO, 0);
    for (int mismatch = 1; mismatch <= 6; ++mismatch)
        child_identity_case(selected, 0, mismatch, "CCFGUguWE", EPERM, 0);
    child_identity_case("OK_SERVICE_MANIFEST 1\nservice console notify /bin/oksh -\n",
                        0, 0, "CCFGUguXWE", ENOENT, 1);
    for (unsigned i = 0; i < 3; ++i) assert(!child_uids[i] && !child_gids[i]);
}

static const char graph_configuration[] = "OK_SERVICE_MANIFEST 1\n"
    "service setup oneshot /bin/setup -\nservice provider notify /bin/provider setup\n"
    "service dependent simple /bin/dependent provider\n";
static struct ns_runtime live_graph(void)
{
    struct ns_runtime runtime = actor_config(graph_configuration);
    assert(!launch_next(&runtime, 0) && sg_next(&runtime.graph, runtime.now).kind == SG_NONE);
    reap(9, 0); assert(!ns_collect(&runtime) && runtime.graph.services[0].phase == SG_READY);
    assert(strstr(events, "event=oneshot-ready service=setup pid=9 generation=1"));
    assert(!launch_next(&runtime, 1)); assert(!ns_collect(&runtime));
    assert(runtime.graph.services[1].phase == SG_STARTING && sg_next(&runtime.graph, runtime.now).kind == SG_NONE);
    int fd = runtime.channels[1].ready_fd;
    descriptors[fd].bytes[0] = 'R'; descriptors[fd].size = 1; descriptors[fd].again = 0;
    assert(!ns_collect(&runtime) && runtime.graph.services[1].phase == SG_READY);
    assert(!launch_next(&runtime, 2) && !ns_collect(&runtime));
    assert(runtime.graph.services[2].phase == SG_READY && forks == 3); return runtime;
}

static void dependencies_and_restarts(void)
{
    struct ns_runtime runtime = live_graph();
    reap(10, 42 << 8); assert(!ns_step(&runtime));
    assert(runtime.graph.services[1].phase == SG_WAIT && runtime.graph.services[2].phase == SG_RETIRING);
    assert(signals == 1 && signal_calls[0].pid == 11 && signal_calls[0].number == SIGTERM);
    reap(11, SIGTERM); assert(!ns_step(&runtime) && runtime.graph.services[2].pid == 0);
    time_ms(1050); assert(!ns_now(&runtime) && !launch_next(&runtime, 1));
    assert(runtime.graph.services[1].generation == 2 && runtime.graph.services[2].generation == 1);
    assert(!ns_collect(&runtime) && sg_next(&runtime.graph, runtime.now).kind == SG_NONE);
    int fd = runtime.channels[1].ready_fd;
    descriptors[fd].bytes[0] = 'R'; descriptors[fd].size = 1; descriptors[fd].again = 0;
    assert(!ns_collect(&runtime) && !launch_next(&runtime, 2));
    assert(runtime.graph.services[2].generation == 2);
    runtime = live_graph(); reap(10, 42 << 8); assert(!ns_step(&runtime));
    time_ms(2500); assert(!ns_step(&runtime));
    assert(signals >= 2 && signal_calls[1].pid == 11 && signal_calls[1].number == SIGKILL);
    time_ms(3000); assert(ns_step(&runtime) < 0 && runtime.graph.failed);
    runtime = live_graph(); reap(10, 42 << 8); signal_error = EIO;
    assert(ns_step(&runtime) < 0 && runtime.graph.services[2].pid == 11 && !runtime.graph.services[2].term_sent);
}

static void independent_failure_and_notify(void)
{
    struct ns_runtime runtime = actor_config("OK_SERVICE_MANIFEST 1\n"
        "service missing simple /missing -\nservice console simple /bin/oksh -\n");
    assert(!launch_next(&runtime, 0) && !launch_next(&runtime, 1));
    int error = ENOENT; memcpy(descriptors[3].bytes, &error, sizeof(error)); descriptors[3].size = sizeof(error);
    reap(9, 127 << 8); assert(!ns_collect(&runtime));
    assert(runtime.graph.services[0].phase == SG_WAIT && runtime.graph.services[1].phase == SG_READY);
    assert(strstr(events, "event=exec-failed service=missing") && strstr(events, "event=simple-ready service=console"));
    runtime = actor_config("OK_SERVICE_MANIFEST 1\nservice delayed notify /bin/notify -\n");
    assert(!launch_next(&runtime, 0)); descriptors[runtime.channels[0].ready_fd].again = 0;
    assert(!ns_step(&runtime) && runtime.graph.services[0].phase == SG_RETIRING && signals == 1);
    assert(!strstr(events, "notify-ready") && strstr(events, "notify-failed"));
    runtime = actor_config("OK_SERVICE_MANIFEST 1\nservice delayed notify /bin/notify -\n");
    assert(!launch_next(&runtime, 0)); descriptors[3].again = 1;
    time_ms(4000); assert(!ns_step(&runtime) && signals == 1);
    descriptors[3].again = 0; reap(9, SIGTERM);
    assert(!ns_collect(&runtime) && !runtime.graph.services[0].pid && !strstr(events, "notify-ready"));
}

static void pure_boundaries(void)
{
    char digits[21]; ns_decimal(digits, UINT64_MAX); assert(!strcmp(digits, "18446744073709551615"));
    ns_decimal(digits, 0); assert(!strcmp(digits, "0")); uint64_t value;
    assert(ns_clock_value(-1, 0, &value) < 0 && ns_clock_value(0, -1, &value) < 0);
    assert(ns_clock_value(0, 1000000000, &value) < 0);
    uint64_t last = UINT64_MAX / 1000, fraction = UINT64_MAX % 1000;
    assert(!ns_clock_value((int64_t)last, (int64_t)fraction * 1000000, &value) && value == UINT64_MAX);
    assert(ns_clock_value((int64_t)last, (int64_t)(fraction + 1) * 1000000, &value) < 0);
    struct ns_runtime runtime = actor(); clock_value.tv_sec = 0;
    assert(ns_now(&runtime) < 0 && errno == EOVERFLOW && runtime.now == 1000);
    static const char *vectors[] = {
        "OK_SERVICE_MANIFEST 1\nservice console simple /bin/oksh -\n",
        "OK_SERVICE_MANIFEST 1\nservice console notify /bin/oksh -\n",
        "OK_SERVICE_MANIFEST 1\nservice console oneshot /bin/oksh -\n",
        "OK_SERVICE_MANIFEST 1\nservice first simple /bin/hello -\nservice second simple /bin/oksh first\n"
    };
    for (unsigned i = 0; i < sizeof(vectors) / sizeof(vectors[0]); ++i) {
        assert(!sm_parse(&manifest, vectors[i], strlen(vectors[i]))); assert(ns_manifest_supported(&manifest));
    }
    manifest.records[0].dependencies = 1; assert(!ns_manifest_supported(&manifest)); assert(!ns_manifest_supported(0));
    for (int error = -1; error <= 4096; error += 4097) {
        struct ns_exec_channel channel = {0}; ns_channel_bytes(&channel, (unsigned char *)&error, sizeof(error));
        ns_channel_eof(&channel); assert(channel.state == NS_EXEC_BROKEN);
    }
}

int main(void)
{
    channels_and_reaping(); launch_failures(); pure_boundaries();
    dependencies_and_restarts(); independent_failure_and_notify();
    permanent_child_identities();
    puts("NATIVE_PID1_MODEL_PASS protocol=bounded readiness=reap-checked launch=owned restart=bounded graph=shared dependency=retired");
    return 0;
}
