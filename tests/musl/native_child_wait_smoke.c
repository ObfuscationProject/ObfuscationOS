#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>
#include "thread_syscall.h"
#include "poll_signal_raw.h"
#if !defined(__x86_64__)
#error "Exploratory x86 child-wait smoke; all-ten guest qualification is separate."
#endif
static int case_id,restart,any,descriptors[2],status_word;
static long pid,child,selector;
static _Atomic int entered,handled;
static unsigned long arguments[6];
static __attribute__((noreturn)) void fail(int code)
{
    char text[]="CHILD_SMOKE_FAIL code=000\n";unsigned n=sizeof("CHILD_SMOKE_FAIL code=")-1;
    text[n]='0'+code/100%10;text[n+1]='0'+code/10%10;text[n+2]='0'+code%10;
    thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0);
    thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
struct line{char bytes[512];unsigned used;};
static void word(struct line *b,const char *s){while(*s){CHECK(b->used+1<sizeof(b->bytes),100);b->bytes[b->used++]=*s++;}}
static void number(struct line *b,const char *key,unsigned long value)
{
    char digits[24];unsigned n=0;word(b,key);do{digits[n++]='0'+value%10;value/=10;}while(value);
    while(n)b->bytes[b->used++]=digits[--n];
}
static void marker(const char *tag,unsigned long pc,long result)
{
    struct line b={0};word(&b,tag);number(&b," case=",case_id);number(&b," restart=",restart);
    number(&b," any=",any);number(&b," pid=",pid);number(&b," child=",child);
    number(&b," selector=",(uint32_t)selector);number(&b," output=",(uintptr_t)&status_word);
    number(&b," pc=",pc);word(&b," result=");if(result<0){word(&b,"-");result=-result;}
    number(&b,"",result);word(&b,"\n");
    CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b.bytes,b.used,0)==(long)b.used,101);
}
static int64_t now(void)
{
    struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,102);
    return (int64_t)t.tv_sec*1000000000+t.tv_nsec;
}
static void delay(int64_t duration){int64_t start=now();while(now()-start<duration){}}
static void handler(int signal,siginfo_t *info,void *context)
{
    ucontext_t *c=context;CHECK(signal==SIGUSR1&&info&&c&&info->si_pid==pid&&info->si_code==SI_TKILL,201);
    CHECK(thread_syscall4(SYS_gettid,0,0,0,0)==pid&&status_word==0x12345678,202);
    CHECK(c->uc_mcontext.gregs[REG_RIP]==(greg_t)(restart?poll_signal_site:poll_signal_resume),203);
    CHECK(c->uc_mcontext.gregs[REG_RAX]==(restart?SYS_wait4:-EINTR),204);
    CHECK(c->uc_mcontext.gregs[REG_RDI]==selector&&c->uc_mcontext.gregs[REG_RSI]==(greg_t)&status_word,205);
    marker("CHILD_SMOKE_HANDLE",c->uc_mcontext.gregs[REG_RIP],c->uc_mcontext.gregs[REG_RAX]);
    __atomic_store_n(&handled,1,__ATOMIC_SEQ_CST);
}
static void *sender(void *unused)
{
    (void)unused;int64_t start=now();while(!__atomic_load_n(&entered,__ATOMIC_SEQ_CST))CHECK(now()-start<5000000000LL,103);
    delay(60000000);marker("CHILD_SMOKE_SEND",(uintptr_t)poll_signal_site,0);
    CHECK(thread_syscall4(SYS_tgkill,pid,pid,SIGUSR1,0)==0,104);
    start=now();while(!__atomic_load_n(&handled,__ATOMIC_SEQ_CST))CHECK(now()-start<5000000000LL,105);
    delay(60000000);marker("CHILD_SMOKE_RELEASE",(uintptr_t)poll_signal_site,0);
    CHECK(write(descriptors[1],"x",1)==1,106);return 0;
}
int main(void)
{
    pid=getpid();
    for(case_id=0;case_id<4;++case_id){
        any=case_id/2;restart=case_id%2;status_word=0x12345678;
        __atomic_store_n(&entered,0,__ATOMIC_SEQ_CST);__atomic_store_n(&handled,0,__ATOMIC_SEQ_CST);
        CHECK(pipe(descriptors)==0,107);
        struct sigaction action={0};action.sa_sigaction=handler;action.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0);
        CHECK(sigemptyset(&action.sa_mask)==0&&sigaction(SIGUSR1,&action,0)==0,108);
        child=fork();CHECK(child>=0,109);
        if(!child){char byte;CHECK(close(descriptors[1])==0,110);CHECK(read(descriptors[0],&byte,1)==1&&byte=='x',111);_Exit(42);}
        CHECK(close(descriptors[0])==0,112);selector=any?-1:child;
        arguments[0]=selector;arguments[1]=(uintptr_t)&status_word;arguments[2]=1;
        CHECK(poll_signal_raw(SYS_wait4,arguments,0)==0&&status_word==0x12345678,113);arguments[2]=0;
        pthread_t thread;CHECK(pthread_create(&thread,0,sender,0)==0,114);
        marker("CHILD_SMOKE_BEGIN",(uintptr_t)poll_signal_site,0);__atomic_store_n(&entered,1,__ATOMIC_SEQ_CST);
        long result=poll_signal_raw(SYS_wait4,arguments,0);
        if(!restart){CHECK(result==-EINTR&&status_word==0x12345678,115);marker("CHILD_SMOKE_EINTR",(uintptr_t)poll_signal_resume,result);result=poll_signal_raw(SYS_wait4,arguments,0);}
        CHECK(result==child&&WIFEXITED(status_word)&&WEXITSTATUS(status_word)==42,116);
        CHECK(__atomic_load_n(&handled,__ATOMIC_SEQ_CST)==1,117);marker("CHILD_SMOKE_REAP",(uintptr_t)poll_signal_resume,result);
        CHECK(poll_signal_raw(SYS_wait4,arguments,0)==-ECHILD,118);
        CHECK(pthread_join(thread,0)==0&&close(descriptors[1])==0,119);marker("CHILD_SMOKE_CASE_PASS",(uintptr_t)poll_signal_resume,result);
    }
    const char text[]="CHILD_SMOKE_PASS cases=4 eintr=2 restart=2\n";
    CHECK(thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0)==sizeof(text)-1,120);return 0;
}
