#include "native_control.h"
#include <errno.h>
#include <ok/socket.h>
#include <ok/syscall.h>
#include <ok/power.h>
#include <sys/stat.h>
#include <unistd.h>

static uint32_t nc_power_action(enum nc_operation operation)
{
    switch (operation) {
    case NC_HALT: return OK_POWER_HALT;
    case NC_REBOOT: return OK_POWER_REBOOT;
    case NC_POWEROFF: return OK_POWER_POWEROFF;
    default: return 0;
    }
}

int nc_begin_power(struct service_graph *graph, struct nc_lifecycle *lifecycle,
                   enum nc_operation operation, uint64_t now)
{
    const uint32_t action = nc_power_action(operation);
    if (!action) { errno = EINVAL; return -1; }
    if (graph->failed || lifecycle->failed) { errno = EBUSY; return -1; }
    if (lifecycle->power_requested) {
        if (lifecycle->power_operation == operation) return 0;
        errno = EBUSY; return -1;
    }
    /* A prior service-only quiescence cannot be upgraded after its boundary. */
    if (lifecycle->requested || graph->stopping || !sg_time_budget(now, NC_QUIESCE_MS)) {
        errno = EBUSY; return -1;
    }
    int token = ok_power_prepare(action);
    if (token < 0) return -1;
    if (!token || (uint32_t)token > OK_POWER_TOKEN_MAX) { errno = EIO; return -1; }
    /* The actor cannot change graph state while PREPARE is in progress. Keep
     * the original start/deadline even if the syscall consumed wall time. */
    if (nc_begin_quiesce(graph, lifecycle, now)) { errno = EIO; return -1; }
    lifecycle->power_token = (uint32_t)token;
    lifecycle->power_operation = operation;
    lifecycle->power_requested = 1;
    return 0;
}

int nc_commit_power(const struct nc_lifecycle *lifecycle)
{
    if (!nc_power_action(lifecycle->power_operation) ||
        !lifecycle->power_requested || !lifecycle->completed || lifecycle->failed ||
        lifecycle->power_committed || lifecycle->children != NC_CHILDREN_EMPTY ||
        !lifecycle->power_token || lifecycle->power_token > OK_POWER_TOKEN_MAX) { errno = EBUSY; return -1; }
    return ok_power_commit(lifecycle->power_token);
}

