#include "../../apps/init/native_control_client.h"
#include "native_fixture_record.h"
#include <stdlib.h>
#include <sys/wait.h>
#include <time.h>

/* An adopted observer must prevent completion until its own exit is reaped. */
static void brief(void)
{
    const struct timespec delay = {0, 10000000};
    (void)nanosleep(&delay, 0);
}
static int failure(unsigned code)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_QUIESCE_FAIL code="); nf_number(&record, code);
    nf_text(&record, "\n"); (void)nf_emit(&record); return 1;
}
static int state(struct nc_state *out)
{
    struct nc_buffer reply;
    return nc_exchange(NC_PREFIX "STATE\n", sizeof(NC_PREFIX "STATE\n") - 1, &reply) ||
        nc_state_snapshot(&reply, out) ? -1 : 0;
}
static int wait_child(pid_t child)
{
    for (unsigned i = 0; i < 500; ++i) {
        int status = 0;
        pid_t found = waitpid(child, &status, WNOHANG);
        if (found == child) return WIFEXITED(status) && !WEXITSTATUS(status) ? 0 : -1;
        if (found < 0 && errno != EINTR) return -1;
        brief();
    }
    return -1;
}
static int error_reply(const char *request, size_t size, const char *code)
{
    struct nc_buffer reply, expected = {0};
    nc_text(&expected, NC_PREFIX "ERROR code="); nc_text(&expected, code);
    nc_text(&expected, "\nEND\n");
    return nc_exchange(request, size, &reply) != 1 || reply.size != expected.size ||
        memcmp(reply.bytes, expected.bytes, reply.size) ? -1 : 0;
}
static int denied(void)
{
    struct nc_state observed;
    if (setresgid(1000, 1000, 1000) || setresuid(1000, 1000, 1000) ||
        state(&observed) || strcmp(observed.phase, "running") ||
        error_reply(NC_PREFIX "QUIESCE\n", sizeof(NC_PREFIX "QUIESCE\n") - 1, "denied") ||
        state(&observed) || strcmp(observed.phase, "running") ||
        observed.started_ms || observed.deadline_ms) return failure(10);
    return nf_marker("\nNATIVE_QUIESCE_DENIED uid=1000 state=public mutation=unchanged\n") ? failure(11) : 0;
}
static int cli_quiesce(void)
{
    pid_t child = fork();
    if (child < 0) return -1;
    if (!child) {
        char *arguments[] = {"/bin/service-ctl", "quiesce", 0};
        char *environment[] = {"PATH=/bin", "HOME=/", 0};
        execve(arguments[0], arguments, environment); _Exit(failure(12));
    }
    return wait_child(child);
}
static int observer(void)
{
    for (unsigned i = 0; getppid() != 1; ++i) {
        if (i == 500) return failure(1);
        brief();
    }
    pid_t child = fork();
    if (child < 0) return failure(2);
    if (!child) _Exit(denied());
    if (wait_child(child)) return failure(3);
    struct nc_state observed;
    if (state(&observed) || strcmp(observed.phase, "running") ||
        strcmp(observed.graph, "running")) return failure(4);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_QUIESCE_BEGIN observer="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " parent=1\n"); if (nf_emit(&record) || cli_quiesce()) return failure(5);
    int stopped = 0;
    for (unsigned i = 0; i < 2000; ++i) {
        if (state(&observed) || strcmp(observed.phase, "quiescing") ||
            (strcmp(observed.children, "live") && strcmp(observed.children, "unknown"))) return failure(6);
        if (!strcmp(observed.graph, "stopped") && !strcmp(observed.children, "live")) { stopped = 1; break; }
        brief();
    }
    if (!stopped) return failure(7);
    const uint64_t started = observed.started_ms, deadline = observed.deadline_ms;
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_QUIESCE_HELD observer="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " phase="); nf_text(&record, observed.phase);
    nf_text(&record, " graph="); nf_text(&record, observed.graph);
    nf_text(&record, " children="); nf_text(&record, observed.children);
    nf_text(&record, " started_ms="); nf_number(&record, started);
    nf_text(&record, " deadline_ms="); nf_number(&record, deadline);
    nf_text(&record, "\n"); if (nf_emit(&record)) return failure(17);
    struct nc_buffer reply;
    struct nc_cursor cursor;
    uint64_t duplicate_started = 0, duplicate_deadline = 0;
    if (nc_exchange(NC_PREFIX "QUIESCE\n", sizeof(NC_PREFIX "QUIESCE\n") - 1, &reply)) return failure(8);
    cursor = (struct nc_cursor){reply.bytes, reply.size, 0};
    if (nc_take(&cursor, NC_PREFIX "QUIESCE accepted=1 ") ||
        nc_quiesce_line(&cursor, &duplicate_started, &duplicate_deadline) ||
        duplicate_started != started || duplicate_deadline != deadline ||
        error_reply(NC_PREFIX "RESTART provider\n", sizeof(NC_PREFIX "RESTART provider\n") - 1, "busy"))
        return failure(9);
    for (unsigned i = 0; i < 20; ++i) {
        if (state(&observed) || strcmp(observed.phase, "quiescing") ||
            strcmp(observed.graph, "stopped") || strcmp(observed.children, "live") ||
            observed.started_ms != started || observed.deadline_ms != deadline) return failure(13);
        brief();
    }
    record = (struct native_fixture_record){0};
    nf_text(&record, "\nNATIVE_QUIESCE_RELEASE observer="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " graph=stopped children=live duplicate=pass restart=busy wait_exit=37\n");
    return nf_emit(&record) ? failure(14) : 37;
}
int main(void)
{
    if (geteuid() || getpid() <= 1) return failure(15);
    pid_t child = fork();
    if (child < 0) return failure(16);
    if (!child) _Exit(observer());
    return 0;
}
