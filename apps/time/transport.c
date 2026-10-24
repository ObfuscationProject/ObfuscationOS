#include "time_service.h"
#include <errno.h>
#include <fcntl.h>
#include <ok/socket.h>
#include <ok/syscall.h>
#include <poll.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

int ts_clock(uint64_t *milliseconds)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0) return -1;
    if (now.tv_sec < 0 || now.tv_nsec < 0 || now.tv_nsec >= 1000000000 ||
        (uint64_t)now.tv_sec > (UINT64_MAX - 999) / 1000) { errno = EOVERFLOW; return -1; }
    *milliseconds = (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000;
    return 0;
}

static int same_socket(const struct stat *a, const struct stat *b)
{
    return a->st_ino == b->st_ino && a->st_mode == b->st_mode &&
        a->st_uid == b->st_uid && a->st_gid == b->st_gid && a->st_nlink == b->st_nlink;
}

static int socket_metadata(const struct stat *s)
{
    /* Public STATUS requires a connectable socket; SET uses peer credentials. */
    if ((s->st_mode & 0170000) != 0140000 || (s->st_mode & 07777) != 0666 ||
        s->st_uid || s->st_gid || s->st_nlink != 1) { errno = EACCES; return -1; }
    return 0;
}

static int protected_dir(int fd)
{
    struct stat s;
    if (fstat(fd, &s) < 0) return -1;
    if (!S_ISDIR(s.st_mode) || s.st_uid || s.st_gid || (s.st_mode & 07022)) { errno = EACCES; return -1; }
    return 0;
}

