/* PID1 `console` service. getty holds the console lease, opens one devpts
 * pair per session, runs /bin/login on the slave as a new session leader and
 * relays bytes between the console and the master. When the session ends it
 * closes the master, which hangs up whatever is left on the slave, reaps
 * login and exits; PID1 then starts it again under a new lease epoch.
 *
 * getty never makes the console its controlling terminal and leaves its
 * raw-compatible termios alone: the pts line discipline echoes, edits lines
 * and turns keys into signals. Native programs have no signal handlers, so no
 * call here returns EINTR. One `GETTY event=...` line per session event is
 * written to the console (docs/native-init.md). */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#define GETTY_LOGIN "/bin/login"
#define GETTY_PTS_PREFIX "/dev/pts/"
#define GETTY_TICK_MS 100
/* After the hangup the session gets this many ticks to exit before SIGKILL. */
#define GETTY_GRACE_TICKS 30
#define GETTY_CHUNK 256
/* Bounded drain of output still queued on the master when the session ends. */
#define GETTY_DRAIN_READS 64

enum getty_end { GETTY_EXIT, GETTY_HANGUP, GETTY_REVOKED };

struct getty {
    int master;
    pid_t child;
    unsigned pts;
    int status, reaped, line_open;
    unsigned char pending[GETTY_CHUNK];
    size_t pending_used, pending_sent;
};

static char *getty_decimal(char *end, long long value)
{
    unsigned long long magnitude = value < 0 ? 0ULL - (unsigned long long)value : (unsigned long long)value;
    *--end = 0;
    do { *--end = (char)('0' + magnitude % 10U); magnitude /= 10U; } while (magnitude);
    if (value < 0) *--end = '-';
    return end;
}

/* Console output: every byte or the console is gone. */
static int getty_put(struct getty *getty, const void *data, size_t size)
{
    const unsigned char *bytes = data;
    while (size) {
        ssize_t count = write(STDOUT_FILENO, bytes, size);
        if (count <= 0 || (size_t)count > size) return -1;
        getty->line_open = bytes[count - 1] != '\n';
        bytes += count;
        size -= (size_t)count;
    }
    return 0;
}

/* An event line is written with one call, so other console writers (PID1,
 * kernel diagnostics) cannot split it. */
struct getty_line {
    char text[160];
    size_t used;
};

static void getty_append(struct getty_line *line, const char *text)
{
    while (*text && line->used + 2 < sizeof(line->text)) line->text[line->used++] = *text++;
}

static void getty_number(struct getty_line *line, const char *name, long long value)
{
    char digits[24];
    getty_append(line, name);
    getty_append(line, getty_decimal(digits + sizeof(digits), value));
}

/* GETTY event=<kind> ...: always a line of its own. */
static void getty_begin(const struct getty *getty, struct getty_line *line, const char *kind)
{
    line->used = 0;
    if (getty->line_open) getty_append(line, "\n");
    getty_append(line, "GETTY event=");
    getty_append(line, kind);
}

static void getty_emit(struct getty *getty, struct getty_line *line)
{
    line->text[line->used++] = '\n';
    (void)getty_put(getty, line->text, line->used);
}

static int getty_failed(struct getty *getty, const char *stage, int error)
{
    struct getty_line line;
    getty_begin(getty, &line, "error");
    getty_append(&line, " stage=");
    getty_append(&line, stage);
    getty_number(&line, " errno=", error);
    getty_emit(getty, &line);
    return 1;
}

static int getty_open(struct getty *getty, char *path, size_t size)
{
    struct winsize window = {.ws_row = 24, .ws_col = 80};
    const char *digits = path + sizeof(GETTY_PTS_PREFIX) - 1;
    int flags;
    getty->master = posix_openpt(O_RDWR | O_NOCTTY);
    if (getty->master < 0) return -1;
    /* No login or shell descendant may keep the master: getty's close must be
     * its last close, which is what hangs the session up. */
    if (fcntl(getty->master, F_SETFD, FD_CLOEXEC) < 0 ||
        (flags = fcntl(getty->master, F_GETFL)) < 0 ||
        fcntl(getty->master, F_SETFL, flags | O_NONBLOCK) < 0 ||
        grantpt(getty->master) < 0 || unlockpt(getty->master) < 0 ||
        ptsname_r(getty->master, path, size) != 0 ||
        ioctl(getty->master, TIOCSWINSZ, (void *)&window) < 0) return -1;
    if (strncmp(path, GETTY_PTS_PREFIX, sizeof(GETTY_PTS_PREFIX) - 1) || !*digits) { errno = EIO; return -1; }
    for (getty->pts = 0; *digits; ++digits) {
        if (*digits < '0' || *digits > '9' || getty->pts > 9999) { errno = EIO; return -1; }
        getty->pts = getty->pts * 10U + (unsigned)(*digits - '0');
    }
    return 0;
}

