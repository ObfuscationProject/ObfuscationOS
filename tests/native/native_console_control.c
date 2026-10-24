#include "native_fixture_record.h"
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <time.h>

#define SELF_PATH "/bin/native-console-control"
#define NONCE_BYTES 32
#define STREAM_BYTES 12289
_Static_assert(OK_NATIVE_CONSOLE_CONTROL_VERSION == 1 && sizeof(pid_t) == 4,
               "native controlling-console contract");

enum { INITIAL = 1, PREPARE_EXEC, BEFORE_EXEC, AFTER_EXEC, EMPTY, BUFFERED, READ_NONCE, FINISH,
       WAIT_READ, WAIT_READV, WAIT_POLL, WAIT_READY, WAIT_REPORT, WAIT_REPORTED, PEER_RECLAIM };
struct identity { pid_t pid, parent, sid, group; uid_t uid, effective, saved; gid_t gid; };
struct message { unsigned operation, code; struct identity identity; uint64_t hash; };
struct peer { pid_t pid; int request, reply; };

static int emit(struct native_fixture_record *record)
{
    if (record->failed) return -1;
    ssize_t count;
    /* stderr remains a canonical console alias in every pipeline stage. */
    do { count = write(STDERR_FILENO, record->bytes, record->size); } while (count < 0 && errno == EINTR);
    return count == (ssize_t)record->size ? 0 : -1;
}

static int marker(const char *text)
{
    struct native_fixture_record record = {0}; nf_text(&record, text);
    return emit(&record);
}

static int fail(unsigned code)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_FAIL pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " code="); nf_number(&record, code); nf_text(&record, "\n");
    (void)emit(&record);
    return (int)(code ? code : 255);
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
    char digits[16]; unsigned used = 0;
    do { digits[used++] = (char)('0' + value % 10); value /= 10; } while (value);
    for (unsigned i = 0; i < used; ++i) output[i] = digits[used - i - 1];
    output[used] = 0;
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

static struct message observe(unsigned operation)
{
    struct message value = {.operation = operation};
    value.identity = (struct identity){.pid = getpid(), .parent = getppid(), .sid = getsid(0),
        .group = getpgrp(), .uid = getuid(), .effective = geteuid(), .gid = getgid()};
    uid_t real = 0, effective = 0, saved = 0;
    gid_t real_gid = 0, effective_gid = 0, saved_gid = 0;
    if (getresuid(&real, &effective, &saved) || getresgid(&real_gid, &effective_gid, &saved_gid) ||
        real != value.identity.uid || effective != value.identity.effective || real != effective || real != saved ||
        real_gid != value.identity.gid || real_gid != effective_gid || real_gid != saved_gid ||
        value.identity.pid <= 1 || value.identity.parent <= 1 || value.identity.sid <= 1 || value.identity.group <= 1 ||
        getpgid(0) != value.identity.group || getpgid(value.identity.pid) != value.identity.group ||
        getsid(value.identity.pid) != value.identity.sid) value.code = 1;
    value.identity.saved = saved;
    return value;
}

static int identity_record(const char *role, int nested)
{
    struct message value = observe(0);
    struct identity *id = &value.identity;
    pid_t parent_group = getpgid(id->parent), tty_sid = tcgetsid(STDERR_FILENO), foreground = tcgetpgrp(STDERR_FILENO);
    if (value.code || id->uid || id->gid || id->group != id->pid || parent_group != id->parent ||
        tty_sid != id->sid || foreground != id->group ||
        (nested ? id->parent == id->sid : id->parent != id->sid)) return -1;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_IDS role="); nf_text(&record, role);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)id->pid);
    nf_text(&record, " ppid="); nf_number(&record, (unsigned)id->parent);
    nf_text(&record, " parent_pgid="); nf_number(&record, (unsigned)parent_group);
    nf_text(&record, " sid="); nf_number(&record, (unsigned)id->sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)id->group);
    nf_text(&record, " tty_sid="); nf_number(&record, (unsigned)tty_sid);
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)foreground);
    nf_text(&record, " uid=0\n");
    return emit(&record);
}

