#include <fcntl.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "native_fixture_record.h"

/* A native-personality fixture. Readiness is a real inherited pipe, not metadata. */
static const char *lookup(char **environment, const char *name)
{
    size_t length = strlen(name);
    for (; *environment; ++environment)
        if (!strncmp(*environment, name, length) && (*environment)[length] == '=')
            return *environment + length + 1;
    return 0;
}

static void brief(void)
{
    const struct timespec delay = {0, 10000000};
    (void)nanosleep(&delay, 0);
}

static int generation_file(char *value, int writing)
{
    int descriptor = open("/tmp/native-service-generation", writing ? O_WRONLY | O_CREAT | O_TRUNC : O_RDONLY, 0600);
    if (descriptor < 0) return -1;
    ssize_t count = writing ? write(descriptor, value, 1) : read(descriptor, value, 1);
    return close(descriptor) || count != 1 ? -1 : 0;
}

static int wait_generation(char expected)
{
    for (unsigned i = 0; i < 500; ++i) {
        char observed = 0;
        if (!generation_file(&observed, 0) && observed == expected) return 0;
        brief();
    }
    return -1;
}

static int child_event(const char *name, int generation, const char *event)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "NATIVE_SERVICE_CHILD service="); nf_text(&record, name);
    nf_text(&record, " generation="); nf_number(&record, (unsigned)generation);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " event="); nf_text(&record, event); nf_text(&record, "\n");
    return nf_emit(&record);
}

static int inherited_descriptors(const char *name, int generation, int ready)
{
    /* Native process descriptor capacity is 32; only the notify writer may
     * survive exec beyond stdin/stdout/stderr. Keep this distinct from models. */
    for (int fd = 3; fd < 32; ++fd) {
        errno = 0;
        int flags = fcntl(fd, F_GETFD);
        if (fd == ready ? flags < 0 : (flags >= 0 || errno != EBADF)) return -1;
    }
    struct native_fixture_record record = {0};
    nf_text(&record, "NATIVE_CONTROL_FDS service="); nf_text(&record, name);
    nf_text(&record, " generation="); nf_number(&record, (unsigned)generation);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " inherited=0\n"); return nf_emit(&record);
}

int main(int argc, char **argv, char **environment)
{
    (void)argc; (void)argv;
    const char *name = lookup(environment, "OK_SERVICE_NAME");
    const char *generation_text = lookup(environment, "OK_SERVICE_GENERATION");
    const char *attempt = lookup(environment, "OK_SERVICE_ATTEMPT");
    const char *ready_text = lookup(environment, "OK_SERVICE_READY_FD");
    if (!name || !generation_text || !attempt || !ready_text || getppid() != 1) return 71;
    int generation = atoi(generation_text), ready = atoi(ready_text);
    if (generation < 1 || generation > 3 || atoi(attempt) != generation) return 72;
    if (inherited_descriptors(name, generation, ready)) return 79;
    if (child_event(name, generation, "start")) return 78;
    if (!strcmp(name, "setup")) {
        char initial = '0';
        if (generation != 1 || ready != -1 || generation_file(&initial, 1)) return 73;
        if (nf_marker("NATIVE_SERVICE_SETUP complete=1\n")) return 78;
        return 0;
    }
    if (ready < 3 || (strcmp(name, "provider") && strcmp(name, "dependent"))) return 74;
    if (write(ready, "R", 1) != 1 || close(ready)) return 75;
    if (child_event(name, generation, "notify")) return 78;
    if (!strcmp(name, "provider")) {
        if (generation == 1) {
            if (wait_generation('1')) return 76;
            for (unsigned i = 0; i < 10; ++i) brief();
            if (nf_marker("NATIVE_SERVICE_PROVIDER crash=42\n")) return 78;
            return 42;
        }
    } else {
        char value = generation == 1 ? '1' : '2';
        if (generation_file(&value, 1)) return 77;
        if (generation == 2 && nf_marker("NATIVE_SERVICE_GRAPH stable=2 dependency_restart=pass\n")) return 78;
    }
    for (;;) brief();
}
