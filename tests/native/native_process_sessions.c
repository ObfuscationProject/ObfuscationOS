#include "native_fixture_record.h"
#include <fcntl.h>
#include <ok/syscall.h>
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>
#include <time.h>

#define SELF_PATH "/bin/native-process-sessions"

_Static_assert(OK_SYS_SETSID == 112 && OK_SYS_SETPGID == 109 &&
    OK_SYS_GETPGID == 121 && OK_SYS_GETSID == 124 && OK_SYS_GETPGRP == 111,
    "native process session syscall contract");

struct identities { pid_t pid, parent, sid, pgid; unsigned code; };
struct peer { pid_t pid; int request, reply; };
struct command { unsigned operation; pid_t other, sid, pgid; };
enum { CHECK = 1, SIBLING_REFUSALS, JOIN_GROUP, FOREIGN_GROUP, OWN_GROUP, FINISH };

static int failure(unsigned code)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_PROCESS_SESSIONS_FAIL pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " code="); nf_number(&record, code); nf_text(&record, "\n");
    (void)nf_emit(&record);
    return (int)code;
}

static int send_bytes(int fd, const void *bytes, size_t size)
{
    ssize_t count;
    do { count = write(fd, bytes, size); } while (count < 0 && errno == EINTR);
    return count == (ssize_t)size ? 0 : -1;
}

static int receive_bytes(int fd, void *bytes, size_t size)
{
    size_t used = 0;
    while (used < size) {
        struct pollfd descriptor = {fd, POLLIN, 0};
        int result;
        do { result = poll(&descriptor, 1, 5000); } while (result < 0 && errno == EINTR);
        if (result != 1 || !(descriptor.revents & POLLIN)) return -1;
        ssize_t count = read(fd, (char *)bytes + used, size - used);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0 || (size_t)count > size - used) return -1;
        used += (size_t)count;
    }
    return 0;
}

static struct identities observe(unsigned code)
{
    struct identities value = {getpid(), getppid(), getsid(0), getpgrp(), code};
    if (!code && (value.pid <= 1 || value.parent < 1 || value.sid < 1 || value.pgid < 1 ||
        getsid(value.pid) != value.sid || getpgid(0) != value.pgid || getpgid(value.pid) != value.pgid)) value.code = 90;
    return value;
}

static int expected_ids(pid_t sid, pid_t pgid)
{
    struct identities value = observe(0);
    return value.code || value.sid != sid || value.pgid != pgid ? -1 : 0;
}

static int wait_child(pid_t child)
{
    for (unsigned attempt = 0; attempt < 500; ++attempt) {
        int status = 0;
        pid_t result = waitpid(child, &status, WNOHANG);
        if (result == child) return WIFEXITED(status) && !WEXITSTATUS(status) ? 0 : -1;
        if (result < 0 && errno != EINTR) return -1;
        const struct timespec delay = {0, 10000000};
        (void)nanosleep(&delay, 0);
    }
    (void)kill(child, SIGKILL);
    (void)waitpid(child, 0, 0);
    return -1;
}

static int peer_child(int request, int reply, int foreign, pid_t inherited_sid, pid_t inherited_pgid)
{
    unsigned code = expected_ids(inherited_sid, inherited_pgid) ? 10 : 0;
    if (!code && foreign && setsid() != getpid()) code = 11;
    struct identities value = observe(code);
    if (send_bytes(reply, &value, sizeof(value)) || value.code) return failure(value.code ? value.code : 12);
    for (;;) {
        struct command command;
        if (receive_bytes(request, &command, sizeof(command))) return failure(13);
        code = 0;
        switch (command.operation) {
        case CHECK:
        case FINISH:
            break;
        case SIBLING_REFUSALS:
            errno = 0;
            if (setpgid(command.other, 0) != -1 || errno != ESRCH) { code = 14; break; }
            errno = 0;
            if (setpgid(getppid(), 0) != -1 || errno != ESRCH) { code = 15; break; }
            errno = 0;
            if (setsid() != -1 || errno != EPERM) code = 16;
            break;
        case JOIN_GROUP:
            if (setpgid(0, command.pgid)) code = 17;
            break;
        case FOREIGN_GROUP:
            errno = 0;
            if (setpgid(0, command.other) != -1 || errno != EPERM) code = 18;
            break;
        case OWN_GROUP:
            if (setpgid(0, 0)) code = 19;
            break;
        default:
            code = 20;
        }
        if (!code && expected_ids(command.sid, command.pgid)) code = 21;
        value = observe(code);
        if (send_bytes(reply, &value, sizeof(value)) || value.code) return failure(value.code ? value.code : 22);
        if (command.operation == FINISH) return close(request) || close(reply) ? failure(23) : 0;
    }
}