static int check_terminal(pid_t sid, pid_t group)
{
    for (int fd = 0; fd < 3; ++fd)
        if (tcgetsid(fd) != sid || tcgetpgrp(fd) != group) return -1;
    return 0;
}

static int expected(const struct message *value, const struct peer *peer, unsigned operation,
                    pid_t sid, pid_t group, uid_t uid)
{
    return value->code || value->operation != operation || value->identity.pid != peer->pid ||
        value->identity.parent != getpid() || value->identity.sid != sid || value->identity.group != group ||
        value->identity.uid != uid || value->identity.effective != uid || value->identity.saved != uid ||
        value->identity.gid != uid ? -1 : 0;
}

static int background(const char *phase, pid_t sid, pid_t foreground)
{
    if (check_terminal(sid, foreground) || getpgrp() == foreground) return -1;
    unsigned char bytes[8]; memset(bytes, 0xa5, sizeof(bytes));
    int alias = fcntl(STDIN_FILENO, F_DUPFD, 3);
    if (alias < 0 || tcgetsid(alias) != sid || tcgetpgrp(alias) != foreground) {
        if (alias >= 0) close(alias);
        return -1;
    }
    int result = -1;
    errno = 0;
    if (read(STDIN_FILENO, bytes, sizeof(bytes)) != -1 || errno != EIO) goto done;
    struct iovec vectors[2] = {{bytes, 3}, {bytes + 3, 5}};
    errno = 0;
    if (readv(STDIN_FILENO, vectors, 2) != -1 || errno != EIO) goto done;
    errno = 0;
    if (read(alias, bytes, sizeof(bytes)) != -1 || errno != EIO) goto done;
    for (unsigned i = 0; i < sizeof(bytes); ++i) if (bytes[i] != 0xa5) goto done;
    struct pollfd descriptors[2] = {{STDIN_FILENO, POLLIN, 0}, {alias, POLLIN, 0}};
    if (poll(descriptors, 2, 0) != 2 || descriptors[0].revents != POLLERR || descriptors[1].revents != POLLERR) goto done;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_BACKGROUND phase="); nf_text(&record, phase);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)getpgrp());
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)foreground);
    nf_text(&record, " uid="); nf_number(&record, getuid());
    nf_text(&record, " read=EIO readv=EIO dup=EIO poll=ERR bytes=untouched\n");
    result = emit(&record);
done:
    return close(alias) ? -1 : result;
}

static int receive_nonce(pid_t sid, uint64_t *hash)
{
    if (check_terminal(sid, getpgrp()) || getuid() != 1000) return -1;
    unsigned char bytes[NONCE_BYTES];
    size_t used = 0;
    struct pollfd descriptor;
    while (used < 8) {
        descriptor = (struct pollfd){STDIN_FILENO, POLLIN, 0};
        if (poll(&descriptor, 1, 5000) != 1 || descriptor.revents != POLLIN) return -1;
        size_t first = 8 - used < 3 ? 8 - used : 3;
        struct iovec vectors[2] = {{bytes + used, first}, {bytes + used + first, 8 - used - first}};
        ssize_t count = readv(STDIN_FILENO, vectors, 2);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0 || (size_t)count > 8 - used) return -1;
        used += (size_t)count;
    }
    while (used < sizeof(bytes)) {
        descriptor = (struct pollfd){STDIN_FILENO, POLLIN, 0};
        if (poll(&descriptor, 1, 5000) != 1 || descriptor.revents != POLLIN) return -1;
        ssize_t count = read(STDIN_FILENO, bytes + used, sizeof(bytes) - used);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0 || (size_t)count > sizeof(bytes) - used) return -1;
        used += (size_t)count;
    }
    descriptor.revents = 0;
    if (poll(&descriptor, 1, 0) != 0) return -1;
    *hash = 14695981039346656037ULL;
    for (unsigned i = 0; i < sizeof(bytes); ++i) {
        if (!((bytes[i] >= '0' && bytes[i] <= '9') || (bytes[i] >= 'a' && bytes[i] <= 'f'))) return -1;
        *hash = (*hash ^ bytes[i]) * 1099511628211ULL;
        ((volatile unsigned char *)bytes)[i] = 0;
    }
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_READ pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)getpgrp());
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)tcgetpgrp(STDIN_FILENO));
    nf_text(&record, " uid=1000 bytes=32 readv=8 read=24 hash="); nf_number(&record, *hash);
    nf_text(&record, "\n");
    return emit(&record);
}

