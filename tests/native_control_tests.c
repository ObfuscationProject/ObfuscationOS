#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <ok/socket.h>
#include <ok/syscall.h>
#include <ok/power.h>

/* Deterministic syscall boundaries around the actual native server/client.
 * This is hosted protocol/actor evidence, not native socket execution. */
struct endpoint {
    const char *input; size_t size, read, chunk;
    char output[4096]; size_t written, send_chunk;
    int recv_again, recv_interrupt, send_again, send_interrupt, recv_flags, recv_error, send_error, closed;
    struct ok_ucred peer;
};
static struct endpoint ends[32];
static int accepts[8], accept_at, accept_count, socket_fd, socket_error, bind_error, listen_error, peer_error, peer_short;
static int pid, uid, run_mode, run_uid, existing, stat_error, mask, masks[8], mask_count, restore_error;
static unsigned accept_calls, send_calls, recv_calls, socket_calls, connect_calls, close_calls;
static int connect_again, clock_error, clock_backwards;
static uint64_t milliseconds;
static unsigned power_prepares, power_commits;
static unsigned power_prepare_advance_ms;
static int power_prepare_error, power_commit_error, power_token;
static uint32_t power_committed_token, power_prepared_action;

int ok_power_prepare(uint32_t action)
{
    assert(action == OK_POWER_HALT || action == OK_POWER_REBOOT || action == OK_POWER_POWEROFF);
    power_prepared_action = action; ++power_prepares;
    milliseconds += power_prepare_advance_ms;
    if (power_prepare_error) { errno = power_prepare_error; return -1; }
    return power_token;
}
int ok_power_commit(uint32_t token)
{
    ++power_commits; power_committed_token = token;
    if (power_commit_error) { errno = power_commit_error; return -1; }
    return 0;
}