static int spawn_peer(struct peer *peer, struct peer *existing, unsigned count, int foreign, pid_t sid, pid_t pgid)
{
    int request[2] = {-1, -1}, reply[2] = {-1, -1};
    if (pipe(request) || pipe(reply)) goto fail;
    pid_t child = fork();
    if (child < 0) goto fail;
    if (!child) {
        (void)close(request[1]); (void)close(reply[0]);
        for (unsigned index = 0; index < count; ++index) {
            if (existing[index].request >= 0) (void)close(existing[index].request);
            if (existing[index].reply >= 0) (void)close(existing[index].reply);
        }
        _Exit(peer_child(request[0], reply[1], foreign, sid, pgid));
    }
    (void)close(request[0]); (void)close(reply[1]);
    *peer = (struct peer){child, request[1], reply[0]};
    struct identities value;
    if (receive_bytes(peer->reply, &value, sizeof(value)) || value.code || value.pid != child || value.parent != getpid() ||
        value.sid != (foreign ? child : sid) || value.pgid != (foreign ? child : pgid)) return -1;
    return 0;
fail:
    for (unsigned index = 0; index < 2; ++index) {
        if (request[index] >= 0) (void)close(request[index]);
        if (reply[index] >= 0) (void)close(reply[index]);
    }
    return -1;
}

static int tell_peer(struct peer *peer, unsigned operation, pid_t other, pid_t sid, pid_t pgid)
{
    struct command command = {operation, other, sid, pgid};
    struct identities value;
    return send_bytes(peer->request, &command, sizeof(command)) || receive_bytes(peer->reply, &value, sizeof(value)) ||
        value.code || value.pid != peer->pid || value.parent != getpid() || value.sid != sid || value.pgid != pgid ? -1 : 0;
}

static void dispose_peer(struct peer *peer)
{
    if (peer->pid > 1) { (void)kill(peer->pid, SIGKILL); (void)waitpid(peer->pid, 0, 0); }
    if (peer->request >= 0) (void)close(peer->request);
    if (peer->reply >= 0) (void)close(peer->reply);
    *peer = (struct peer){-1, -1, -1};
}

static int finish_peer(struct peer *peer, pid_t sid, pid_t pgid)
{
    if (tell_peer(peer, FINISH, 0, sid, pgid)) return -1;
    if (close(peer->request) || close(peer->reply)) return -1;
    peer->request = peer->reply = -1;
    pid_t child = peer->pid;
    if (wait_child(child)) return -1;
    peer->pid = -1;
    errno = 0;
    if (getpgid(child) != -1 || errno != ESRCH) return -1;
    errno = 0;
    return getsid(child) == -1 && errno == ESRCH ? 0 : -1;
}