static const char *wait_kind(unsigned operation)
{
    return operation == WAIT_READ ? "read" : operation == WAIT_READV ? "readv" : "poll";
}

static int peer_reclaim(pid_t sid, pid_t parent_group)
{
    pid_t group = getpgrp();
    if (getuid() != 1000 || check_terminal(sid, parent_group) || group == parent_group ||
        tcsetpgrp(STDIN_FILENO, group) || check_terminal(sid, group)) return -1;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_PEER_RECLAIM pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)group);
    nf_text(&record, " previous="); nf_number(&record, (unsigned)parent_group);
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)group);
    nf_text(&record, " uid=1000 caller=background\n");
    if (emit(&record) || tcsetpgrp(STDIN_FILENO, parent_group) || check_terminal(sid, parent_group)) return -1;
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_PEER_RETURN pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)group);
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)parent_group);
    nf_text(&record, " uid=1000 caller=foreground\n");
    return emit(&record);
}

static int wait_peer(unsigned operation, int request_fd, int reply_fd, pid_t sid, pid_t parent_group)
{
    if (check_terminal(sid, getpgrp())) return -1;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_WAIT_ARM kind="); nf_text(&record, wait_kind(operation));
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)getpgrp());
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)tcgetpgrp(STDIN_FILENO));
    nf_text(&record, " proof=pre-syscall\n");
    struct message value = observe(WAIT_READY);
    if (emit(&record) || value.code || send_bytes(reply_fd, &value, sizeof(value))) return -1;
    unsigned char bytes[8]; memset(bytes, 0xa5, sizeof(bytes));
    int valid;
    if (operation == WAIT_POLL) {
        struct pollfd descriptor = {STDIN_FILENO, POLLIN, 0};
        int ready;
        do { ready = poll(&descriptor, 1, 5000); } while (ready < 0 && errno == EINTR);
        valid = ready == 1 && descriptor.revents == POLLERR;
    } else {
        struct iovec vectors[2] = {{bytes, 3}, {bytes + 3, 5}};
        ssize_t count;
        do {
            errno = 0;
            count = operation == WAIT_READ ? read(STDIN_FILENO, bytes, sizeof(bytes)) : readv(STDIN_FILENO, vectors, 2);
        } while (count < 0 && errno == EINTR);
        valid = count == -1 && errno == EIO;
        for (unsigned i = 0; i < sizeof(bytes); ++i) valid &= bytes[i] == 0xa5;
    }
    value = observe(operation);
    if (!valid || value.code || check_terminal(sid, parent_group) || send_bytes(reply_fd, &value, sizeof(value))) return -1;
    /* Report only after the parent emitted its verified transfer record.
     * The pre-syscall handshake and pending pipe snapshot do not prove that
     * the scheduler had armed this particular syscall before the transfer. */
    struct message report;
    if (receive_bytes(request_fd, &report, sizeof(report)) || report.operation != WAIT_REPORT) return -1;
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_WAIT_RESULT kind="); nf_text(&record, wait_kind(operation));
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)getpgrp());
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)tcgetpgrp(STDIN_FILENO));
    nf_text(&record, operation == WAIT_POLL ? " result=ERR bytes=none armed=unproven\n" : " result=EIO bytes=untouched armed=unproven\n");
    value = observe(WAIT_REPORTED);
    return emit(&record) || value.code || send_bytes(reply_fd, &value, sizeof(value)) ? -1 : 0;
}

