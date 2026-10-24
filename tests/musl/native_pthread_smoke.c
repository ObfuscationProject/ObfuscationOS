#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include "../probe_output.h"

// Ordinary musl pthread entry/exit and TLS, without cancellation or delivery.
#define CHECK(x) do { if (!(x)) probe_failure("PTHREAD_SMOKE_FAIL", __LINE__, errno); } while (0)
static _Thread_local unsigned tls_value = 17;
static pthread_key_t key;
static unsigned destructions;
struct state { long pid, parent_tid, tid; pthread_t parent; void *tls; unsigned round; };

static void destroy(void *value)
{
    CHECK(value != 0 && tls_value == 93 && errno == ERANGE);
    __atomic_fetch_add(&destructions, 1, __ATOMIC_SEQ_CST);
}

static void *worker(void *opaque)
{
    struct state *s = opaque;
    CHECK(tls_value == 17);
    tls_value = 93;
    errno = ERANGE;
    s->tls = &tls_value;
    s->tid = syscall(SYS_gettid);
    CHECK(s->tid != s->parent_tid && getpid() == s->pid);
    CHECK(!pthread_equal(pthread_self(), s->parent));
    sigset_t mask, one;
    CHECK(pthread_sigmask(SIG_SETMASK, 0, &mask) == 0 && sigismember(&mask, SIGUSR1) == 1);
    CHECK(sigemptyset(&one) == 0 && sigaddset(&one, SIGUSR1) == 0);
    CHECK(pthread_sigmask(SIG_UNBLOCK, &one, 0) == 0);
    CHECK(pthread_sigmask(SIG_SETMASK, 0, &mask) == 0 && sigismember(&mask, SIGUSR1) == 0);
    CHECK(pthread_setspecific(key, s) == 0 && pthread_getspecific(key) == s);
    struct timespec wait = {0, 2000000};
    CHECK(nanosleep(&wait, 0) == 0);
    CHECK(tls_value == 93 && errno == ERANGE);
    return s;
}

int main(void)
{
    sigset_t one, saved, current;
    CHECK(sigemptyset(&one) == 0 && sigaddset(&one, SIGUSR1) == 0);
    CHECK(pthread_sigmask(SIG_BLOCK, &one, &saved) == 0);
    CHECK(pthread_key_create(&key, destroy) == 0);
    tls_value = 41;
    errno = EDOM;
    for (unsigned round = 0; round < 8; ++round) {
        struct state s = {.pid=getpid(), .parent_tid=syscall(SYS_gettid), .parent=pthread_self(), .round=round};
        pthread_t thread;
        int result = pthread_create(&thread, 0, worker, &s);
        if (result) probe_failure("PTHREAD_SMOKE_FAIL", __LINE__, result);
        void *returned = 0;
        result = pthread_join(thread, &returned);
        if (result) probe_failure("PTHREAD_SMOKE_FAIL", __LINE__, result);
        CHECK(returned == &s && s.tls != &tls_value && s.tid != s.parent_tid);
        CHECK(tls_value == 41 && errno == EDOM && destructions == round + 1);
        CHECK(pthread_getspecific(key) == 0);
        CHECK(pthread_sigmask(SIG_SETMASK, 0, &current) == 0 && sigismember(&current, SIGUSR1) == 1);
    }
    CHECK(pthread_key_delete(key) == 0 && pthread_sigmask(SIG_SETMASK, &saved, 0) == 0);
    probe_text("OK_MUSL_PTHREAD_SMOKE create=pass join=pass tls=pass errno=pass mask=pass tsd=pass default_stack=pass rounds=8\n");
    return 0;
}
