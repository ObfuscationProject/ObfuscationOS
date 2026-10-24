#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "service_generation.h"

static volatile sig_atomic_t stopping;
static const char *service_name;
static unsigned generation, attempt;
static void stop(int number) { (void)number; stopping = 1; }

static void mark(const char *kind, long value)
{
    char text[224];
    int size = snprintf(text, sizeof(text),
        "SERVICE_CHILD kind=%s name=%s generation=%u attempt=%u pid=%ld value=%ld\n",
        kind, service_name, generation, attempt, (long)getpid(), value);
    if (size > 0 && (size_t)size < sizeof(text)) (void)write(1, text, (size_t)size);
}

static void brief(void)
{
    const struct timespec time = {.tv_sec = 0, .tv_nsec = 10000000L};
    (void)nanosleep(&time, 0);
}

static int write_generation(char value)
{
    return generation_write(value);
}

static int wait_generation(char value)
{
    for (unsigned i = 0; i < 500 && !stopping; ++i) {
        char got = 0;
        if (generation_read(&got)) { mark("generation-read-error", errno); return -1; }
        int progress = generation_progress(got, value);
        if (progress < 0) { mark("generation-read-error", errno); return -1; }
        if (progress) return 0;
        brief();
    }
    return -1;
}

static int orphan(void)
{
    int report[2];
    if (pipe(report)) return -1;
    pid_t middle = fork();
    if (middle < 0) return -1;
    if (middle == 0) {
        close(report[0]);
        pid_t adopted = fork();
        if (adopted < 0) _Exit(81);
        if (adopted > 0) _Exit(0);
        for (unsigned i = 0; i < 300 && getppid() != 1; ++i) brief();
        if (getppid() != 1) _Exit(82);
        mark("orphan", (long)getppid());
        if (write(report[1], "O", 1) != 1) _Exit(83);
        close(report[1]);
        _Exit(17);
    }
    close(report[1]);
    int status;
    if (waitpid(middle, &status, 0) != middle || !WIFEXITED(status) || WEXITSTATUS(status)) return -1;
    char acknowledgment = 0;
    ssize_t size;
    do { size = read(report[0], &acknowledgment, 1); } while (size < 0 && errno == EINTR);
    close(report[0]);
    return size == 1 && acknowledgment == 'O' ? 0 : -1;
}

int main(void)
{
    service_name = getenv("OK_SERVICE_NAME");
    const char *generation_text = getenv("OK_SERVICE_GENERATION");
    const char *attempt_text = getenv("OK_SERVICE_ATTEMPT");
    const char *descriptor_text = getenv("OK_SERVICE_READY_FD");
    if (!service_name || !generation_text || !attempt_text || !descriptor_text || getppid() != 1) return 71;
    generation = (unsigned)atoi(generation_text);
    attempt = (unsigned)atoi(attempt_text);
    int ready = atoi(descriptor_text);
    if (!generation || !attempt || attempt > 2) return 72;
    mark("start", 0);
    if (!strcmp(service_name, "setup")) {
        if (attempt != 1 || generation != 1 || ready != -1) return 73;
        if (write_generation('0')) { mark("setup-generation-error", errno); return 74; }
        mark("setup", 0);
        return 0;
    }
    if (ready < 3 || (strcmp(service_name, "upstream") && strcmp(service_name, "downstream"))) return 75;
    struct sigaction action = {0};
    action.sa_handler = stop;
    if (sigemptyset(&action.sa_mask) || sigaction(SIGTERM, &action, 0)) return 76;
    if (write(ready, "R", 1) != 1 || close(ready)) return 77;
    mark("notify", 0);
    if (!strcmp(service_name, "upstream")) {
        if (wait_generation(attempt == 1 ? '1' : '2')) return 78;
        if (attempt == 1) {
            for (unsigned i = 0; i < 10; ++i) brief();
            mark("crash", 42);
            _Exit(42);
        }
    } else {
        for (unsigned i = 0; i < 10; ++i) brief();
        if (write_generation(attempt == 1 ? '1' : '2')) {
            mark("generation-write-error", errno);
            return 79;
        }
        if (attempt == 2) {
            for (unsigned i = 0; i < 20; ++i) brief();
            mark("request-stop", 1);
            if (kill(1, SIGTERM)) return 80;
        }
    }
    for (unsigned i = 0; i < 500 && !stopping; ++i) brief();
    if (!stopping) return 84;
    if (!strcmp(service_name, "downstream") && attempt == 1 && orphan()) return 85;
    mark("stop", 0);
    return 0;
}