static int exec_peer(int argc, char **argv)
{
    unsigned values[5];
    if (argc != 7) return fail(10);
    for (unsigned i = 0; i < 5; ++i) if (number(argv[i + 2], &values[i])) return fail(11);
    int request_fd = (int)values[0], reply_fd = (int)values[1];
    pid_t sid = (pid_t)values[2], parent = (pid_t)values[3], parent_group = (pid_t)values[4];
    struct message value = observe(AFTER_EXEC);
    if (value.code || value.identity.parent != parent || value.identity.sid != sid ||
        value.identity.group != getpid() || value.identity.uid != 1000 || value.identity.gid != 1000 ||
        check_terminal(sid, parent_group) || send_bytes(reply_fd, &value, sizeof(value))) return fail(12);
    for (;;) {
        struct message command;
        if (receive_bytes(request_fd, &command, sizeof(command))) return fail(13);
        value = observe(command.operation);
        if (value.code) return fail(14);
        if (command.operation == FINISH) {
            if (check_terminal(sid, parent_group)) return fail(15);
            return close(request_fd) || close(reply_fd) ? fail(16) : 0;
        }
        if (command.operation == EMPTY || command.operation == BUFFERED) {
            if (background(command.operation == EMPTY ? "empty" : "buffered", sid, parent_group)) return fail(17);
        } else if (command.operation == READ_NONCE) {
            if (receive_nonce(sid, &value.hash)) return fail(18);
        } else if (command.operation == PEER_RECLAIM) {
            if (peer_reclaim(sid, parent_group)) return fail(26);
        } else if (command.operation >= WAIT_READ && command.operation <= WAIT_POLL) {
            if (wait_peer(command.operation, request_fd, reply_fd, sid, parent_group)) return fail(25);
            continue;
        } else return fail(19);
        if (send_bytes(reply_fd, &value, sizeof(value))) return fail(20);
    }
}

