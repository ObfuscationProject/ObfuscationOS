#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include "thread_syscall.h"
#include "poll_signal_raw.h"
#include "poll_signal_context.h"

enum { call_poll,call_ppoll,call_select,call_pselect };
struct lane {unsigned long number;int interface,wide,packed,libc;};
#if defined(__x86_64__)
#define PROBE_ARCH "x86_64"
#elif defined(__i386__)
#define PROBE_ARCH "i386"
#elif defined(__aarch64__)
#define PROBE_ARCH "aarch64"
#elif defined(__arm__)
#define PROBE_ARCH "arm32"
#elif defined(__riscv) && __riscv_xlen==32
#define PROBE_ARCH "rv32"
#elif defined(__riscv)
#define PROBE_ARCH "rv64"
#elif defined(__loongarch64)
#define PROBE_ARCH "loongarch64"
#elif defined(__mips64)
#define PROBE_ARCH "mips64"
#elif defined(__mips__)
#define PROBE_ARCH "mips"
#elif defined(__powerpc__)
#define PROBE_ARCH "ppc"
#if __SIZEOF_POINTER__!=4 || __BYTE_ORDER__!=__ORDER_BIG_ENDIAN__ || !defined(__NO_FPRS__)
#error "PPC requires big-endian scalar soft-float"
#endif
#else
#error "Unsupported poll signal profile"
#endif
#if defined(__arm__) || defined(__powerpc__)
enum {raw_forms=2};
#else
enum {raw_forms=1};
#endif
#if defined(__powerpc__) && defined(__clang__)
#define load(p) __c11_atomic_load((p),__ATOMIC_SEQ_CST)
#define store(p,v) __c11_atomic_store((p),(v),__ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p),__ATOMIC_SEQ_CST)
#define store(p,v) __atomic_store_n((p),(v),__ATOMIC_SEQ_CST)
#endif
#if defined(SYS_ppoll)
#define LIBC_PPOLL SYS_ppoll
#else
#define LIBC_PPOLL SYS_ppoll_time64
#endif
#if defined(SYS_pselect6)
#define LIBC_PSELECT SYS_pselect6
#else
#define LIBC_PSELECT SYS_pselect6_time64
#endif
#if defined(SYS_poll)
#define LIBC_POLL SYS_poll
#else
#define LIBC_POLL LIBC_PPOLL
#endif
#if defined(SYS__newselect)
#define LIBC_SELECT SYS__newselect
#elif defined(SYS_select)
#define LIBC_SELECT SYS_select
#else
#define LIBC_SELECT LIBC_PSELECT
#endif
static const struct lane lanes[]={
#ifdef SYS_poll
    {SYS_poll,call_poll,sizeof(long)==8,0,0},
#endif
#ifdef SYS_ppoll
    {SYS_ppoll,call_ppoll,sizeof(long)==8,0,0},
#endif
#if defined(SYS_ppoll_time64) && (!defined(SYS_ppoll) || SYS_ppoll_time64!=SYS_ppoll)
    {SYS_ppoll_time64,call_ppoll,1,0,0},
#endif
#ifdef SYS_select
    {SYS_select,call_select,sizeof(long)==8,
#if defined(__i386__) || defined(__powerpc__)
    1,
#else
    0,
#endif
    0},
#endif
#ifdef SYS__newselect
    {SYS__newselect,call_select,sizeof(long)==8,0,0},
#endif
#ifdef SYS_pselect6
    {SYS_pselect6,call_pselect,sizeof(long)==8,0,0},
#endif
#if defined(SYS_pselect6_time64) && (!defined(SYS_pselect6) || SYS_pselect6_time64!=SYS_pselect6)
    {SYS_pselect6_time64,call_pselect,1,0,0},
#endif
    {LIBC_POLL,call_poll,sizeof(long)==8,0,1},
    {LIBC_PPOLL,call_ppoll,sizeof(long)==8,0,1},
    {LIBC_SELECT,call_select,sizeof(long)==8,0,1},
    {LIBC_PSELECT,call_pselect,sizeof(long)==8,0,1},
};
enum {variants=sizeof(lanes)/sizeof(lanes[0]),normal_cases=17,cases=19};
static int variant,form,case_id;
static _Thread_local int role,depth;
static struct {
    unsigned char *output_page,*timeout_page;
    struct pollfd *fds;fd_set *reads;void *timeout;
    unsigned long args[6],packed[5];
    int original[2],replacement[2],timed,kind,wide,readonly_output,readonly_timeout;
    unsigned long initial_mask;unsigned char expected_timeout[32];
    int64_t duration,elapsed;long result;int error;
    uintptr_t site,resume;pid_t pid,target;uid_t uid;
    _Atomic int ready,go,entered,done,handled,nested;
} state;
static __attribute__((noreturn)) void fail(int code)
{
    char text[]="POLL_SIGNAL_FAIL code=000 variant=00 form=0 case=00 role=0\n";
    unsigned p=sizeof("POLL_SIGNAL_FAIL code=")-1;text[p]='0'+code/100%10;text[p+1]='0'+code/10%10;text[p+2]='0'+code%10;
    p=sizeof("POLL_SIGNAL_FAIL code=000 variant=")-1;text[p]='0'+variant/10;text[p+1]='0'+variant%10;
    text[sizeof("POLL_SIGNAL_FAIL code=000 variant=00 form=")-1]='0'+form;
    p=sizeof("POLL_SIGNAL_FAIL code=000 variant=00 form=0 case=")-1;text[p]='0'+case_id/10;text[p+1]='0'+case_id%10;
    text[sizeof("POLL_SIGNAL_FAIL code=000 variant=00 form=0 case=00 role=")-1]='0'+role;
    thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0);thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{
    char buffer[768];va_list ap;va_start(ap,format);int size=vsnprintf(buffer,sizeof(buffer),format,ap);va_end(ap);
    CHECK(size>0&&(size_t)size<sizeof(buffer),101);CHECK(thread_syscall4(SYS_write,1,(uintptr_t)buffer,size,0)==size,102);
}
struct line {char bytes[512];unsigned used;};
static void word(struct line *b,const char *s){while(*s){CHECK(b->used+1<sizeof(b->bytes),201);b->bytes[b->used++]=*s++;}}
static void number(struct line *b,const char *key,unsigned long value)
{
    char digits[24];unsigned count=0;word(b,key);do{digits[count++]='0'+value%10;value/=10;}while(value);
    while(count){char x[]={digits[--count],0};word(b,x);}
}
static void handler_marker(const char *tag,ucontext_t *c,int inspected)
{
    struct line b={0};word(&b,tag);word(&b," arch=" PROBE_ARCH);number(&b," variant=",variant);number(&b," form=",form);number(&b," case=",case_id);
    number(&b," pid=",state.pid);number(&b," tid=",state.target);number(&b," pc=",(uintptr_t)CTX_PC(c));number(&b," inspected=",inspected);
    if(inspected){
        number(&b," result=",(uintptr_t)CTX_RESULT(c));
#if defined(__mips__)
        number(&b," a3=",c->uc_mcontext.gregs[7]);
#elif defined(__powerpc__)
        number(&b," cr=",c->uc_regs->gregs[38]);number(&b," diagnostic_result=",c->uc_regs->gregs[43]);
#elif defined(__arm__)
        number(&b," cpsr=",c->uc_mcontext.arm_cpsr);
#endif
    }
    word(&b,"\n");CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b.bytes,b.used,0)==(long)b.used,202);
}
static int64_t now(void){struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,103);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void wait_word(_Atomic int *p,int value){int64_t start=now();while(load(p)!=value)CHECK(now()-start<5000000000LL,104);}
static void delay(int64_t ns){int64_t start=now();while(now()-start<ns){}}
static int caught(void){return case_id<=5||case_id==7||case_id==8||case_id==14;}
static void encode_time(int64_t ns)
{
    const struct lane *l=&lanes[variant];void *p=state.timeout_page+64;
    if(l->libc){
        if(l->interface==call_select){struct timeval *t=p;t->tv_sec=ns/1000000000;t->tv_usec=ns%1000000000/1000;}
        else {struct timespec *t=p;t->tv_sec=ns/1000000000;t->tv_nsec=ns%1000000000;}
    }else if(state.wide){int64_t t[2]={ns/1000000000,ns%1000000000/(l->interface==call_select?1000:1)};memcpy(p,t,16);}
    else{int32_t t[2]={(int32_t)(ns/1000000000),(int32_t)(ns%1000000000/(l->interface==call_select?1000:1))};memcpy(p,t,8);}
}
static int64_t remaining(void)
{
    const struct lane *l=&lanes[variant];if(l->interface==call_poll)return -1;
    const void *p=state.timeout_page+64;int64_t s,sub;
    if(l->libc){if(l->interface==call_select){const struct timeval *t=p;s=t->tv_sec;sub=t->tv_usec;}else{const struct timespec *t=p;s=t->tv_sec;sub=t->tv_nsec;}}
    else if(state.wide){int64_t t[2];memcpy(t,p,16);s=t[0];sub=t[1];}else{int32_t t[2];memcpy(t,p,8);s=t[0];sub=t[1];}
    CHECK(s>=0&&sub>=0&&sub<(l->interface==call_select?1000000:1000000000),105);
    return s*1000000000+sub*(l->interface==call_select?1000:1);
}
static void handle(int signal,siginfo_t *info,void *context)
{
    int saved=errno;ucontext_t *c=context;sigset_t mask;
    CHECK(role==1&&info&&c&&thread_syscall4(SYS_gettid,0,0,0,0)==state.target,203);
    CHECK(info->si_signo==signal&&info->si_errno==0&&info->si_code==SI_TKILL&&info->si_pid==state.pid&&info->si_uid==state.uid,204);
    ++depth;CHECK(sigprocmask(SIG_SETMASK,0,&mask)==0&&sigismember(&mask,signal)==1,205);
#if defined(__powerpc__)
    CHECK(c->uc_regs!=0,206);
#endif
    if(signal==SIGUSR2){CHECK(case_id==14&&depth==2&&!load(&state.nested),207);handler_marker("POLL_SIGNAL_NESTED",c,0);store(&state.nested,1);--depth;errno=saved;return;}
    CHECK(signal==SIGUSR1&&depth==1&&!load(&state.handled),208);
    if(caught()){
        CHECK(context_result(c)==-(case_id==7&&!state.kind?EFAULT:EINTR),209);
        if(!lanes[variant].libc)CHECK((uintptr_t)CTX_PC(c)==state.resume,210);
#if defined(__arm__)
        if(!lanes[variant].libc)CHECK(((c->uc_mcontext.arm_cpsr&0x20)!=0)==(form==1),211);
#endif
    }else CHECK(load(&state.done)==1,212);
    handler_marker("POLL_SIGNAL_HANDLE",c,caught());
    if(case_id==14){CHECK(thread_syscall4(SYS_tgkill,state.pid,state.target,SIGUSR2,0)==0,213);CHECK(load(&state.nested)==1,214);}
    handler_marker("POLL_SIGNAL_HANDLER_RETURN",c,caught());store(&state.handled,1);--depth;errno=saved;
}
static long invoke(void)
{
    const struct lane *l=&lanes[variant];
    if(l->libc){
        if(l->interface==call_poll)return poll(state.fds,2,state.timed?(int)(state.duration/1000000):-1);
        if(l->interface==call_ppoll)return ppoll(state.fds,2,state.timeout,0);
        if(l->interface==call_select)return select(state.original[0]+1,state.reads,0,0,state.timeout);
        return pselect(state.original[0]+1,state.reads,0,0,state.timeout,0);
    }
#if defined(__arm__)
    if(form)return poll_signal_thumb(l->number,state.args,0);
#endif
    return poll_signal_raw(l->number,state.args,form);
}
static void *waiter(void *unused)
{
    (void)unused;role=1;state.target=(pid_t)thread_syscall4(SYS_gettid,0,0,0,0);CHECK(state.target>0&&state.target!=state.pid,106);
    sigset_t mask;CHECK(sigemptyset(&mask)==0,107);if(case_id==12)CHECK(sigaddset(&mask,SIGUSR1)==0,108);
    CHECK(sigprocmask(SIG_SETMASK,&mask,0)==0,109);store(&state.ready,1);wait_word(&state.go,1);
    marker("POLL_SIGNAL_ATTEMPT arch=%s variant=%d form=%d case=%d pid=%ld tid=%ld a0=%lu a1=%lu a2=%lu a3=%lu a4=%lu a5=%lu\n",PROBE_ARCH,variant,form,case_id,(long)state.pid,(long)state.target,state.args[0],state.args[1],state.args[2],state.args[3],state.args[4],state.args[5]);
    errno=111;int64_t start=now();store(&state.entered,1);state.result=invoke();state.error=errno;state.elapsed=now()-start;
    unsigned long maskword=0;memcpy(&maskword,state.reads,sizeof(maskword));
    marker("POLL_SIGNAL_RETURN arch=%s variant=%d form=%d case=%d result=%ld error=%d elapsed=%llu revents=%u mask=%lu remaining=%lld\n",PROBE_ARCH,variant,form,case_id,state.result,state.error,(unsigned long long)state.elapsed,state.kind?0:(unsigned short)state.fds[0].revents,state.kind?maskword:0,(long long)remaining());
    store(&state.done,1);
    if(case_id==10||case_id==11)wait_word(&state.handled,1);
    if(case_id==12){
        CHECK(sigpending(&mask)==0&&sigismember(&mask,SIGUSR1)==1&&!load(&state.handled),110);
        marker("POLL_SIGNAL_UNMASK arch=%s variant=%d form=%d case=%d\n",PROBE_ARCH,variant,form,case_id);
        CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0&&load(&state.handled)==1,111);
    }
    return (void *)(uintptr_t)0x2875;
}
static void confirm_wait(void)
{
    wait_word(&state.entered,1);
#ifdef POLL_SIGNAL_LINUX_REFERENCE
    char path[128];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)state.target)>0,112);
    int64_t start=now();int observed=0;
    while(!observed){char buffer[384];int fd=open(path,O_RDONLY);CHECK(fd>=0,113);ssize_t size=read(fd,buffer,sizeof(buffer)-1);CHECK(size>=0&&close(fd)==0,114);buffer[size]=0;
        long nr=-1;unsigned long a[6]={0};
        if(sscanf(buffer,"%ld %lx %lx %lx %lx %lx %lx",&nr,a,a+1,a+2,a+3,a+4,a+5)==7){observed=nr==(long)lanes[variant].number;if(!lanes[variant].libc)for(unsigned i=0;i<6;++i)observed=observed&&a[i]==state.args[i];}
        CHECK(!load(&state.done)&&now()-start<5000000000LL,115);
    }
    marker("POLL_SIGNAL_LINUX_WAIT arch=%s variant=%d form=%d case=%d pid=%ld tid=%ld syscall=%lu\n",PROBE_ARCH,variant,form,case_id,(long)state.pid,(long)state.target,lanes[variant].number);
