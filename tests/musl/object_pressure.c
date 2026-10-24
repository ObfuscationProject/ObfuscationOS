/* Real process and anonymous-page pressure around public musl poll. */
#include <errno.h>
#include <poll.h>
#include <stdint.h>
#include "../probe_output.h"
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define LIMIT 12
#define PAGE 4096
#define CHILD_PAGES 256
#define CHECK(x) do { if (!(x)) { probe_failure("OBJECT_PRESSURE_FAIL", __LINE__, errno); } } while (0)
struct report { int child, pages, completed; };
static int releases[LIMIT];
static pid_t children[LIMIT];
static int ready[2];

static void child(int index, int reader)
{
    void *pages[CHILD_PAGES];
    unsigned count = 0;
    CHECK(close(ready[0]) == 0);
    for (int i = 0; i <= index; ++i) CHECK(close(releases[i]) == 0);
    for (; count < CHILD_PAGES; ++count)
    {
        pages[count] = mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (pages[count] == MAP_FAILED) { CHECK(errno == ENOMEM); break; }
        volatile unsigned char *bytes = pages[count];
        CHECK(bytes[0] == 0 && bytes[PAGE - 1] == 0);
        bytes[0] = (unsigned char)(count + 1);
        bytes[PAGE - 1] = (unsigned char)(index + 1);
    }
    CHECK(count > 0 && count <= CHILD_PAGES);
    struct report report = {index, (int)count, 0};
    CHECK(write(ready[1], &report, sizeof report) == sizeof report);
    struct pollfd wait = {reader, POLLIN, 0};
    CHECK(poll(&wait, 1, -1) == 1 && wait.revents == POLLIN);
    unsigned char byte = 0;
    CHECK(read(reader, &byte, 1) == 1 && byte == 42);
    for (unsigned i = 0; i < count; ++i)
    {
        volatile unsigned char *bytes = pages[i];
        CHECK(bytes[0] == (unsigned char)(i + 1) && bytes[PAGE - 1] == (unsigned char)(index + 1));
        CHECK(munmap(pages[i], PAGE) == 0);
    }
    report.completed = 1;
    CHECK(write(ready[1], &report, sizeof report) == sizeof report);
    CHECK(close(reader) == 0 && close(ready[1]) == 0);
    _exit(0);
}

int main(void)
{
    CHECK(pipe(ready) == 0);
    int count = 0, first = 0, last = 0, total = 0;
    for (; count < LIMIT; ++count)
    {
        int release[2];
        CHECK(pipe(release) == 0);
        releases[count] = release[1];
        children[count] = fork();
        CHECK(children[count] >= 0);
        if (!children[count]) child(count, release[0]);
        CHECK(close(release[0]) == 0);
        struct report report;
        CHECK(read(ready[0], &report, sizeof report) == sizeof report);
        CHECK(report.child == count && report.pages > 0 && report.completed == 0);
        if (!count) first = report.pages;
        last = report.pages;
        total += last;
        CHECK(last <= first);
        /* Each child caps its allocation to keep room for subsequent peers. A
           smaller final allocation demonstrates the shared user quota. */
        if (last < first) { ++count; break; }
    }
    CHECK(count > 1 && count < LIMIT && last < first);
    struct timespec delay = {0, 10000000};
    CHECK(nanosleep(&delay, 0) == 0);
    for (int i = 0; i < count; ++i)
    {
        const unsigned char byte = 42;
        CHECK(write(releases[i], &byte, 1) == 1);
        struct report report;
        CHECK(read(ready[0], &report, sizeof report) == sizeof report);
        CHECK(report.child == i && report.completed == 1);
        int status;
        CHECK(waitpid(children[i], &status, 0) == children[i] && WIFEXITED(status) && WEXITSTATUS(status) == 0);
        CHECK(close(releases[i]) == 0);
    }
    CHECK(close(ready[0]) == 0 && close(ready[1]) == 0);
    void *reuse = mmap(0, 16 * PAGE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(reuse != MAP_FAILED);
    CHECK(munmap(reuse, 16 * PAGE) == 0);
    struct pollfd invalid = {-1, POLLIN, 123};
    CHECK(poll(&invalid, 1, 0) == 0 && invalid.revents == 0);
    probe_text("OK_MUSL_OBJECT_PRESSURE children="); probe_number(count);
    probe_text(" pages="); probe_number(total); probe_text(" first="); probe_number(first);
    probe_text(" last="); probe_number(last); probe_text(" poll=pass reclaim=pass reuse=pass\n");
    return 0;
}
