/* Linux personality interval timers on the guest: alarm, setitimer/getitimer,
 * the timer_create family (SIGEV_SIGNAL, SIGEV_NONE, musl SIGEV_THREAD), signal
 * overruns, sleep interruption, CLOCK_REALTIME absolute expiry, and the fork
 * and exec rules. Prints one TIMERS_PASS line, or TIMERS_FAIL with a code. */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#if defined(__i386__)
#define PROBE_ARCH "i386"
#elif defined(__x86_64__)
#define PROBE_ARCH "x86_64"
#elif defined(__arm__)
#define PROBE_ARCH "arm32"
#elif defined(__aarch64__)
#define PROBE_ARCH "aarch64"
#elif defined(__riscv) && __riscv_xlen == 32
#define PROBE_ARCH "rv32"
#elif defined(__riscv) && __riscv_xlen == 64
#define PROBE_ARCH "rv64"
#elif defined(__mips64)
#define PROBE_ARCH "mips64"
#elif defined(__mips__)
#define PROBE_ARCH "mips"
#elif defined(__loongarch64)
#define PROBE_ARCH "loongarch64"
#elif defined(__powerpc__) || defined(__PPC__)
#define PROBE_ARCH "ppc"
#else
#error "Unsupported timer probe profile"
#endif

#define MS 1000000LL

static int checks;
static __attribute__((noreturn)) void fail(int code, long detail)
{
    printf("TIMERS_FAIL arch=%s code=%d detail=%ld errno=%d\n", PROBE_ARCH, code, detail, errno);
    fflush(stdout);
    _exit(1);
}
#define CHECK(c, n) do { ++checks; if (!(c)) fail((n), 0); } while (0)
#define CHECKV(c, n, v) do { ++checks; if (!(c)) fail((n), (long)(v)); } while (0)

static int64_t now(int clock)
{
    struct timespec t;
    if (clock_gettime(clock, &t)) fail(1, clock);
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}
static void pause_for(int64_t ns)
{
    struct timespec t = {ns / 1000000000, ns % 1000000000};
    while (nanosleep(&t, &t) && errno == EINTR) {}
}
static void block(int signal, int how)
{
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, signal);
    if (sigprocmask(how, &set, 0)) fail(2, signal);
}
static int wait_for(int signal, siginfo_t *info)
{
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, signal);
    int got;
    while ((got = sigwaitinfo(&set, info)) < 0 && errno == EINTR) {}
    return got;
}

static volatile sig_atomic_t alarms;
static volatile int alarm_code;
static void on_alarm(int signal, siginfo_t *info, void *context)
{
    (void)signal; (void)context;
    alarm_code = info->si_code;
    ++alarms;
}
static void catch_alarm(int flags)
{
    struct sigaction action;
    memset(&action, 0, sizeof action);
    action.sa_sigaction = on_alarm;
    action.sa_flags = SA_SIGINFO | flags;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGALRM, &action, 0)) fail(3, 0);
}
static void disarm(void)
{
    struct itimerval zero;
    memset(&zero, 0, sizeof zero);
    if (setitimer(ITIMER_REAL, &zero, 0)) fail(4, 0);
}

/* 1xx: alarm rounds the old remainder up and shares ITIMER_REAL. */
static void case_alarm(void)
{
    CHECK(alarm(5) == 0, 101);
    unsigned left = alarm(0);
    CHECKV(left == 5, 102, left);
    struct itimerval it;
    CHECK(getitimer(ITIMER_REAL, &it) == 0 && !it.it_value.tv_sec && !it.it_value.tv_usec, 103);
}

/* 2xx: a one-shot ITIMER_REAL wakes sigsuspend with SI_KERNEL SIGALRM. */
static int64_t oneshot_late;
static void case_oneshot(void)
{
    catch_alarm(0);
    block(SIGALRM, SIG_BLOCK);
    alarms = 0;
    struct itimerval it = {{0, 0}, {0, 50000}};
    int64_t start = now(CLOCK_MONOTONIC);
    CHECK(setitimer(ITIMER_REAL, &it, 0) == 0, 201);
    sigset_t open;
    sigemptyset(&open);
    while (!alarms) sigsuspend(&open);
    int64_t elapsed = now(CLOCK_MONOTONIC) - start;
    CHECKV(elapsed >= 50 * MS, 202, elapsed);
    CHECKV(alarm_code == SI_KERNEL, 203, alarm_code);
    oneshot_late = elapsed - 50 * MS;
    CHECK(getitimer(ITIMER_REAL, &it) == 0 && !it.it_value.tv_sec && !it.it_value.tv_usec, 204);
    block(SIGALRM, SIG_UNBLOCK);
}