static int topology(pid_t sid)
{
    struct peer peers[3] = {{-1, -1, -1}, {-1, -1, -1}, {-1, -1, -1}};
    unsigned code = 30;
    if (spawn_peer(peers, peers, 0, 0, sid, sid) || spawn_peer(peers + 1, peers, 1, 0, sid, sid)) goto done;
    pid_t first = peers[0].pid, second = peers[1].pid;
    code = 31;
    if (setpgid(first, 0) || getpgid(first) != first || getsid(first) != sid ||
        setpgid(second, first) || getpgid(second) != first || getsid(second) != sid) goto done;
    code = 32;
    errno = 0;
    /* The second PID exists but does not yet name a process group. */
    if (setpgid(first, second) != -1 || errno != EPERM || getpgid(first) != first) goto done;
    code = 33;
    if (tell_peer(peers, SIBLING_REFUSALS, second, sid, first) ||
        tell_peer(peers + 1, CHECK, 0, sid, first)) goto done;
    if (nf_marker("\nNATIVE_PROCESS_SESSIONS case=child-and-sibling parent_moves=pass sibling=ESRCH leader_setsid=EPERM\n")) goto done;
    code = 34;
    if (tell_peer(peers, JOIN_GROUP, 0, sid, sid) || getpgid(first) != sid) goto done;
    if (spawn_peer(peers + 2, peers, 2, 1, sid, sid)) goto done;
    pid_t foreign = peers[2].pid;
    code = 35;
    errno = 0;
    if (setpgid(foreign, sid) != -1 || errno != EPERM || getsid(foreign) != foreign || getpgid(foreign) != foreign ||
        tell_peer(peers, FOREIGN_GROUP, foreign, sid, sid)) goto done;
    code = 36;
    if (tell_peer(peers + 1, OWN_GROUP, 0, sid, second) || getpgid(second) != second) goto done;
    errno = 0;
    /* Both members have left the first child's former group. */
    if (setpgid(second, first) != -1 || errno != EPERM || getpgid(second) != second ||
        setpgid(second, sid) || tell_peer(peers + 1, CHECK, 0, sid, sid)) goto done;
    if (nf_marker("\nNATIVE_PROCESS_SESSIONS case=session-boundaries foreign_group=EPERM foreign_child=EPERM absent_group=EPERM self_group=pass\n")) goto done;
    code = 37;
    if (finish_peer(peers + 2, foreign, foreign) || finish_peer(peers + 1, sid, sid) || finish_peer(peers, sid, sid)) goto done;
    code = 0;
done:
    for (unsigned index = 0; index < 3; ++index) dispose_peer(peers + index);
    return code ? failure(code) : 0;
}

static void decimal(char output[12], pid_t value)
{
    char reverse[10];
    unsigned used = 0, offset = 0, number = (unsigned)value;
    do { reverse[used++] = (char)('0' + number % 10); number /= 10; } while (number);
    while (used) output[offset++] = reverse[--used];
    output[offset] = 0;
}

static int positive(const char *text, pid_t *value)
{
    uint64_t result = 0;
    if (!*text) return -1;
    for (; *text; ++text) {
        if (*text < '0' || *text > '9') return -1;
        result = result * 10 + (unsigned)(*text - '0');
        if (result > INT32_MAX) return -1;
    }
    if (!result) return -1;
    *value = (pid_t)result;
    return 0;
}

static int exec_wait(int argc, char **argv)
{
    pid_t numbers[6];
    if (argc != 8) return failure(50);
    for (unsigned index = 0; index < 6; ++index)
        if (positive(argv[index + 2], numbers + index)) return failure(51);
    int reply = numbers[0], request = numbers[1];
    if (reply < 3 || request < 3 || reply == request || getpid() != numbers[2] || getppid() != numbers[3] ||
        expected_ids(numbers[4], numbers[5])) return failure(52);
    struct identities value = observe(0);
    if (send_bytes(reply, &value, sizeof(value))) return failure(53);
    char command;
    if (receive_bytes(request, &command, 1) || command != 'G' || setpgid(0, 0) ||
        expected_ids(numbers[4], getpid())) return failure(54);
    value = observe(0);
    if (send_bytes(reply, &value, sizeof(value)) || receive_bytes(request, &command, 1) || command != 'X') return failure(55);
    return close(request) || close(reply) ? failure(56) : 0;
}