static const char *nc_phase(enum sg_phase phase)
{
    static const char *const names[] = {"wait", "reserved", "starting", "ready", "retiring", "stopped", "failed"};
    return (unsigned)phase < sizeof(names) / sizeof(names[0]) ? names[phase] : "invalid";
}
static void nc_error(struct nc_buffer *reply, const char *reason)
{
    *reply = (struct nc_buffer){0};
    nc_text(reply, NC_PREFIX "ERROR code="); nc_text(reply, reason); nc_text(reply, "\nEND\n");
}
static void nc_identity(struct nc_buffer *reply, const struct service_graph *graph, unsigned i)
{
    nc_text(reply, "service="); nc_text(reply, graph->specs[i].name);
    nc_text(reply, " pid="); nc_number(reply, (unsigned)graph->services[i].pid);
    nc_text(reply, " generation="); nc_number(reply, graph->services[i].generation);
}
void nc_dispatch(struct service_graph *graph, struct nc_lifecycle *lifecycle,
                 uint32_t uid, const char *bytes, size_t size,
                 uint64_t now, struct nc_buffer *reply)
{
    *reply = (struct nc_buffer){0};
    struct nc_request request = nc_parse(bytes, size);
    if (request.operation == NC_INVALID) { nc_error(reply, "protocol"); return; }
    unsigned index = graph->count;
    if (request.service[0]) {
        for (unsigned i = 0; i < graph->count; ++i)
            if (sg_equal(request.service, graph->specs[i].name)) { index = i; break; }
    }
    /* Authenticate mutation before revealing its target or changing graph state. */
    if ((request.operation == NC_RESTART || request.operation == NC_QUIESCE || request.operation == NC_HALT ||
         request.operation == NC_REBOOT || request.operation == NC_POWEROFF) && uid != 0) {
        nc_error(reply, "denied"); return;
    }
    if (request.service[0] && index == graph->count) { nc_error(reply, "unknown-service"); return; }
    if (nc_power_action(request.operation)) {
        if (nc_begin_power(graph, lifecycle, request.operation, now)) {
            nc_error(reply, errno == EOPNOTSUPP || errno == ENOSYS ? "unsupported" :
                errno == EPERM || errno == EACCES ? "denied" : "busy");
            return;
        }
        switch (request.operation) {
        case NC_HALT: nc_text(reply, NC_PREFIX "HALT accepted=1 started_ms="); break;
        case NC_REBOOT: nc_text(reply, NC_PREFIX "REBOOT accepted=1 started_ms="); break;
        case NC_POWEROFF: nc_text(reply, NC_PREFIX "POWEROFF accepted=1 started_ms="); break;
        default: nc_error(reply, "protocol"); return;
        }
        nc_number(reply, lifecycle->started_ms);
        nc_text(reply, " deadline_ms="); nc_number(reply, lifecycle->deadline_ms); nc_text(reply, "\nEND\n");
    } else if (request.operation == NC_QUIESCE) {
        if (nc_begin_quiesce(graph, lifecycle, now)) { nc_error(reply, "busy"); return; }
        nc_text(reply, NC_PREFIX "QUIESCE accepted=1 started_ms="); nc_number(reply, lifecycle->started_ms);
        nc_text(reply, " deadline_ms="); nc_number(reply, lifecycle->deadline_ms); nc_text(reply, "\nEND\n");
    } else if (request.operation == NC_STATE) {
        if (graph->failed || lifecycle->failed || (lifecycle->completed && (!sg_stopped(graph) || lifecycle->children != NC_CHILDREN_EMPTY))) {
            nc_error(reply, "busy"); return;
        }
        nc_text(reply, NC_PREFIX "STATE phase=");
        nc_text(reply, lifecycle->completed ? "quiesced" : lifecycle->requested ? "quiescing" : "running");
        nc_text(reply, " graph="); nc_text(reply, !graph->stopping ? "running" : sg_stopped(graph) ? "stopped" : "stopping");
        nc_text(reply, " children=");
        nc_text(reply, lifecycle->children == NC_CHILDREN_EMPTY ? "empty" :
            lifecycle->children == NC_CHILDREN_LIVE ? "live" : "unknown");
        nc_text(reply, " started_ms="); nc_number(reply, lifecycle->started_ms);
        nc_text(reply, " deadline_ms="); nc_number(reply, lifecycle->deadline_ms); nc_text(reply, "\nEND\n");
    } else if (request.operation == NC_RESTART) {
        struct sg_service *service = &graph->services[index];
        if (graph->failed || graph->stopping || (service->phase != SG_READY && service->phase != SG_STARTING)) {
            nc_error(reply, "busy"); return;
        }
        nc_text(reply, NC_PREFIX "ACCEPTED "); nc_identity(reply, graph, index); nc_text(reply, "\nEND\n");
        /* Existing retirement owns TERM/KILL, exact reap, backoff and dependent
         * withdrawal. ACCEPTED does not promise a new generation is ready. */
        sg_retire(service, SG_CRASH, now);
        if (!service->pid) service->next_ms = now;
        sg_settle(graph, now);
    } else {
        nc_text(reply, NC_PREFIX "STATUS\n");
        for (unsigned i = 0; i < graph->count; ++i) {
            if (request.service[0] && index != i) continue;
            nc_text(reply, "SERVICE "); nc_identity(reply, graph, i);
            nc_text(reply, " phase="); nc_text(reply, nc_phase(graph->services[i].phase));
            nc_text(reply, " mode="); nc_text(reply, graph->specs[i].mode == SG_SIMPLE ? "simple" :
                graph->specs[i].mode == SG_NOTIFY ? "notify" : "oneshot");
            nc_text(reply, " next_ms="); nc_number(reply, graph->services[i].next_ms);
            nc_text(reply, " launches="); nc_number(reply, graph->services[i].launches);
            nc_text(reply, "\n");
        }
        nc_text(reply, "END\n");
    }
    if (reply->failed) nc_error(reply, "capacity");
}