/* 3xx: a periodic ITIMER_REAL rearms after each dequeue. */
static void case_periodic(void)
{
    block(SIGALRM, SIG_BLOCK);
    struct itimerval it = {{0, 20000}, {0, 20000}}, old;
    int64_t start = now(CLOCK_MONOTONIC);
    CHECK(setitimer(ITIMER_REAL, &it, 0) == 0, 301);
    for (int i = 0; i < 5; ++i)
    {
        siginfo_t info;
        CHECK(wait_for(SIGALRM, &info) == SIGALRM && info.si_code == SI_KERNEL, 302);
    }
    int64_t elapsed = now(CLOCK_MONOTONIC) - start;
    CHECKV(elapsed >= 100 * MS, 303, elapsed);
    CHECK(getitimer(ITIMER_REAL, &it) == 0 && it.it_interval.tv_usec == 20000, 304);
    memset(&it, 0, sizeof it);
    CHECK(setitimer(ITIMER_REAL, &it, &old) == 0 && old.it_interval.tv_usec == 20000, 305);
    siginfo_t info;
    struct timespec zero = {0, 0};
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGALRM);
    while (sigtimedwait(&set, &info, &zero) == SIGALRM) {}
    block(SIGALRM, SIG_UNBLOCK);
}

/* 4xx: SIGALRM interrupts nanosleep with EINTR and the remaining time. */
static void case_sleep(void)
{
    catch_alarm(0);
    alarms = 0;
    struct itimerval it = {{0, 0}, {0, 30000}};
    CHECK(setitimer(ITIMER_REAL, &it, 0) == 0, 401);
    struct timespec request = {1, 0}, left = {0, 0};
    errno = 0;
    int result = nanosleep(&request, &left);
    CHECKV(result == -1 && errno == EINTR, 402, result);
    CHECK(alarms == 1, 403);
    CHECKV(left.tv_sec == 0 && left.tv_nsec > 500 * MS, 404, left.tv_nsec);
}

/* 5xx: SIGEV_SIGNAL carries SI_TIMER, the timer id and the sigevent value. */
static int marker;
static void case_signal(void)
{
    block(SIGRTMIN, SIG_BLOCK);
    struct sigevent event;
    memset(&event, 0, sizeof event);
    event.sigev_notify = SIGEV_SIGNAL;
    event.sigev_signo = SIGRTMIN;
    event.sigev_value.sival_ptr = &marker;
    timer_t timer;
    CHECK(timer_create(CLOCK_MONOTONIC, &event, &timer) == 0, 501);
    struct itimerspec spec = {{0, 0}, {0, 30 * MS}}, read;
    int64_t start = now(CLOCK_MONOTONIC);
    CHECK(timer_settime(timer, 0, &spec, 0) == 0, 502);
    CHECK(timer_gettime(timer, &read) == 0 && read.it_value.tv_nsec > 0 && read.it_value.tv_nsec <= 30 * MS, 503);
    siginfo_t info;
    CHECK(wait_for(SIGRTMIN, &info) == SIGRTMIN, 504);
    CHECKV(now(CLOCK_MONOTONIC) - start >= 30 * MS, 505, now(CLOCK_MONOTONIC) - start);
    CHECKV(info.si_code == SI_TIMER, 506, info.si_code);
    CHECK(info.si_value.sival_ptr == &marker, 507);
    CHECKV(info.si_timerid == (int)(intptr_t)timer, 508, info.si_timerid);
    CHECKV(info.si_overrun == 0, 509, info.si_overrun);
    CHECK(timer_gettime(timer, &read) == 0 && !read.it_value.tv_sec && !read.it_value.tv_nsec, 510);
    CHECK(timer_delete(timer) == 0, 511);
    errno = 0;
    CHECK(timer_gettime(timer, &read) == -1 && errno == EINVAL, 512);
    block(SIGRTMIN, SIG_UNBLOCK);
}

