#include "native_fixture_record.h"
#include <ok/syscall.h>
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>
#include <time.h>

#define SELF_PATH "/bin/native-group-signals"
#define PEER_LIMIT 4
_Static_assert(OK_SYS_KILL == 62 && SIGTERM == 15 && SIGKILL == 9,
               "native group termination syscall contract");

enum { INITIAL = 1, BEFORE_EXEC, AFTER_EXEC, PING, SEND, SELF, EXIT };
struct identity { pid_t pid, parent, sid, pgid; uid_t uid, euid, saved; };
struct request { unsigned operation, token; pid_t selector; int signal; };
struct response { unsigned operation, token, code; int result, error; struct identity identity; };
struct peer { pid_t pid, pgid; int request, reply; uid_t uid; };
struct peers { struct peer entries[PEER_LIMIT]; unsigned count; };

static int fail(unsigned code)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_GROUP_SIGNALS_FAIL pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " code="); nf_number(&record, code); nf_text(&record, "\n");
    (void)nf_emit(&record);
    return (int)(code ? code : 255);
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
        int ready;
        do { ready = poll(&descriptor, 1, 5000); } while (ready < 0 && errno == EINTR);
        if (ready != 1 || !(descriptor.revents & POLLIN)) return -1;
        ssize_t count = read(fd, (char *)bytes + used, size - used);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0 || (size_t)count > size - used) return -1;
        used += (size_t)count;
    }
    return 0;
}

static struct response observe(unsigned operation)
{
    struct response value = {.operation = operation};
    value.identity = (struct identity){.pid = getpid(), .parent = getppid(),
        .sid = getsid(0), .pgid = getpgrp(), .uid = getuid(), .euid = geteuid()};
    uid_t real = 0, effective = 0, saved = 0;
    if (getresuid(&real, &effective, &saved) || real != value.identity.uid ||
        effective != value.identity.euid || value.identity.pid <= 1 || value.identity.parent <= 1 ||
        value.identity.sid <= 1 || value.identity.pgid <= 1 ||
        getsid(value.identity.pid) != value.identity.sid ||
        getpgid(value.identity.pid) != value.identity.pgid || getpgid(0) != value.identity.pgid) value.code = 1;
    value.identity.saved = saved;
    return value;
}

static int expected(const struct response *value, const struct peer *peer, unsigned operation,
                    pid_t parent, pid_t sid, pid_t pgid, uid_t uid)
{
    return value->code || value->operation != operation || value->identity.pid != peer->pid ||
        value->identity.parent != parent || value->identity.sid != sid || value->identity.pgid != pgid ||
        value->identity.uid != uid || value->identity.euid != uid || value->identity.saved != uid ? -1 : 0;
}

static int number(const char *text, unsigned *out)
{
    unsigned value = 0;
    if (!text || !*text) return -1;
    for (; *text; ++text) {
        if (*text < '0' || *text > '9' || value > (2147483647u - (unsigned)(*text - '0')) / 10u) return -1;
        value = value * 10u + (unsigned)(*text - '0');
    }
    *out = value;
    return 0;
}

static void decimal(unsigned value, char output[16])
{
    char reversed[16]; unsigned used = 0;
    do { reversed[used++] = (char)('0' + value % 10); value /= 10; } while (value);
    for (unsigned index = 0; index < used; ++index) output[index] = reversed[used - index - 1];
    output[used] = 0;
}

static int exec_peer(int argc, char **argv)
{
    unsigned values[5];
    if (argc != 7) return fail(10);
    for (unsigned index = 0; index < 5; ++index)
        if (number(argv[index + 2], &values[index])) return fail(11);
    int request_fd = (int)values[0], reply_fd = (int)values[1];
    struct response value = observe(AFTER_EXEC);
    if (value.code || value.identity.pgid != (pid_t)values[2] ||
        value.identity.parent != (pid_t)values[3] || value.identity.uid != values[4] ||
        value.identity.euid != values[4] || value.identity.saved != values[4] ||
        send_bytes(reply_fd, &value, sizeof(value))) return fail(12);
    for (;;) {
        struct request request;
        if (receive_bytes(request_fd, &request, sizeof(request))) return fail(13);
        if (request.operation == EXIT) return 0;
        value = observe(request.operation); value.token = request.token;
        if (request.operation == SELF) {
            struct native_fixture_record record = {0};
            nf_text(&record, "\nNATIVE_GROUP_SELF_ARM pid="); nf_number(&record, (unsigned)getpid());
            nf_text(&record, " pgid="); nf_number(&record, (unsigned)getpgrp());
            nf_text(&record, " signal="); nf_number(&record, (unsigned)request.signal); nf_text(&record, "\n");
            if (nf_emit(&record)) return fail(14);
            (void)kill(0, request.signal);
            /* Successful self-group termination must prevent user reentry. */
            return fail(15);
        }
        if (request.operation == SEND) {
            errno = 0;
            value.result = kill(request.selector, request.signal);
            value.error = errno;
        } else if (request.operation != PING) return fail(16);
        if (value.code || send_bytes(reply_fd, &value, sizeof(value))) return fail(17);
    }
}