static int spawn_peer(struct peer *peer, pid_t sid, pid_t group)
{
    int request[2] = {-1, -1}, reply[2] = {-1, -1};
    if (pipe(request) || pipe(reply)) goto fail;
    pid_t child = fork();
    if (child < 0) goto fail;
    if (!child) {
        for (int fd = 3; fd < 64; ++fd)
            if (fd != request[0] && fd != reply[1]) (void)close(fd);
        struct message value = observe(INITIAL);
        if (value.code || send_bytes(reply[1], &value, sizeof(value))) _Exit(fail(21));
        struct message command;
        if (receive_bytes(request[0], &command, sizeof(command)) || command.operation != PREPARE_EXEC ||
            setresgid(1000, 1000, 1000) || setresuid(1000, 1000, 1000)) _Exit(fail(22));
        value = observe(BEFORE_EXEC);
        if (value.code || value.identity.group != getpid() || value.identity.sid != sid ||
            send_bytes(reply[1], &value, sizeof(value))) _Exit(fail(23));
        char request_text[16], reply_text[16], sid_text[16], parent_text[16], group_text[16];
        decimal((unsigned)request[0], request_text); decimal((unsigned)reply[1], reply_text);
        decimal((unsigned)sid, sid_text); decimal((unsigned)getppid(), parent_text); decimal((unsigned)group, group_text);
        char *arguments[] = {SELF_PATH, "peer", request_text, reply_text, sid_text, parent_text, group_text, 0};
        char *environment[] = {"PATH=/bin", 0};
        execve(arguments[0], arguments, environment);
        _Exit(fail(24));
    }
    close(request[0]); close(reply[1]);
    *peer = (struct peer){child, request[1], reply[0]};
    struct message value;
    if (receive_bytes(peer->reply, &value, sizeof(value)) || expected(&value, peer, INITIAL, sid, group, 0) ||
        setpgid(child, child)) return -1;
    struct message command = {.operation = PREPARE_EXEC};
    if (send_bytes(peer->request, &command, sizeof(command)) || receive_bytes(peer->reply, &value, sizeof(value)) ||
        expected(&value, peer, BEFORE_EXEC, sid, child, 1000) || receive_bytes(peer->reply, &value, sizeof(value)) ||
        expected(&value, peer, AFTER_EXEC, sid, child, 1000)) return -1;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_PEER pid="); nf_number(&record, (unsigned)child);
    nf_text(&record, " ppid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)child);
    nf_text(&record, " inherited_pgid="); nf_number(&record, (unsigned)group);
    nf_text(&record, " uid=1000 fork=pipe exec=pipe\n");
    return emit(&record);
fail:
    for (unsigned i = 0; i < 2; ++i) {
        if (request[i] >= 0) close(request[i]);
        if (reply[i] >= 0) close(reply[i]);
    }
    return -1;
}

static int exchange(struct peer *peer, unsigned operation, pid_t sid)
{
    struct message command = {.operation = operation}, response;
    return send_bytes(peer->request, &command, sizeof(command)) ||
        receive_bytes(peer->reply, &response, sizeof(response)) ||
        expected(&response, peer, operation, sid, peer->pid, 1000) ? -1 : 0;
}

static int wait_child(pid_t child, int success_required)
{
    for (unsigned attempt = 0; attempt < 500; ++attempt) {
        int status;
        pid_t found = waitpid(child, &status, WNOHANG);
        if (found == child) return !success_required || (WIFEXITED(status) && !WEXITSTATUS(status)) ? 0 : -1;
        if (found < 0 && errno != EINTR) return -1;
        const struct timespec delay = {0, 10000000};
        (void)nanosleep(&delay, 0);
    }
    return -1;
}

static void dispose_peer(struct peer *peer)
{
    if (peer->pid > 1) { (void)kill(peer->pid, SIGKILL); (void)wait_child(peer->pid, 0); }
    if (peer->request >= 0) close(peer->request);
    if (peer->reply >= 0) close(peer->reply);
    *peer = (struct peer){.request = -1, .reply = -1};
}

static int wait_transfer(struct peer *peer, unsigned operation, pid_t sid, pid_t group)
{
    struct pollfd descriptor = {STDIN_FILENO, POLLIN, 0};
    if (poll(&descriptor, 1, 0) != 0 || tcsetpgrp(STDIN_FILENO, peer->pid)) return -1;
    struct message command = {.operation = operation}, response;
    if (send_bytes(peer->request, &command, sizeof(command)) || receive_bytes(peer->reply, &response, sizeof(response)) ||
        expected(&response, peer, WAIT_READY, sid, peer->pid, 1000)) return -1;
    const struct timespec delay = {0, 100000000};
    if (nanosleep(&delay, 0)) return -1;
    descriptor = (struct pollfd){peer->reply, POLLIN, 0};
    if (poll(&descriptor, 1, 0) != 0) return -1;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_WAIT_PENDING kind="); nf_text(&record, wait_kind(operation));
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " peer="); nf_number(&record, (unsigned)peer->pid);
    nf_text(&record, " completed=no proof=pipe-snapshot\n");
    if (emit(&record) || tcsetpgrp(STDIN_FILENO, group) || check_terminal(sid, group) ||
        receive_bytes(peer->reply, &response, sizeof(response)) ||
        expected(&response, peer, operation, sid, peer->pid, 1000)) return -1;
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_WAIT_CHANGE kind="); nf_text(&record, wait_kind(operation));
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " previous="); nf_number(&record, (unsigned)peer->pid);
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)group); nf_text(&record, "\n");
    command.operation = WAIT_REPORT;
    return emit(&record) || send_bytes(peer->request, &command, sizeof(command)) ||
        receive_bytes(peer->reply, &response, sizeof(response)) ||
        expected(&response, peer, WAIT_REPORTED, sid, peer->pid, 1000) ? -1 : 0;
}

