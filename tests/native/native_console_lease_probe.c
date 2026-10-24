#include "native_fixture_record.h"
#include <fcntl.h>
#include <ok/console.h>
#include <poll.h>
#include <stdlib.h>
#include <sys/uio.h>
#include <time.h>

_Static_assert(OK_UAPI_VERSION_MAJOR == 0 && OK_UAPI_VERSION_MINOR == 16 && OK_UAPI_VERSION_PATCH == 0,
    "console lease fixture requires the explicit UAPI 0.16.0 SDK");
_Static_assert(OK_NATIVE_CONSOLE_LEASE_VERSION == 1, "console lease version");

#define FIRST_PATH "/run/console-lease-first"
#define DONE_PATH "/run/console-lease-done"
#define GUARD_PATH "/run/console-lease-guard"
#define WINDOW_PATH "/run/console-lease-window"
#define GUARD_WINDOW "/run/console-guard-window"
#define ACTIVE_PATH "/run/console-lease-active"

struct first_owner { uint32_t epoch; pid_t leader; pid_t children[3]; };

static int failure(unsigned code)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_FAIL pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " code="); nf_number(&record, code); nf_text(&record, "\n");
    (void)nf_emit(&record); return (int)code;
}
static const char *lookup(char **environment, const char *key)
{
    size_t length = strlen(key);
    for (; *environment; ++environment)
        if (!strncmp(*environment, key, length) && (*environment)[length] == '=') return *environment + length + 1;
    return 0;
}
static void pause_ms(unsigned milliseconds)
{
    const struct timespec delay = {milliseconds / 1000, (long)(milliseconds % 1000) * 1000000};
    (void)nanosleep(&delay, 0);
}
static int exists(const char *path)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return errno == ENOENT ? 0 : -1;
    return close(fd) ? -1 : 1;
}
static int put(const char *path, const void *bytes, size_t count)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0) return -1;
    ssize_t result = write(fd, bytes, count);
    return close(fd) || result != (ssize_t)count ? -1 : 0;
}
static int mark(const char *path) { return put(path, "1", 1); }
static int active_epoch(uint32_t *epoch)
{
    int fd = open(ACTIVE_PATH, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    ssize_t count = read(fd, epoch, sizeof(*epoch));
    return close(fd) || count != sizeof(*epoch) || !*epoch || *epoch > OK_CONSOLE_EPOCH_MAX ? -1 : 0;
}
static int old_path(char path[40], unsigned role, int complete)
{
    if (role > 2) return -1;
    strcpy(path, "/run/console-old-");
    size_t length = strlen(path);
    path[length] = (char)('0' + role); path[length + 1] = '-';
    strcpy(path + length + 2, complete == 2 ? "window" : complete ? "done" : "ready");
    return 0;
}
static const char *kind(unsigned role) { return role == 0 ? "read" : role == 1 ? "readv" : "poll"; }

/* Every rejection uses a positive valid-width epoch and a writable buffer.
 * Successful input stealing is a failure even if it returns a short read. */
static int denied(uint32_t epoch)
{
    char byte = 0;
    struct iovec vector = {&byte, 1};
    errno = 0;
    if (read(0, &byte, 1) != -1 || errno != EACCES) return -1;
    errno = 0;
    if (readv(0, &vector, 1) != -1 || errno != EACCES) return -1;
    int alias = dup(0);
    if (alias < 3) return -1;
    errno = 0;
    ssize_t count = read(alias, &byte, 1);
    int error = errno;
    if (close(alias) || count != -1 || error != EACCES) return -1;
    struct pollfd descriptor = {0, POLLIN, 0};
    if (poll(&descriptor, 1, 0) != 1 || descriptor.revents != (POLLERR | POLLHUP)) return -1;
    errno = 0;
    if (ok_console_claim(getpid()) != -1 || errno != EACCES) return -1;
    errno = 0;
    if (ok_console_revoke(epoch) != -1 || errno != EACCES) return -1;
    errno = 0;
    if (ok_console_flush(epoch) != -1 || errno != EACCES) return -1;
    return 0;
}
static int child_record(const char *event, unsigned role, uint32_t epoch, unsigned attempts)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_"); nf_text(&record, event);
    nf_text(&record, " kind="); nf_text(&record, kind(role));
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " parent="); nf_number(&record, (unsigned)getppid());
    nf_text(&record, " epoch="); nf_number(&record, epoch);
    if (!strcmp(event, "REVOKED")) nf_text(&record, role == 2 ? " initial=ERR_HUP" : " initial=EACCES");
    if (!strcmp(event, "OLD_PASS")) {
        nf_text(&record, " attempts="); nf_number(&record, attempts);
        nf_text(&record, " read=EACCES readv=EACCES dup=EACCES poll=ERR_HUP controls=EACCES");
    }
    nf_text(&record, "\n"); return nf_emit(&record);
}
static int window_record(const char *role, uint32_t epoch, uint32_t current)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_WINDOW role="); nf_text(&record, role);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " epoch="); nf_number(&record, epoch);
    nf_text(&record, " control_epoch="); nf_number(&record, current);
    nf_text(&record, " read=EACCES readv=EACCES dup=EACCES poll=ERR_HUP controls=EACCES\n");
    return nf_emit(&record);
}
static int old_child(unsigned role, uint32_t epoch, int reader, int writer)
{
    if (close(reader) || child_record("WAIT", role, epoch, 0) || write(writer, "B", 1) != 1 || close(writer))
        return failure(20);
    char byte;
    struct iovec vector = {&byte, 1};
    struct pollfd descriptor = {0, POLLIN, 0};
    errno = 0;
    int result = role == 0 ? (int)read(0, &byte, 1) : role == 1 ? (int)readv(0, &vector, 1) : poll(&descriptor, 1, -1);
    int error = errno;
    if (getppid() != 1 || (role == 2 ? result != 1 || descriptor.revents != (POLLERR | POLLHUP)
                                         : result != -1 || error != EACCES)) return failure(21);
    char path[40];
    if (child_record("REVOKED", role, epoch, 0) || old_path(path, role, 0) || mark(path)) return failure(22);
    unsigned attempts = 0;
    int window_seen = 0;
    for (unsigned ticks = 0; ticks != 3000; ++ticks) {
        if (denied(epoch)) return failure(23);
        ++attempts;
        int window = exists(WINDOW_PATH);
        if (window < 0) return failure(27);
        if (window && !window_seen) {
            uint32_t current;
            if (active_epoch(&current) || current <= epoch || denied(epoch) || denied(current) ||
                window_record(kind(role), epoch, current) || old_path(path, role, 2) || mark(path)) return failure(28);
            window_seen = 1;
        }
        int done = exists(DONE_PATH);
        if (done < 0) return failure(24);
        if (done && attempts >= 5 && window_seen) {
            if (getppid() != 1 || child_record("OLD_PASS", role, epoch, attempts) || old_path(path, role, 1) || mark(path))
                return failure(25);
            return 41 + (int)role;
        }
        pause_ms(10);
    }
    return failure(26);
}
static int guard(int ready, uint32_t epoch)
{
    if (ready < 3 || epoch || denied(1)) return failure(10);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_GUARD_START pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " parent=1 uid=0 gid=0 epoch=0\n");
    if (nf_emit(&record) || write(ready, "R", 1) != 1 || close(ready)) return failure(11);
    unsigned attempts = 0;
    int window_seen = 0;
    for (unsigned ticks = 0; ticks != 3000; ++ticks) {
        if (denied(1)) return failure(12);
        ++attempts;
        int window = exists(WINDOW_PATH);
        if (window < 0) return failure(16);
        if (window && !window_seen) {
            uint32_t current;
            if (active_epoch(&current) || denied(current) || window_record("guard", 0, current) || mark(GUARD_WINDOW))
                return failure(17);
            window_seen = 1;
        }
        int done = exists(DONE_PATH);
        if (done < 0) return failure(13);
        if (done && attempts >= 5 && window_seen) {
            record = (struct native_fixture_record){0};
            nf_text(&record, "\nNATIVE_CONSOLE_GUARD_PASS pid="); nf_number(&record, (unsigned)getpid());
            nf_text(&record, " attempts="); nf_number(&record, attempts);
            nf_text(&record, " read=EACCES readv=EACCES dup=EACCES poll=ERR_HUP controls=EACCES\n");
            if (nf_emit(&record) || mark(GUARD_PATH)) return failure(14);
            for (;;) pause_ms(100);
        }
        pause_ms(10);
    }
    return failure(15);
}
static int first_console(uint32_t epoch)
{
    int barrier[2];
    if (pipe(barrier)) return failure(30);
    struct first_owner owner = {.epoch = epoch, .leader = getpid()};
    for (unsigned role = 0; role != 3; ++role) {
        pid_t child = fork();
        if (child < 0) return failure(31);
        if (!child) _Exit(old_child(role, epoch, barrier[0], barrier[1]));
        owner.children[role] = child;
    }
    if (close(barrier[1])) return failure(32);
    for (unsigned count = 0; count != 3; ++count) {
        char ready;
        if (read(barrier[0], &ready, 1) != 1 || ready != 'B') return failure(33);
    }
    if (close(barrier[0]) || put(FIRST_PATH, &owner, sizeof(owner))) return failure(34);
    /* The acknowledgements precede each syscall. Give every runnable child an
     * execution slice; no serial key is supplied before the next generation. */
    pause_ms(100);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_FIRST_EXIT pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " epoch="); nf_number(&record, epoch);
    nf_text(&record, " read_pid="); nf_number(&record, (unsigned)owner.children[0]);
    nf_text(&record, " readv_pid="); nf_number(&record, (unsigned)owner.children[1]);
    nf_text(&record, " poll_pid="); nf_number(&record, (unsigned)owner.children[2]);
    nf_text(&record, " status=37\n");
    return nf_emit(&record) ? failure(35) : 37;
}
static int wait_flags(int complete)
{
    for (unsigned ticks = 0; ticks != 3000; ++ticks) {
        int all = 1;
        for (unsigned role = 0; role != 3; ++role) {
            char path[40];
            if (old_path(path, role, complete)) return -1;
            int ready = exists(path);
            if (ready < 0) return -1;
            all &= ready;
        }
        if (complete) {
            int ready = exists(complete == 2 ? GUARD_WINDOW : GUARD_PATH);
            if (ready < 0) return -1;
            all &= ready;
        }
        if (all) return 0;
        pause_ms(10);
    }
    return -1;
}
static int next_console(uint32_t epoch)
{
    struct first_owner owner = {0};
    int fd = open(FIRST_PATH, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return failure(40);
    ssize_t count = read(fd, &owner, sizeof(owner));
    if (close(fd) || count != (ssize_t)sizeof(owner) || !owner.epoch || epoch <= owner.epoch || owner.leader == getpid() ||
        wait_flags(0) || ok_console_flush(epoch)) return failure(41);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_PROMPT generation=2 pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " epoch="); nf_number(&record, epoch); nf_text(&record, " bytes=32\n");
    if (nf_emit(&record)) return failure(42);
    struct pollfd descriptor = {0, POLLIN, 0};
    if (poll(&descriptor, 1, 5000) != 1 || descriptor.revents != POLLIN) return failure(49);
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_BUFFERED pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " epoch="); nf_number(&record, epoch); nf_text(&record, " ready=POLLIN\n");
    if (nf_emit(&record) || put(ACTIVE_PATH, &epoch, sizeof(epoch)) || mark(WINDOW_PATH)) return failure(50);
    pause_ms(200);
    if (wait_flags(2)) return failure(51);
    char key[32];
    descriptor.revents = 0;
    struct iovec vectors[2] = {{key, 3}, {key + 3, 5}};
    if (poll(&descriptor, 1, 5000) != 1 || descriptor.revents != POLLIN || readv(0, vectors, 2) != 8)
        return failure(43);
    size_t received = 8;
    while (received < sizeof(key)) {
        ssize_t size = read(0, key + received, sizeof(key) - received);
        if (size <= 0) return failure(44);
        received += (size_t)size;
    }
    descriptor.revents = 0;
    if (poll(&descriptor, 1, 0)) return failure(45);
    uint64_t hash = 14695981039346656037ULL;
    for (unsigned i = 0; i != sizeof(key); ++i) {
        if (!((key[i] >= '0' && key[i] <= '9') || (key[i] >= 'a' && key[i] <= 'f'))) return failure(46);
        hash = (hash ^ (unsigned char)key[i]) * 1099511628211ULL;
        ((volatile char *)key)[i] = 0;
    }
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_READ_PASS pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " epoch="); nf_number(&record, epoch);
    nf_text(&record, " bytes=32 readv=8 read=24 hash="); nf_number(&record, hash); nf_text(&record, "\n");
    if (nf_emit(&record) || mark(DONE_PATH) || wait_flags(1)) return failure(47);
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_CONSOLE_PASS pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " epoch="); nf_number(&record, epoch);
    nf_text(&record, " guard=live old_children=3 key=exact\n");
    if (nf_emit(&record)) return failure(48);
    for (;;) pause_ms(100);
}
int main(int argc, char **argv, char **environment)
{
    (void)argv;
    const char *service = lookup(environment, "OK_SERVICE_NAME");
    const char *generation = lookup(environment, "OK_SERVICE_GENERATION");
    const char *epoch_text = lookup(environment, "OK_CONSOLE_EPOCH");
    const char *ready = lookup(environment, "OK_SERVICE_READY_FD");
    if (argc != 1 || !service || !generation || !epoch_text || !ready || getppid() != 1 ||
        getuid() || geteuid() || getgid() || getegid()) return failure(1);
    uint32_t epoch = (uint32_t)atoi(epoch_text);
    if (!strcmp(service, "guard")) return guard(atoi(ready), epoch);
    if (strcmp(service, "console") || !epoch || epoch > OK_CONSOLE_EPOCH_MAX || atoi(ready) != -1) return failure(2);
    unsigned pass = (unsigned)atoi(generation);
    if (pass != 1 && pass != 2) return failure(3);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_CONSOLE_LEADER generation="); nf_number(&record, pass);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " parent=1 epoch="); nf_number(&record, epoch); nf_text(&record, "\n");
    if (nf_emit(&record)) return failure(4);
    return pass == 1 ? first_console(epoch) : next_console(epoch);
}