static int wait_status(pid_t pid, int expected_signal)
{
    for (unsigned attempt = 0; attempt < 500; ++attempt) {
        int status = 0;
        pid_t found = waitpid(pid, &status, WNOHANG);
        if (found == pid) return expected_signal
            ? (WIFSIGNALED(status) && WTERMSIG(status) == expected_signal ? 0 : -1)
            : (WIFEXITED(status) && !WEXITSTATUS(status) ? 0 : -1);
        if (found < 0 && errno != EINTR) return -1;
        const struct timespec delay = {0, 10000000};
        (void)nanosleep(&delay, 0);
    }
    return -1;
}

static void cleanup(struct peers *peers)
{
    for (unsigned index = 0; index < peers->count; ++index) {
        struct peer *peer = &peers->entries[index];
        if (peer->pid > 1) { (void)kill(peer->pid, SIGKILL); (void)waitpid(peer->pid, 0, 0); }
        if (peer->request >= 0) (void)close(peer->request);
        if (peer->reply >= 0) (void)close(peer->reply);
        *peer = (struct peer){.request = -1, .reply = -1};
    }
}

static int member_record(const char *case_name, const struct peer *peer, pid_t inherited)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_GROUP_MEMBER case="); nf_text(&record, case_name);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)peer->pid);
    nf_text(&record, " ppid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)getsid(0));
    nf_text(&record, " inherited_pgid="); nf_number(&record, (unsigned)inherited);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)peer->pgid);
    nf_text(&record, " uid="); nf_number(&record, peer->uid);
    nf_text(&record, " fork=pipe exec=pipe\n");
    return nf_emit(&record);
}

static struct peer *spawn(struct peers *peers, pid_t group, uid_t uid, const char *case_name)
{
    if (peers->count == PEER_LIMIT) return 0;
    int request[2], reply[2];
    if (pipe(request)) return 0;
    if (pipe(reply)) { close(request[0]); close(request[1]); return 0; }
    struct peer *peer = &peers->entries[peers->count++];
    *peer = (struct peer){.pid = fork(), .request = request[1], .reply = reply[0], .uid = uid};
    if (peer->pid < 0) { close(request[0]); close(reply[1]); return 0; }
    if (!peer->pid) {
        for (int fd = 3; fd < 32; ++fd)
            if (fd != request[0] && fd != reply[1]) (void)close(fd);
        struct response initial = observe(INITIAL);
        if (initial.code || send_bytes(reply[1], &initial, sizeof(initial))) _Exit(fail(20));
        struct request start;
        if (receive_bytes(request[0], &start, sizeof(start)) || start.operation != BEFORE_EXEC ||
            setresgid(uid, uid, uid) || setresuid(uid, uid, uid)) _Exit(fail(21));
        struct response before = observe(BEFORE_EXEC);
        if (before.code || before.identity.pgid != start.selector || send_bytes(reply[1], &before, sizeof(before))) _Exit(fail(22));
        char request_text[16], reply_text[16], group_text[16], parent_text[16], uid_text[16];
        decimal((unsigned)request[0], request_text); decimal((unsigned)reply[1], reply_text);
        decimal((unsigned)before.identity.pgid, group_text); decimal((unsigned)getppid(), parent_text);
        decimal(uid, uid_text);
        char *arguments[] = {SELF_PATH, "peer", request_text, reply_text, group_text, parent_text, uid_text, 0};
        char *environment[] = {"PATH=/bin", 0};
        execve(arguments[0], arguments, environment);
        _Exit(fail(23));
    }
    close(request[0]); close(reply[1]);
    struct response value;
    pid_t inherited = getpgrp(), sid = getsid(0);
    if (receive_bytes(peer->reply, &value, sizeof(value)) ||
        expected(&value, peer, INITIAL, getpid(), sid, inherited, 0)) return 0;
    peer->pgid = group < 0 ? inherited : group ? group : peer->pid;
    if (group >= 0 && setpgid(peer->pid, peer->pgid)) return 0;
    struct request start = {.operation = BEFORE_EXEC, .selector = peer->pgid};
    if (send_bytes(peer->request, &start, sizeof(start)) ||
        receive_bytes(peer->reply, &value, sizeof(value)) ||
        expected(&value, peer, BEFORE_EXEC, getpid(), sid, peer->pgid, uid) ||
        receive_bytes(peer->reply, &value, sizeof(value)) ||
        expected(&value, peer, AFTER_EXEC, getpid(), sid, peer->pgid, uid) ||
        member_record(case_name, peer, inherited)) return 0;
    return peer;
}