/* 6xx: a blocked periodic timer counts its missed intervals as overruns. */
static int overruns;
static void case_overrun(void)
{
    int signal = SIGRTMIN + 1;
    block(signal, SIG_BLOCK);
    struct sigevent event;
    memset(&event, 0, sizeof event);
    event.sigev_notify = SIGEV_SIGNAL;
    event.sigev_signo = signal;
    timer_t timer;
    CHECK(timer_create(CLOCK_MONOTONIC, &event, &timer) == 0, 601);
    struct itimerspec spec = {{0, 10 * MS}, {0, 10 * MS}}, read;
    CHECK(timer_settime(timer, 0, &spec, 0) == 0, 602);
    pause_for(105 * MS);
    siginfo_t info;
    CHECK(wait_for(signal, &info) == signal && info.si_code == SI_TIMER, 603);
    overruns = info.si_overrun;
    CHECKV(overruns >= 3, 604, overruns);
    CHECKV(timer_getoverrun(timer) == overruns, 605, timer_getoverrun(timer));
    CHECK(timer_gettime(timer, &read) == 0 && read.it_interval.tv_nsec == 10 * MS, 606);
    CHECKV(read.it_value.tv_sec == 0 && read.it_value.tv_nsec > 0 && read.it_value.tv_nsec <= 10 * MS, 607,
           read.it_value.tv_nsec);
    pause_for(30 * MS);
    CHECK(timer_delete(timer) == 0, 608);
    sigset_t pending;
    CHECK(sigpending(&pending) == 0 && !sigismember(&pending, signal), 609);
    block(signal, SIG_UNBLOCK);
}

/* 7xx: SIGEV_NONE never signals but reports its remaining time. */
static void case_none(void)
{
    struct sigevent event;
    memset(&event, 0, sizeof event);
    event.sigev_notify = SIGEV_NONE;
    timer_t timer;
    CHECK(timer_create(CLOCK_MONOTONIC, &event, &timer) == 0, 701);
    struct itimerspec spec = {{0, 0}, {0, 200 * MS}}, first, second;
    CHECK(timer_settime(timer, 0, &spec, 0) == 0, 702);
    CHECK(timer_gettime(timer, &first) == 0 && first.it_value.tv_nsec > 0, 703);
    pause_for(50 * MS);
    CHECK(timer_gettime(timer, &second) == 0, 704);
    CHECKV(second.it_value.tv_nsec <= first.it_value.tv_nsec - 40 * MS, 705, second.it_value.tv_nsec);
    spec.it_value.tv_nsec = 1 * MS;
    CHECK(timer_settime(timer, 0, &spec, 0) == 0, 706);
    pause_for(20 * MS);
    CHECK(timer_gettime(timer, &second) == 0 && !second.it_value.tv_sec && !second.it_value.tv_nsec, 707);
    CHECK(timer_delete(timer) == 0, 708);
}

/* 8xx: musl SIGEV_THREAD runs the callback on its SIGEV_THREAD_ID helper. */
static int calls;
static pid_t caller;
static pid_t helper;
static void notified(union sigval value)
{
    if (value.sival_int != 0x5a) fail(801, value.sival_int);
    helper = (pid_t)syscall(SYS_gettid);
    __atomic_fetch_add(&calls, 1, __ATOMIC_SEQ_CST);
}
static void case_thread(void)
{
    caller = (pid_t)syscall(SYS_gettid);
    struct sigevent event;
    memset(&event, 0, sizeof event);
    event.sigev_notify = SIGEV_THREAD;
    event.sigev_notify_function = notified;
    event.sigev_value.sival_int = 0x5a;
    timer_t timer;
    CHECK(timer_create(CLOCK_MONOTONIC, &event, &timer) == 0, 802);
    struct itimerspec spec = {{0, 20 * MS}, {0, 20 * MS}};
    CHECK(timer_settime(timer, 0, &spec, 0) == 0, 803);
    int64_t start = now(CLOCK_MONOTONIC);
    while (__atomic_load_n(&calls, __ATOMIC_SEQ_CST) < 3)
    {
        CHECKV(now(CLOCK_MONOTONIC) - start < 5000 * MS, 804, calls);
        pause_for(10 * MS);
    }
    CHECK(timer_delete(timer) == 0, 805);
    CHECKV(helper && helper != caller, 806, helper);
}