void nc_reset(struct native_control *control)
{
    *control = (struct native_control){.listener = -1};
    for (unsigned i = 0; i < NC_CLIENTS; ++i) control->clients[i].fd = -1;
}
static int nc_drop(struct nc_client *client)
{
    int fd = client->fd; client->fd = -1;
    return fd < 0 ? 0 : close(fd);
}
int nc_close(struct native_control *control)
{
    int failed = 0;
    for (unsigned i = 0; i < NC_CLIENTS; ++i) if (nc_drop(&control->clients[i]) < 0) failed = 1;
    int fd = control->listener; control->listener = -1;
    if (fd >= 0 && close(fd) < 0) failed = 1;
    return failed ? -1 : 0;
}
int nc_open(struct native_control *control)
{
    if (control->listener >= 0) { errno = EBUSY; return -1; }
    if (getpid() != 1 || geteuid() != 0) { errno = EPERM; return -1; }
    struct stat metadata;
    if (lstat("/run", &metadata) < 0) return -1;
    if (!S_ISDIR(metadata.st_mode) || metadata.st_uid || (metadata.st_mode & 0022)) { errno = EACCES; return -1; }
    if (!lstat(NC_PATH, &metadata)) { errno = EEXIST; return -1; }
    if (errno != ENOENT) return -1;
    int fd = ok_socket(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC, 0);
    if (fd < 0) return -1;
    struct ok_sockaddr_un address = {.family = OK_AF_UNIX};
    memcpy(address.path, NC_PATH, sizeof(NC_PATH));
    /* Native bind applies umask; its existing raw operation avoids inventing a
     * chmod wrapper. Only root can create/unlink names in the checked /run. */
    long mask = ok_syscall_ret(ok_syscall1(OK_SYS_UMASK, 0111));
    if (mask < 0) { int error = errno; (void)close(fd); errno = error; return -1; }
    int bound = ok_bind(fd, &address, (ok_socklen_t)(2 + sizeof(NC_PATH))), error = errno;
    long restored = ok_syscall_ret(ok_syscall1(OK_SYS_UMASK, mask));
    if (bound < 0 || restored < 0) { if (restored < 0) error = errno; (void)close(fd); errno = error; return -1; }
    if (ok_listen(fd, NC_CLIENTS) < 0) { error = errno; (void)close(fd); errno = error; return -1; }
    /* Never unlink a preexisting pathname, including after partial setup. */
    control->listener = fd;
    return 0;
}

int nc_step(struct native_control *control, struct service_graph *graph,
            struct nc_lifecycle *lifecycle, uint64_t now)
{
    if (control->listener < 0) return 0;
    for (unsigned i = 0; i < NC_CLIENTS; ++i) {
        struct nc_client *client = &control->clients[i];
        if (client->fd >= 0 && now >= client->deadline && nc_drop(client) < 0) return -1;
        if (client->fd < 0) {
            int fd = ok_accept4(control->listener, 0, 0, OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC);
            if (fd < 0) {
                if (errno == EINTR || errno == EAGAIN || errno == EMFILE || errno == ENFILE) continue;
                return -1;
            }
            *client = (struct nc_client){.fd = fd};
            struct ok_ucred peer = {0}; ok_socklen_t length = sizeof(peer);
            if (ok_getsockopt(fd, OK_SOL_SOCKET, OK_SO_PEERCRED, &peer, &length) < 0 ||
                length != sizeof(peer) || peer.pid <= 0 || !sg_time_budget(now, NC_DEADLINE_MS)) {
                if (nc_drop(client) < 0) return -1;
                continue;
            }
            client->uid = peer.uid;
            client->deadline = now + NC_DEADLINE_MS;
        }
        if (!client->reply.size) {
            struct ok_iovec vector = {(uintptr_t)(client->request + client->used), sizeof(client->request) - client->used};
            struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
            ssize_t count = ok_recvmsg(client->fd, &message, OK_MSG_DONTWAIT);
            if (count < 0 && (errno == EINTR || errno == EAGAIN)) continue;
            if (count <= 0) { if (nc_drop(client) < 0) return -1; continue; }
            if ((size_t)count > sizeof(client->request) - client->used) { errno = EIO; return -1; }
            client->used += (size_t)count;
            /* Zero ancillary capacity publishes no received descriptors. */
            if (message.flags || message.control_length || client->used >= sizeof(client->request)) nc_error(&client->reply, "protocol");
            else {
                for (size_t j = 0; j < client->used; ++j)
                    if (client->request[j] == '\n') {
                        nc_dispatch(graph, lifecycle, client->uid, client->request, client->used, now, &client->reply);
                        break;
                    }
            }
        }
        if (client->reply.size) {
            struct ok_iovec vector = {(uintptr_t)(client->reply.bytes + client->sent), client->reply.size - client->sent};
            struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
            ssize_t count = ok_sendmsg(client->fd, &message, OK_MSG_DONTWAIT | OK_MSG_NOSIGNAL);
            if (count < 0 && (errno == EINTR || errno == EAGAIN)) continue;
            if (count <= 0) { if (nc_drop(client) < 0) return -1; continue; }
            if ((size_t)count > client->reply.size - client->sent) { errno = EIO; return -1; }
            client->sent += (size_t)count;
            if (client->sent == client->reply.size && nc_drop(client) < 0) return -1;
        }
    }
    return 0;
}
