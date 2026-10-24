#include "native_control_client.h"
#include <errno.h>
#include <ok/socket.h>
#include <time.h>
#include <unistd.h>

static int nc_clock(uint64_t *value)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0) return -1;
    if (now.tv_sec < 0 || now.tv_nsec < 0 || now.tv_nsec >= 1000000000 ||
        (uint64_t)now.tv_sec > (UINT64_MAX - 999) / 1000) { errno = EOVERFLOW; return -1; }
    *value = (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000;
    return 0;
}
static int nc_budget(uint64_t start, uint64_t *last)
{
    uint64_t now;
    if (nc_clock(&now) < 0) return -1;
    if (now < *last) { errno = EOVERFLOW; return -1; }
    *last = now;
    if (now - start >= NC_DEADLINE_MS) { errno = EAGAIN; return -1; }
    return 0;
}
static int nc_pause(void)
{
    const struct timespec pause = {0, 10000000};
    return nanosleep(&pause, 0) < 0 && errno != EINTR ? -1 : 0;
}
int nc_exchange(const char *request, size_t size, struct nc_buffer *reply)
{
    *reply = (struct nc_buffer){0};
    struct nc_request parsed = nc_parse(request, size);
    if (parsed.operation == NC_INVALID) { errno = EINVAL; return -1; }
    uint64_t start, last;
    if (nc_clock(&start) < 0) return -1;
    last = start;
    int fd = ok_socket(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC, 0);
    if (fd < 0) return -1;
    int result = -1, error;
    struct ok_sockaddr_un address = {.family = OK_AF_UNIX};
    memcpy(address.path, NC_PATH, sizeof(NC_PATH));
    for (;;) {
        if (nc_budget(start, &last) < 0) goto done;
        if (!ok_connect(fd, &address, (ok_socklen_t)(2 + sizeof(NC_PATH))) || errno == EISCONN) break;
        if (errno != EAGAIN && errno != EINTR) goto done;
        if (nc_pause() < 0) goto done;
    }
    struct ok_ucred peer = {0}; ok_socklen_t length = sizeof(peer);
    if (ok_getsockopt(fd, OK_SOL_SOCKET, OK_SO_PEERCRED, &peer, &length) < 0) goto done;
    if (length != sizeof(peer) || peer.pid != 1 || peer.uid != 0) { errno = EACCES; goto done; }
    size_t sent = 0;
    for (;;) {
        if (nc_budget(start, &last) < 0) goto done;
        struct ok_iovec vector;
        struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
        ssize_t count;
        if (sent < size) {
            vector = (struct ok_iovec){(uintptr_t)(request + sent), size - sent};
            count = ok_sendmsg(fd, &message, OK_MSG_DONTWAIT | OK_MSG_NOSIGNAL);
            if (count > 0 && (size_t)count <= size - sent) { sent += (size_t)count; continue; }
        } else {
            /* Reserve one scratch byte at capacity to distinguish exact EOF
             * from an oversized or suffixed response without accepting it. */
            char excess;
            vector = (struct ok_iovec){(uintptr_t)(reply->size == NC_REPLY_BYTES ? &excess : reply->bytes + reply->size),
                reply->size == NC_REPLY_BYTES ? 1 : NC_REPLY_BYTES - reply->size};
            count = ok_recvmsg(fd, &message, OK_MSG_DONTWAIT);
            if (message.flags || message.control_length || (count > 0 &&
                ((size_t)count > vector.length || reply->size == NC_REPLY_BYTES))) { errno = EIO; goto done; }
            if (count > 0) { reply->size += (size_t)count; continue; }
            if (!count) {
                result = nc_response(reply->bytes, reply->size);
                if (!result) {
                    struct nc_cursor in = {reply->bytes, reply->size, 0};
                    struct nc_status row;
                    if (parsed.operation == NC_RESTART) {
                        if (nc_take(&in, NC_PREFIX "ACCEPTED ") || nc_status_line(&in, &row, 0) ||
                            strcmp(row.service, parsed.service) || !row.generation) result = -1;
                    } else if (parsed.operation == NC_QUIESCE || parsed.operation == NC_HALT ||
                               parsed.operation == NC_REBOOT || parsed.operation == NC_POWEROFF) {
                        uint64_t started, deadline;
                        const char *prefix = 0;
                        switch (parsed.operation) {
                        case NC_QUIESCE: prefix = NC_PREFIX "QUIESCE accepted=1 "; break;
                        case NC_HALT: prefix = NC_PREFIX "HALT accepted=1 "; break;
                        case NC_REBOOT: prefix = NC_PREFIX "REBOOT accepted=1 "; break;
                        case NC_POWEROFF: prefix = NC_PREFIX "POWEROFF accepted=1 "; break;
                        default: break;
                        }
                        if (!prefix || nc_take(&in, prefix) || nc_quiesce_line(&in, &started, &deadline)) result = -1;
                    } else if (parsed.operation == NC_STATE) {
                        struct nc_state state;
                        if (nc_take(&in, NC_PREFIX "STATE ") || nc_state_line(&in, &state)) result = -1;
                    } else if (nc_take(&in, NC_PREFIX "STATUS\n")) result = -1;
                    else if (parsed.service[0] && (nc_take(&in, "SERVICE ") || nc_status_line(&in, &row, 1) ||
                        strcmp(row.service, parsed.service) || nc_take(&in, "END\n") || in.at != in.size)) result = -1;
                }
                if (result < 0) errno = EIO;
                goto done;
            }
        }
        if (count < 0 && (errno == EINTR || errno == EAGAIN)) {
            if (nc_pause() < 0) goto done;
            continue;
        }
        if (count >= 0) errno = EIO;
        goto done;
    }
done:
    error = errno;
    if (close(fd) < 0 && result >= 0) return -1;
    errno = error;
    return result;
}