static unsigned tokens;
static int exchange(struct peer *peer, unsigned operation, pid_t selector, int signal, int result, int error)
{
    struct request request = {.operation = operation, .token = ++tokens, .selector = selector, .signal = signal};
    struct response response;
    if (send_bytes(peer->request, &request, sizeof(request)) || receive_bytes(peer->reply, &response, sizeof(response)) ||
        expected(&response, peer, operation, getpid(), getsid(0), peer->pgid, peer->uid) ||
        response.token != request.token || response.result != result || response.error != error) return -1;
    return 0;
}

static int retire(struct peer *peer, int signal)
{
    if (wait_status(peer->pid, signal)) return -1;
    peer->pid = 0;
    return 0;
}

static int finish(struct peer *peer)
{
    struct request request = {.operation = EXIT};
    return send_bytes(peer->request, &request, sizeof(request)) || retire(peer, 0) ? -1 : 0;
}

static int exact_failure(pid_t selector, int signal, int expected_error)
{
    errno = 0;
    return kill(selector, signal) == -1 && errno == expected_error ? 0 : -1;
}

static int terminating_group(int signal, int self)
{
    const char *name = self ? (signal == SIGTERM ? "self-term" : "self-kill") :
                              (signal == SIGTERM ? "negative-term" : "negative-kill");
    struct peers peers = {0}; int code = 30;
    struct peer *first = spawn(&peers, 0, 0, name);
    struct peer *second = first ? spawn(&peers, first->pgid, 0, name) : 0;
    struct peer *survivor = second ? spawn(&peers, -1, 0, name) : 0;
    if (!survivor || first->pgid == getpgrp() || kill(-first->pgid, 0) ||
        exchange(first, PING, 0, 0, 0, 0) || exchange(second, PING, 0, 0, 0, 0) ||
        exchange(survivor, PING, 0, 0, 0, 0)) goto done;
    pid_t pgid = first->pgid, a = first->pid, b = second->pid, outside = survivor->pid;
    code = 31;
    if (self) {
        if (exchange(first, SEND, 0, 0, 0, 0)) goto done;
        struct request request = {.operation = SELF, .signal = signal};
        if (send_bytes(first->request, &request, sizeof(request))) goto done;
    } else if (kill(-pgid, signal)) goto done;
    if (retire(first, signal) || retire(second, signal) || exchange(survivor, PING, 0, 0, 0, 0) ||
        exact_failure(-pgid, 0, ESRCH) || finish(survivor)) goto done;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_GROUP_SIGNALS case="); nf_text(&record, name);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)pgid);
    nf_text(&record, " first="); nf_number(&record, (unsigned)a);
    nf_text(&record, " second="); nf_number(&record, (unsigned)b);
    nf_text(&record, " survivor="); nf_number(&record, (unsigned)outside);
    nf_text(&record, " wait_signal="); nf_number(&record, (unsigned)signal);
    nf_text(&record, " probe=live out_group=heartbeat retired=ESRCH");
    nf_text(&record, self ? " self=deferred\n" : " selector=negative\n");
    if (nf_emit(&record)) goto done;
    code = 0;
done:
    cleanup(&peers);
    return code ? fail(code) : 0;
}

static int retained_group(void)
{
    struct peers peers = {0}; int code = 40;
    struct peer *leader = spawn(&peers, 0, 0, "retained-group");
    struct peer *member = leader ? spawn(&peers, leader->pgid, 0, "retained-group") : 0;
    if (!member) goto done;
    pid_t group = leader->pgid, first = leader->pid, second = member->pid;
    if (finish(leader) || kill(-group, 0) || exchange(member, PING, 0, 0, 0, 0) ||
        kill(-group, SIGTERM) || retire(member, SIGTERM) || exact_failure(-group, 0, ESRCH)) goto done;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_GROUP_SIGNALS case=retained-group pgid="); nf_number(&record, (unsigned)group);
    nf_text(&record, " leader="); nf_number(&record, (unsigned)first);
    nf_text(&record, " member="); nf_number(&record, (unsigned)second);
    nf_text(&record, " leader=reaped probe=live member_wait=15 retired=ESRCH\n");
    if (nf_emit(&record)) goto done;
    code = 0;
done:
    cleanup(&peers);
    return code ? fail(code) : 0;
}