/* 9xx: TIMER_ABSTIME on CLOCK_REALTIME expires at the wall-clock time. */
static const char *realtime = "absent";
static void case_realtime(void)
{
    struct timespec wall;
    if (clock_gettime(CLOCK_REALTIME, &wall)) return;
    int signal = SIGRTMIN + 2;
    block(signal, SIG_BLOCK);
    struct sigevent event;
    memset(&event, 0, sizeof event);
    event.sigev_notify = SIGEV_SIGNAL;
    event.sigev_signo = signal;
    timer_t timer;
    CHECK(timer_create(CLOCK_REALTIME, &event, &timer) == 0, 901);
    int64_t start = now(CLOCK_MONOTONIC), at = now(CLOCK_REALTIME) + 50 * MS;
    struct itimerspec spec = {{0, 0}, {at / 1000000000, at % 1000000000}};
    CHECK(timer_settime(timer, TIMER_ABSTIME, &spec, 0) == 0, 902);
    siginfo_t info;
    CHECK(wait_for(signal, &info) == signal && info.si_code == SI_TIMER, 903);
    CHECKV(now(CLOCK_MONOTONIC) - start >= 45 * MS, 904, now(CLOCK_MONOTONIC) - start);
    CHECKV(now(CLOCK_REALTIME) >= at, 905, at - now(CLOCK_REALTIME));
    CHECK(timer_delete(timer) == 0, 906);
    block(signal, SIG_UNBLOCK);
    realtime = "abstime";
}

/* 10xx: fork inherits no timer. */
static void case_fork(void)
{
    struct itimerval it = {{0, 0}, {10, 0}};
    CHECK(setitimer(ITIMER_REAL, &it, 0) == 0, 1001);
    struct sigevent event;
    memset(&event, 0, sizeof event);
    event.sigev_notify = SIGEV_NONE;
    timer_t timer;
    CHECK(timer_create(CLOCK_MONOTONIC, &event, &timer) == 0, 1002);
    pid_t child = fork();
    CHECK(child >= 0, 1003);
    if (!child)
    {
        struct itimerval left;
        struct itimerspec spec;
        if (getitimer(ITIMER_REAL, &left) || left.it_value.tv_sec || left.it_value.tv_usec) _exit(11);
        errno = 0;
        if (timer_gettime(timer, &spec) != -1 || errno != EINVAL) _exit(12);
        _exit(0);
    }
    int status = -1;
    CHECK(waitpid(child, &status, 0) == child, 1004);
    CHECKV(WIFEXITED(status) && WEXITSTATUS(status) == 0, 1005, status);
    CHECK(getitimer(ITIMER_REAL, &it) == 0 && it.it_value.tv_sec >= 8, 1006);
    CHECK(timer_delete(timer) == 0, 1007);
    disarm();
}

/* 11xx: exec keeps ITIMER_REAL and deletes POSIX timers. */
static int exec_child(const char *id)
{
    struct itimerval left;
    struct itimerspec spec;
    if (getitimer(ITIMER_REAL, &left) || left.it_value.tv_sec < 8) return 21;
    errno = 0;
    if (timer_gettime((timer_t)(intptr_t)atoi(id), &spec) != -1 || errno != EINVAL) return 22;
    disarm();
    return 0;
}
static void case_exec(const char *self)
{
    pid_t child = fork();
    CHECK(child >= 0, 1101);
    if (!child)
    {
        struct itimerval it = {{0, 0}, {10, 0}};
        struct sigevent event;
        memset(&event, 0, sizeof event);
        event.sigev_notify = SIGEV_NONE;
        timer_t timer;
        if (setitimer(ITIMER_REAL, &it, 0) || timer_create(CLOCK_MONOTONIC, &event, &timer)) _exit(23);
        char id[16];
        snprintf(id, sizeof id, "%d", (int)(intptr_t)timer);
        execl(self, self, "exec-child", id, (char *)0);
        _exit(24);
    }
    int status = -1;
    CHECK(waitpid(child, &status, 0) == child, 1102);
    CHECKV(WIFEXITED(status) && WEXITSTATUS(status) == 0, 1103, status);
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "exec-child")) return exec_child(argv[2]);
    case_alarm();
    case_oneshot();
    case_periodic();
    case_sleep();
    case_signal();
    case_overrun();
    case_none();
    case_thread();
    case_realtime();
    case_fork();
    case_exec(argv[0]);
    printf("TIMERS_PASS arch=%s checks=%d oneshot_late_us=%lld overrun=%d thread_calls=%d realtime=%s\n",
           PROBE_ARCH, checks, (long long)(oneshot_late / 1000), overruns, calls, realtime);
    fflush(stdout);
    return 0;
}