static int exec_boundary(pid_t sid)
{
    int request[2] = {-1, -1}, reply[2] = {-1, -1};
    pid_t child = -1;
    unsigned code = 60;
    if (pipe(request) || pipe(reply)) goto done;
    child = fork();
    if (child < 0) goto done;
    if (!child) {
        (void)close(request[1]); (void)close(reply[0]);
        char descriptors[2][12], identities[4][12];
        decimal(descriptors[0], reply[1]); decimal(descriptors[1], request[0]);
        decimal(identities[0], getpid()); decimal(identities[1], getppid());
        decimal(identities[2], sid); decimal(identities[3], sid);
        char *arguments[] = {SELF_PATH, "exec-wait", descriptors[0], descriptors[1],
            identities[0], identities[1], identities[2], identities[3], 0};
        char *environment[] = {"PATH=/bin", 0};
        execve(arguments[0], arguments, environment);
        _Exit(failure(61));
    }
    (void)close(request[0]); request[0] = -1;
    (void)close(reply[1]); reply[1] = -1;
    struct identities value;
    code = 62;
    /* Only code in the successfully exec'd image emits this pipe handshake. */
    if (receive_bytes(reply[0], &value, sizeof(value)) || value.code || value.pid != child ||
        value.parent != getpid() || value.sid != sid || value.pgid != sid) goto done;
    code = 63;
    errno = 0;
    if (setpgid(child, 0) != -1 || errno != EACCES || getpgid(child) != sid || getsid(child) != sid) goto done;
    errno = 0;
    if (setpgid(child, sid) != -1 || errno != EACCES || getpgid(child) != sid) goto done;
    code = 64;
    if (send_bytes(request[1], "G", 1) || receive_bytes(reply[0], &value, sizeof(value)) || value.code ||
        value.pid != child || value.parent != getpid() || value.sid != sid || value.pgid != child) goto done;
    errno = 0;
    if (setpgid(child, sid) != -1 || errno != EACCES || getpgid(child) != child || getsid(child) != sid) goto done;
    code = 65;
    if (send_bytes(request[1], "X", 1) || wait_child(child)) goto done;
    child = -1;
    if (nf_marker("\nNATIVE_PROCESS_SESSIONS case=exec pipe_handshake=pass identities=preserved parent_setpgid=EACCES self_setpgid=pass\n")) goto done;
    code = 0;
done:
    if (child > 1) { (void)kill(child, SIGKILL); (void)waitpid(child, 0, 0); }
    for (unsigned index = 0; index < 2; ++index) {
        if (request[index] >= 0) (void)close(request[index]);
        if (reply[index] >= 0) (void)close(reply[index]);
    }
    return code ? failure(code) : 0;
}

static int worker(pid_t parent, pid_t inherited_sid, pid_t inherited_pgid)
{
    pid_t pid = getpid();
    if (getppid() != parent || expected_ids(inherited_sid, inherited_pgid) || setsid() != pid ||
        getppid() != parent || expected_ids(pid, pid)) return failure(70);
    errno = 0;
    if (setsid() != -1 || errno != EPERM || expected_ids(pid, pid)) return failure(71);
    errno = 0;
    if (setpgid(0, 0) != -1 || errno != EPERM || expected_ids(pid, pid)) return failure(72);
    errno = 0;
    if (setpgid(0, -1) != -1 || errno != EINVAL || expected_ids(pid, pid)) return failure(73);
    errno = 0;
    if (getpgid(-1) != -1 || errno != ESRCH) return failure(74);
    errno = 0;
    if (getsid(-1) != -1 || errno != ESRCH) return failure(75);
    if (nf_marker("\nNATIVE_PROCESS_SESSIONS case=inherit-and-setsid fork=preserved new_sid=pid new_pgid=pid leader=EPERM invalid=pass\n")) return failure(76);
    if (topology(pid) || exec_boundary(pid) || expected_ids(pid, pid)) return failure(77);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc > 1 && !strcmp(argv[1], "exec-wait")) return exec_wait(argc, argv);
    int login_child = argc == 2 && !strcmp(argv[1], "login-child");
    struct identities initial = observe(0);
    if ((argc != 1 && !login_child) || initial.code ||
        (login_child && (initial.parent <= 1 || initial.sid != initial.parent || initial.pgid != initial.parent))) return failure(1);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_PROCESS_SESSION_IDS pid="); nf_number(&record, (unsigned)initial.pid);
    nf_text(&record, " ppid="); nf_number(&record, (unsigned)initial.parent);
    nf_text(&record, " sid="); nf_number(&record, (unsigned)initial.sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)initial.pgid);
    nf_text(&record, login_child ? " login_child=1\n" : " login_child=0\n");
    if (nf_emit(&record)) return failure(2);
    pid_t child = fork();
    if (child < 0) return failure(3);
    if (!child) _Exit(worker(initial.pid, initial.sid, initial.pgid));
    if (wait_child(child) || expected_ids(initial.sid, initial.pgid) || getppid() != initial.parent) return failure(4);
    return nf_marker("\nNATIVE_PROCESS_SESSIONS_PASS native=1 inherit=pass setsid=pass child_groups=pass sibling=ESRCH session=EPERM exec_parent=EACCES exec_identity=preserved pty=untested job_control=untested\n")
        ? failure(5) : 0;
}