static void getty_child_failed(const char *stage)
{
    int error = errno;
    struct getty report = {.line_open = 1};
    (void)getty_failed(&report, stage, error);
    _Exit(127);
}

/* The forked child: a new session that acquires the slave by opening it. */
static void getty_child(int master, const char *path, char **environment)
{
    static const int defaults[] = {SIGHUP, SIGINT, SIGQUIT, SIGTERM, SIGCHLD, SIGCONT,
                                   SIGTSTP, SIGTTIN, SIGTTOU, SIGWINCH};
    char *arguments[] = {GETTY_LOGIN, 0};
    char *kept[3] = {0, 0, 0};
    size_t used = 0;
    int terminal;
    for (size_t i = 0; i < sizeof(defaults) / sizeof(defaults[0]); ++i)
        if (signal(defaults[i], SIG_DFL) == SIG_ERR) getty_child_failed("signals");
    if (close(master) < 0) getty_child_failed("master");
    if (setsid() < 0) getty_child_failed("setsid");
    terminal = open(path, O_RDWR);
    if (terminal < 0) getty_child_failed("open");
    /* Acquisition on open is silent; a session that did not get the slave
     * would run login without a controlling terminal. */
    if (tcgetsid(terminal) != getpid()) { errno = ENOTTY; getty_child_failed("ctty"); }
    for (int fd = 0; fd < 3; ++fd)
        if (terminal != fd && dup2(terminal, fd) < 0) getty_child_failed("dup");
    if (terminal > 2 && close(terminal) < 0) getty_child_failed("close");
    /* login reads only its lease epoch; TERM is kept for the terminal type. */
    for (size_t i = 0; environment && environment[i] && used < 2; ++i)
        if (!strncmp(environment[i], "OK_CONSOLE_EPOCH=", sizeof("OK_CONSOLE_EPOCH=") - 1) ||
            !strncmp(environment[i], "TERM=", sizeof("TERM=") - 1)) kept[used++] = environment[i];
    execve(arguments[0], arguments, kept);
    getty_child_failed("exec");
}

static void getty_reap(struct getty *getty, int options)
{
    int status = 0;
    if (getty->reaped) return;
    pid_t pid = waitpid(getty->child, &status, options);
    if (pid == getty->child) {
        getty->reaped = 1;
        getty->status = status;
    } else if (pid < 0) {
        /* The child is gone without a status; never wait for it again. */
        getty->reaped = 1;
        getty->status = -1;
    }
}

/* Master output to the console. Returns 1 while the slave is open, 0 once it
 * is hung up (EIO after the last slave close), -1 when the console failed. */
static int getty_output(struct getty *getty)
{
    unsigned char buffer[GETTY_CHUNK];
    ssize_t count = read(getty->master, buffer, sizeof(buffer));
    if (count < 0 && errno == EAGAIN) return 1;
    if (count <= 0) return 0;
    return getty_put(getty, buffer, (size_t)count) < 0 ? -1 : 1;
}

/* Console input waiting for the master. Returns 0 once it is all written or
 * the master is full, -1 when the master refused it. */
static int getty_input(struct getty *getty)
{
    while (getty->pending_sent < getty->pending_used) {
        size_t size = getty->pending_used - getty->pending_sent;
        ssize_t count = write(getty->master, getty->pending + getty->pending_sent, size);
        if (count < 0 && errno == EAGAIN) return 0;
        if (count <= 0 || (size_t)count > size) return -1;
        getty->pending_sent += (size_t)count;
    }
    getty->pending_used = getty->pending_sent = 0;
    return 0;
}

