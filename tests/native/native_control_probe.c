#include "../../apps/init/native_control_client.h"
#include "native_fixture_record.h"
#include <signal.h>
#include <ok/socket.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <time.h>

/* Native fixture only: the retained qualifier installs this explicitly. */
static int raw_owned = -1, held_owned = -1;
static int failure(unsigned code)
{
    if (raw_owned >= 0) { (void)close(raw_owned); raw_owned = -1; }
    if (held_owned >= 0) { (void)close(held_owned); held_owned = -1; }
    struct native_fixture_record record = {0};
    nf_text(&record, "NATIVE_CONTROL_FAIL code="); nf_number(&record, code); nf_text(&record, "\n");
    (void)nf_emit(&record); return (int)code;
}
static void pause_briefly(void)
{
    const struct timespec delay = {0, 10000000};
    (void)nanosleep(&delay, 0);
}
static int snapshot(struct nc_status *provider, struct nc_status *dependent)
{
    struct nc_buffer reply;
    if (nc_exchange(NC_PREFIX "STATUS\n", sizeof(NC_PREFIX "STATUS\n") - 1, &reply) ||
        nc_snapshot(&reply, "provider", provider) || nc_snapshot(&reply, "dependent", dependent)) return -1;
    return 0;
}
static int ready(const struct nc_status *row)
{ return row->pid > 1 && !strcmp(row->phase, "ready"); }
static int same(const struct nc_status *left, const struct nc_status *right)
{ return left->pid == right->pid && left->generation == right->generation && !strcmp(left->phase, right->phase); }
static int wait_child(pid_t child)
{
    for (unsigned i = 0; i < 500; ++i) {
        int status = 0; pid_t found = waitpid(child, &status, WNOHANG);
        if (found == child) return WIFEXITED(status) && !WEXITSTATUS(status) ? 0 : -1;
        if (found < 0 && errno != EINTR) return -1;
        pause_briefly();
    }
    (void)kill(child, SIGKILL); (void)waitpid(child, 0, 0); return -1;
}
static int cli(const char *operation, const char *service)
{
    pid_t child = fork();
    if (child < 0) return -1;
    if (!child) {
        char *arguments[] = {"/bin/service-ctl", (char *)operation, (char *)service, 0};
        char *environment[] = {"PATH=/bin", "HOME=/", 0};
        execve(arguments[0], arguments, environment); _Exit(failure(89));
    }
    return wait_child(child);
}
static int denied_child(void)
{
    pid_t child = fork();
    if (child < 0) return -1;
    if (!child) {
        char *arguments[] = {"/bin/native-control-drop", 0};
        char *environment[] = {"PATH=/bin", "HOME=/", 0};
        execve(arguments[0], arguments, environment); _Exit(failure(90));
    }
    return wait_child(child);
}
static int raw_open(void)
{
    raw_owned = ok_socket(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC, 0);
    if (raw_owned < 0) return -1;
    struct ok_sockaddr_un address = {.family = OK_AF_UNIX};
    memcpy(address.path, NC_PATH, sizeof(NC_PATH));
    int connected = 0;
    for (unsigned i = 0; i < 100; ++i) {
        if (!ok_connect(raw_owned, &address, (ok_socklen_t)(2 + sizeof(NC_PATH)))) { connected = 1; break; }
        if (errno != EAGAIN && errno != EINTR) return -1;
        pause_briefly();
    }
    struct ok_ucred peer = {0}; ok_socklen_t length = sizeof(peer);
    return !connected || ok_getsockopt(raw_owned, OK_SOL_SOCKET, OK_SO_PEERCRED, &peer, &length) ||
        length != sizeof(peer) || peer.pid != 1 || peer.uid ? -1 : 0;
}
static int raw_send(const char *bytes, size_t size)
{
    size_t sent = 0;
    for (unsigned i = 0; i < 100 && sent < size; ++i) {
        struct ok_iovec vector = {(uintptr_t)(bytes + sent), size - sent};
        struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
        ssize_t count = ok_sendmsg(raw_owned, &message, OK_MSG_DONTWAIT | OK_MSG_NOSIGNAL);
        if (count > 0 && (size_t)count <= size - sent) sent += (size_t)count;
        else if (count >= 0 || (errno != EINTR && errno != EAGAIN)) return -1;
        if (sent < size) pause_briefly();
    }
    return sent == size ? 0 : -1;
}
static int raw_finish(struct nc_buffer *reply)
{
    *reply = (struct nc_buffer){0};
    for (unsigned i = 0; i < 200; ++i) {
        if (reply->size == sizeof(reply->bytes)) return -1;
        struct ok_iovec vector = {(uintptr_t)(reply->bytes + reply->size), sizeof(reply->bytes) - reply->size};
        struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
        ssize_t count = ok_recvmsg(raw_owned, &message, OK_MSG_DONTWAIT);
        if (message.flags || message.control_length) return -1;
        if (count > 0 && (size_t)count <= vector.length) reply->size += (size_t)count;
        else if (!count) { int result = close(raw_owned); raw_owned = -1; return result; }
        else if (count > 0 || (errno != EINTR && errno != EAGAIN)) return -1;
        if (count < 0) pause_briefly();
    }
    return -1;
}
static int milliseconds(uint64_t *value)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) || now.tv_sec < 0 ||
        now.tv_nsec < 0 || now.tv_nsec >= 1000000000 ||
        (uint64_t)now.tv_sec > (UINT64_MAX - 999) / 1000) return -1;
    *value = (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000;
    return 0;
}
static int fixed_deadline(void)
{
    if (raw_open() || raw_send("O", 1)) return -1;
    uint64_t start, last, activity = 0;
    if (milliseconds(&start)) return -1;
    last = start;
    for (;;) {
        uint64_t now;
        if (milliseconds(&now) || now < last || now - start > 1200) return -1;
        last = now;
        if (!activity && now - start >= 600) {
            if (now - start >= 900 || raw_send("K", 1)) return -1;
            activity = now - start;
        }
        char byte;
        struct ok_iovec vector = {(uintptr_t)&byte, 1};
        struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
        ssize_t count = ok_recvmsg(raw_owned, &message, OK_MSG_DONTWAIT);
        if (!count) {
            if (message.flags || message.control_length || !activity || now - start < 900 || close(raw_owned))
                return -1;
            raw_owned = -1;
            struct native_fixture_record record = {0};
            nf_text(&record, "NATIVE_CONTROL_DEADLINE elapsed_ms="); nf_number(&record, now - start);
            nf_text(&record, " activity_ms="); nf_number(&record, activity);
            nf_text(&record, " bound_ms=1200\n"); return nf_emit(&record);
        }
        if (count > 0 || (errno != EAGAIN && errno != EINTR) || message.flags || message.control_length) return -1;
        pause_briefly();
    }
}
static int transport(const struct nc_status *provider, const struct nc_status *dependent)
{
    struct nc_buffer reply; struct nc_status observed[2];
    const char malformed[] = NC_PREFIX "STATUS\r\n", expected[] = NC_PREFIX "ERROR code=protocol\nEND\n";
    if (raw_open() || raw_send(malformed, sizeof(malformed) - 1) || raw_finish(&reply) ||
        reply.size != sizeof(expected) - 1 || memcmp(reply.bytes, expected, reply.size)) return -1;
    if (raw_open() || raw_send(NC_PREFIX "STA", sizeof(NC_PREFIX "STA") - 1)) return -1;
    pause_briefly(); pause_briefly();
    if (raw_send("TUS\n", 4) || raw_finish(&reply) || nc_snapshot(&reply, "provider", &observed[0]) ||
        nc_snapshot(&reply, "dependent", &observed[1]) || !same(provider, &observed[0]) || !same(dependent, &observed[1])) return -1;
    if (raw_open() || raw_send("O", 1)) return -1;
    if (close(raw_owned)) return -1;
    raw_owned = -1;
    if (fixed_deadline() || snapshot(&observed[0], &observed[1]) ||
        !same(provider, &observed[0]) || !same(dependent, &observed[1])) return -1;
    return nf_marker("NATIVE_CONTROL_TRANSPORT malformed=pass partial=pass deadline=pass disconnected=pass\n");
}
static int generation(const char *name, const struct nc_status *old, const struct nc_status *next)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "NATIVE_CONTROL_GENERATION service="); nf_text(&record, name);
    nf_text(&record, " old_pid="); nf_number(&record, old->pid);
    nf_text(&record, " new_pid="); nf_number(&record, next->pid);
    nf_text(&record, " old_generation="); nf_number(&record, old->generation);
    nf_text(&record, " new_generation="); nf_number(&record, next->generation);
    nf_text(&record, "\n"); return nf_emit(&record);
}
int main(int argc, char **argv)
{
    struct nc_status before[2], after[2]; struct nc_buffer reply;
    int denied = argc == 2 && !strcmp(argv[1], "denied");
    if ((argc != 1 && !denied) || (denied ? (getuid() != 1000 || geteuid() != 1000 || getgid() != 1000 || getegid() != 1000) : geteuid() != 0)) return failure(80);
    int found = 0;
    for (unsigned i = 0; i < 500; ++i) {
        if (!snapshot(&before[0], &before[1]) && ready(&before[0]) && ready(&before[1]) &&
            before[0].generation == 2 && before[1].generation == 2) { found = 1; break; }
        pause_briefly();
    }
    if (!found) return failure(81);
    if (denied) {
        const char expected[] = NC_PREFIX "ERROR code=denied\nEND\n";
        if (nc_exchange(NC_PREFIX "RESTART provider\n", sizeof(NC_PREFIX "RESTART provider\n") - 1, &reply) != 1 ||
            reply.size != sizeof(expected) - 1 || memcmp(reply.bytes, expected, reply.size) ||
            snapshot(&after[0], &after[1]) || !same(&before[0], &after[0]) || !same(&before[1], &after[1]) || cli("status", "provider")) return failure(82);
        return nf_marker("NATIVE_CONTROL_DENIED uid=nonroot status=public mutation=unchanged\n") ? failure(83) : 0;
    }
    const char unknown[] = NC_PREFIX "ERROR code=unknown-service\nEND\n";
    if (nc_exchange(NC_PREFIX "RESTART no-such-service\n", sizeof(NC_PREFIX "RESTART no-such-service\n") - 1, &reply) != 1 ||
        reply.size != sizeof(unknown) - 1 || memcmp(reply.bytes, unknown, reply.size) ||
        snapshot(&after[0], &after[1]) || !same(&before[0], &after[0]) || !same(&before[1], &after[1])) return failure(84);
    if (denied_child() || transport(&before[0], &before[1])) return failure(91);
    /* Keep an incomplete accepted client open while PID1 forks replacements. */
    if (raw_open() || raw_send("O", 1)) return failure(92);
    held_owned = raw_owned; raw_owned = -1;
    if (cli("status", "provider") || cli("restart", "provider")) return failure(85);
    found = 0;
    for (unsigned i = 0; i < 500; ++i) {
        if (!snapshot(&after[0], &after[1]) && ready(&after[0]) && ready(&after[1]) &&
            after[0].generation == before[0].generation + 1 && after[1].generation == before[1].generation + 1 &&
            after[0].pid != before[0].pid && after[1].pid != before[1].pid) { found = 1; break; }
        pause_briefly();
    }
    if (close(held_owned)) return failure(93);
    held_owned = -1;
    if (!found || cli("status", "dependent")) return failure(86);
    if (generation("provider", &before[0], &after[0]) || generation("dependent", &before[1], &after[1])) return failure(87);
    return nf_marker("NATIVE_CONTROL_PASS status=public root_restart=accepted dependency_replacement=pass unknown=unchanged\n") ? failure(88) : 0;
}
