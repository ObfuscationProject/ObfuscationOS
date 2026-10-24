#define _GNU_SOURCE 1
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static uint64_t simulated_ms, term_ms, kill_ms;
static int child_live, child_killed, read_mode, readiness_logged;
static unsigned fork_delay, term_delay;
static unsigned fork_calls, config_closes, directory_closes;
static const char *configuration_input;
static size_t configuration_size, configuration_offset;
static mode_t configuration_mode;
static uid_t configuration_uid;
static int model_clock(clockid_t id, struct timespec *time);
static ssize_t model_read(int fd, void *data, size_t size);
static ssize_t model_write(int fd, const void *data, size_t size);
static int model_close(int fd);
static int model_kill(pid_t pid, int signal_number);
static pid_t model_fork(void);
static pid_t model_waitpid(pid_t pid, int *status, int options);
static int model_pipe2(int descriptors[2], int flags);
static int model_sigaction(int number, const struct sigaction *action, struct sigaction *old);
static int model_sigprocmask(int how, const sigset_t *set, sigset_t *old);
static int model_sigpending(sigset_t *set);
static int model_nanosleep(const struct timespec *time, struct timespec *remaining);
static pid_t model_getpid(void);
static int model_open(const char *path, int flags, ...);
static int model_openat(int directory, const char *path, int flags, ...);
static int model_fstat(int descriptor, struct stat *metadata);

#define main service_manager_entry
#define clock_gettime model_clock
#define read model_read
#define write model_write
#define close model_close
#define kill model_kill
#define fork model_fork
#define waitpid model_waitpid
#define pipe2 model_pipe2
#define sigaction(...) model_sigaction(__VA_ARGS__)
#define sigprocmask model_sigprocmask
#define sigpending model_sigpending
#define nanosleep model_nanosleep
#define getpid model_getpid
#define open model_open
#define openat model_openat
#define fstat model_fstat
#include "../apps/init/service_manager.c"
#undef main
#undef clock_gettime
#undef read
#undef write
#undef close
#undef kill
#undef fork
#undef waitpid
#undef pipe2
#undef sigaction
#undef sigprocmask
#undef sigpending
#undef nanosleep
#undef getpid
#undef open
#undef openat
#undef fstat