int ok_socket(int domain, int type, int protocol)
{
    ++socket_calls; assert(domain == OK_AF_UNIX && type == (OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC) && !protocol);
    if (socket_error) { errno = socket_error; return -1; } return socket_fd;
}
int ok_bind(int fd, const struct ok_sockaddr_un *address, ok_socklen_t length)
{
    assert(fd == socket_fd && address->family == OK_AF_UNIX && !strcmp(address->path, "/run/init.sock"));
    assert(length == 2 + sizeof("/run/init.sock") && mask == 0111);
    if (bind_error) { errno = bind_error; return -1; } return 0;
}
int ok_listen(int fd, int backlog)
{ assert(fd == socket_fd && backlog == 2); if (listen_error) { errno = listen_error; return -1; } return 0; }
int ok_accept4(int fd, struct ok_sockaddr_un *address, ok_socklen_t *length, int flags)
{
    ++accept_calls; assert(fd == socket_fd && !address && !length && flags == (OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC));
    if (accept_at == accept_count) { errno = EAGAIN; return -1; } return accepts[accept_at++];
}
int ok_connect(int fd, const struct ok_sockaddr_un *address, ok_socklen_t length)
{
    ++connect_calls; assert(fd == socket_fd && address->family == OK_AF_UNIX &&
        !strcmp(address->path, "/run/init.sock") && length == 2 + sizeof("/run/init.sock"));
    if (connect_again) { --connect_again; errno = EAGAIN; return -1; } return 0;
}
int ok_getsockopt(int fd, int level, int option, void *out, ok_socklen_t *length)
{
    assert(fd >= 3 && fd < 32 && level == OK_SOL_SOCKET && option == OK_SO_PEERCRED && *length == sizeof(struct ok_ucred));
    if (peer_error) { errno = peer_error; return -1; }
    memcpy(out, &ends[fd].peer, sizeof(struct ok_ucred)); if (peer_short) --*length; return 0;
}
ssize_t ok_recvmsg(int fd, struct ok_msghdr *message, int flags)
{
    ++recv_calls; assert(fd >= 3 && fd < 32 && flags == OK_MSG_DONTWAIT && !message->control && !message->control_length);
    assert(message->vector_count == 1 && !message->name);
    struct endpoint *end = &ends[fd]; struct ok_iovec *vector = (void *)message->vectors;
    if (end->recv_interrupt) { --end->recv_interrupt; errno = EINTR; return -1; }
    if (end->recv_again) { if (end->recv_again > 0) --end->recv_again; errno = EAGAIN; return -1; }
    if (end->recv_error) { errno = end->recv_error; return -1; }
    size_t count = end->size - end->read;
    if (count > vector->length) count = vector->length;
    if (end->chunk && count > end->chunk) count = end->chunk;
    if (count) memcpy((void *)vector->base, end->input + end->read, count);
    end->read += count; message->flags = end->recv_flags; return (ssize_t)count;
}
ssize_t ok_sendmsg(int fd, const struct ok_msghdr *message, int flags)
{
    ++send_calls; assert(fd >= 3 && fd < 32 && flags == (OK_MSG_DONTWAIT | OK_MSG_NOSIGNAL));
    assert(message->vector_count == 1 && !message->control && !message->control_length);
    struct endpoint *end = &ends[fd]; const struct ok_iovec *vector = (void *)message->vectors;
    if (end->send_interrupt) { --end->send_interrupt; errno = EINTR; return -1; }
    if (end->send_again) { --end->send_again; errno = EAGAIN; return -1; }
    if (end->send_error) { errno = end->send_error; return -1; }
    size_t count = vector->length;
    if (end->send_chunk && count > end->send_chunk) count = end->send_chunk;
    assert(count <= sizeof(end->output) - end->written);
    memcpy(end->output + end->written, (void *)vector->base, count); end->written += count; return (ssize_t)count;
}
long ok_syscall1(long number, long argument)
{
    assert(number == OK_SYS_UMASK && mask_count < 8); masks[mask_count++] = (int)argument;
    if (restore_error && mask_count == 2) return -EIO;
    int previous = mask; mask = (int)argument; return previous;
}
long ok_syscall_ret(long result) { if (result < 0) { errno = (int)-result; return -1; } return result; }
static int fake_close(int fd) { assert(fd >= 3 && fd < 32); ++ends[fd].closed; ++close_calls; return 0; }
static pid_t fake_pid(void) { return pid; }
static uid_t fake_uid(void) { return (uid_t)uid; }
static int fake_stat(const char *path, struct stat *out)
{
    if (stat_error) { errno = stat_error; return -1; }
    memset(out, 0, sizeof(*out));
    if (!strcmp(path, "/run")) { out->st_mode = (mode_t)run_mode; out->st_uid = (uid_t)run_uid; return 0; }
    assert(!strcmp(path, "/run/init.sock"));
    if (existing) { out->st_mode = S_IFLNK | 0777; return 0; } errno = ENOENT; return -1;
}
static int fake_clock(clockid_t id, struct timespec *out)
{
    assert(id == CLOCK_MONOTONIC);
    if (clock_error) { errno = clock_error; return -1; }
    uint64_t now = milliseconds; if (clock_backwards && now) --milliseconds;
    out->tv_sec = (time_t)(now / 1000); out->tv_nsec = (long)(now % 1000) * 1000000; return 0;
}
static int fake_sleep(const struct timespec *pause, struct timespec *remaining)
{ assert(pause->tv_nsec == 10000000 && !remaining); milliseconds += 10; return 0; }

#define close fake_close
#define getpid fake_pid
#define geteuid fake_uid
#define lstat fake_stat
#define clock_gettime fake_clock
#define nanosleep fake_sleep
#include "../apps/init/native_control.c"
#include "../apps/init/native_control_client.c"
#undef close
#undef getpid
#undef geteuid
#undef lstat
#undef clock_gettime
#undef nanosleep

static struct nc_lifecycle lifecycle;
#define nc_step(control, graph, now) nc_step((control), (graph), &lifecycle, (now))

