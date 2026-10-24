#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <poll.h>
#include <ok/socket.h>
#include <ok/syscall.h>
#include "../apps/time/time_service.h"

/* Actual product sources, with deterministic syscall seams. These tests do
 * not execute a native kernel or qualify an RTC, storage or UTC source. */
static int calls, fail_at, injected, descriptors[32], held;
static int root_bad, run_bad, launch_uid, launch_gid, process_pid;
static int socket_exists, socket_kind, socket_mode, socket_uid, socket_gid, socket_links, socket_inode, socket_swap;
static int connect_error, bind_error, listen_error, mask_value, unlinks, accepted, accept_available;
static int peer_uid, peer_gid, peer_pid, peer_short, peer_error;
static int recv_again, recv_interrupt, peek_interrupt, recv_flags, recv_control, recv_oversize, recv_eof;
static int send_again, send_interrupt, send_error, send_oversize, send_zero;
static int clock_failure, clock_backwards, clock_overflow, monotonic_bad, realtime_error, realtime_bad;
static int setter_error, setter_calls, setter_backwards;
static int notify_bytes, notify_closed, notify_interrupt, notify_zero;
static size_t input_size, read_at, recv_chunk, send_chunk, output_size;
static char input[700], output[700];
static uint64_t milliseconds, clock_step, receive_delay, receive_delay_each, send_delay, send_delay_each, eof_delay, setter_delay;
static int64_t realtime_seconds;
static uint32_t realtime_nanoseconds;