static int open_run(void)
{
    int root = open("/", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC), run = -1, error;
    if (root < 0) return -1;
    if (protected_dir(root) < 0) goto done;
    run = openat(root, "run", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (run >= 0 && protected_dir(run) < 0) { error = errno; close(run); run = -1; errno = error; }
done:
    error = errno;
    if (close(root) < 0) { if (run >= 0) close(run); return -1; }
    errno = error;
    return run;
}

static struct ok_sockaddr_un address(void)
{
    struct ok_sockaddr_un a = {.family = OK_AF_UNIX};
    memcpy(a.path, TS_PATH, sizeof(TS_PATH));
    return a;
}

static int connect_socket(int fd)
{
    struct ok_sockaddr_un a = address();
    return ok_connect(fd, &a, (ok_socklen_t)(2 + sizeof(TS_PATH)));
}

static int new_socket(void)
{ return ok_socket(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC, 0); }

void ts_server_reset(struct ts_server *server)
{ *server = (struct ts_server){.listener = -1, .run = -1, .client = {.fd = -1}}; }

static int drop(struct ts_client *client)
{
    int fd = client->fd;
    *client = (struct ts_client){.fd = -1};
    return fd < 0 ? 0 : close(fd);
}

int ts_server_close(struct ts_server *server)
{
    int failed = drop(&server->client) < 0, fd = server->listener;
    server->listener = -1;
    if (fd >= 0 && close(fd) < 0) failed = 1;
    fd = server->run; server->run = -1;
    if (fd >= 0 && close(fd) < 0) failed = 1;
    /* Checked restart, rather than unchecked unlink, owns stale names. */
    return failed ? -1 : 0;
}

static int budget(uint64_t deadline, uint64_t *last)
{
    uint64_t now;
    if (ts_clock(&now) < 0) return -1;
    if (now < *last) { errno = EOVERFLOW; return -1; }
    *last = now;
    if (now >= deadline) { errno = EAGAIN; return -1; }
    return 0;
}

int ts_server_open(struct ts_server *server)
{
    struct stat before, after;
    uint64_t start, last;
    int probe = -1, error, bound;
    ts_server_reset(server);
    if (geteuid() || getegid()) { errno = EPERM; return -1; }
    if (ts_clock(&start) < 0) return -1;
    if (start > UINT64_MAX - TS_DEADLINE_MS) { errno = EOVERFLOW; return -1; }
    last = start;
    server->run = open_run();
    if (server->run < 0) goto fail;
    if (!fstatat(server->run, TS_NAME, &before, AT_SYMLINK_NOFOLLOW)) {
        if (socket_metadata(&before) < 0) goto fail;
        probe = new_socket();
        if (probe < 0) goto fail;
        int connected = connect_socket(probe); error = errno;
        if (close(probe) < 0) { probe = -1; goto fail; }
        probe = -1;
        if (connected >= 0 || error != ECONNREFUSED) { errno = connected >= 0 ? EADDRINUSE : error; goto fail; }
        if (budget(start + TS_DEADLINE_MS, &last) < 0) goto fail;
        if (fstatat(server->run, TS_NAME, &after, AT_SYMLINK_NOFOLLOW) < 0 || socket_metadata(&after) < 0) goto fail;
        if (!same_socket(&before, &after)) { errno = EIO; goto fail; }
        if (budget(start + TS_DEADLINE_MS, &last) < 0) goto fail;
        if (unlinkat(server->run, TS_NAME, 0) < 0) goto fail;
    } else if (errno != ENOENT) goto fail;
    if (budget(start + TS_DEADLINE_MS, &last) < 0) goto fail;
    server->listener = new_socket();
    if (server->listener < 0) goto fail;
    struct ok_sockaddr_un a = address();
    long mask = ok_syscall_ret(ok_syscall1(OK_SYS_UMASK, 0111));
    if (mask < 0) goto fail;
    bound = ok_bind(server->listener, &a, (ok_socklen_t)(2 + sizeof(TS_PATH))); error = errno;
    long restored = ok_syscall_ret(ok_syscall1(OK_SYS_UMASK, mask));
    if (bound < 0 || restored < 0) { if (restored >= 0) errno = error; goto fail; }
    if (fstatat(server->run, TS_NAME, &server->socket_identity, AT_SYMLINK_NOFOLLOW) < 0 ||
        socket_metadata(&server->socket_identity) < 0 || ok_listen(server->listener, 1) < 0 ||
        budget(start + TS_DEADLINE_MS, &last) < 0) goto fail;
    server->last = last;
    return 0;
fail:
    error = errno;
    if (probe >= 0) close(probe);
    ts_server_close(server);
    errno = error;
    return -1;
}

static ssize_t receive(int fd, void *bytes, size_t size, int peek, int *invalid)
{
    struct ok_iovec vector = {(uintptr_t)bytes, size};
    struct ok_msghdr message = {0};
    message.vectors = (uintptr_t)&vector; message.vector_count = 1;
    ssize_t count = ok_recvmsg(fd, &message, OK_MSG_DONTWAIT | (peek ? OK_MSG_PEEK : 0));
    *invalid = message.flags || message.control_length || (count > 0 && (size_t)count > size);
    return count;
}

static ssize_t send_bytes(int fd, const void *bytes, size_t size)
{
    struct ok_iovec vector = {(uintptr_t)bytes, size};
    struct ok_msghdr message = {0};
    message.vectors = (uintptr_t)&vector; message.vector_count = 1;
    return ok_sendmsg(fd, &message, OK_MSG_DONTWAIT | OK_MSG_NOSIGNAL);
}

int ts_server_step(struct ts_server *server, uint64_t now)
{
    struct ts_client *client = &server->client;
    if (now < server->last) { errno = EOVERFLOW; return -1; }
    server->last = now;
    if (client->fd >= 0 && now >= client->deadline) return drop(client);
    if (client->fd < 0) {
        if (now > UINT64_MAX - TS_DEADLINE_MS) { errno = EOVERFLOW; return -1; }
        int fd = ok_accept4(server->listener, 0, 0, OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC);
        if (fd < 0) return errno == EINTR || errno == EAGAIN || errno == EMFILE || errno == ENFILE ? 0 : -1;
        *client = (struct ts_client){.fd = fd, .deadline = now + TS_DEADLINE_MS};
        ok_socklen_t length = sizeof(client->peer);
        if (ok_getsockopt(fd, OK_SOL_SOCKET, OK_SO_PEERCRED, &client->peer, &length) < 0 ||
            length != sizeof(client->peer) || client->peer.pid <= 0) return drop(client);
    }
    if (budget(client->deadline, &server->last) < 0) return errno == EAGAIN ? drop(client) : -1;
    if (client->reply.size) {
        ssize_t count = send_bytes(client->fd, client->reply.bytes + client->sent, client->reply.size - client->sent);
        int error = errno;
        if (budget(client->deadline, &server->last) < 0) return errno == EAGAIN ? drop(client) : -1;
        errno = error;
        if (count < 0 && (errno == EINTR || errno == EAGAIN)) return 0;
        if (count <= 0) return drop(client);
        if ((size_t)count > client->reply.size - client->sent) { errno = EIO; return -1; }
        client->sent += (size_t)count;
        return client->sent == client->reply.size ? drop(client) : 0;
    }
    struct ts_request request;
    int parsed = ts_request_parse(client->request, client->used, &request), invalid = 0;
    ssize_t count;
    if (parsed < 0) return drop(client);
    if (!parsed) {
        count = receive(client->fd, client->request + client->used, sizeof(client->request) - client->used, 0, &invalid);
        if (count < 0 && (errno == EINTR || errno == EAGAIN) && !invalid) return 0;
        if (invalid || count <= 0) return drop(client);
        client->used += (size_t)count;
        parsed = ts_request_parse(client->request, client->used, &request);
        if (parsed < 0) return drop(client);
        if (!parsed) return 0;
    }
    /* Stream packets are not framing. Refuse every suffix visible before
     * dispatch; bytes arriving after dispatch cannot revoke a kernel commit. */
    unsigned char extra;
    count = receive(client->fd, &extra, 1, 1, &invalid);
    if (invalid || count > 0 || (count < 0 && errno != EAGAIN && errno != EINTR)) return drop(client);
    if (count < 0 && errno == EINTR) return 0;
    if (budget(client->deadline, &server->last) < 0) return errno == EAGAIN ? drop(client) : -1;
    struct ts_reply reply;
    ts_dispatch(&request, &client->peer, &server->manual_updates, &reply);
    /* Neither fragments nor a synchronous setter renew this fixed deadline. */
    if (budget(client->deadline, &server->last) < 0) return errno == EAGAIN ? drop(client) : -1;
    if (ts_reply_encode(&reply, &client->reply) < 0) { errno = EIO; return -1; }
    return 0;
}

int ts_ready_descriptor(char **environment)
{
    const char *value = 0;
    for (; environment && *environment; ++environment) {
        if (!strncmp(*environment, "OK_SERVICE_READY_FD=", 20)) {
            if (value) return -1;
            value = *environment + 20;
        }
    }
    uint64_t descriptor;
    if (!value || ts_unsigned(value, strlen(value), 31, &descriptor) < 0 || descriptor < 3) return -1;
    return (int)descriptor;
}

int ts_service_open(struct ts_server *server, int ready)
{
    uint64_t start, end;
    int error;
    if (ready < 3 || ready >= 32) { errno = EINVAL; return -1; }
    if (ts_clock(&start) < 0 || ts_server_open(server) < 0 || ts_clock(&end) < 0) goto fail;
    if (end < start || end - start >= 2500) { errno = EAGAIN; goto fail; }
    ssize_t count; unsigned attempts = 0;
    do { count = write(ready, "R", 1); } while (count < 0 && errno == EINTR && ++attempts < 16);
    error = errno;
    int closed = close(ready);
    if (count != 1) { errno = count < 0 ? error : EIO; return -1; }
    return closed;
fail:
    error = errno;
    if (close(ready) < 0) return -1;
    errno = error;
    return -1;
}

int ts_exchange(const struct ts_request *request, struct ts_buffer *wire, struct ts_reply *reply)
{
    struct ts_buffer frame;
    size_t sent = 0, used = 0;
    char response[TS_REPLY_BYTES + 1];
    int fd = -1, run = -1, status = -1, error;
    uint64_t start, last, deadline;
    struct stat before, after;
    if (ts_request_encode(request, &frame) < 0) { errno = EINVAL; return -1; }
    if (ts_clock(&start) < 0) return -1;
    if (start > UINT64_MAX - TS_DEADLINE_MS) { errno = EOVERFLOW; return -1; }
    last = start; deadline = start + TS_DEADLINE_MS;
    run = open_run();
    if (run < 0) goto done;
    if (fstatat(run, TS_NAME, &before, AT_SYMLINK_NOFOLLOW) < 0 || socket_metadata(&before) < 0) goto done;
    fd = new_socket();
    if (fd < 0 || connect_socket(fd) < 0) goto done;
    if (fstatat(run, TS_NAME, &after, AT_SYMLINK_NOFOLLOW) < 0) goto done;
    if (!same_socket(&before, &after)) { errno = EIO; goto done; }
    struct ok_ucred peer = {0};
    ok_socklen_t peer_size = sizeof(peer);
    if (ok_getsockopt(fd, OK_SOL_SOCKET, OK_SO_PEERCRED, &peer, &peer_size) < 0) goto done;
    if (peer_size != sizeof(peer) || peer.pid <= 1 || peer.uid || peer.gid) { errno = EACCES; goto done; }
    for (;;) {
        if (budget(deadline, &last) < 0) goto done;
        ssize_t count; int invalid = 0;
        if (sent < frame.size) {
            count = send_bytes(fd, frame.bytes + sent, frame.size - sent);
            if (count > 0 && (size_t)count <= frame.size - sent) { sent += (size_t)count; continue; }
        } else {
            count = receive(fd, response + used, sizeof(response) - used, 0, &invalid);
            if (invalid) { errno = EIO; goto done; }
            if (count > 0) {
                used += (size_t)count;
                if (used > TS_REPLY_BYTES) { errno = EIO; goto done; }
                continue;
            }
            if (!count) {
                if (budget(deadline, &last) < 0) goto done;
                if (ts_reply_parse(response, used, reply) < 0 ||
                    (reply->operation != TS_ERROR && (reply->operation != request->operation || reply->pid != (uint32_t)peer.pid))) {
                    errno = EIO; goto done;
                }
                *wire = (struct ts_buffer){.size = used};
                memcpy(wire->bytes, response, used); status = 0; goto done;
            }
        }
        if (count >= 0) { errno = EIO; goto done; }
        if (errno != EAGAIN && errno != EINTR) goto done;
        struct pollfd wait = {.fd = fd, .events = sent < frame.size ? POLLOUT : POLLIN};
        if (poll(&wait, 1, 10) < 0 && errno != EINTR) goto done;
    }
done:
    error = errno;
    if (fd >= 0 && close(fd) < 0) { error = errno; status = -1; }
    if (run >= 0 && close(run) < 0) { error = errno; status = -1; }
    errno = error;
    return status;
}