static enum getty_end getty_relay(struct getty *getty)
{
    for (;;) {
        struct pollfd fds[2];
        int pending = getty->pending_used != 0;
        getty_reap(getty, WNOHANG);
        if (getty->reaped) return GETTY_EXIT;
        /* Console input waits while earlier input still fills the master. */
        fds[0] = (struct pollfd){.fd = STDIN_FILENO, .events = pending ? 0 : POLLIN};
        fds[1] = (struct pollfd){.fd = getty->master, .events = POLLIN | (pending ? POLLOUT : 0)};
        int ready = poll(fds, 2, GETTY_TICK_MS);
        if (ready < 0) return GETTY_REVOKED;
        if (!ready) continue;
        /* A revoked or retired lease reports POLLERR|POLLHUP on the console. */
        if (fds[0].revents & (POLLERR | POLLHUP | POLLNVAL)) return GETTY_REVOKED;
        if (fds[1].revents & POLLIN) {
            int open = getty_output(getty);
            if (open < 0) return GETTY_REVOKED;
            if (!open) return GETTY_HANGUP;
        } else if (fds[1].revents & (POLLHUP | POLLERR | POLLNVAL)) return GETTY_HANGUP;
        if (pending && (fds[1].revents & POLLOUT) && getty_input(getty) < 0) return GETTY_HANGUP;
        if (fds[0].revents & POLLIN) {
            ssize_t count = read(STDIN_FILENO, getty->pending, sizeof(getty->pending));
            if (count <= 0 || (size_t)count > sizeof(getty->pending)) return GETTY_REVOKED;
            getty->pending_used = (size_t)count;
            getty->pending_sent = 0;
            if (getty_input(getty) < 0) return GETTY_HANGUP;
        }
    }
}

static void getty_pause(void)
{
    struct timespec tick = {0, GETTY_TICK_MS * 1000000L};
    (void)nanosleep(&tick, 0);
}

static void getty_finish(struct getty *getty, enum getty_end end)
{
    static const char *const reasons[] = {"exit", "hangup", "revoked"};
    /* Output the session wrote before it ended still reaches the console. */
    for (int i = 0; end != GETTY_REVOKED && i < GETTY_DRAIN_READS; ++i) {
        unsigned char buffer[GETTY_CHUNK];
        ssize_t count = read(getty->master, buffer, sizeof(buffer));
        if (count <= 0 || getty_put(getty, buffer, (size_t)count) < 0) break;
    }
    /* The last master close hangs the session up: SIGHUP and SIGCONT to its
     * leader, and the slave reads 0 and writes EIO for anything left. */
    (void)close(getty->master);
    getty->master = -1;
    for (int tick = 0; !getty->reaped; ++tick) {
        getty_reap(getty, tick > GETTY_GRACE_TICKS ? 0 : WNOHANG);
        if (getty->reaped) break;
        if (tick == GETTY_GRACE_TICKS) (void)kill(getty->child, SIGKILL);
        else getty_pause();
    }
    struct getty_line line;
    getty_begin(getty, &line, "close");
    getty_number(&line, " pts=", getty->pts);
    getty_number(&line, " pid=", getty->child);
    getty_number(&line, " status=", getty->status);
    getty_append(&line, " reason=");
    getty_append(&line, reasons[end]);
    getty_emit(getty, &line);
}

int main(int argc, char **argv, char **environment)
{
    struct getty getty = {.master = -1};
    char path[32];
    (void)argv;
    if (argc != 1) return getty_failed(&getty, "arguments", EINVAL);
    if (getty_open(&getty, path, sizeof(path)) < 0) {
        int error = errno;
        if (getty.master >= 0) (void)close(getty.master);
        return getty_failed(&getty, "open", error);
    }
    getty.child = fork();
    if (getty.child < 0) {
        int error = errno;
        (void)close(getty.master);
        return getty_failed(&getty, "fork", error);
    }
    if (!getty.child) getty_child(getty.master, path, environment);
    struct getty_line line;
    getty_begin(&getty, &line, "open");
    getty_number(&line, " pts=", getty.pts);
    getty_number(&line, " pid=", getty.child);
    getty_emit(&getty, &line);
    getty_finish(&getty, getty_relay(&getty));
    return 0;
}
