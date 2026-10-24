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
#include "../apps/resolver/resolver.h"

/* Actual product sources, with deterministic syscall seams. These tests do
 * not execute a native kernel or qualify DNS transport or a concurrent root edit. */
static int calls, fail_at, injected, descriptors[32], held;
static int root_bad, run_bad, etc_bad, launch_uid, launch_gid, process_pid, parent_pid, daemon_poll_stop;
static int file_kind, file_mode, file_uid, file_gid, file_links, file_swap, file_stats;
static int file_open_error, file_interrupt, file_oversize;
static int file_path_error, file_path_swap, file_path_kind, file_path_mode_flip;
static size_t file_size, file_read_at, file_chunk;
static int64_t file_reported_size;
static char file_bytes[RS_HOSTS_BYTES + 2];
static int socket_exists, socket_kind, socket_mode, socket_uid, socket_gid, socket_links, socket_inode, socket_swap;
static int connect_error, bind_error, listen_error, mask_value, unlinks, accepted, accept_available;
static int peer_uid, peer_gid, peer_pid, peer_short, peer_error;
static int recv_again, recv_interrupt, peek_interrupt, recv_flags, recv_control, recv_oversize, recv_eof;
static int send_again, send_interrupt, send_error, send_oversize, send_zero;
static int clock_failure, clock_backwards, clock_overflow, monotonic_bad;
static int notify_bytes, notify_closed, notify_interrupt, notify_zero;
static size_t input_size, read_at, recv_chunk, send_chunk, output_size;
static char input[700], output[700];
static uint64_t milliseconds, clock_step, receive_delay, receive_delay_each, send_delay, send_delay_each, eof_delay, file_delay;

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
    if (fd == 10) {
        assert(flags == (O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        assert(!strcmp(name, "run") || !strcmp(name, "etc"));
        return event() < 0 ? -1 : acquire(!strcmp(name, "run") ? 11 : 12);
    }
    assert(fd == 12 && !strcmp(name, "hosts") && flags == (O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK));
    if (event() < 0) return -1;
    if (file_open_error) { errno = file_open_error; return -1; }
    return acquire(13);
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
    assert(fd >= 10 && fd <= 13);
    if (event() < 0) return -1;
    memset(value, 0, sizeof(*value));
    if (fd == 13) {
        value->st_mode = (mode_t)(file_kind | file_mode);
        value->st_uid = (unsigned)file_uid; value->st_gid = (unsigned)file_gid;
        value->st_nlink = (unsigned)file_links; value->st_ino = 155;
        value->st_size = file_reported_size;
        if (file_stats++ && file_swap) ++value->st_ino;
        return 0;
    }
    value->st_mode = S_IFDIR | 0755;
    int bad = fd == 10 ? root_bad : fd == 11 ? run_bad : etc_bad;
    if (bad == 1) value->st_mode |= 0020;
    if (bad == 2) value->st_uid = 1000;
    if (bad == 3) value->st_mode = S_IFLNK | 0755;
    if (bad == 4) value->st_mode |= 02000;
    if (bad == 5) value->st_gid = 1000;
    return 0;
}
static ssize_t t_read(int fd, void *buffer, size_t size)
{
    assert(fd == 13 && size > 0);
    if (event() < 0) return -1;
    if (file_interrupt) { --file_interrupt; errno = EINTR; return -1; }
    if (file_oversize) return (ssize_t)size + 1;
    size_t count = file_size - file_read_at;
    if (count > size) count = size;
    if (file_chunk && count > file_chunk) count = file_chunk;
    memcpy(buffer, file_bytes + file_read_at, count); file_read_at += count;
    advance(file_delay); file_delay = 0;
    return (ssize_t)count;
}
static int t_fstatat(int fd, const char *name, struct stat *value, int flags)
{
    assert(flags == AT_SYMLINK_NOFOLLOW);
    if (event() < 0) return -1;
    if (fd == 12) {
        assert(!strcmp(name, "hosts") && file_read_at == file_size);
        if (file_path_error) { errno = file_path_error; return -1; }
        memset(value, 0, sizeof(*value));
        value->st_mode = (mode_t)((file_path_kind ? file_path_kind : file_kind) | (file_mode ^ file_path_mode_flip));
        value->st_uid = (unsigned)file_uid; value->st_gid = (unsigned)file_gid;
        value->st_nlink = (unsigned)file_links; value->st_ino = (ino_t)(155 + file_path_swap);
        value->st_size = file_reported_size;
        return 0;
    }
    assert(fd == 11 && !strcmp(name, RS_NAME));
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
    assert(fd == 11 && !strcmp(name, RS_NAME) && !flags);
    if (event() < 0) return -1;
    socket_exists = 0; ++unlinks; return 0;
}
int ok_socket(int domain, int type, int protocol)
{
    assert(domain == OK_AF_UNIX && type == (OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC) && !protocol);
    return event() < 0 ? -1 : acquire(24);
}
static void check_address(int fd, const struct ok_sockaddr_un *address, ok_socklen_t size)
{ assert(fd == 24 && address->family == OK_AF_UNIX && !strcmp(address->path, RS_PATH) && size == 2 + sizeof(RS_PATH)); }
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
static pid_t t_parent(void) { return parent_pid; }
static int t_clock(clockid_t id, struct timespec *value)
{
    if (event() < 0) return -1;
    assert(id == CLOCK_MONOTONIC);
    if (clock_failure) { errno = clock_failure; return -1; }
    uint64_t now = milliseconds;
    if (clock_backwards) { assert(now >= 2); now -= 2; }
    value->tv_sec = clock_overflow ? INT64_MAX : (time_t)(now / 1000);
    value->tv_nsec = monotonic_bad ? 1000000000 : (long)(now % 1000) * 1000000;
    advance(clock_step);
    return 0;
}
static int t_poll(struct pollfd *fds, nfds_t count, int timeout)
{
    assert((count == 1 || count == 2) && fds->fd == 24 && timeout == 10);
    if (count == 2 && daemon_poll_stop) { errno = EIO; return -1; }
    advance(10); return event();
}
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
#define read t_read
#define fstat t_fstat
#define fstatat t_fstatat
#define unlinkat t_unlinkat
#define geteuid t_uid
#define getegid t_gid
#define getpid t_pid
#define getppid t_parent
#define clock_gettime t_clock
#define poll t_poll
#define write t_write
#include "../apps/resolver/hosts.c"
#include "../apps/resolver/protocol.c"
#include "../apps/resolver/transport.c"
#define main resolver_daemon_main
#include "../apps/resolved/main.c"
#undef main
#undef open
#undef openat
#undef close
#undef read
#undef fstat
#undef fstatat
#undef unlinkat
#undef geteuid
#undef getegid
#undef getpid
#undef getppid
#undef clock_gettime
#undef poll
#undef write

static struct rs_hosts table, scratch, previous;
static struct rs_workspace fixture_workspace;
static const char seed[] = "127.0.0.1 localhost\n";

static void set_file(const char *bytes, size_t size)
{
    assert(size <= sizeof(file_bytes)); memcpy(file_bytes, bytes, size);
    file_size = size; file_reported_size = (int64_t)size;
    file_read_at = 0; file_stats = 0;
}
static void reset(void)
{
    assert(!held); memset(descriptors, 0, sizeof(descriptors));
    calls = fail_at = injected = root_bad = run_bad = etc_bad = launch_uid = launch_gid = 0;
    process_pid = 73;
    parent_pid = 1; daemon_poll_stop = 0;
    file_kind = S_IFREG; file_mode = 0644; file_uid = file_gid = file_swap = file_stats = 0;
    file_links = 1; file_open_error = file_interrupt = file_oversize = 0; file_chunk = 0;
    file_path_error = file_path_swap = file_path_kind = file_path_mode_flip = 0;
    set_file(seed, sizeof(seed) - 1);
    socket_exists = socket_uid = socket_gid = socket_swap = connect_error = bind_error = listen_error = unlinks = accepted = accept_available = 0;
    socket_kind = 0140000; socket_mode = 0666; socket_links = 1; socket_inode = 99; mask_value = 0022;
    peer_uid = peer_gid = peer_short = peer_error = 0; peer_pid = 73;
    recv_again = recv_interrupt = peek_interrupt = recv_flags = recv_control = recv_oversize = recv_eof = 0;
    send_again = send_interrupt = send_error = send_oversize = send_zero = 0;
    clock_failure = clock_backwards = clock_overflow = monotonic_bad = 0;
    notify_bytes = notify_closed = notify_interrupt = notify_zero = 0;
    input_size = read_at = recv_chunk = send_chunk = output_size = 0;
    milliseconds = 100; clock_step = receive_delay = receive_delay_each = send_delay = send_delay_each = eof_delay = file_delay = 0;
    assert(!rs_hosts_parse(seed, sizeof(seed) - 1, &table, &scratch));
}
static void feed(const char *value)
{ input_size = strlen(value); assert(input_size <= sizeof(input)); memcpy(input, value, input_size); read_at = 0; }
static void start(struct rs_server *server, const char *request)
{ reset(); assert(!rs_server_open(server, &table)); assert(mask_value == 0022); accept_available = 1; feed(request); }
static int step(struct rs_server *server, uint64_t now)
{ milliseconds = now; return rs_server_step(server, now); }
static void finish(struct rs_server *server)
{ fail_at = 0; assert(!rs_server_close(server)); assert(!held); }
static struct rs_reply response(void)
{ struct rs_reply reply; assert(!rs_reply_parse(output, output_size, &reply)); return reply; }

static void parser_tests(void)
{
    reset();
    uint8_t address[4] = {42, 42, 42, 42};
    assert(!rs_ipv4("0.1.254.255", 11, address) && address[0] == 0 && address[3] == 255);
    const char *bad_ip[] = {"", "0", "127.1", "1.2.3", "1.2.3.4.5", "01.2.3.4", "1.2.3.004", "1.2.3.256", "-1.2.3.4", "+1.2.3.4", "0x7f.0.0.1", "1.2.3.4 ", "1..2.3", "1.2.3.4."};
    for (size_t i = 0; i < sizeof(bad_ip) / sizeof(*bad_ip); ++i) assert(rs_ipv4(bad_ip[i], strlen(bad_ip[i]), address) < 0);
    char name[RS_NAME_BYTES + 1];
    assert(!rs_name_normalize("Web-1.Example.", 14, name) && !strcmp(name, "web-1.example"));
    const char *bad_name[] = {"", ".", "a..b", "a..", "-a", "a-", "a.-b", "a-.b", "a_b", "a b", "a/b", "a\tb", "a\nb", "\xff"};
    for (size_t i = 0; i < sizeof(bad_name) / sizeof(*bad_name); ++i) assert(rs_name_normalize(bad_name[i], strlen(bad_name[i]), name) < 0);
    char maximum[RS_NAME_BYTES + 2]; memset(maximum, 'a', sizeof(maximum));
    maximum[63] = maximum[127] = maximum[191] = '.'; maximum[253] = 0;
    assert(!rs_name_normalize(maximum, 253, name));
    maximum[253] = 'a'; maximum[254] = 0;
    assert(rs_name_normalize(maximum, 254, name) < 0);
    memset(maximum, 'a', 64); assert(rs_name_normalize(maximum, 64, name) < 0);
    assert(rs_query_normalize("127.1", 5, name) < 0 && rs_query_normalize("001.2.3.4", 9, name) < 0);

    const char *valid[] = {"OKR1 STATUS\n", "OKR1 LOOKUP localhost\n", "OKR1 LOOKUP 255.0.1.2\n"};
    struct rs_request request;
    for (size_t i = 0; i < sizeof(valid) / sizeof(*valid); ++i) {
        size_t size = strlen(valid[i]);
        for (size_t cut = 0; cut < size; ++cut) assert(!rs_request_parse(valid[i], cut, &request));
        assert(rs_request_parse(valid[i], size, &request) == 1);
        struct rs_buffer encoded; assert(!rs_request_encode(&request, &encoded));
        assert(encoded.size == size && !memcmp(encoded.bytes, valid[i], size));
    }
    const char *folded = "OKR1 LOOKUP LOCALHOST.\n";
    assert(rs_request_parse(folded, strlen(folded), &request) == 1 && !strcmp(request.name, "localhost"));
    const char *bad[] = {"OKR1 STATUS\r\n", "OKR1 STATUS\nx", "OKR1 STATUS\nOKR1 STATUS\n", "OKR1 LOOKUP \n", "OKR1 LOOKUP a b\n", "OKR1 LOOKUP 127.1\n", "OKR1 LOOKUP 1.2.3.04\n", "OKR1 LOOKUP a/../b\n", "OKR1 LOOKUP a..b\n", "OKR1 LOOKUP a\t\n", "OKR2 STATUS\n"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) assert(rs_request_parse(bad[i], strlen(bad[i]), &request) < 0);
    char large[RS_REQUEST_BYTES + 1]; memset(large, 'A', sizeof(large));
    assert(rs_request_parse(large, RS_REQUEST_BYTES, &request) < 0 && rs_request_parse(large, sizeof(large), &request) < 0);
    assert(rs_request_parse("OKR1\0 STATUS\n", 13, &request) < 0);
    struct rs_reply originals[] = {
        {.operation = RS_STATUS, .pid = 73, .aliases = 64, .bytes = 4096},
        {.operation = RS_LOOKUP, .pid = 73, .source = RS_NUMERIC, .name = "255.0.1.2", .address = {255, 0, 1, 2}},
        {.operation = RS_LOOKUP, .pid = 73, .source = RS_HOSTS, .name = "localhost", .address = {127, 0, 0, 1}},
        {.operation = RS_ERROR, .error = ENOENT}
    };
    for (size_t i = 0; i < sizeof(originals) / sizeof(*originals); ++i) {
        struct rs_buffer encoded; struct rs_reply decoded;
        assert(!rs_reply_encode(&originals[i], &encoded));
        for (size_t cut = 0; cut < encoded.size; ++cut) assert(rs_reply_parse(encoded.bytes, cut, &decoded) < 0);
        assert(!rs_reply_parse(encoded.bytes, encoded.size, &decoded) && decoded.operation == originals[i].operation);
        encoded.bytes[encoded.size++] = 'x'; assert(rs_reply_parse(encoded.bytes, encoded.size, &decoded) < 0);
    }
    const char *bad_replies[] = {
        "OKR1 ERROR errno=0\nEND\n", "OKR1 ERROR errno=01\nEND\n", "OKR1 ERROR errno=4096\nEND\n",
        "OKR1 STATUS pid=1 aliases=1 bytes=19\nEND\n", "OKR1 STATUS pid=73 aliases=65 bytes=19\nEND\n",
        "OKR1 STATUS pid=73 aliases=1 bytes=4097\nEND\n",
        "OKR1 LOOKUP pid=73 name=LOCALHOST address=127.0.0.1 source=hosts\nEND\n",
        "OKR1 LOOKUP pid=73 name=localhost. address=127.0.0.1 source=hosts\nEND\n",
        "OKR1 LOOKUP pid=73 name=localhost address=127.0.0.1 source=numeric\nEND\n",
        "OKR1 LOOKUP pid=73 name=127.0.0.1 address=127.0.0.2 source=numeric\nEND\n",
        "OKR1 LOOKUP pid=73 name=127.0.0.1 address=127.0.0.1 source=hosts\nEND\n",
        "OKR1 LOOKUP pid=73 name=localhost address=127.0.0.01 source=hosts\nEND\n"
    };
    struct rs_reply decoded;
    for (size_t i = 0; i < sizeof(bad_replies) / sizeof(*bad_replies); ++i) assert(rs_reply_parse(bad_replies[i], strlen(bad_replies[i]), &decoded) < 0);
    memset(maximum, 'a', 253); maximum[63] = maximum[127] = maximum[191] = '.'; maximum[253] = 0;
    request.operation = RS_LOOKUP; memcpy(request.name, maximum, 254);
    struct rs_buffer largest; assert(!rs_request_encode(&request, &largest) && largest.size == 266);
    assert(rs_request_parse(largest.bytes, largest.size, &request) == 1 && !strcmp(request.name, maximum));
    struct rs_reply long_reply = {.operation = RS_LOOKUP, .pid = INT32_MAX, .source = RS_HOSTS, .address = {255, 255, 255, 255}};
    memcpy(long_reply.name, maximum, 254);
    assert(!rs_reply_encode(&long_reply, &largest) && !rs_reply_parse(largest.bytes, largest.size, &decoded));
    assert(!strcmp(decoded.name, maximum) && decoded.pid == INT32_MAX);
    memset(request.name, 'a', sizeof(request.name)); request.operation = RS_LOOKUP;
    struct rs_buffer encoded; assert(rs_request_encode(&request, &encoded) < 0);
}

static void hosts_parser_tests(void)
{
    reset();
    const char *valid = "# local records\n\n\t127.0.0.1 LocalHost LOCALHOST. loop # comment\n192.0.2.1 Peer.example PEER\n127.0.0.1 localhost\n";
    assert(!rs_hosts_parse(valid, strlen(valid), &table, &scratch) && table.count == 4 && table.bytes == strlen(valid));
    assert(!strcmp(table.aliases[0].name, "localhost") && !strcmp(table.aliases[1].name, "loop"));
    previous = table;
    const char *bad[] = {"127.0.0.1 localhost", "127.0.0.1\n", "127.0.0.1 # empty\n", "127.0.0.01 host\n", "::1 localhost\n", "127.0.0.1 a_b\n", "127.0.0.1 -a\n", "127.0.0.1 1.2.3.4\n", "127.0.0.1 same\n127.0.0.2 SAME.\n", "127.0.0.1 local\r\n"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) {
        assert(rs_hosts_parse(bad[i], strlen(bad[i]), &table, &scratch) < 0);
        assert(!memcmp(&table, &previous, sizeof(table)));
    }
    char bytes[RS_HOSTS_BYTES + 1];
    for (unsigned c = 0; c <= 255; ++c) {
        if (c >= 32 && c <= 126) continue;
        if (c == '\n' || c == '\t') continue;
        char bad_byte[] = {'#', (char)c, '\n'};
        assert(rs_hosts_parse(bad_byte, sizeof(bad_byte), &table, &scratch) < 0);
        assert(!memcmp(&table, &previous, sizeof(table)));
    }
    memset(bytes, 'x', sizeof(bytes)); bytes[0] = '#'; bytes[RS_HOSTS_BYTES - 1] = '\n';
    assert(!rs_hosts_parse(bytes, RS_HOSTS_BYTES, &table, &scratch) && !table.count);
    assert(rs_hosts_parse(bytes, sizeof(bytes), &table, &scratch) < 0);
    size_t used = 0;
    for (unsigned i = 0; i <= RS_ALIAS_CAPACITY; ++i) {
        int wrote = snprintf(bytes + used, sizeof(bytes) - used, "192.0.2.1 h%u\n", i); assert(wrote > 0); used += (size_t)wrote;
        if (i + 1 == RS_ALIAS_CAPACITY) {
            assert(!rs_hosts_parse(bytes, used, &table, &scratch) && table.count == RS_ALIAS_CAPACITY); previous = table;
        }
    }
    assert(rs_hosts_parse(bytes, used, &table, &scratch) < 0 && !memcmp(&table, &previous, sizeof(table)));
    assert(!rs_hosts_parse("", 0, &table, &scratch) && !table.count && !table.bytes);
    assert(rs_hosts_parse(seed, sizeof(seed) - 1, &table, &table) < 0);
}

static void file_admission_tests(void)
{
    reset(); assert(!rs_hosts_load(&table, &fixture_workspace) && !held && table.count == 1); int completed = calls;
    for (int fault = 1; fault <= completed; ++fault) {
        reset(); previous = table; fail_at = fault;
        assert(rs_hosts_load(&table, &fixture_workspace) < 0 && injected && !held && !memcmp(&table, &previous, sizeof(table)));
    }
    for (size_t chunk = 1; chunk <= sizeof(seed); ++chunk) {
        reset(); file_chunk = chunk; file_interrupt = 2;
        assert(!rs_hosts_load(&table, &fixture_workspace) && !held && table.count == 1);
    }
    for (unsigned kind = 0; kind < 20; ++kind) {
        reset(); previous = table;
        if (kind == 0) file_kind = S_IFDIR;
        if (kind == 1) file_kind = S_IFLNK;
        if (kind == 2) file_uid = 1000;
        if (kind == 3) file_gid = 1000;
        if (kind == 4) file_mode |= 0020;
        if (kind == 5) file_mode |= 04000;
        if (kind == 6) file_links = 2;
        if (kind == 7) file_reported_size = -1;
        if (kind == 8) file_reported_size = RS_HOSTS_BYTES + 1;
        if (kind == 9) file_swap = 1;
        if (kind == 10) --file_reported_size;
        if (kind == 11) file_open_error = ELOOP;
        if (kind == 12) file_interrupt = 20;
        if (kind == 13) file_oversize = 1;
        if (kind == 14) file_open_error = ENOENT;
        if (kind == 15) set_file("127.0.0.1 a\n127.0.0.2 A\n", 24);
        if (kind == 16) file_path_swap = 1;
        if (kind == 17) file_path_error = ENOENT;
        if (kind == 18) file_path_kind = S_IFLNK;
        if (kind == 19) file_path_mode_flip = 0400;
        assert(rs_hosts_load(&table, &fixture_workspace) < 0 && !held && !memcmp(&table, &previous, sizeof(table)));
    }
    for (unsigned directory = 0; directory < 2; ++directory) for (int bad = 1; bad <= 5; ++bad) {
        reset(); if (directory) etc_bad = bad; else root_bad = bad;
        assert(rs_hosts_load(&table, &fixture_workspace) < 0 && !held);
    }
    reset(); memset(file_bytes, '#', sizeof(file_bytes)); file_size = RS_HOSTS_BYTES + 1; file_bytes[file_size - 1] = '\n';
    file_reported_size = RS_HOSTS_BYTES;
    assert(rs_hosts_load(&table, &fixture_workspace) < 0 && errno == EFBIG && !held);
    reset(); set_file("", 0); assert(!rs_hosts_load(&table, &fixture_workspace) && !table.count && !held);
}

static void dispatch_tests(void)
{
    reset(); struct rs_request request = {.operation = RS_STATUS}; struct rs_reply reply;
    rs_dispatch(&request, &table, &reply); assert(reply.operation == RS_STATUS && reply.pid == 73 && reply.aliases == 1 && reply.bytes == sizeof(seed) - 1);
    request.operation = RS_LOOKUP; strcpy(request.name, "LOCALHOST.");
    rs_dispatch(&request, &table, &reply); assert(reply.operation == RS_LOOKUP && reply.source == RS_HOSTS && !strcmp(reply.name, "localhost") && reply.address[0] == 127);
    strcpy(request.name, "192.0.2.9"); rs_dispatch(&request, &table, &reply);
    assert(reply.operation == RS_LOOKUP && reply.source == RS_NUMERIC && reply.address[3] == 9);
    strcpy(request.name, "missing.example"); rs_dispatch(&request, &table, &reply); assert(reply.operation == RS_ERROR && reply.error == ENOENT);
    strcpy(request.name, "127.1"); rs_dispatch(&request, &table, &reply); assert(reply.error == EINVAL);
    request.operation = RS_INVALID; rs_dispatch(&request, &table, &reply); assert(reply.error == EINVAL);
    process_pid = 1; request.operation = RS_STATUS; rs_dispatch(&request, &table, &reply); assert(reply.error == EIO);
}

static void server_tests(void)
{
    struct rs_server server;
    for (size_t chunk = 1; chunk <= 35; ++chunk) {
        start(&server, "OKR1 LOOKUP LOCALHOST.\n"); recv_chunk = chunk; send_chunk = 1;
        recv_interrupt = recv_again = send_interrupt = send_again = 2; peek_interrupt = 1;
        for (uint64_t now = 101; now < 1000 && (!accepted || server.client.fd >= 0); ++now) assert(!step(&server, now));
        assert(accepted == 1 && response().source == RS_HOSTS && !strcmp(response().name, "localhost")); finish(&server);
    }
    start(&server, "OKR1 STATUS\n"); peer_uid = peer_gid = 1000;
    assert(!step(&server, 101) && !step(&server, 102) && response().operation == RS_STATUS); finish(&server);
    start(&server, "OKR1 LOOKUP missing.example\n"); peer_uid = 1000;
    assert(!step(&server, 101) && !step(&server, 102) && response().error == ENOENT); finish(&server);
    for (unsigned kind = 0; kind < 9; ++kind) {
        start(&server, "OKR1 LOOKUP localhost\n");
        if (kind == 0) peer_pid = 0;
        if (kind == 1) peer_short = 1;
        if (kind == 2) peer_error = EIO;
        if (kind == 3) recv_flags = 1;
        if (kind == 4) recv_control = 1;
        if (kind == 5) recv_oversize = 1;
        if (kind == 6) input[input_size++] = 'x';
        if (kind == 7) { input[input_size++] = 'x'; recv_chunk = input_size - 1; }
        if (kind == 8) input[0] = 'x';
        assert(!step(&server, 101) && server.client.fd < 0 && !output_size); finish(&server);
    }
    start(&server, "OKR1 STATUS\n"); assert(!step(&server, 101));
    feed("OKR1 LOOKUP localhost\n"); assert(!step(&server, 102) && response().operation == RS_STATUS); finish(&server);
    start(&server, "OKR"); recv_eof = 1;
    assert(!step(&server, 101) && !step(&server, 102) && server.client.fd < 0 && !output_size); finish(&server);
    start(&server, "OKR1 LOOKUP localhost\n"); recv_chunk = 1;
    for (uint64_t now = 101; now < 1101; now += 100) assert(!step(&server, now) && server.client.deadline == 1101);
    assert(!step(&server, 1101) && server.client.fd < 0 && !output_size); finish(&server);
    const uint64_t delays[] = {999, 1000, 1001};
    for (size_t i = 0; i < sizeof(delays) / sizeof(*delays); ++i) {
        start(&server, "OKR1 STATUS\n"); receive_delay = delays[i]; assert(!step(&server, 101));
        assert((server.client.reply.size > 0) == (delays[i] < RS_DEADLINE_MS)); finish(&server);
    }
    start(&server, "OKR1 STATUS\n"); send_chunk = 1; assert(!step(&server, 101));
    for (uint64_t now = 102; now < 1101; now += 100) assert(!step(&server, now) && server.client.deadline == 1101);
    assert(!step(&server, 1101) && server.client.fd < 0 && output_size == 10); finish(&server);
    start(&server, "OKR1 STATUS\n"); assert(!step(&server, 101)); send_delay = 1000;
    assert(!step(&server, 102) && server.client.fd < 0); finish(&server);
    start(&server, "OKR1 STATUS\n"); assert(step(&server, 99) < 0 && errno == EOVERFLOW); finish(&server);
    start(&server, "OKR1 STATUS\n"); assert(step(&server, UINT64_MAX) < 0 && errno == EOVERFLOW); finish(&server);
    start(&server, "OKR1 STATUS\n"); clock_backwards = 1;
    assert(step(&server, 101) < 0 && errno == EOVERFLOW && !output_size); finish(&server);
    for (unsigned kind = 0; kind < 3; ++kind) {
        start(&server, "OKR1 STATUS\n"); assert(!step(&server, 101));
        if (kind == 0) send_error = EPIPE;
        if (kind == 1) send_zero = 1;
        if (kind == 2) send_oversize = 1;
        if (kind == 2) assert(step(&server, 102) < 0 && errno == EIO && !output_size);
        else assert(!step(&server, 102) && server.client.fd < 0 && !output_size);
        finish(&server);
    }
}

static void endpoint_tests(void)
{
    struct rs_server server;
    reset(); assert(!rs_server_open(&server, &table)); int startup_calls = calls; finish(&server);
    for (int fault = 1; fault <= startup_calls; ++fault) {
        reset(); fail_at = fault; assert(rs_server_open(&server, &table) < 0 && injected && !held);
    }
    for (unsigned directory = 0; directory < 2; ++directory) for (int bad = 1; bad <= 5; ++bad) {
        reset(); if (directory) run_bad = bad; else root_bad = bad;
        assert(rs_server_open(&server, &table) < 0 && !held && !unlinks);
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
        int result = rs_server_open(&server, &table);
        assert((result == 0) == (kind == 2) && unlinks == (kind == 2)); finish(&server);
    }
    reset(); launch_uid = 1000; assert(rs_server_open(&server, &table) < 0 && errno == EPERM && !held);
    reset(); launch_gid = 1000; assert(rs_server_open(&server, &table) < 0 && errno == EPERM && !held);
    reset(); clock_overflow = 1; assert(rs_server_open(&server, &table) < 0 && errno == EOVERFLOW && !held);
    reset(); bind_error = EADDRINUSE; assert(rs_server_open(&server, &table) < 0 && !held && mask_value == 0022);
    reset(); listen_error = EIO; assert(rs_server_open(&server, &table) < 0 && !held && mask_value == 0022);
}

static void ready_tests(void)
{
    char *good[] = {"OTHER=1", "OK_SERVICE_READY_FD=30", 0}; assert(rs_ready_descriptor(good) == 30);
    char *duplicate[] = {"OK_SERVICE_READY_FD=30", "OK_SERVICE_READY_FD=30", 0}; assert(rs_ready_descriptor(duplicate) < 0);
    const char *bad[] = {"", "2", "32", "+3", "03", "3x", " 3", "30000000000000000000000000"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) {
        char value[100]; snprintf(value, sizeof(value), "OK_SERVICE_READY_FD=%s", bad[i]);
        char *environment[] = {value, 0}; assert(rs_ready_descriptor(environment) < 0);
    }
    assert(rs_ready_descriptor(0) < 0);
    struct rs_server server;
    reset(); acquire(30); rs_server_reset(&server); notify_interrupt = 2;
    assert(!rs_service_open(&server, &table, &fixture_workspace, 30) && notify_bytes == 1 && notify_closed == 1); finish(&server);
    for (unsigned kind = 0; kind < 6; ++kind) {
        reset(); acquire(30); rs_server_reset(&server);
        if (kind == 0) notify_zero = 1;
        if (kind == 1) notify_interrupt = 20;
        if (kind == 2) clock_failure = EIO;
        if (kind == 3) file_uid = 1000;
        if (kind == 4) file_delay = 2500;
        if (kind == 5) set_file("127.0.0.1 bad_name\n", 19);
        assert(rs_service_open(&server, &table, &fixture_workspace, 30) < 0 && !notify_bytes && notify_closed == 1); finish(&server);
    }
}

static int exchange(struct rs_request request, struct rs_reply *reply)
{ struct rs_buffer wire; return rs_exchange(&request, &wire, reply); }
static void client_tests(void)
{
    const char *status = "OKR1 STATUS pid=73 aliases=1 bytes=19\nEND\n";
    struct rs_request request = {.operation = RS_STATUS}; struct rs_reply reply;
    for (size_t chunk = 1; chunk <= 15; ++chunk) {
        reset(); socket_exists = 1; launch_uid = launch_gid = 1000; feed(status); recv_eof = 1;
        recv_chunk = chunk; send_chunk = 1; recv_again = recv_interrupt = send_again = send_interrupt = 2;
        assert(!exchange(request, &reply) && reply.operation == RS_STATUS && !held);
        assert(output_size == 12 && !memcmp(output, "OKR1 STATUS\n", output_size));
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
    reset(); socket_exists = 1; feed("OKR1 ERROR errno=2\nEND\n"); recv_eof = 1;
    assert(!exchange(request, &reply) && reply.operation == RS_ERROR && reply.error == ENOENT && !held);
    const uint64_t delays[] = {999, 1000, 1001};
    for (size_t i = 0; i < sizeof(delays) / sizeof(*delays); ++i) {
        reset(); socket_exists = 1; feed(status); recv_eof = 1; receive_delay = delays[i];
        assert((exchange(request, &reply) == 0) == (delays[i] < RS_DEADLINE_MS) && !held);
        reset(); socket_exists = 1; feed(status); recv_eof = 1; eof_delay = delays[i];
        assert((exchange(request, &reply) == 0) == (delays[i] < RS_DEADLINE_MS) && !held);
        reset(); socket_exists = 1; feed(status); recv_eof = 1; send_delay = delays[i];
        assert((exchange(request, &reply) == 0) == (delays[i] < RS_DEADLINE_MS) && !held);
    }
    reset(); socket_exists = 1; feed(status); recv_eof = 0;
    assert(exchange(request, &reply) < 0 && errno == EAGAIN && milliseconds == 1100 && !held);
    reset(); socket_exists = 1; feed(status); recv_eof = 1; recv_chunk = 1; receive_delay_each = 30;
    assert(exchange(request, &reply) < 0 && errno == EAGAIN && !held);
    reset(); socket_exists = 1; feed(status); recv_eof = 1; send_chunk = 1; send_delay_each = 100;
    assert(exchange(request, &reply) < 0 && errno == EAGAIN && !held);
    reset(); socket_exists = 1; feed(status); recv_eof = 1;
    assert(!exchange(request, &reply)); int completed = calls;
    for (int fault = 1; fault <= completed; ++fault) {
        reset(); socket_exists = 1; feed(status); recv_eof = 1; fail_at = fault;
        assert(exchange(request, &reply) < 0 && injected && !held);
    }
    const char *lookup = "OKR1 LOOKUP pid=73 name=localhost address=127.0.0.1 source=hosts\nEND\n";
    request.operation = RS_LOOKUP; strcpy(request.name, "LOCALHOST.");
    reset(); socket_exists = 1; feed(lookup); recv_eof = 1;
    assert(!exchange(request, &reply) && !strcmp(reply.name, "localhost") && !held);
    strcpy(request.name, "different"); reset(); socket_exists = 1; feed(lookup); recv_eof = 1;
    assert(exchange(request, &reply) < 0 && !held);
    request.operation = RS_STATUS; reset(); socket_exists = 1; feed(lookup); recv_eof = 1;
    assert(exchange(request, &reply) < 0 && !held);
}

static void daemon_entry_tests(void)
{
    char *argv[] = {"resolved", 0}; char *environment[] = {"OK_SERVICE_READY_FD=30", 0};
    reset(); acquire(30); daemon_poll_stop = 1;
    assert(resolver_daemon_main(1, argv, environment) == 1 && notify_bytes == 1 && notify_closed == 1 && !held);
    for (unsigned kind = 0; kind < 5; ++kind) {
        reset();
        if (kind == 0) parent_pid = 2;
        if (kind == 1) launch_uid = 1000;
        if (kind == 2) launch_gid = 1000;
        assert(resolver_daemon_main(kind == 3 ? 2 : 1, argv, kind == 4 ? 0 : environment) == 1 && !notify_bytes && !held);
    }
    reset(); acquire(30); file_uid = 1000;
    assert(resolver_daemon_main(1, argv, environment) == 1 && !notify_bytes && notify_closed == 1 && !held);
}

static int cli_calls, cli_transport_error, cli_error, cli_output_error;
static size_t cli_output_size;
static char cli_output[RS_REPLY_BYTES];
static FILE *cli_stream;
static struct rs_request cli_request;
static int cli_exchange(const struct rs_request *request, struct rs_buffer *wire, struct rs_reply *reply)
{
    ++cli_calls; cli_request = *request;
    if (cli_transport_error) { errno = EIO; return -1; }
    rs_dispatch(request, &table, reply);
    if (cli_error) *reply = (struct rs_reply){.operation = RS_ERROR, .error = ENOENT};
    return rs_reply_encode(reply, wire);
}
static int cli_putc(int c, FILE *stream)
{
    assert(stream == cli_stream);
    if (cli_output_error) return EOF;
    assert(cli_output_size < sizeof(cli_output)); cli_output[cli_output_size++] = (char)c; return c;
}
#define main resolver_cli_main
#define rs_exchange cli_exchange
#define fputc cli_putc
#include "../apps/resolvectl/main.c"
#undef main
#undef rs_exchange
#undef fputc

static void cli_reset(void)
{
    reset(); cli_calls = cli_transport_error = cli_error = cli_output_error = 0;
    cli_output_size = 0; cli_stream = stdout;
}
static void cli_entry_tests(void)
{
    char *status[] = {"resolvectl", "status", 0};
    char *lookup[] = {"resolvectl", "lookup", "LOCALHOST.", 0};
    cli_reset(); assert(!resolver_cli_main(2, status) && cli_calls == 1 && cli_request.operation == RS_STATUS);
    struct rs_reply reply; assert(!rs_reply_parse(cli_output, cli_output_size, &reply) && reply.operation == RS_STATUS);
    cli_reset(); assert(!resolver_cli_main(3, lookup) && cli_calls == 1 && !strcmp(cli_request.name, "localhost"));
    assert(!rs_reply_parse(cli_output, cli_output_size, &reply) && reply.source == RS_HOSTS);
    char *numeric[] = {"resolvectl", "lookup", "192.0.2.9", 0};
    cli_reset(); assert(!resolver_cli_main(3, numeric) && cli_calls == 1);
    assert(!rs_reply_parse(cli_output, cli_output_size, &reply) && reply.source == RS_NUMERIC);
    char *bad[] = {"resolvectl", "lookup", "01.2.3.4", 0};
    cli_reset(); assert(resolver_cli_main(3, bad) == 2 && !cli_calls);
    cli_reset(); assert(resolver_cli_main(1, status) == 2 && !cli_calls);
    cli_reset(); cli_error = 1; cli_stream = stderr;
    assert(resolver_cli_main(2, status) == 1 && cli_calls == 1);
    assert(!rs_reply_parse(cli_output, cli_output_size, &reply) && reply.error == ENOENT);
    cli_reset(); cli_transport_error = 1; assert(resolver_cli_main(2, status) == 1 && !cli_output_size);
    cli_reset(); cli_output_error = 1; assert(resolver_cli_main(2, status) == 1 && !cli_output_size);
}

int main(void)
{
    parser_tests(); hosts_parser_tests(); file_admission_tests(); dispatch_tests();
    server_tests(); endpoint_tests(); ready_tests(); client_tests(); daemon_entry_tests(); cli_entry_tests();
    puts("resolver service actual-code fault controls passed (10 groups)"); return 0;
}