#else
    delay(60000000);
#endif
    CHECK(!load(&state.done),116);
}
static void send_signal(int delivered)
{
    marker("POLL_SIGNAL_SEND arch=%s variant=%d form=%d case=%d pid=%ld tid=%ld signal=%d\n",PROBE_ARCH,variant,form,case_id,(long)state.pid,(long)state.target,SIGUSR1);
    CHECK(thread_syscall4(SYS_tgkill,state.pid,state.target,SIGUSR1,0)==0,117);if(delivered)wait_word(&state.handled,1);
}
static void write_ready(int replacement)
{
    marker("POLL_SIGNAL_READY arch=%s variant=%d form=%d case=%d source=%s\n",PROBE_ARCH,variant,form,case_id,replacement?"replacement":"original");
    CHECK(write(replacement?state.replacement[1]:state.original[1],"R",1)==1,118);
}
static void run_case(void)
{
    const struct lane *l=&lanes[variant];memset(&state,0,sizeof(state));state.pid=getpid();state.uid=getuid();state.kind=l->interface>=call_select;state.wide=l->wide;
    state.timed=case_id==2||case_id==3||case_id==7||case_id==8||case_id==9||case_id==11||case_id==14||case_id==15;
    state.duration=case_id==15?0:case_id==9||case_id==11?160000000:500000000;
    state.output_page=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);state.timeout_page=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(state.output_page!=MAP_FAILED&&state.timeout_page!=MAP_FAILED,119);memset(state.output_page,0xa5,4096);memset(state.timeout_page,0xa5,4096);memset(state.timeout_page+64,0,32);
    state.fds=(struct pollfd *)(state.output_page+64);state.reads=(fd_set *)(state.output_page+64);
    CHECK(pipe(state.original)==0&&pipe(state.replacement)==0,120);CHECK(state.original[0]>=0&&state.original[0]<32,121);state.initial_mask=1ul<<state.original[0];
    if(state.kind){FD_ZERO(state.reads);FD_SET(state.original[0],state.reads);}else{state.fds[0]=(struct pollfd){state.original[0],POLLIN,0x3333};state.fds[1]=(struct pollfd){-1,POLLOUT,0x4444};}
    encode_time(state.duration);memcpy(state.expected_timeout,state.timeout_page+64,32);state.timeout=state.timed?state.timeout_page+64:0;
    state.site=(uintptr_t)poll_signal_site;state.resume=(uintptr_t)poll_signal_resume;
