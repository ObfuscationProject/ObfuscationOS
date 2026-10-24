#include "../../apps/time/time_service.h"
#include "native_fixture_record.h"
#include <ok/socket.h>
#include <signal.h>
#include <sys/wait.h>
#include <time.h>

/* Explicit native integration fixture. Never staged as an ordinary program. */
static int raw_fd = -1;
static uint32_t daemon_pid;

static int failure(unsigned code)
{
    if (raw_fd >= 0) { (void)close(raw_fd); raw_fd = -1; }
    struct native_fixture_record record = {0};
    nf_text(&record, "NATIVE_TIME_FAIL code="); nf_number(&record, code);
    nf_text(&record, "\n"); (void)nf_emit(&record);
    return (int)code;
}

static int pause_briefly(void)
{
    const struct timespec delay = {0, 10000000};
    return nanosleep(&delay, 0) < 0 && errno != EINTR ? -1 : 0;
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

static int budget(uint64_t start, uint64_t *last, uint64_t limit)
{
    uint64_t now;
    if (milliseconds(&now) || now < *last || now - start >= limit) return -1;
    *last = now;
    return 0;
}

static int ordered(const struct timespec *left, const struct timespec *right)
{
    return left->tv_sec < right->tv_sec ||
        (left->tv_sec == right->tv_sec && left->tv_nsec <= right->tv_nsec);
}

/* Compare the public response to actual syscalls around this exchange. */
static int status(struct ts_reply *reply)
{
    struct timespec mono_before, mono_after, real_before = {0}, real_after = {0};
    if (clock_gettime(CLOCK_MONOTONIC, &mono_before)) return -1;
    int before_error = clock_gettime(CLOCK_REALTIME, &real_before) ? errno : 0;
    struct ts_request request = {.operation = TS_STATUS}; struct ts_buffer wire;
    if (ts_exchange(&request, &wire, reply) || reply->operation != TS_STATUS ||
        reply->pid <= 1 || (daemon_pid && reply->pid != daemon_pid)) return -1;
    int after_error = clock_gettime(CLOCK_REALTIME, &real_after) ? errno : 0;
    if (clock_gettime(CLOCK_MONOTONIC, &mono_after)) return -1;
    const struct timespec reported_mono = {reply->monotonic_seconds, reply->monotonic_nanoseconds};
    const struct timespec reported_real = {reply->realtime_seconds, reply->realtime_nanoseconds};
    if (!ordered(&mono_before, &reported_mono) || !ordered(&reported_mono, &mono_after)) return -1;
    if (before_error || after_error) {
        if (before_error != after_error || reply->realtime_error != before_error ||
            reply->realtime_seconds || reply->realtime_nanoseconds) return -1;
    } else if (reply->realtime_error || !ordered(&real_before, &reported_real) ||
               !ordered(&reported_real, &real_after)) return -1;
    return 0;
}

static int unchanged(uint64_t updates)
{
    struct ts_reply reply;
    return status(&reply) || reply.manual_updates != updates ? -1 : 0;
}

static int raw_open(void)
{
    if (raw_fd >= 0) return -1;
    uint64_t start, last;
    if (milliseconds(&start)) return -1;
    last = start;
    raw_fd = ok_socket(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC, 0);
    if (raw_fd < 0) return -1;
    struct ok_sockaddr_un address = {.family = OK_AF_UNIX};
    memcpy(address.path, TS_PATH, sizeof(TS_PATH));
    for (;;) {
        if (budget(start, &last, 1500)) return -1;
        if (!ok_connect(raw_fd, &address, (ok_socklen_t)(2 + sizeof(TS_PATH))) || errno == EISCONN) break;
        if ((errno != EAGAIN && errno != EINTR) || pause_briefly()) return -1;
    }
    struct ok_ucred peer = {0}; ok_socklen_t size = sizeof(peer);
    return ok_getsockopt(raw_fd, OK_SOL_SOCKET, OK_SO_PEERCRED, &peer, &size) ||
        size != sizeof(peer) || peer.pid != (int32_t)daemon_pid || peer.uid ? -1 : 0;
}

static int raw_send(const char *bytes, size_t size)
{
    uint64_t start, last;
    if (milliseconds(&start)) return -1;
    last = start;
    size_t sent = 0;
    while (sent < size) {
        if (budget(start, &last, 1500)) return -1;
        struct ok_iovec vector = {(uintptr_t)(bytes + sent), size - sent};
        struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
        ssize_t count = ok_sendmsg(raw_fd, &message, OK_MSG_DONTWAIT | OK_MSG_NOSIGNAL);
        if (count > 0 && (size_t)count <= size - sent) sent += (size_t)count;
        else if (count >= 0 || (errno != EAGAIN && errno != EINTR)) return -1;
        else if (pause_briefly()) return -1;
    }
    return 0;
}

static int raw_finish(struct ts_reply *reply)
{
    uint64_t start, last;
    if (milliseconds(&start)) return -1;
    last = start;
    struct ts_buffer wire = {0};
    for (;;) {
        if (budget(start, &last, 1500)) return -1;
        char excess;
        struct ok_iovec vector = {(uintptr_t)(wire.size == sizeof(wire.bytes) ? &excess : wire.bytes + wire.size),
            wire.size == sizeof(wire.bytes) ? 1 : sizeof(wire.bytes) - wire.size};
        struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
        ssize_t count = ok_recvmsg(raw_fd, &message, OK_MSG_DONTWAIT);
        if (message.flags || message.control_length) return -1;
        if (count > 0) {
            if ((size_t)count > vector.length || wire.size == sizeof(wire.bytes)) return -1;
            wire.size += (size_t)count;
        } else if (!count) {
            if (close(raw_fd)) return -1;
            raw_fd = -1;
            if (!wire.size) { *reply = (struct ts_reply){.operation = TS_INVALID}; return 0; }
            return ts_reply_parse(wire.bytes, wire.size, reply);
        } else if ((errno != EAGAIN && errno != EINTR) || pause_briefly()) return -1;
    }
}

static int malformed(uint64_t updates)
{
    const char *requests[] = {
        "OKT1 STATUS\r\n", "OKT1 SET 4100000000 0\nOKT1 SET 4200000000 0\n",
        "OKT1 SET 4000000000 1000000000\n", "OKT1 SET 04000000000 0\n",
        "OKT1 SET 8277292036 0\n", "OKT1 SET -1 0\n"
    };
    for (size_t i = 0; i < sizeof(requests) / sizeof(requests[0]); ++i) {
        struct ts_reply reply;
        if (raw_open() || raw_send(requests[i], strlen(requests[i])) || raw_finish(&reply) ||
            reply.operation != TS_INVALID || unchanged(updates)) return -1;
    }
    if (raw_open() || raw_send("OKT1 STA", 8) || pause_briefly() || pause_briefly() ||
        raw_send("TUS\n", 4)) return -1;
    struct ts_reply reply;
    if (raw_finish(&reply) || reply.operation != TS_STATUS || reply.pid != daemon_pid ||
        reply.manual_updates != updates || unchanged(updates)) return -1;
    /* Disconnect an unfinished client, then prove the endpoint still works. */
    if (raw_open() || raw_send("OKT1 S", 6) || close(raw_fd)) return -1;
    raw_fd = -1;
    if (unchanged(updates)) return -1;
    return nf_marker("NATIVE_TIME_TRANSPORT malformed=6 malformed_eof=pass fragments=pass disconnected=pass mutation=unchanged\n");
}

static int actual_time(int64_t seconds)
{
    struct timespec value;
    return clock_gettime(CLOCK_REALTIME, &value) || value.tv_sec < seconds ||
        value.tv_sec > seconds + 3 || value.tv_nsec < 0 || value.tv_nsec >= 1000000000 ? -1 : 0;
}

/* Exercise the server deadline while real kernel wall time steps both ways.
 * External setters must not change the daemon-local manual commit counter. */
static int fixed_deadline(uint64_t updates)
{
    if (raw_open() || raw_send("OKT1 STA", 8)) return -1;
    uint64_t start, last, activity = 0;
    if (milliseconds(&start)) return -1;
    last = start;
    unsigned steps = 0;
    for (;;) {
        uint64_t now;
        if (milliseconds(&now) || now < last || now - start > 1400) return -1;
        last = now;
        if (!steps && now - start >= 200) {
            const struct timespec forward = {4200000000, 123456789};
            if (now - start >= 450 || clock_settime(CLOCK_REALTIME, &forward) || actual_time(forward.tv_sec)) return -1;
            steps = 1;
        }
        if (steps == 1 && now - start >= 500) {
            const struct timespec backward = {4000000000, 987654321};
            if (now - start >= 700 || clock_settime(CLOCK_REALTIME, &backward) || actual_time(backward.tv_sec)) return -1;
            steps = 2;
        }
        if (!activity && now - start >= 650) {
            if (now - start >= 800 || raw_send("T", 1)) return -1;
            activity = now - start;
        }
        char byte;
        struct ok_iovec vector = {(uintptr_t)&byte, 1};
        struct ok_msghdr message = {0}; message.vectors = (uintptr_t)&vector; message.vector_count = 1;
        ssize_t count = ok_recvmsg(raw_fd, &message, OK_MSG_DONTWAIT);
        if (message.flags || message.control_length) return -1;
        if (!count) {
            if (steps != 2 || !activity || now - start < 850 || now - start > 1400 || close(raw_fd)) return -1;
            raw_fd = -1;
            if (unchanged(updates)) return -1;
            struct native_fixture_record record = {0};
            nf_text(&record, "NATIVE_TIME_DEADLINE elapsed_ms="); nf_number(&record, now - start);
            nf_text(&record, " activity_ms="); nf_number(&record, activity);
            nf_text(&record, " bound_ms=1400 wall_forward=pass wall_backward=pass external_counter=unchanged\n");
            return nf_emit(&record);
        }
        if (count > 0 || (errno != EAGAIN && errno != EINTR) || pause_briefly()) return -1;
    }
}

static int permanent_ids(void)
{
    uid_t users[3]; gid_t groups[3];
    if (getresuid(users, users + 1, users + 2) || getresgid(groups, groups + 1, groups + 2) ||
        users[0] != 1000 || users[1] != 1000 || users[2] != 1000 ||
        groups[0] != 1000 || groups[1] != 1000 || groups[2] != 1000 ||
        getuid() != 1000 || geteuid() != 1000 || getgid() != 1000 || getegid() != 1000) return -1;
    errno = 0;
    if (setuid(0) != -1 || errno != EPERM) return -1;
    errno = 0;
    if (setgid(0) != -1 || errno != EPERM) return -1;
    return 0;
}

static int wait_child(pid_t child)
{
    uint64_t start, last;
    if (milliseconds(&start)) goto cancel;
    last = start;
    for (;;) {
        int state = 0; pid_t found = waitpid(child, &state, WNOHANG);
        if (found == child) return WIFEXITED(state) && !WEXITSTATUS(state) ? 0 : -1;
        if (found < 0 && errno != EINTR) goto cancel;
        if (budget(start, &last, 5000) || pause_briefly()) goto cancel;
    }
cancel: {
    /* A failed qualifier still consumes its child; never leave an orphan. */
    int sent;
    do { sent = kill(child, SIGKILL); } while (sent < 0 && errno == EINTR);
    int error = sent < 0 ? errno : 0;
    int state; pid_t found;
    do { found = waitpid(child, &state, 0); } while (found < 0 && errno == EINTR);
    if (found != child || (error && error != ESRCH))
        (void)nf_marker("NATIVE_TIME_FAIL code=child-cleanup\n");
    return -1;
    }
}

static int denied_child(uint64_t updates)
{
    pid_t child = fork();
    if (child < 0) return -1;
    if (!child) {
        if (setresgid(1000, 1000, 1000) || setresuid(1000, 1000, 1000) || permanent_ids() ||
            unchanged(updates)) _Exit(failure(21));
        struct ts_request request = {TS_SET, 5000000000, 0};
        struct ts_reply reply; struct ts_buffer wire;
        if (ts_exchange(&request, &wire, &reply) || reply.operation != TS_ERROR || reply.error != EPERM ||
            unchanged(updates) || permanent_ids()) _Exit(failure(22));
        if (nf_marker("NATIVE_TIME_DENIED uid=1000 euid=1000 gid=1000 egid=1000 saved=1000 regain=denied status=public set=EPERM\n"))
            _Exit(failure(23));
        _Exit(0);
    }
    return wait_child(child) || unchanged(updates) ? -1 : 0;
}

static int root_set(int64_t seconds, uint64_t updates)
{
    struct ts_request request = {TS_SET, seconds, 123456789};
    struct ts_reply reply; struct ts_buffer wire;
    if (ts_exchange(&request, &wire, &reply) || reply.operation != TS_SET ||
        reply.pid != daemon_pid || reply.manual_updates != updates || actual_time(seconds) ||
        unchanged(updates)) return -1;
    return 0;
}

int main(void)
{
    if (getuid() || geteuid() || getgid() || getegid()) return failure(1);
    struct ts_reply initial;
    if (status(&initial) || initial.manual_updates > UINT64_MAX - 2) return failure(2);
    daemon_pid = initial.pid;
    struct native_fixture_record record = {0};
    nf_text(&record, "NATIVE_TIME_STATUS pid="); nf_number(&record, daemon_pid);
    nf_text(&record, " initial_realtime_errno="); nf_number(&record, (unsigned)initial.realtime_error);
    nf_text(&record, " initial_manual_updates="); nf_number(&record, initial.manual_updates);
    nf_text(&record, " public=pass actual_clock=pass\n");
    if (nf_emit(&record)) return failure(3);
    if (malformed(initial.manual_updates)) return failure(4);
    if (fixed_deadline(initial.manual_updates)) return failure(5);
    if (denied_child(initial.manual_updates)) return failure(6);
    if (root_set(4200000030, initial.manual_updates + 1) ||
        root_set(4000000030, initial.manual_updates + 2)) return failure(7);
    return nf_marker("NATIVE_TIME_PASS public_status=pass native_permanent_drop=pass malformed=pass fragments=pass fixed_monotonic_deadline=pass actual_set_forward=pass actual_set_backward=pass post2038=pass children=reaped\n")
        ? failure(8) : 0;
}