static int session(void)
{
    pid_t sid = getsid(0), group = getpgrp();
    struct peer peer = {.request = -1, .reply = -1};
    unsigned code = 30;
    if (identity_record("session", 0) || check_terminal(sid, group)) return fail(31);
    if (spawn_peer(&peer, sid, group) || exchange(&peer, EMPTY, sid)) goto done;
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_PROMPT pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)group);
    nf_text(&record, " peer="); nf_number(&record, (unsigned)peer.pid); nf_text(&record, " bytes=32\n");
    code = 32;
    if (emit(&record)) goto done;
    struct pollfd descriptor = {STDIN_FILENO, POLLIN, 0};
    if (poll(&descriptor, 1, 5000) != 1 || descriptor.revents != POLLIN) goto done;
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_BUFFERED pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)group);
    nf_text(&record, " peer="); nf_number(&record, (unsigned)peer.pid); nf_text(&record, " bytes=32 ready=POLLIN\n");
    code = 33;
    if (emit(&record) || exchange(&peer, BUFFERED, sid)) goto done;
    descriptor.revents = 0;
    if (poll(&descriptor, 1, 0) != 1 || descriptor.revents != POLLIN) goto done;
    code = 34;
    if (tcsetpgrp(STDIN_FILENO, peer.pid) || background("handoff", sid, peer.pid) || exchange(&peer, READ_NONCE, sid)) goto done;
    code = 35;
    if (tcsetpgrp(STDIN_FILENO, group) || check_terminal(sid, group)) goto done;
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_RECLAIM pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)group);
    nf_text(&record, " previous="); nf_number(&record, (unsigned)peer.pid);
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)tcgetpgrp(STDIN_FILENO));
    nf_text(&record, " caller=background policy=no-sigttou\n");
    if (emit(&record) || exchange(&peer, PEER_RECLAIM, sid)) goto done;
    code = 38;
    for (unsigned operation = WAIT_READ; operation <= WAIT_POLL; ++operation)
        if (wait_transfer(&peer, operation, sid, group)) goto done;
    struct message command = {.operation = FINISH};
    code = 36;
    if (send_bytes(peer.request, &command, sizeof(command)) || wait_child(peer.pid, 1)) goto done;
    peer.pid = 0;
    dispose_peer(&peer);
    code = 37;
    if (check_terminal(sid, group) || marker("\nNATIVE_CONSOLE_CONTROL_PASS native=1 background=EIO no_consume=nonce transfer=exact reclaim=background peer_uid=1000 fork=pipe exec=pipe waiters=read-readv-poll armed=unproven select=untested\n")) goto done;
    return 0;
done:
    (void)tcsetpgrp(STDIN_FILENO, group);
    dispose_peer(&peer);
    return fail(code);
}

static int stream_write(const unsigned char *bytes, size_t size)
{
    size_t used = 0;
    while (used < size) {
        ssize_t count = write(STDOUT_FILENO, bytes + used, size - used);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0 || (size_t)count > size - used) return -1;
        used += (size_t)count;
    }
    return 0;
}