static void reset(void)
{
    lifecycle = (struct nc_lifecycle){0};
    memset(ends, 0, sizeof(ends)); memset(accepts, 0, sizeof(accepts));
    accept_at = accept_count = 0; socket_fd = 3; socket_error = bind_error = listen_error = peer_error = peer_short = 0;
    pid = 1; uid = 0; run_mode = S_IFDIR | 0755; run_uid = existing = stat_error = 0;
    mask = 0022; mask_count = restore_error = 0;
    accept_calls = send_calls = recv_calls = socket_calls = connect_calls = close_calls = 0;
    connect_again = clock_error = clock_backwards = 0; milliseconds = 1000;
    power_prepares = power_commits = 0; power_prepare_error = power_commit_error = 0;
    power_prepare_advance_ms = 0;
    power_token = 0x2abc1234; power_committed_token = power_prepared_action = 0;
    for (unsigned i = 0; i < 32; ++i) ends[i].peer = (struct ok_ucred){1, 0, 0};
}
static struct service_graph graph_ready(void)
{
    struct service_graph graph;
    const struct sg_spec specs[] = {{"provider", "/bin/provider", 0, SG_SIMPLE}, {"dependent", "/bin/dependent", 1, SG_SIMPLE}};
    assert(!sg_init(&graph, specs, 2));
    for (int i = 0; i < 2; ++i) {
        struct sg_action action = sg_next(&graph, 1000); assert(action.kind == SG_LAUNCH && action.token.index == (unsigned)i);
        assert(!sg_launched(&graph, action.token, 10 + i, 1000)); assert(!sg_exec(&graph, sg_token(&graph, (unsigned)i), 1, 1000));
    }
    return graph;
}
static void dispatch(struct service_graph *graph, unsigned caller, const char *request, struct nc_buffer *reply)
{ nc_dispatch(graph, &lifecycle, caller, request, strlen(request), 1000, reply); assert(nc_response(reply->bytes, reply->size) >= 0); }
static void protocol_policy(void)
{
    struct service_graph graph = graph_ready(), before = graph; struct nc_buffer reply;
    const char *bad[] = {"STATUS\n", NC_PREFIX "STATUS\r\n", NC_PREFIX "STATUS \n", NC_PREFIX "RESTART\n",
        NC_PREFIX "RESTART provider x\n", NC_PREFIX "STATUS\n\n", NC_PREFIX "STATUS\nRESTART provider\n",
        NC_PREFIX "STATUS provider!\n", "OK_INIT_CONTROL 2 STATUS\n", NC_PREFIX "STATUS"};
    for (unsigned i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) {
        dispatch(&graph, 0, bad[i], &reply); assert(nc_response(reply.bytes, reply.size) == 1); assert(!memcmp(&graph, &before, sizeof(graph)));
    }
    const char nul[] = NC_PREFIX "STATUS\0\n"; assert(nc_parse(nul, sizeof(nul) - 1).operation == NC_INVALID);
    dispatch(&graph, 1000, NC_PREFIX "STATUS\n", &reply);
    struct nc_status row; assert(!nc_snapshot(&reply, "provider", &row) && row.pid == 10 && row.generation == 1 && !strcmp(row.phase, "ready"));
    assert(!memcmp(&graph, &before, sizeof(graph)));
    dispatch(&graph, 1000, NC_PREFIX "RESTART provider\n", &reply); assert(nc_response(reply.bytes, reply.size) == 1);
    assert(!memcmp(&graph, &before, sizeof(graph)));
    dispatch(&graph, 0, NC_PREFIX "RESTART absent\n", &reply); assert(nc_response(reply.bytes, reply.size) == 1);
    assert(!memcmp(&graph, &before, sizeof(graph)));
    dispatch(&graph, 0, NC_PREFIX "RESTART provider\n", &reply); assert(!nc_response(reply.bytes, reply.size));
    assert(graph.services[0].phase == SG_RETIRING && graph.services[1].phase == SG_RETIRING);
    assert(graph.services[0].generation == 1 && graph.services[0].pid == 10);
    before = graph; dispatch(&graph, 0, NC_PREFIX "RESTART provider\n", &reply); assert(nc_response(reply.bytes, reply.size) == 1);
    assert(!memcmp(&before, &graph, sizeof(graph)));
    struct sg_action action = sg_next(&graph, 1000); assert(action.kind == SG_TERM && action.token.pid == 11);
    assert(!sg_signaled(&graph, action, 1000)); action = sg_next(&graph, 1000 + PID1_STOP_TERM_MS);
    assert(action.kind == SG_KILL && action.token.pid == 11); assert(!sg_signaled(&graph, action, 1000 + PID1_STOP_TERM_MS));
    assert(sg_reaped(&graph, 11, 0, 1001 + PID1_STOP_TERM_MS) == 1);
    action = sg_next(&graph, 1001 + PID1_STOP_TERM_MS); assert(action.kind == SG_TERM && action.token.pid == 10);
    assert(!sg_signaled(&graph, action, 1001 + PID1_STOP_TERM_MS));
    assert(sg_reaped(&graph, 10, 0, 1002 + PID1_STOP_TERM_MS) == 0);
    uint64_t next = graph.services[0].next_ms; assert(next > 1002 + PID1_STOP_TERM_MS);
    assert(sg_next(&graph, next - 1).kind == SG_NONE); action = sg_next(&graph, next);
    assert(action.kind == SG_LAUNCH && action.token.index == 0 && action.token.generation == 2);
    assert(!sg_launched(&graph, action.token, 12, next)); assert(!sg_exec(&graph, sg_token(&graph, 0), 1, next));
    action = sg_next(&graph, next); assert(action.kind == SG_LAUNCH && action.token.index == 1 && action.token.generation == 2);
    assert(!sg_launched(&graph, action.token, 13, next)); assert(!sg_exec(&graph, sg_token(&graph, 1), 1, next));
    dispatch(&graph, 1000, NC_PREFIX "STATUS dependent\n", &reply);
    assert(!nc_snapshot(&reply, "dependent", &row) && row.pid == 13 && row.generation == 2);
    graph.services[0].pid = 0; graph.specs[0].mode = SG_ONESHOT;
    dispatch(&graph, 0, NC_PREFIX "RESTART provider\n", &reply);
    assert(!nc_response(reply.bytes, reply.size) && graph.services[0].phase == SG_WAIT && graph.services[0].next_ms == 1000);
    const char *bad_replies[] = {NC_PREFIX "STATUS\nEND\n", NC_PREFIX "ERROR code=denied\nEND\nextra",
        NC_PREFIX "ACCEPTED service=provider pid=x generation=1\nEND\n", NC_PREFIX "ERROR code=denied\nEND\nEND\n",
        NC_PREFIX "STATUS\nSERVICE service=p pid=2 generation=18446744073709551616 phase=ready mode=simple next_ms=0 launches=1\nEND\n"};
    for (unsigned i = 0; i < sizeof(bad_replies) / sizeof(bad_replies[0]); ++i) assert(nc_response(bad_replies[i], strlen(bad_replies[i])) == -1);
}
static void server_open(void)
{
    struct native_control control;
    reset(); nc_reset(&control); assert(!nc_open(&control)); assert(control.listener == 3 && mask == 0022 && mask_count == 2);
    assert(nc_open(&control) < 0 && errno == EBUSY); assert(!nc_close(&control) && ends[3].closed == 1);
    for (unsigned test = 0; test < 8; ++test) {
        reset(); nc_reset(&control);
        if (test == 0) pid = 9;
        if (test == 1) uid = 1000;
        if (test == 2) run_mode |= 0002;
        if (test == 3) run_uid = 1000;
        if (test == 4) existing = 1;
        if (test == 5) stat_error = EIO;
        if (test == 6) run_mode = S_IFLNK | 0755;
        if (test == 7) run_mode = S_IFREG | 0755;
        assert(nc_open(&control) < 0 && !socket_calls && !mask_count && control.listener == -1);
    }
    reset(); nc_reset(&control); bind_error = EADDRINUSE;
    assert(nc_open(&control) < 0 && errno == EADDRINUSE && mask == 0022 && mask_count == 2 && ends[3].closed == 1);
    reset(); nc_reset(&control); listen_error = EIO;
    assert(nc_open(&control) < 0 && mask == 0022 && ends[3].closed == 1);
    reset(); nc_reset(&control); restore_error = 1;
    assert(nc_open(&control) < 0 && errno == EIO && mask_count == 2 && ends[3].closed == 1);
}
static void queue(int fd, const char *request)
{ accepts[accept_count++] = fd; ends[fd].input = request; ends[fd].size = strlen(request); ends[fd].peer.pid = 25; }
static void server_transport(void)
{
    struct native_control control; struct service_graph graph;
    reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control));
    queue(4, NC_PREFIX "STATUS\n"); ends[4].chunk = 2; ends[4].send_chunk = 3;
    ends[4].recv_interrupt = ends[4].recv_again = ends[4].send_interrupt = ends[4].send_again = 1;
    for (unsigned step = 0; step < 200 && !ends[4].closed; ++step) assert(!nc_step(&control, &graph, 1000 + step));
    assert(ends[4].closed == 1 && !nc_response(ends[4].output, ends[4].written));
    assert(graph.services[0].phase == SG_READY);
    assert(!nc_close(&control));
    reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control));
    queue(4, NC_PREFIX "RESTART provider\n"); ends[4].peer.uid = 1000;
    assert(!nc_step(&control, &graph, 1000)); assert(nc_response(ends[4].output, ends[4].written) == 1 && graph.services[0].phase == SG_READY);
    reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control));
    queue(4, NC_PREFIX "STATUS\n"); queue(5, NC_PREFIX "STATUS\n"); queue(6, NC_PREFIX "STATUS\n");
    ends[4].recv_again = ends[5].recv_again = -1;
    assert(!nc_step(&control, &graph, 1000) && accept_calls == 2 && accept_at == 2);
    assert(!nc_step(&control, &graph, 1999) && accept_calls == 2 && !ends[4].closed);
    assert(!nc_step(&control, &graph, 2000) && ends[4].closed && ends[5].closed && accept_at == 3);
    assert(!nc_close(&control));
    for (unsigned test = 0; test < 5; ++test) {
        reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control)); queue(4, NC_PREFIX "STATUS\n");
        if (test == 0) peer_error = EIO;
        if (test == 1) peer_short = 1;
        if (test == 2) ends[4].peer.pid = 0;
        if (test == 3) ends[4].recv_flags = OK_MSG_CTRUNC;
        if (test == 4) ends[4].size = 0;
        assert(!nc_step(&control, &graph, 1000) && ends[4].closed);
        if (test != 3) assert(!ends[4].written); else assert(nc_response(ends[4].output, ends[4].written) == 1);
        assert(graph.services[0].phase == SG_READY); assert(!nc_close(&control));
    }
    char overflow[NC_REQUEST_BYTES]; memset(overflow, 'x', sizeof(overflow));
    reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control)); queue(4, "");
    ends[4].input = overflow; ends[4].size = sizeof(overflow);
    assert(!nc_step(&control, &graph, 1000) && ends[4].closed && nc_response(ends[4].output, ends[4].written) == 1);
    reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control)); queue(4, NC_PREFIX "STATUS\n");
    ends[4].send_error = EPIPE; assert(!nc_step(&control, &graph, 1000) && ends[4].closed);
}
static const char success[] = NC_PREFIX "STATUS\nSERVICE service=provider pid=10 generation=1 phase=ready mode=simple next_ms=0 launches=1\nEND\n";
static char cli_output[4096];
static size_t cli_size;
static unsigned cli_errors;
static ssize_t cli_write(int fd, const void *bytes, size_t size)
{
    assert(fd == STDOUT_FILENO || fd == STDERR_FILENO);
    if (size > 3) size = 3;
    assert(size <= sizeof(cli_output) - cli_size);
    memcpy(cli_output + cli_size, bytes, size); cli_size += size; return (ssize_t)size;
}
static void cli_perror(const char *message) { assert(!strcmp(message, "service-ctl")); ++cli_errors; }
#define main control_cli_main
#define write cli_write
#define perror cli_perror
#include "../apps/service-ctl/main.c"
#undef main
#undef write
#undef perror
static void cli_controls(void)
{
    char *status[] = {"service-ctl", "status", "provider", 0};
    char *restart[] = {"service-ctl", "restart", "provider", 0};
    char *invalid[] = {"service-ctl", "restart", "provider;bad", 0};
    reset(); cli_size = cli_errors = 0; ends[3].input = success; ends[3].size = sizeof(success) - 1;
    assert(!control_cli_main(3, status)); assert(cli_size == sizeof(success) - 1 && !memcmp(cli_output, success, cli_size));
    reset(); cli_size = cli_errors = 0; ends[3].input = NC_PREFIX "ERROR code=denied\nEND\n"; ends[3].size = strlen(ends[3].input);
    assert(control_cli_main(3, restart) == 1 && cli_size == ends[3].size && !cli_errors);
    reset(); cli_size = cli_errors = 0; assert(control_cli_main(3, invalid) == 2 && !socket_calls && cli_size);
    reset(); cli_size = cli_errors = 0; ends[3].peer.uid = 1000;
    assert(control_cli_main(3, status) == 1 && cli_errors == 1 && !cli_size && !send_calls);
}
static void client_transport(void)
{
    struct nc_buffer reply;
    reset(); ends[3].input = success; ends[3].size = sizeof(success) - 1; ends[3].chunk = 2; ends[3].send_chunk = 3;
    ends[3].recv_interrupt = ends[3].recv_again = ends[3].send_interrupt = ends[3].send_again = 1; connect_again = 2;
    assert(!nc_exchange(NC_PREFIX "STATUS\n", sizeof(NC_PREFIX "STATUS\n") - 1, &reply));
    assert(ends[3].closed == 1 && !nc_response(reply.bytes, reply.size));
    assert(ends[3].written == sizeof(NC_PREFIX "STATUS\n") - 1 && !memcmp(ends[3].output, NC_PREFIX "STATUS\n", ends[3].written));
    for (unsigned test = 0; test < 4; ++test) {
        reset(); if (test == 0) ends[3].peer.pid = 2; if (test == 1) ends[3].peer.uid = 1000;
        if (test == 2) peer_short = 1;
        if (test == 3) peer_error = EIO;
        assert(nc_exchange(NC_PREFIX "RESTART provider\n", sizeof(NC_PREFIX "RESTART provider\n") - 1, &reply) < 0);
        assert(!send_calls && !recv_calls && ends[3].closed == 1);
    }
    reset(); ends[3].recv_again = -1;
    assert(nc_exchange(NC_PREFIX "STATUS\n", sizeof(NC_PREFIX "STATUS\n") - 1, &reply) < 0 && errno == EAGAIN);
    assert(milliseconds == 2000 && ends[3].closed == 1);
    for (unsigned test = 0; test < 5; ++test) {
        reset(); ends[3].input = success; ends[3].size = sizeof(success) - 1;
        if (test == 0) --ends[3].size;
        if (test == 1) ends[3].recv_flags = OK_MSG_CTRUNC;
        if (test == 2) ends[3].send_error = EPIPE;
        if (test == 3) { ends[3].input = NC_PREFIX "STATUS\nEND\n"; ends[3].size = strlen(ends[3].input); }
        if (test == 4) clock_backwards = 1;
        assert(nc_exchange(NC_PREFIX "STATUS\n", sizeof(NC_PREFIX "STATUS\n") - 1, &reply) < 0 && ends[3].closed == 1);
    }
    reset(); ends[3].input = NC_PREFIX "ERROR code=denied\nEND\n"; ends[3].size = strlen(ends[3].input);
    assert(nc_exchange(NC_PREFIX "RESTART provider\n", sizeof(NC_PREFIX "RESTART provider\n") - 1, &reply) == 1);
    reset(); ends[3].input = success; ends[3].size = sizeof(success) - 1;
    assert(nc_exchange(NC_PREFIX "RESTART provider\n", sizeof(NC_PREFIX "RESTART provider\n") - 1, &reply) < 0);
    reset(); ends[3].input = NC_PREFIX "ACCEPTED service=other pid=10 generation=1\nEND\n"; ends[3].size = strlen(ends[3].input);
    assert(nc_exchange(NC_PREFIX "RESTART provider\n", sizeof(NC_PREFIX "RESTART provider\n") - 1, &reply) < 0);
    reset(); ends[3].input = success; ends[3].size = sizeof(success) - 1;
    assert(nc_exchange(NC_PREFIX "STATUS other\n", sizeof(NC_PREFIX "STATUS other\n") - 1, &reply) < 0);
    reset(); assert(nc_exchange("bad", 3, &reply) < 0 && !socket_calls);
}
#ifndef NATIVE_CONTROL_TEST_ENTRY
#define NATIVE_CONTROL_TEST_ENTRY main
#endif
int NATIVE_CONTROL_TEST_ENTRY(void)
{
    protocol_policy(); server_open(); server_transport(); client_transport(); cli_controls();
    puts("native control hosted protocol, retirement, auth and bounded transport controls passed"); return 0;
}