static int model_clock(clockid_t id, struct timespec *time)
{
    assert(id == CLOCK_MONOTONIC);
    time->tv_sec = (time_t)(simulated_ms / 1000);
    time->tv_nsec = (long)(simulated_ms % 1000) * 1000000;
    errno = EIO; /* A successful intervening call must not replace read's errno. */
    return 0;
}
static ssize_t model_read(int fd, void *data, size_t size)
{
    if (fd == 21) {
        size_t remaining = configuration_size - configuration_offset;
        if (size > remaining) size = remaining;
        memcpy(data, configuration_input + configuration_offset, size); configuration_offset += size;
        return (ssize_t)size;
    }
    (void)fd; (void)data; (void)size;
    if (read_mode == 1) simulated_ms = 4000;
    if (read_mode == 2) { errno = EAGAIN; return -1; }
    return 0;
}
static ssize_t model_write(int fd, const void *data, size_t size)
{
    assert(fd == 1);
    char text[256];
    assert(size < sizeof(text)); memcpy(text, data, size); text[size] = 0;
    if (strstr(text, "kind=term ")) simulated_ms += 400;
    if (strstr(text, "kind=ready ")) { readiness_logged = 1; stop_requested = 1; }
    return (ssize_t)size;
}
static int model_close(int fd) { if (fd == 20) ++directory_closes; if (fd == 21) ++config_closes; return 0; }
static int model_kill(pid_t pid, int number)
{
    assert(pid == 42);
    if (number == SIGTERM) { simulated_ms += term_delay; term_ms = simulated_ms; }
    else { assert(number == SIGKILL); kill_ms = simulated_ms; child_killed = 1; }
    return 0;
}
static pid_t model_fork(void)
{ ++fork_calls; simulated_ms += fork_delay; child_live = 1; return 42; }
static pid_t model_waitpid(pid_t pid, int *status, int options)
{
    (void)pid; assert(options == WNOHANG || options == 0);
    if (!child_live) { errno = ECHILD; return -1; }
    if (!child_killed) return 0;
    child_live = 0; *status = SIGKILL; return 42;
}
static int model_pipe2(int descriptors[2], int flags)
{ assert(flags == (O_CLOEXEC | O_NONBLOCK)); descriptors[0] = 10; descriptors[1] = 11; return 0; }
static int model_sigaction(int number, const struct sigaction *action, struct sigaction *old)
{ (void)number; (void)action; (void)old; return 0; }
static int model_sigprocmask(int how, const sigset_t *set, sigset_t *old)
{ (void)how; (void)set; if (old) sigemptyset(old); return 0; }
static int model_sigpending(sigset_t *set) { return sigemptyset(set); }
static int model_nanosleep(const struct timespec *time, struct timespec *remaining)
{ (void)remaining; assert(time->tv_sec == 0 && time->tv_nsec == 10000000L); simulated_ms += 10; return 0; }
static pid_t model_getpid(void) { return 1; }
static int model_open(const char *path, int flags, ...)
{ assert(!strcmp(path, "/etc") && flags == (O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW)); return 20; }
static int model_openat(int directory, const char *path, int flags, ...)
{
    assert(directory == 20 && !strcmp(path, "services.conf") && flags == (O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
    if (configuration_input) return 21;
    errno = ENOENT; return -1;
}
static int model_fstat(int descriptor, struct stat *metadata)
{
    memset(metadata, 0, sizeof(*metadata));
    if (descriptor == 20) metadata->st_mode = S_IFDIR | 0755;
    else {
        assert(descriptor == 21); metadata->st_mode = configuration_mode;
        metadata->st_uid = configuration_uid; metadata->st_size = (off_t)configuration_size;
    }
    return 0;
}

static void reset(void)
{
    simulated_ms = term_ms = kill_ms = 0;
    child_live = child_killed = read_mode = readiness_logged = 0;
    fork_delay = term_delay = 0; stop_requested = 0;
    fork_calls = config_closes = directory_closes = 0;
    configuration_input = 0; configuration_size = configuration_offset = 0;
    configuration_mode = S_IFREG | 0644; configuration_uid = 0;
}

int main(void)
{
    reset();
    assert(service_manager_entry() == 0 && readiness_logged);
    assert(kill_ms >= term_ms && kill_ms - term_ms == PID1_STOP_TERM_MS);
    /* The term log blocked 400 ms, without aging the actual TERM deadline. */
    assert(term_ms >= 400);
    reset();
    term_delay = 400;
    assert(service_manager_entry() == 0 && readiness_logged);
    assert(kill_ms >= term_ms && kill_ms - term_ms == PID1_STOP_TERM_MS);
    reset();
    const struct sg_spec spec = {"one", "/one", 0, SG_ONESHOT};
    struct service_graph graph;
    assert(sg_init(&graph, &spec, 1) == 0);
    struct sg_action action = sg_next(&graph, 0);
    assert(sg_launched(&graph, action.token, 42, 0) == 0);
    struct channel channel = {.token = sg_token(&graph, 0), .exec_fd = 10, .ready_fd = -1};
    simulated_ms = 2999; read_mode = 1;
    assert(inspect_channel(&graph, &channel) == 0);
    assert(simulated_ms == 4000 && graph.services[0].phase == SG_RETIRING);
    assert(sg_reaped(&graph, 42, 1, simulated_ms) == 0 && graph.services[0].phase == SG_WAIT);
    reset();
    assert(sg_init(&graph, &spec, 1) == 0);
    action = sg_next(&graph, 1000);
    struct channel channels[SG_CAPACITY];
    for (unsigned i = 0; i < SG_CAPACITY; ++i) channels[i] = (struct channel){.exec_fd = -1, .ready_fd = -1};
    simulated_ms = 1000; fork_delay = 400;
    assert(launch(&graph, channels, action) == 0 && graph.services[0].launched_ms == 1400);
    read_mode = 2;
    assert(inspect_channel(&graph, &channels[0]) == 0 && graph.services[0].phase == SG_STARTING);
    reset();
    configuration_input = "OK_SERVICE_MANIFEST 1\nservice configured simple /bin/configured -\n";
    configuration_size = strlen(configuration_input);
    assert(service_manager_entry() == 0 && fork_calls == 1 && readiness_logged && config_closes == 1 && directory_closes == 1);
    const char *invalid[] = {"bad\n", "OK_SERVICE_MANIFEST 1\nservice a simple /a b\nservice b simple /b a\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a - extra\n", "OK_SERVICE_MANIFEST 1\nservice a simple /a unknown\n"};
    for (size_t index = 0; index < sizeof(invalid) / sizeof(invalid[0]); ++index) {
        reset(); configuration_input = invalid[index]; configuration_size = strlen(configuration_input);
        assert(service_manager_entry() == 13 && fork_calls == 0 && config_closes == 1 && directory_closes == 1);
    }
    reset(); configuration_input = "OK_SERVICE_MANIFEST 1\nservice a simple /a -\n\0";
    configuration_size = strlen(configuration_input) + 1;
    assert(service_manager_entry() == 13 && fork_calls == 0);
    for (unsigned index = 0; index < 4; ++index) {
        reset(); configuration_input = "bad\n"; configuration_size = 4;
        if (index == 0) configuration_uid = 1000;
        if (index == 1) configuration_mode |= 0020;
        if (index == 2) configuration_mode = S_IFIFO | 0644;
        if (index == 3) configuration_size = SM_BYTE_LIMIT + 1;
        assert(service_manager_entry() == 13 && fork_calls == 0 && config_closes == 1 && directory_closes == 1);
    }
    puts("SERVICE_MANAGER_ACTOR_CLOCK_HOSTED_PASS");
    return 0;
}
