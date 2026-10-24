#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>
#include "../probe_output.h"
#include "thread_syscall.h"

// Exercise musl's assembly syscall trampoline. Its public clone() intentionally
// rejects THREAD/SETTLS/CLEARTID; this fixture does not fabricate a pthread.
extern int __clone(int (*)(void *), void *, int, void *, int *, void *, int *);

#define CHECK(x) do { if (!(x)) probe_failure("THREAD_FAIL", __LINE__, errno); } while (0)
struct state {
    volatile uint32_t phase, gate, tid, checked, delay;
    uintptr_t tls;
    long pid;
};
static uintptr_t thread_pointer(void)
{
    uintptr_t result;
#if defined(__x86_64__)
    __asm__ volatile("mov %%fs:0,%0" : "=r"(result));
#elif defined(__i386__)
    __asm__ volatile("mov %%gs:0,%0" : "=r"(result));
#elif defined(__aarch64__)
    __asm__ volatile("mrs %0,tpidr_el0" : "=r"(result));
#elif defined(__arm__)
    __asm__ volatile("mrc p15,0,%0,c13,c0,3" : "=r"(result));
#elif defined(__riscv)
    __asm__ volatile("mv %0,tp" : "=r"(result));
#elif defined(__loongarch64)
    __asm__ volatile("or %0,$tp,$zero" : "=r"(result));
#elif defined(__mips__)
    __asm__ volatile(".set push\n.set mips32r2\nrdhwr %0,$29\n.set pop" : "=r"(result));
#elif defined(__powerpc__)
    __asm__ volatile("mr %0,2" : "=r"(result));
#endif
    return result;
}
static long futex(volatile uint32_t *word, unsigned operation, unsigned value)
{
    return thread_syscall4(SYS_futex,(uintptr_t)word,operation,value,0);
}
static int peer(void *opaque)
{
    struct state *s=opaque;
    long tid=thread_syscall4(SYS_gettid,0,0,0,0);
    s->checked=thread_pointer()==s->tls && tid==(long)s->tid && tid!=s->pid &&
        thread_syscall4(SYS_getpid,0,0,0,0)==s->pid;
    __atomic_store_n(&s->phase,1,__ATOMIC_RELEASE);
    (void)futex(&s->phase,129,1);
    while(!__atomic_load_n(&s->gate,__ATOMIC_ACQUIRE))
        (void)futex(&s->gate,128,0);
    // Encourage a queued clear-TID wait without treating scheduling as a
    // guarantee. The parent accepts an already-exited peer and requires at
    // least one actual exit wake across the repeated lifecycle checks.
    struct { int64_t seconds, nanoseconds; } wide = {0, 20000000};
    struct { long seconds, nanoseconds; } legacy = {0, 20000000};
    const void *timeout = sizeof(long) == 8 ? (const void *)&wide : (const void *)&legacy;
#if defined(SYS_futex_time64) && SYS_futex == SYS_futex_time64
    timeout = &wide;
#endif
    s->checked = s->checked && thread_syscall4(SYS_futex,(uintptr_t)&s->delay,128,0,(uintptr_t)timeout) == -ETIMEDOUT;
    return s->checked ? 0 : 73; // Musl's clone trampoline issues raw exit.
}
static int survivor(void *opaque)
{
    int fd=(int)(intptr_t)opaque;
    (void)thread_syscall4(SYS_gettid,0,0,0,0);
    (void)thread_syscall4(SYS_gettid,0,0,0,0);
    const char value='t';
    return thread_syscall4(SYS_write,fd,(uintptr_t)&value,1,0)==1 ? 7 : 74;
}
int main(void)
{
    void *stack=mmap(0,16384,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    void *tls=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(stack!=MAP_FAILED && tls!=MAP_FAILED);
    *(uintptr_t *)tls=(uintptr_t)tls;
    const uintptr_t parent_tls=thread_pointer();
    const int shared=CLONE_VM|CLONE_FS|CLONE_FILES|CLONE_SIGHAND|CLONE_THREAD|CLONE_SYSVSEM;
    unsigned exit_wakes = 0;
    for(unsigned round=0;round<16;++round) {
        struct state s={.tls=(uintptr_t)tls,.pid=getpid()};
        int tid=__clone(peer,(char *)stack+16384,shared|CLONE_SETTLS|CLONE_PARENT_SETTID|CLONE_CHILD_SETTID|CLONE_CHILD_CLEARTID,
                      &s,(int *)&s.tid,tls,(int *)&s.tid);
        CHECK(tid>0 && s.tid==(uint32_t)tid && tid!=s.pid);
        while(!__atomic_load_n(&s.phase,__ATOMIC_ACQUIRE)) {
            long result=futex(&s.phase,128,0);CHECK(result==0 || result==-EAGAIN);
        }
        CHECK(s.checked==1 && thread_pointer()==parent_tls);
        __atomic_store_n(&s.gate,1,__ATOMIC_RELEASE);
        // The peer may still be returning from its phase notification. The
        // predicate closes that race even when no gate waiter is queued yet.
        long woken=futex(&s.gate,129,1);CHECK(woken==0 || woken==1);
        long joined=futex(&s.tid,0,(uint32_t)tid);
        if(joined==0) ++exit_wakes;
        CHECK((joined==0 || joined==-EAGAIN) && __atomic_load_n(&s.tid,__ATOMIC_ACQUIRE)==0 && s.checked==1);
        CHECK(thread_pointer()==parent_tls && getpid()==s.pid);
    }
    CHECK(exit_wakes>0);
    int channel[2];CHECK(pipe(channel)==0);
    pid_t child=fork();CHECK(child>=0);
    if(!child) {
        int tid=__clone(survivor,(char *)stack+16384,shared,(void *)(intptr_t)channel[1],0,0,0);
        CHECK(tid>0);
        (void)thread_syscall4(SYS_exit,13,0,0,0);
        for(;;) {}
    }
    CHECK(close(channel[1])==0);
    char value=0;CHECK(read(channel[0],&value,1)==1 && value=='t');
    int status=-1;CHECK(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==7);
    CHECK(close(channel[0])==0 && munmap(stack,16384)==0 && munmap(tls,4096)==0);
    probe_text("OK_MUSL_THREADS clone=pass tls=pass child_tid=pass exit_wake=pass reuse=16 leader_exit=pass\n");
    return 0;
}