#if defined(__arm__)
    if(form&&!l->libc){state.site=(uintptr_t)poll_signal_thumb_site;state.resume=(uintptr_t)poll_signal_thumb_resume;}
#endif
    if(!state.kind){state.args[0]=(uintptr_t)state.fds;state.args[1]=2;state.args[2]=l->interface==call_poll?(state.timed?(unsigned long)(state.duration/1000000):(unsigned long)-1):(uintptr_t)state.timeout;state.args[4]=l->interface==call_ppoll?_NSIG/8:0;}
    else{state.args[0]=state.original[0]+1;state.args[1]=(uintptr_t)state.reads;state.args[4]=(uintptr_t)state.timeout;if(l->packed){memcpy(state.packed,state.args,sizeof(state.packed));memset(state.args,0,sizeof(state.args));state.args[0]=(uintptr_t)state.packed;}}
    struct sigaction action={0};action.sa_sigaction=handle;action.sa_flags=SA_SIGINFO;if(case_id!=0&&case_id!=2)action.sa_flags|=SA_RESTART;
    CHECK(sigemptyset(&action.sa_mask)==0&&sigaction(SIGUSR1,&action,0)==0&&sigaction(SIGUSR2,&action,0)==0,122);
    if(case_id==13||case_id==17){action.sa_handler=case_id==13?SIG_IGN:SIG_DFL;CHECK(sigaction(SIGUSR1,&action,0)==0,123);}
    sigset_t mask;CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,124);
    if(case_id==16)CHECK(write(state.original[1],"R",1)==1,125);
    pthread_t thread;CHECK(pthread_create(&thread,0,waiter,0)==0,126);wait_word(&state.ready,1);
    marker("POLL_SIGNAL_CASE_BEGIN arch=%s variant=%d form=%d case=%d pid=%ld tid=%ld syscall=%lu kind=%s libc=%d timed=%d duration=%llu site=%lu resume=%lu count=%d fd=%d output=%lu timeout=%lu width=%d packed=%d\n",PROBE_ARCH,variant,form,case_id,(long)state.pid,(long)state.target,l->number,state.kind?"select":"poll",l->libc,state.timed,(unsigned long long)state.duration,(unsigned long)state.site,(unsigned long)state.resume,state.kind?1:2,state.original[0],(unsigned long)(uintptr_t)(state.output_page+64),(unsigned long)(uintptr_t)state.timeout,state.wide?64:32,l->packed);
    store(&state.go,1);
    if(case_id<15||case_id>=17){
        confirm_wait();
        if(case_id==4){marker("POLL_SIGNAL_MUTATE_INPUT arch=%s variant=%d form=%d case=%d\n",PROBE_ARCH,variant,form,case_id);if(state.kind)FD_ZERO(state.reads);else{state.fds[0].fd=state.replacement[0];state.fds[0].events=POLLOUT;}}
        if(case_id==5||case_id==6){marker("POLL_SIGNAL_REUSE arch=%s variant=%d form=%d case=%d fd=%d replacement=%d\n",PROBE_ARCH,variant,form,case_id,state.original[0],state.replacement[0]);CHECK(close(state.original[0])==0&&dup2(state.replacement[0],state.original[0])==state.original[0],127);if(case_id==5){write_ready(1);delay(20000000);CHECK(!load(&state.done),128);}}
        if(case_id==7){marker("POLL_SIGNAL_PROTECT arch=%s variant=%d form=%d case=%d target=output\n",PROBE_ARCH,variant,form,case_id);CHECK(mprotect(state.output_page,4096,PROT_READ)==0,129);state.readonly_output=1;}
        if(case_id==8&&!l->libc&&l->interface!=call_poll){marker("POLL_SIGNAL_PROTECT arch=%s variant=%d form=%d case=%d target=timeout\n",PROBE_ARCH,variant,form,case_id);CHECK(mprotect(state.timeout_page,4096,PROT_READ)==0,130);state.readonly_timeout=1;}
        if(caught())send_signal(1);
        else if(case_id==9){marker("POLL_SIGNAL_MUTATE_TIMEOUT arch=%s variant=%d form=%d case=%d\n",PROBE_ARCH,variant,form,case_id);encode_time(2000000000);state.args[2]=l->interface==call_poll?2000:state.args[2];memcpy(state.expected_timeout,state.timeout_page+64,32);}
        else if(case_id==11){wait_word(&state.done,1);send_signal(1);}
        else if(case_id==17){send_signal(0);delay(5000000000LL);fail(131);}
        else if(case_id==18){marker("POLL_SIGNAL_EXIT arch=%s variant=%d form=%d case=%d pid=%ld\n",PROBE_ARCH,variant,form,case_id,(long)state.pid);thread_syscall4(SYS_exit_group,0,0,0,0);fail(132);}
        else{if(case_id==12||case_id==13){send_signal(0);delay(20000000);CHECK(!load(&state.handled)&&!load(&state.done),133);}write_ready(0);if(case_id==10){wait_word(&state.done,1);send_signal(1);}}
    }
    wait_word(&state.done,1);void *joined=0;CHECK(pthread_join(thread,&joined)==0&&joined==(void *)(uintptr_t)0x2875,134);
    long expected=caught()?-(case_id==7&&!state.kind?EFAULT:EINTR):case_id==9||case_id==11||case_id==15?0:1;
    CHECK(state.result==(l->libc&&expected<0?-1:expected)&&state.error==(l->libc&&expected<0?-expected:111),135);
    CHECK(load(&state.handled)==(caught()||case_id==10||case_id==11||case_id==12)&&load(&state.nested)==(case_id==14),136);
    if(state.timed&&caught())CHECK(state.elapsed<state.duration,137);
    if(case_id==9||case_id==11)CHECK(state.elapsed>=state.duration&&state.elapsed<state.duration+1000000000,138);
    if(!state.kind){CHECK(state.fds[0].fd==(case_id==4?state.replacement[0]:state.original[0])&&state.fds[0].events==(case_id==4?POLLOUT:POLLIN),139);CHECK(state.fds[0].revents==(case_id==7?0x3333:expected==1?POLLIN:0)&&state.fds[1].fd==-1&&state.fds[1].events==POLLOUT&&state.fds[1].revents==(case_id==7?0x4444:0),140);}
    else{unsigned long value=0;memcpy(&value,state.reads,sizeof(value));CHECK(value==(case_id==4||expected==0?0:state.initial_mask),141);for(unsigned i=sizeof(value);i<sizeof(fd_set);++i)CHECK(((unsigned char *)state.reads)[i]==0,142);}
    if(l->libc||!state.timed||state.readonly_timeout||l->interface==call_poll)CHECK(memcmp(state.timeout_page+64,state.expected_timeout,32)==0,143);
    else{int64_t left=remaining();CHECK(left>=0&&left<=state.duration,144);if(case_id==9||case_id==11||case_id==15)CHECK(left==0,145);for(unsigned i=state.wide?16:8;i<32;++i)CHECK(state.timeout_page[64+i]==0,146);}
    for(unsigned i=0;i<4096;++i){if(i<64||i>=64+(state.kind?sizeof(fd_set):2*sizeof(struct pollfd)))CHECK(state.output_page[i]==0xa5,147);if(i<64||i>=96)CHECK(state.timeout_page[i]==0xa5,148);}
    CHECK(close(state.original[0])==0&&close(state.original[1])==0&&close(state.replacement[0])==0&&close(state.replacement[1])==0,149);
    CHECK(munmap(state.output_page,4096)==0&&munmap(state.timeout_page,4096)==0,150);
    marker("POLL_SIGNAL_CASE_PASS arch=%s variant=%d form=%d case=%d\n",PROBE_ARCH,variant,form,case_id);
}
int main(void)
{
    CHECK(__atomic_always_lock_free(sizeof(state.handled),&state.handled),151);int groups=0;
    for(variant=0;variant<variants;++variant)for(form=0;form<(lanes[variant].libc?1:raw_forms);++form){
        ++groups;
        for(int batch=0;batch<3;++batch){pid_t child=fork();CHECK(child>=0,152);
            if(!child){if(batch==0)for(case_id=0;case_id<normal_cases;++case_id)run_case();else{case_id=16+batch;run_case();}thread_syscall4(SYS_exit_group,0,0,0,0);fail(153);}
            int status=-1;CHECK(waitpid(child,&status,0)==child,154);
            CHECK(batch==1?(WIFSIGNALED(status)&&WTERMSIG(status)==SIGUSR1):(WIFEXITED(status)&&WEXITSTATUS(status)==0),155);
            if(batch)marker("POLL_SIGNAL_EXIT_PASS arch=%s variant=%d form=%d case=%d pid=%ld signal=%d\n",PROBE_ARCH,variant,form,16+batch,(long)child,batch==1?SIGUSR1:0);
        }
    }
#ifdef POLL_SIGNAL_LINUX_REFERENCE
    marker("POLL_SIGNAL_LINUX_REFERENCE_PASS arch=%s variants=%d groups=%d cases=%d waits=%d parent=1\n",PROBE_ARCH,variants,groups,groups*cases,groups*17);
#else
    marker("POLL_SIGNAL_PASS arch=%s variants=%d groups=%d cases=%d waits=%d parent=1\n",PROBE_ARCH,variants,groups,groups*cases,groups*17);
#endif
    return 0;
}
