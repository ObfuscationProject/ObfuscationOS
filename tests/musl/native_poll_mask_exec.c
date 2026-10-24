#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/select.h>
#include <sys/syscall.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>
#include "thread_syscall.h"
#include "poll_signal_context.h"

/* Each successful exec starts a fresh image, including fresh libc/TLS state. */
static int stage, mode, family, dirty;
static long pid, waiter, executor;
static const char *image_path;
static _Atomic int entered;
#if defined(__powerpc__) && defined(__clang__)
#define load(p) __c11_atomic_load((p),__ATOMIC_SEQ_CST)
#define store(p,v) __c11_atomic_store((p),(v),__ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p),__ATOMIC_SEQ_CST)
#define store(p,v) __atomic_store_n((p),(v),__ATOMIC_SEQ_CST)
#endif
static __attribute__((noreturn)) void fail(int code)
{
    char text[]="MASK_EXEC_FAIL code=000\n";
    unsigned n=sizeof("MASK_EXEC_FAIL code=")-1;
    text[n]='0'+code/100%10;text[n+1]='0'+code/10%10;text[n+2]='0'+code%10;
    thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0);
    thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
struct line {char bytes[320];unsigned used;};
static void text(struct line *b,const char *s){while(*s){CHECK(b->used+1<sizeof(b->bytes),100);b->bytes[b->used++]=*s++;}}
static void number(struct line *b,const char *key,unsigned long value)
{
    char digits[24];unsigned n=0;text(b,key);
    do{digits[n++]='0'+value%10;value/=10;}while(value);
    while(n)b->bytes[b->used++]=digits[--n];
}
static void marker(const char *tag)
{
    struct line b={0};text(&b,tag);number(&b," stage=",stage);number(&b," family=",family);
    number(&b," mode=",mode);number(&b," pid=",pid);number(&b," waiter=",waiter);
    number(&b," executor=",executor);text(&b,"\n");
    CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b.bytes,b.used,0)==(long)b.used,101);
}
static int64_t now(void)
{
    struct timespec value;CHECK(clock_gettime(CLOCK_MONOTONIC,&value)==0,102);
    return (int64_t)value.tv_sec*1000000000+value.tv_nsec;
}
static void current(int usr1,int usr2,int term)
{
    sigset_t value;CHECK(sigprocmask(SIG_SETMASK,0,&value)==0,103);
    CHECK(sigismember(&value,SIGUSR1)==usr1&&sigismember(&value,SIGUSR2)==usr2&&sigismember(&value,SIGTERM)==term,104);
}
static void set_original(void)
{
    sigset_t value;CHECK(sigemptyset(&value)==0&&sigaddset(&value,SIGTERM)==0,105);
    CHECK(sigprocmask(SIG_SETMASK,&value,0)==0,106);
}
static __attribute__((noreturn)) void replace_image(void)
{
    int caught=mode<2;current(caught,caught,!caught);
    char next[2]={(char)('0'+stage+1),0};
    char *arguments[]={(char *)image_path,next,0};char *environment[]={0};
    CHECK(thread_syscall4(SYS_execve,(uintptr_t)"/bin/missing-mask-exec-image",(uintptr_t)arguments,(uintptr_t)environment,0)==-ENOENT,107);
    current(caught,caught,!caught);CHECK(dirty==1,108);
    marker("MASK_EXEC_FAILED_PRESERVED");marker("MASK_EXEC_COMMIT");
    thread_syscall4(SYS_execve,(uintptr_t)image_path,(uintptr_t)arguments,(uintptr_t)environment,0);
    fail(109);
}
static void handle(int signal,siginfo_t *info,void *context)
{
    ucontext_t *c=context;CHECK(signal==SIGUSR1&&info&&c&&mode<2,201);
    CHECK(info->si_pid==pid&&info->si_code==SI_TKILL,202);
    CHECK(thread_syscall4(SYS_gettid,0,0,0,0)==waiter&&waiter==executor,203);
    CHECK(context_result(c)==-EINTR,204);
    CHECK(sigismember(&c->uc_sigmask,SIGUSR1)==0&&sigismember(&c->uc_sigmask,SIGUSR2)==0&&sigismember(&c->uc_sigmask,SIGTERM)==1,205);
    current(1,1,0);marker("MASK_EXEC_HANDLER");replace_image();
}
static __attribute__((noreturn)) void wait_masked(void)
{
    set_original();waiter=thread_syscall4(SYS_gettid,0,0,0,0);
    if(mode<2)executor=waiter;
    sigset_t temporary;CHECK(sigemptyset(&temporary)==0&&sigaddset(&temporary,SIGUSR2)==0,110);
    struct timespec timeout={10,0};marker("MASK_EXEC_WAIT");store(&entered,1);
    if(family==0)(void)ppoll(0,0,&timeout,&temporary);
    else (void)pselect(0,0,0,0,&timeout,&temporary);
    fail(111);
}
static __attribute__((noreturn)) void trigger(void)
{
    int64_t start=now();while(!load(&entered))CHECK(now()-start<5000000000LL,112);
    start=now();while(now()-start<60000000){}
    if(mode<2){
        marker("MASK_EXEC_SEND");CHECK(thread_syscall4(SYS_tgkill,pid,waiter,SIGUSR1,0)==0,113);
        for(;;)CHECK(now()-start<5000000000LL,114);
    }
    executor=thread_syscall4(SYS_gettid,0,0,0,0);set_original();replace_image();
}
static void *peer(void *unused)
{
    (void)unused;if(mode==0||mode==2)trigger();else wait_masked();
}
static void check_replacement(int completed)
{
    CHECK(!dirty&&!load(&entered)&&waiter==0&&executor==0,115);
    CHECK(thread_syscall4(SYS_gettid,0,0,0,0)==pid,116);
    int caught=(completed%4)<2;current(caught,caught,!caught);
    struct sigaction action;CHECK(sigaction(SIGUSR1,0,&action)==0&&action.sa_handler==SIG_DFL,117);
    sigset_t empty;CHECK(sigemptyset(&empty)==0,118);struct timespec timeout={0,0};
    CHECK(ppoll(0,0,&timeout,&empty)==0,119);current(caught,caught,!caught);
    CHECK(pselect(0,0,0,0,&timeout,&empty)==0,120);current(caught,caught,!caught);
    /* New image masks survive two independent admission/restoration cycles. */
    stage=completed;family=stage/4;mode=stage%4;marker("MASK_EXEC_REPLACED");
}
int main(int argc,char **argv)
{
    pid=thread_syscall4(SYS_getpid,0,0,0,0);CHECK(argc==1||argc==2,121);
    image_path=argv[0][0]=='/'?argv[0]:"/bin/native-poll-mask-exec";
    int next=0;
    if(argc==2){CHECK(argv[1][0]>='1'&&argv[1][0]<='8'&&argv[1][1]==0,122);next=argv[1][0]-'0';check_replacement(next-1);}
    if(next==8){
        const char done[]="MASK_EXEC_PASS replacements=8 failed_exec=8\n";
        CHECK(thread_syscall4(SYS_write,1,(uintptr_t)done,sizeof(done)-1,0)==sizeof(done)-1,123);return 0;
    }
    stage=next;mode=stage%4;family=stage/4;dirty=1;set_original();
    struct sigaction action={0};action.sa_sigaction=handle;action.sa_flags=SA_SIGINFO|SA_RESTART;
    CHECK(sigemptyset(&action.sa_mask)==0&&sigaction(SIGUSR1,&action,0)==0,124);
    pthread_t thread;CHECK(pthread_create(&thread,0,peer,0)==0,125);
    if(mode==0||mode==2)wait_masked();else trigger();
}