static int permissions(int signal)
{
    const char *name = signal == SIGTERM ? "permission-term" : "permission-kill";
    struct peers peers = {0}; int code = 50;
    struct peer *denied = spawn(&peers, 0, 0, name);
    struct peer *allowed = denied ? spawn(&peers, denied->pgid, 1000, name) : 0;
    struct peer *sender = allowed ? spawn(&peers, 0, 1000, name) : 0;
    if (!sender || sender->pgid == denied->pgid || exchange(sender, SEND, -denied->pgid, 0, 0, 0) ||
        exchange(denied, PING, 0, 0, 0, 0) || exchange(allowed, PING, 0, 0, 0, 0)) goto done;
    pid_t group = denied->pgid, root = denied->pid, user = allowed->pid, actor = sender->pid;
    code = 51;
    if (exchange(sender, SEND, -group, signal, 0, 0) || retire(allowed, signal) ||
        exchange(denied, PING, 0, 0, 0, 0) || exchange(sender, SEND, -group, 0, -1, EPERM) ||
        exchange(sender, SEND, -group, signal, -1, EPERM) || exchange(denied, PING, 0, 0, 0, 0) ||
        finish(sender) || finish(denied)) goto done;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_GROUP_SIGNALS case="); nf_text(&record, name);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)group);
    nf_text(&record, " root="); nf_number(&record, (unsigned)root);
    nf_text(&record, " allowed="); nf_number(&record, (unsigned)user);
    nf_text(&record, " sender="); nf_number(&record, (unsigned)actor);
    nf_text(&record, " wait_signal="); nf_number(&record, (unsigned)signal);
    nf_text(&record, " partial=success root=heartbeat all_denied=EPERM sender_uid=1000\n");
    if (nf_emit(&record)) goto done;
    code = 0;
done:
    cleanup(&peers);
    return code ? fail(code) : 0;
}

static int rejections(void)
{
    struct peers peers = {0}; int code = 60;
    struct peer *peer = spawn(&peers, 0, 0, "rejections");
    if (!peer || exact_failure(INT32_MIN, 0, ESRCH) || exact_failure(INT32_MIN, SIGTERM, ESRCH) ||
        exact_failure(-INT32_MAX, 0, ESRCH) || exact_failure(-1, 0, EOPNOTSUPP) ||
        exact_failure(-1, SIGTERM, EOPNOTSUPP) || exact_failure(-peer->pgid, 1, EOPNOTSUPP) ||
        exact_failure(-peer->pgid, 65, EINVAL) || exchange(peer, PING, 0, 0, 0, 0) || finish(peer)) goto done;
    if (nf_marker("\nNATIVE_GROUP_SIGNALS case=rejections absent=ESRCH int_min=ESRCH broadcast=EOPNOTSUPP unsupported=EOPNOTSUPP invalid=EINVAL survivor=heartbeat\n")) goto done;
    code = 0;
done:
    cleanup(&peers);
    return code ? fail(code) : 0;
}

int main(int argc, char **argv)
{
    if (argc > 1 && !strcmp(argv[1], "peer")) return exec_peer(argc, argv);
    struct response initial = observe(INITIAL);
    if (argc != 2 || strcmp(argv[1], "login-child") || initial.code ||
        initial.identity.parent != initial.identity.sid || initial.identity.parent != initial.identity.pgid ||
        initial.identity.uid || initial.identity.euid || initial.identity.saved) return fail(1);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_GROUP_SIGNALS_IDS pid="); nf_number(&record, (unsigned)initial.identity.pid);
    nf_text(&record, " ppid="); nf_number(&record, (unsigned)initial.identity.parent);
    nf_text(&record, " sid="); nf_number(&record, (unsigned)initial.identity.sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)initial.identity.pgid);
    nf_text(&record, " login_child=1 uid=0\n");
    if (nf_emit(&record) || terminating_group(SIGTERM, 0) || terminating_group(SIGKILL, 0) ||
        terminating_group(SIGTERM, 1) || terminating_group(SIGKILL, 1) || retained_group() ||
        permissions(SIGTERM) || permissions(SIGKILL) || rejections()) return fail(2);
    struct response final = observe(INITIAL);
    if (final.code || memcmp(&initial.identity, &final.identity, sizeof(initial.identity))) return fail(3);
    return nf_marker("\nNATIVE_GROUP_SIGNALS_PASS native=1 cases=8 negative=term-kill self=deferred fork=pipe exec=pipe retained_group=pass permission=partial-and-denied survivor=heartbeat broadcast=unsupported tty=untested job_control=untested\n") ? fail(4) : 0;
}
