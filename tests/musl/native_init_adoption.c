/* Native PID 1 / orphan-adoption guest. This file is installed as /init. */
#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static const char *stage = "startup";

static void record(const char *format, ...)
{
    char buffer[256];
    va_list args;
    va_start(args, format);
    int size = vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (size <= 0 || (unsigned)size >= sizeof(buffer) || write(1, buffer, size) != size)
        _Exit(91);
}

static __attribute__((noreturn)) void fail(unsigned line)
{
    record("INIT_ADOPTION_FAIL line=%u stage=%s errno=%d\n", line, stage, errno);
    _Exit(90);
}

#define CHECK(expression) do { if (!(expression)) fail(__LINE__); } while (0)

static void exact_read(int descriptor, void *buffer, unsigned size)
{
    unsigned done = 0;
    while (done < size)
    {
        ssize_t received = read(descriptor, (char *)buffer + done, size - done);
        if (received == -1 && errno == EINTR) continue;
        CHECK(received > 0);
        done += received;
    }
}

static void exact_write(int descriptor, const void *buffer, unsigned size)
{
    unsigned done = 0;
    while (done < size)
    {
        ssize_t sent = write(descriptor, (const char *)buffer + done, size - done);
        if (sent == -1 && errno == EINTR) continue;
        CHECK(sent > 0);
        done += sent;
    }
}

static sigset_t child_signals(void)
{
    sigset_t set;
    CHECK(sigemptyset(&set) == 0 && sigaddset(&set, SIGCHLD) == 0);
    return set;
}

static void notification(const char *case_name, const char *owner, pid_t child, int code)
{
    sigset_t set = child_signals();
    siginfo_t info;
    struct timespec timeout = {2, 0};
    CHECK(sigtimedwait(&set, &info, &timeout) == SIGCHLD);
    CHECK(info.si_pid == child && info.si_code == CLD_EXITED && info.si_status == code);
    record("INIT_ADOPTION_SIGNAL case=%s owner=%s child=%ld status=%d\n",
           case_name, owner, (long)child, code);
}

static pid_t wait_any(int code)
{
    int status = -1;
    pid_t child = waitpid(-1, &status, 0);
    CHECK(child > 1 && status == (code << 8));
    record("INIT_ADOPTION_WAIT child=%ld status=%d\n", (long)child, status);
    return child;
}

static void live_orphan(void)
{
    stage = "live";
    int gate[2], identity[2];
    CHECK(pipe(gate) == 0 && pipe(identity) == 0);
    pid_t service = fork();
    CHECK(service >= 0);
    if (service == 0)
    {
        CHECK(close(gate[1]) == 0 && close(identity[0]) == 0);
        pid_t grandchild = fork();
        CHECK(grandchild >= 0);
        if (grandchild == 0)
        {
            char go;
            CHECK(close(identity[1]) == 0);
            exact_read(gate[0], &go, 1);
            CHECK(go == 'G' && getppid() == 1);
            record("INIT_ADOPTION_GRANDCHILD case=live pid=%ld ppid=%ld\n",
                   (long)getpid(), (long)getppid());
            _Exit(23);
        }
        exact_write(identity[1], &grandchild, sizeof(grandchild));
        _Exit(17);
    }
    CHECK(close(gate[0]) == 0 && close(identity[1]) == 0);
    pid_t grandchild = -1;
    exact_read(identity[0], &grandchild, sizeof(grandchild));
    CHECK(close(identity[0]) == 0 && grandchild > 1 && grandchild != service);
    CHECK(wait_any(17) == service);
    notification("live", "init", service, 17);
    exact_write(gate[1], "G", 1);
    CHECK(close(gate[1]) == 0);
    CHECK(wait_any(23) == grandchild);
    notification("live", "init", grandchild, 23);
    record("INIT_ADOPTION_CASE case=live service=%ld grandchild=%ld pass=1\n",
           (long)service, (long)grandchild);
}

static void completed_orphan(void)
{
    stage = "completed";
    int identity[2];
    CHECK(pipe(identity) == 0);
    pid_t service = fork();
    CHECK(service >= 0);
    if (service == 0)
    {
        CHECK(close(identity[0]) == 0);
        pid_t grandchild = fork();
        CHECK(grandchild >= 0);
        if (grandchild == 0)
        {
            CHECK(close(identity[1]) == 0);
            _Exit(31);
        }
        notification("completed", "service", grandchild, 31); /* Deliberately unreaped. */
        exact_write(identity[1], &grandchild, sizeof(grandchild));
        _Exit(19);
    }
    CHECK(close(identity[1]) == 0);
    pid_t grandchild = -1;
    exact_read(identity[0], &grandchild, sizeof(grandchild));
    CHECK(close(identity[0]) == 0 && grandchild > 1 && grandchild != service);
    CHECK(wait_any(19) == service);
    notification("completed", "init", service, 19);
    CHECK(wait_any(31) == grandchild);
    record("INIT_ADOPTION_CASE case=completed service=%ld grandchild=%ld pass=1\n",
           (long)service, (long)grandchild);
}

int main(void)
{
    CHECK(getpid() == 1 && getppid() == 0);
    sigset_t set = child_signals();
    CHECK(sigprocmask(SIG_BLOCK, &set, 0) == 0);
    record("INIT_ADOPTION_BEGIN pid=1 ppid=0\n");
    live_orphan();
    completed_orphan();
    stage = "drained";
    errno = 0;
    CHECK(waitpid(-1, 0, WNOHANG) == -1 && errno == ECHILD);
    record("INIT_ADOPTION_PASS live=1 completed=1 wait_any=1 signal=1 drained=1\n");
    for (;;) pause();
}