static int event(void)
{
    ++calls;
    if (calls == fail_at) { injected = 1; errno = EIO; return -1; }
    return 0;
}
static void advance(uint64_t delay) { assert(milliseconds <= UINT64_MAX - delay); milliseconds += delay; }
static int acquire(int fd) { assert(!descriptors[fd]); descriptors[fd] = 1; ++held; return fd; }
static int t_open(const char *name, int flags, ...)
{
    assert(!strcmp(name, "/") && flags == (O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
    return event() < 0 ? -1 : acquire(10);
}
static int t_openat(int fd, const char *name, int flags, ...)
{
    assert(fd == 10 && !strcmp(name, "run") && flags == (O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
    return event() < 0 ? -1 : acquire(11);
}
static int t_close(int fd)
{
    assert(fd >= 0 && fd < 32 && descriptors[fd]);
    descriptors[fd] = 0; --held;
    if (fd == 30) ++notify_closed;
    return event();
}
static int t_fstat(int fd, struct stat *value)
{
    assert(fd == 10 || fd == 11);
    if (event() < 0) return -1;
    memset(value, 0, sizeof(*value)); value->st_mode = S_IFDIR | 0755;
    int bad = fd == 10 ? root_bad : run_bad;
    if (bad == 1) value->st_mode |= 0020;
    if (bad == 2) value->st_uid = 1000;
    if (bad == 3) value->st_mode = S_IFLNK | 0755;
    if (bad == 4) value->st_mode |= 02000;
    if (bad == 5) value->st_gid = 1000;
    return 0;
}
static int t_fstatat(int fd, const char *name, struct stat *value, int flags)
{
    assert(fd == 11 && !strcmp(name, TS_NAME) && flags == AT_SYMLINK_NOFOLLOW);
    if (event() < 0) return -1;
    if (!socket_exists) { errno = ENOENT; return -1; }
    memset(value, 0, sizeof(*value));
    value->st_mode = (mode_t)(socket_kind | socket_mode);
    value->st_uid = (unsigned)socket_uid; value->st_gid = (unsigned)socket_gid;
    value->st_nlink = (unsigned)socket_links; value->st_ino = (ino_t)socket_inode;
    if (socket_swap) { ++socket_inode; socket_swap = 0; }
    return 0;
}
static int t_unlinkat(int fd, const char *name, int flags)
{
    assert(fd == 11 && !strcmp(name, TS_NAME) && !flags);
    if (event() < 0) return -1;
    socket_exists = 0; ++unlinks; return 0;
}
int ok_socket(int domain, int type, int protocol)
{
    assert(domain == OK_AF_UNIX && type == (OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC) && !protocol);
    return event() < 0 ? -1 : acquire(24);
}
static void check_address(int fd, const struct ok_sockaddr_un *address, ok_socklen_t size)
{ assert(fd == 24 && address->family == OK_AF_UNIX && !strcmp(address->path, TS_PATH) && size == 2 + sizeof(TS_PATH)); }
int ok_bind(int fd, const struct ok_sockaddr_un *address, ok_socklen_t size)
{
    check_address(fd, address, size); assert(mask_value == 0111);
    if (event() < 0) return -1;
    if (bind_error) { errno = bind_error; return -1; }
    assert(!socket_exists); socket_exists = 1; return 0;
}
int ok_connect(int fd, const struct ok_sockaddr_un *address, ok_socklen_t size)
{
    check_address(fd, address, size);
    if (event() < 0) return -1;
    if (connect_error) { errno = connect_error; return -1; }
    return 0;
}
int ok_listen(int fd, int backlog)
{
    assert(fd == 24 && backlog == 1);
    if (event() < 0) return -1;
    if (listen_error) { errno = listen_error; return -1; }
    return 0;
}
int ok_accept4(int fd, struct ok_sockaddr_un *address, ok_socklen_t *size, int flags)
{
    assert(fd == 24 && !address && !size && flags == (OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC));
    if (event() < 0) return -1;
    if (!accept_available) { errno = EAGAIN; return -1; }
    --accept_available; ++accepted; return acquire(25);
}
int ok_getsockopt(int fd, int level, int option, void *value, ok_socklen_t *size)
{
    assert((fd == 24 || fd == 25) && level == OK_SOL_SOCKET && option == OK_SO_PEERCRED && *size == sizeof(struct ok_ucred));
    if (event() < 0) return -1;
    if (peer_error) { errno = peer_error; return -1; }
    struct ok_ucred peer = {.pid = peer_pid, .uid = (unsigned)peer_uid, .gid = (unsigned)peer_gid};
    memcpy(value, &peer, sizeof(peer));
    if (peer_short) --*size;
    return 0;
}
ssize_t ok_recvmsg(int fd, struct ok_msghdr *message, int flags)
{
    assert((fd == 24 || fd == 25) && (flags & OK_MSG_DONTWAIT) && !(flags & ~(OK_MSG_DONTWAIT | OK_MSG_PEEK)));
    assert(!message->control && !message->control_length && !message->name && message->vector_count == 1);
    struct ok_iovec *vector = (void *)message->vectors;
    if (event() < 0) return -1;
    if ((flags & OK_MSG_PEEK) && peek_interrupt) { --peek_interrupt; errno = EINTR; return -1; }
    if (recv_interrupt) { --recv_interrupt; errno = EINTR; return -1; }
    if (recv_again) { --recv_again; errno = EAGAIN; return -1; }
    message->flags = (unsigned)recv_flags; message->control_length = (unsigned)recv_control;
    if (recv_oversize) return (ssize_t)vector->length + 1;
    size_t size = input_size - read_at;
    if (size > vector->length) size = vector->length;
    if (recv_chunk && size > recv_chunk) size = recv_chunk;
    if (!size && !recv_eof) { errno = EAGAIN; return -1; }
    memcpy((void *)vector->base, input + read_at, size);
    if (!(flags & OK_MSG_PEEK)) {
        read_at += size; advance(receive_delay + receive_delay_each); receive_delay = 0;
        if (!size) { advance(eof_delay); eof_delay = 0; }
    }
    return (ssize_t)size;
}
ssize_t ok_sendmsg(int fd, const struct ok_msghdr *message, int flags)
{
    assert((fd == 24 || fd == 25) && flags == (OK_MSG_DONTWAIT | OK_MSG_NOSIGNAL));
    assert(!message->control && !message->control_length && message->vector_count == 1);
    if (event() < 0) return -1;
    if (send_interrupt) { --send_interrupt; errno = EINTR; return -1; }
    if (send_again) { --send_again; errno = EAGAIN; return -1; }
    if (send_error) { errno = send_error; return -1; }
    struct ok_iovec *vector = (void *)message->vectors;
    if (send_oversize) return (ssize_t)vector->length + 1;
    if (send_zero) return 0;
    advance(send_delay + send_delay_each); send_delay = 0;
    size_t size = vector->length;
    if (send_chunk && size > send_chunk) size = send_chunk;
    assert(output_size + size <= sizeof(output));
    memcpy(output + output_size, (const void *)vector->base, size); output_size += size;
    return (ssize_t)size;
}
long ok_syscall1(long number, long argument)
{
    assert(number == OK_SYS_UMASK);
    if (event() < 0) return -EIO;
    int old = mask_value; mask_value = (int)argument; return old;
}
long ok_syscall_ret(long result) { if (result < 0) { errno = (int)-result; return -1; } return result; }
static uid_t t_uid(void) { return (uid_t)launch_uid; }
static gid_t t_gid(void) { return (gid_t)launch_gid; }
static pid_t t_pid(void) { return process_pid; }
static int t_clock(clockid_t id, struct timespec *value)
{
    if (event() < 0) return -1;
    if (id == CLOCK_REALTIME) {
        if (realtime_error) { errno = realtime_error; return -1; }
        value->tv_sec = realtime_seconds;
        value->tv_nsec = realtime_bad ? 1000000000 : realtime_nanoseconds;
        return 0;
    }
    assert(id == CLOCK_MONOTONIC);
    if (clock_failure) { errno = clock_failure; return -1; }
    uint64_t now = milliseconds;
    if (clock_backwards) { assert(now >= 2); now -= 2; }
    value->tv_sec = clock_overflow ? INT64_MAX : (time_t)(now / 1000);
    value->tv_nsec = monotonic_bad ? 1000000000 : (long)(now % 1000) * 1000000;
    advance(clock_step);
    return 0;
}
static int t_set(clockid_t id, const struct timespec *value)
{
    assert(id == CLOCK_REALTIME); ++setter_calls;
    if (setter_error) { errno = setter_error; return -1; }
    realtime_seconds = value->tv_sec; realtime_nanoseconds = (uint32_t)value->tv_nsec;
    advance(setter_delay); setter_delay = 0;
    if (setter_backwards) { assert(milliseconds >= 2); milliseconds -= 2; }
    return 0;
}
static int t_poll(struct pollfd *fds, nfds_t count, int timeout)
{ assert(count == 1 && fds->fd == 24 && timeout == 10); advance(10); return event(); }
static ssize_t t_write(int fd, const void *bytes, size_t size)
{
    assert(fd == 30 && size == 1 && *(const char *)bytes == 'R');
    if (event() < 0) return -1;
    if (notify_interrupt) { --notify_interrupt; errno = EINTR; return -1; }
    if (notify_zero) return 0;
    ++notify_bytes; return 1;
}
#define open t_open
#define openat t_openat
#define close t_close
#define fstat t_fstat
#define fstatat t_fstatat
#define unlinkat t_unlinkat
#define geteuid t_uid
#define getegid t_gid
#define getpid t_pid
#define clock_gettime t_clock
#define clock_settime t_set
#define poll t_poll
#define write t_write
#include "../apps/time/protocol.c"
#include "../apps/time/transport.c"
#undef open
#undef openat
#undef close
#undef fstat
#undef fstatat
#undef unlinkat
#undef geteuid
#undef getegid
#undef getpid
#undef clock_gettime
#undef clock_settime
#undef poll
#undef write

static void reset(void)
{
    assert(!held); memset(descriptors, 0, sizeof(descriptors));
    calls = fail_at = injected = root_bad = run_bad = launch_uid = launch_gid = 0;
    process_pid = 73;
    socket_exists = socket_uid = socket_gid = socket_swap = connect_error = bind_error = listen_error = unlinks = accepted = accept_available = 0;
    socket_kind = 0140000; socket_mode = 0666; socket_links = 1; socket_inode = 99; mask_value = 0022;
    peer_uid = peer_gid = peer_short = peer_error = 0; peer_pid = 73;
    recv_again = recv_interrupt = peek_interrupt = recv_flags = recv_control = recv_oversize = recv_eof = 0;
    send_again = send_interrupt = send_error = send_oversize = send_zero = 0;
    clock_failure = clock_backwards = clock_overflow = monotonic_bad = realtime_error = realtime_bad = 0;
    setter_error = setter_calls = setter_backwards = notify_bytes = notify_closed = notify_interrupt = notify_zero = 0;
    input_size = read_at = recv_chunk = send_chunk = output_size = 0;
    milliseconds = 100; clock_step = receive_delay = receive_delay_each = send_delay = send_delay_each = eof_delay = setter_delay = 0;
    realtime_seconds = 1700000000; realtime_nanoseconds = 123;
}
static void feed(const char *value) { input_size = strlen(value); assert(input_size <= sizeof(input)); memcpy(input, value, input_size); read_at = 0; }
static void start(struct ts_server *server, const char *request)
{ reset(); assert(!ts_server_open(server)); assert(mask_value == 0022); accept_available = 1; feed(request); }
static int step(struct ts_server *server, uint64_t now)
{ milliseconds = now; return ts_server_step(server, now); }
static void finish(struct ts_server *server) { fail_at = 0; assert(!ts_server_close(server)); assert(!held); }
static struct ts_reply response(void)
{ struct ts_reply reply; assert(!ts_reply_parse(output, output_size, &reply)); return reply; }

static void parser_tests(void)
{
    struct ts_request request;
    const char *valid[] = {"OKT1 STATUS\n", "OKT1 SET 0 0\n", "OKT1 SET 8277292035 999999999\n"};
    for (size_t i = 0; i < sizeof(valid) / sizeof(*valid); ++i) {
        size_t size = strlen(valid[i]);
        for (size_t cut = 0; cut < size; ++cut) assert(!ts_request_parse(valid[i], cut, &request));
        assert(ts_request_parse(valid[i], size, &request) == 1);
        struct ts_buffer frame; assert(!ts_request_encode(&request, &frame));
        assert(frame.size == size && !memcmp(frame.bytes, valid[i], size));
    }
    const char *bad[] = {"OKT1 STATUS\r\n", "OKT1 STATUS\nx", "OKT1 STATUS\nOKT1 STATUS\n", "OKT1 SET 01 0\n", "OKT1 SET -1 0\n", "OKT1 SET +1 0\n", "OKT1 SET 8277292036 0\n", "OKT1 SET 1 1000000000\n", "OKT1 SET 1 00\n", "OKT1 SET 1 0 \n", "OKT1 SET 18446744073709551616 0\n", "OKT2 STATUS\n"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) assert(ts_request_parse(bad[i], strlen(bad[i]), &request) < 0);
    char large[TS_REQUEST_BYTES + 1]; memset(large, 'A', sizeof(large));
    assert(ts_request_parse(large, TS_REQUEST_BYTES, &request) < 0);
    assert(ts_request_parse(large, sizeof(large), &request) < 0);
    assert(ts_request_parse("OKT1\0 STATUS\n", 13, &request) < 0);
    uint64_t value; assert(!ts_unsigned("18446744073709551615", 20, UINT64_MAX, &value) && value == UINT64_MAX);
    assert(ts_unsigned("18446744073709551616", 20, UINT64_MAX, &value) < 0);
    struct ts_reply original = {.operation = TS_STATUS, .pid = 73, .manual_updates = UINT64_MAX,
        .realtime_seconds = INT64_MIN, .realtime_nanoseconds = 999999999,
        .monotonic_seconds = INT64_MAX, .monotonic_nanoseconds = 999999999};
    struct ts_buffer encoded; struct ts_reply decoded;
    assert(!ts_reply_encode(&original, &encoded));
    for (size_t cut = 0; cut < encoded.size; ++cut) assert(ts_reply_parse(encoded.bytes, cut, &decoded) < 0);
    assert(!ts_reply_parse(encoded.bytes, encoded.size, &decoded) && decoded.realtime_seconds == INT64_MIN && decoded.manual_updates == UINT64_MAX);
    encoded.bytes[encoded.size++] = 'x'; assert(ts_reply_parse(encoded.bytes, encoded.size, &decoded) < 0);
    const char *bad_replies[] = {"OKT1 ERROR errno=0\nEND\n", "OKT1 ERROR errno=01\nEND\n", "OKT1 ERROR errno=4096\nEND\n", "OKT1 SET pid=73 manual_updates=0\nEND\n", "OKT1 SET pid=0 manual_updates=1\nEND\n", "OKT1 SET pid=73 manual_updates=1\r\nEND\n"};
    for (size_t i = 0; i < sizeof(bad_replies) / sizeof(*bad_replies); ++i) assert(ts_reply_parse(bad_replies[i], strlen(bad_replies[i]), &decoded) < 0);
}

static void dispatch_tests(void)
{
    reset(); struct ok_ucred peer = {.pid = 88, .uid = 1000, .gid = 1000};
    struct ts_request request = {.operation = TS_STATUS}; struct ts_reply reply; uint64_t updates = 0;
    ts_dispatch(&request, &peer, &updates, &reply);
    assert(reply.operation == TS_STATUS && reply.pid == 73 && reply.realtime_seconds == realtime_seconds && !updates);
    request = (struct ts_request){TS_SET, 1800000000, 999};
    ts_dispatch(&request, &peer, &updates, &reply); assert(reply.operation == TS_ERROR && reply.error == EPERM && !setter_calls && !updates);
    peer.uid = 0; peer.gid = 1000; setter_error = EINVAL;
    ts_dispatch(&request, &peer, &updates, &reply); assert(reply.error == EINVAL && setter_calls == 1 && !updates);
    setter_error = 0; ts_dispatch(&request, &peer, &updates, &reply);
    assert(reply.operation == TS_SET && reply.manual_updates == 1 && updates == 1 && setter_calls == 2 && realtime_seconds == 1800000000 && realtime_nanoseconds == 999);
    updates = UINT64_MAX; ts_dispatch(&request, &peer, &updates, &reply); assert(reply.error == EOVERFLOW && setter_calls == 2);
    updates = 0; process_pid = 1; ts_dispatch(&request, &peer, &updates, &reply); assert(reply.error == EIO && setter_calls == 2 && !updates); process_pid = 73;
    request.operation = TS_STATUS; realtime_error = EIO;
    ts_dispatch(&request, &peer, &updates, &reply); assert(reply.operation == TS_STATUS && reply.realtime_error == EIO && !reply.realtime_seconds && !reply.realtime_nanoseconds);
    realtime_error = 0; realtime_bad = 1; ts_dispatch(&request, &peer, &updates, &reply); assert(reply.realtime_error == EIO && !reply.realtime_seconds);
    realtime_bad = 0; realtime_seconds = INT64_MIN; ts_dispatch(&request, &peer, &updates, &reply); assert(reply.realtime_seconds == INT64_MIN);
    monotonic_bad = 1; ts_dispatch(&request, &peer, &updates, &reply); assert(reply.operation == TS_ERROR && reply.error == EIO);
    monotonic_bad = 0; clock_failure = EOVERFLOW; ts_dispatch(&request, &peer, &updates, &reply); assert(reply.error == EOVERFLOW);
}

static void server_tests(void)
{
    struct ts_server server;
    for (size_t chunk = 1; chunk <= 40; ++chunk) {
        start(&server, "OKT1 SET 1800000000 3\n"); recv_chunk = chunk; send_chunk = 1;
        recv_interrupt = recv_again = send_interrupt = send_again = 2; peek_interrupt = 1;
        uint64_t now;
        for (now = 101; now < 1000 && (!accepted || server.client.fd >= 0); ++now) assert(!step(&server, now));
        assert(accepted == 1 && setter_calls == 1 && server.manual_updates == 1 && response().operation == TS_SET);
        finish(&server);
    }
    start(&server, "OKT1 STATUS\n"); peer_uid = peer_gid = 1000; realtime_error = EIO;
    assert(!step(&server, 101) && !step(&server, 102));
    assert(response().operation == TS_STATUS && response().realtime_error == EIO && !setter_calls); finish(&server);
    start(&server, "OKT1 SET 1800000000 0\n"); peer_uid = 1000;
    assert(!step(&server, 101) && !step(&server, 102)); assert(response().error == EPERM && !setter_calls); finish(&server);
    for (unsigned kind = 0; kind < 9; ++kind) {
        start(&server, "OKT1 SET 1800000000 0\n");
        if (kind == 0) peer_pid = 0;
        if (kind == 1) peer_short = 1;
        if (kind == 2) peer_error = EIO;
        if (kind == 3) recv_flags = 1;
        if (kind == 4) recv_control = 1;
        if (kind == 5) recv_oversize = 1;
        if (kind == 6) input[input_size++] = 'x';
        if (kind == 7) { input[input_size++] = 'x'; recv_chunk = input_size - 1; }
        if (kind == 8) input[0] = 'x';
        assert(!step(&server, 101) && server.client.fd < 0 && !setter_calls && !output_size); finish(&server);
    }
    start(&server, "OKT1 SET 1800000000 0\n");
    assert(!step(&server, 101) && server.manual_updates == 1);
    input[input_size++] = 'x'; send_error = EPIPE;
    assert(!step(&server, 102) && server.client.fd < 0 && server.manual_updates == 1 && setter_calls == 1 && !output_size); finish(&server);
    /* A suffix arriving after commit is ignored, including another SET. */
    start(&server, "OKT1 SET 1800000000 0\n"); assert(!step(&server, 101));
    feed("OKT1 SET 1900000000 0\n"); assert(!step(&server, 102));
    assert(response().operation == TS_SET && setter_calls == 1 && realtime_seconds == 1800000000); finish(&server);
    start(&server, "OKT"); recv_eof = 1;
    assert(!step(&server, 101) && !step(&server, 102) && server.client.fd < 0 && !setter_calls); finish(&server);
    start(&server, "OKT1 SET 1800000000 0\n"); recv_chunk = 1;
    for (uint64_t now = 101; now < 1101; now += 100) assert(!step(&server, now) && server.client.deadline == 1101);
    assert(!step(&server, 1101) && server.client.fd < 0 && !setter_calls); finish(&server);
    const uint64_t delays[] = {999, 1000, 1001};
    for (size_t i = 0; i < sizeof(delays) / sizeof(*delays); ++i) {
        start(&server, "OKT1 SET 1800000000 0\n"); receive_delay = delays[i];
        assert(!step(&server, 101));
        assert(setter_calls == (delays[i] < TS_DEADLINE_MS));
        assert((server.client.fd >= 0) == (delays[i] < TS_DEADLINE_MS)); finish(&server);
        start(&server, "OKT1 SET 1800000000 0\n"); setter_delay = delays[i];
        assert(!step(&server, 101) && setter_calls == 1 && server.manual_updates == 1);
        assert((server.client.reply.size > 0) == (delays[i] < TS_DEADLINE_MS)); finish(&server);
    }
    start(&server, "OKT1 SET 1800000000 0\n"); send_chunk = 1;
    assert(!step(&server, 101));
    for (uint64_t now = 102; now < 1101; now += 100) assert(!step(&server, now) && server.client.deadline == 1101);
    assert(!step(&server, 1101) && server.client.fd < 0 && setter_calls == 1 && output_size == 10); finish(&server);
    start(&server, "OKT1 SET 1 0\n"); assert(!step(&server, 101)); send_delay = 1000;
    assert(!step(&server, 102) && server.client.fd < 0 && server.manual_updates == 1); finish(&server);
    start(&server, "OKT1 SET 1800000000 0\n"); setter_backwards = 1;
    assert(step(&server, 101) < 0 && errno == EOVERFLOW && server.manual_updates == 1 && !output_size); finish(&server);
    start(&server, "OKT1 STATUS\n"); assert(step(&server, 99) < 0 && errno == EOVERFLOW); finish(&server);
    start(&server, "OKT1 STATUS\n"); assert(step(&server, UINT64_MAX) < 0 && errno == EOVERFLOW); finish(&server);
    start(&server, "OKT1 STATUS\n"); clock_backwards = 1;
    assert(step(&server, 101) < 0 && errno == EOVERFLOW && !output_size); finish(&server);
}

static void endpoint_tests(void)
{
    struct ts_server server;
    reset(); assert(!ts_server_open(&server)); int startup_calls = calls; finish(&server);
    for (int fault = 1; fault <= startup_calls; ++fault) {
        reset(); fail_at = fault;
        assert(ts_server_open(&server) < 0 && injected && !held);
    }
    for (int directory = 0; directory < 2; ++directory) for (int bad = 1; bad <= 5; ++bad) {
        reset(); if (directory) run_bad = bad; else root_bad = bad;
        assert(ts_server_open(&server) < 0 && !held && !unlinks);
    }
    for (unsigned kind = 0; kind < 12; ++kind) {
        reset(); socket_exists = 1;
        if (kind == 1) connect_error = EAGAIN;
        if (kind >= 2) connect_error = ECONNREFUSED;
        if (kind == 3) socket_uid = 1000;
        if (kind == 4) socket_gid = 1000;
        if (kind == 5) socket_kind = S_IFREG;
        if (kind == 6) socket_kind = S_IFLNK;
        if (kind == 7) socket_mode = 0600;
        if (kind == 8) socket_links = 2;
        if (kind == 9) socket_swap = 1;
        if (kind == 10) socket_mode |= 02000;
        if (kind == 11) clock_step = 1000;
        int result = ts_server_open(&server);
        assert((result == 0) == (kind == 2)); assert(unlinks == (kind == 2)); finish(&server);
    }
    reset(); launch_uid = 1000; assert(ts_server_open(&server) < 0 && errno == EPERM && !held);
    reset(); launch_gid = 1000; assert(ts_server_open(&server) < 0 && errno == EPERM && !held);
    reset(); clock_overflow = 1; assert(ts_server_open(&server) < 0 && errno == EOVERFLOW && !held);
    reset(); bind_error = EADDRINUSE; assert(ts_server_open(&server) < 0 && !held && mask_value == 0022);
    reset(); listen_error = EIO; assert(ts_server_open(&server) < 0 && !held && mask_value == 0022);
}

static void ready_tests(void)
{
    char *good[] = {"OTHER=1", "OK_SERVICE_READY_FD=30", 0}; assert(ts_ready_descriptor(good) == 30);
    char *duplicate[] = {"OK_SERVICE_READY_FD=30", "OK_SERVICE_READY_FD=30", 0}; assert(ts_ready_descriptor(duplicate) < 0);
    const char *bad[] = {"", "2", "32", "+3", "03", "3x", " 3", "30000000000000000000000000"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) {
        char text[100]; snprintf(text, sizeof(text), "OK_SERVICE_READY_FD=%s", bad[i]);
        char *environment[] = {text, 0}; assert(ts_ready_descriptor(environment) < 0);
    }
    assert(ts_ready_descriptor(0) < 0);
    struct ts_server server;
    reset(); realtime_error = EIO; acquire(30); ts_server_reset(&server); notify_interrupt = 2;
    assert(!ts_service_open(&server, 30) && notify_bytes == 1 && notify_closed == 1); finish(&server);
    for (int kind = 0; kind < 3; ++kind) {
        reset(); acquire(30); ts_server_reset(&server);
        if (kind == 0) notify_zero = 1;
        if (kind == 1) notify_interrupt = 20;
        if (kind == 2) clock_failure = EIO;
        assert(ts_service_open(&server, 30) < 0 && !notify_bytes && notify_closed == 1); finish(&server);
    }
}

static int exchange(struct ts_request request, struct ts_reply *reply)
{ struct ts_buffer wire; return ts_exchange(&request, &wire, reply); }
static void client_tests(void)
{
    const char *status = "OKT1 STATUS pid=73 manual_updates=0 realtime_error=5 realtime_seconds=0 realtime_nanoseconds=0 monotonic_seconds=2 monotonic_nanoseconds=9\nEND\n";
    struct ts_request request = {.operation = TS_STATUS}; struct ts_reply reply;
    for (size_t chunk = 1; chunk <= 15; ++chunk) {
        reset(); socket_exists = 1; launch_uid = launch_gid = 1000; feed(status); recv_eof = 1;
        recv_chunk = chunk; send_chunk = 1; recv_again = recv_interrupt = send_again = send_interrupt = 2;
        assert(!exchange(request, &reply) && reply.realtime_error == EIO && !held);
        assert(output_size == 12 && !memcmp(output, "OKT1 STATUS\n", output_size));
    }
    for (unsigned kind = 0; kind < 14; ++kind) {
        reset(); socket_exists = 1; feed(status); recv_eof = 1;
        if (kind == 0) peer_uid = 1000;
        if (kind == 1) peer_gid = 1000;
        if (kind == 2) peer_pid = 0;
        if (kind == 3) peer_pid = 1;
        if (kind == 4) peer_short = 1;
        if (kind == 5) peer_error = EIO;
        if (kind == 6) socket_swap = 1;
        if (kind == 7) recv_flags = 1;
        if (kind == 8) recv_control = 1;
        if (kind == 9) recv_oversize = 1;
        if (kind == 10) send_oversize = 1;
        if (kind == 11) send_zero = 1;
        if (kind == 12) input[input_size++] = 'x';
        if (kind == 13) peer_pid = 74;
        assert(exchange(request, &reply) < 0 && !held);
    }
    reset(); socket_exists = 1; feed("OKT1 ERROR errno=1\nEND\n"); recv_eof = 1;
    assert(!exchange(request, &reply) && reply.operation == TS_ERROR && reply.error == EPERM && !held);
    reset(); socket_exists = 1; feed("OKT1 SET pid=73 manual_updates=1\nEND\n"); recv_eof = 1;
    assert(exchange(request, &reply) < 0 && !held);
    const uint64_t delays[] = {999, 1000, 1001};
    for (size_t i = 0; i < sizeof(delays) / sizeof(*delays); ++i) {
        reset(); socket_exists = 1; feed(status); recv_eof = 1; receive_delay = delays[i];
        assert((exchange(request, &reply) == 0) == (delays[i] < TS_DEADLINE_MS)); assert(!held);
        reset(); socket_exists = 1; feed(status); recv_eof = 1; eof_delay = delays[i];
        assert((exchange(request, &reply) == 0) == (delays[i] < TS_DEADLINE_MS)); assert(!held);
        reset(); socket_exists = 1; feed(status); recv_eof = 1; send_delay = delays[i];
        assert((exchange(request, &reply) == 0) == (delays[i] < TS_DEADLINE_MS)); assert(!held);
    }
    reset(); socket_exists = 1; feed(status); recv_eof = 0;
    assert(exchange(request, &reply) < 0 && errno == EAGAIN && milliseconds == 1100 && !held);
    reset(); socket_exists = 1; feed(status); recv_eof = 1; recv_chunk = 1; receive_delay_each = 10;
    assert(exchange(request, &reply) < 0 && errno == EAGAIN && !held);
    reset(); socket_exists = 1; feed(status); recv_eof = 1; send_chunk = 1; send_delay_each = 100;
    assert(exchange(request, &reply) < 0 && errno == EAGAIN && !held);
    reset(); socket_exists = 1; feed(status); recv_eof = 1;
    assert(!exchange(request, &reply)); int completed_calls = calls;
    for (int fault = 1; fault <= completed_calls; ++fault) {
        reset(); socket_exists = 1; feed(status); recv_eof = 1; fail_at = fault;
        assert(exchange(request, &reply) < 0 && injected && !held);
    }
}

int main(void)
{
    parser_tests(); dispatch_tests(); server_tests(); endpoint_tests(); ready_tests(); client_tests();
    puts("time service actual-code fault controls passed"); return 0;
}