static int stage(unsigned index)
{
    static const char *roles[] = {"stage0", "stage1", "stage2"};
    if (index > 2) return fail(40);
    /* Only stage zero is the group leader. Every stage checks the same
     * controlling session and foreground group through canonical stderr. */
    struct message value = observe(0);
    if (value.code || value.identity.uid || value.identity.gid || value.identity.parent != value.identity.sid ||
        getpgid(value.identity.parent) != value.identity.parent ||
        ((index == 0) != (value.identity.group == value.identity.pid)) ||
        tcgetsid(STDERR_FILENO) != value.identity.sid || tcgetpgrp(STDERR_FILENO) != value.identity.group) return fail(41);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_IDS role="); nf_text(&record, roles[index]);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)value.identity.pid);
    nf_text(&record, " ppid="); nf_number(&record, (unsigned)value.identity.parent);
    nf_text(&record, " parent_pgid="); nf_number(&record, (unsigned)getpgid(value.identity.parent));
    nf_text(&record, " sid="); nf_number(&record, (unsigned)value.identity.sid);
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)value.identity.group);
    nf_text(&record, " tty_sid="); nf_number(&record, (unsigned)tcgetsid(STDERR_FILENO));
    nf_text(&record, " foreground="); nf_number(&record, (unsigned)tcgetpgrp(STDERR_FILENO));
    nf_text(&record, " uid=0\n");
    if (emit(&record)) return fail(42);
    size_t total = 0;
    unsigned char bytes[317];
    if (!index) {
        memset(bytes, 'x', sizeof(bytes));
        while (total < STREAM_BYTES) {
            size_t count = STREAM_BYTES - total < sizeof(bytes) ? STREAM_BYTES - total : sizeof(bytes);
            if (stream_write(bytes, count)) return fail(43);
            total += count;
        }
    } else {
        for (;;) {
            ssize_t count = read(STDIN_FILENO, bytes, sizeof(bytes));
            if (count < 0 && errno == EINTR) continue;
            if (count < 0 || (size_t)count > sizeof(bytes)) return fail(44);
            if (!count) break;
            for (ssize_t i = 0; i < count; ++i) if (bytes[i] != 'x') return fail(45);
            total += (size_t)count;
            if (total > STREAM_BYTES || (index == 1 && stream_write(bytes, (size_t)count))) return fail(46);
        }
        if (total != STREAM_BYTES) return fail(47);
    }
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_STAGE stage="); nf_number(&record, index);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)getsid(0));
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)getpgrp());
    nf_text(&record, " bytes=12289 role="); nf_text(&record, index == 0 ? "emit" : index == 1 ? "forward" : "verify");
    nf_text(&record, "\n");
    return emit(&record) ? fail(48) : 0;
}

static int nested(void)
{
    if (identity_record("nested", 1) || check_terminal(getsid(0), getpgrp())) return fail(50);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_NESTED_PASS pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " parent="); nf_number(&record, (unsigned)getppid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)getsid(0));
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)getpgrp());
    nf_text(&record, " parent_group="); nf_number(&record, (unsigned)getpgid(getppid())); nf_text(&record, "\n");
    return emit(&record) ? fail(51) : 0;
}

static int aliases(void)
{
    if (identity_record("alias", 0)) return fail(52);
    for (int fd = 0; fd < 2; ++fd) {
        errno = 0;
        if (tcgetsid(fd) != -1 || errno != ENOTTY) return fail(53);
    }
    int alias = fcntl(STDERR_FILENO, F_DUPFD, 3);
    if (alias < 0) return fail(54);
    int valid = tcgetsid(alias) == getsid(0) && tcgetpgrp(alias) == getpgrp();
    if (close(alias) || !valid) return fail(55);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_CONTROL_ALIAS_PASS pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " sid="); nf_number(&record, (unsigned)getsid(0));
    nf_text(&record, " pgid="); nf_number(&record, (unsigned)getpgrp());
    nf_text(&record, " canonical=stderr stdin=ENOTTY stdout=ENOTTY dup=pass\n");
    return emit(&record) ? fail(56) : 0;
}

int main(int argc, char **argv)
{
    if (argc >= 2 && !strcmp(argv[1], "peer")) return exec_peer(argc, argv);
    /* An execed shell command must inherit only the three standard aliases. */
    for (int fd = 3; fd < 64; ++fd) {
        errno = 0;
        if (fcntl(fd, F_GETFD) != -1 || errno != EBADF) return fail(1);
    }
    if (argc == 2 && !strcmp(argv[1], "session")) return session();
    if (argc == 2 && !strcmp(argv[1], "nested")) return nested();
    if (argc == 2 && !strcmp(argv[1], "alias")) return aliases();
    unsigned index;
    if (argc == 3 && !strcmp(argv[1], "stage") && !number(argv[2], &index)) return stage(index);
    return fail(2);
}
