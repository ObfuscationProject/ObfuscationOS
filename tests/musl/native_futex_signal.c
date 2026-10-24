#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
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
#include <sys/syscall.h>
#include <sys/wait.h>
#include "thread_syscall.h"
#include "futex_signal_raw.h"

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
#elif defined(__powerpc__)
#define PROBE_ARCH "ppc"
#if __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__NO_FPRS__)
#error "PPC requires big-endian PPC32 scalar soft-float"
#endif
#else
#error "Unsupported futex signal profile"
#endif
#if defined(__arm__) || defined(__powerpc__)
enum { forms=2 };
#else
enum { forms=1 };
#endif
#if defined(__powerpc__) && defined(__clang__)
#define load(p) __c11_atomic_load((p),__ATOMIC_SEQ_CST)
#define store(p,v) __c11_atomic_store((p),(v),__ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p),__ATOMIC_SEQ_CST)
#define store(p,v) __atomic_store_n((p),(v),__ATOMIC_SEQ_CST)
#endif
#if defined(SYS_futex_time64) && SYS_futex_time64 != SYS_futex
enum { abis=2 };
#else
enum { abis=1 };
#endif
enum { rounds=2,cases=19 };
static int form,abi,domain,round_id,case_id;
static _Thread_local int role,depth;
static struct {
    unsigned char *mapping;
    _Atomic uint32_t *word,*alternate;
    struct { unsigned char before[16]; _Alignas(8) unsigned char value[16]; unsigned char after[16]; } timeout;
    void *time_pointer;
    unsigned long number,expected,operation;
    int wide,timed;
    uintptr_t site,resume;
    pid_t pid,target;
    uid_t uid;
    long result;
    int error;
    int64_t duration,elapsed;
    _Atomic int ready,go,entered,done,handled,nested;
} state;
static const uint32_t initial_value=0x12345678u,alternate_value=0x87654321u;
static __attribute__((noreturn)) void fail(int code)
{
    char text[]="FUTEX_SIGNAL_FAIL code=000 form=0 abi=0 domain=0 round=0 case=00 role=0\n";
    unsigned p=sizeof("FUTEX_SIGNAL_FAIL code=")-1;
    text[p]='0'+code/100%10;text[p+1]='0'+code/10%10;text[p+2]='0'+code%10;
    text[sizeof("FUTEX_SIGNAL_FAIL code=000 form=")-1]='0'+form;
    text[sizeof("FUTEX_SIGNAL_FAIL code=000 form=0 abi=")-1]='0'+abi;
    text[sizeof("FUTEX_SIGNAL_FAIL code=000 form=0 abi=0 domain=")-1]='0'+domain;
    text[sizeof("FUTEX_SIGNAL_FAIL code=000 form=0 abi=0 domain=0 round=")-1]='0'+round_id;
    p=sizeof("FUTEX_SIGNAL_FAIL code=000 form=0 abi=0 domain=0 round=0 case=")-1;
    text[p]='0'+case_id/10;text[p+1]='0'+case_id%10;
    text[sizeof("FUTEX_SIGNAL_FAIL code=000 form=0 abi=0 domain=0 round=0 case=00 role=")-1]='0'+role;
    thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0);
    thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{
    char buffer[512];va_list values;va_start(values,format);
    int size=vsnprintf(buffer,sizeof(buffer),format,values);va_end(values);
    CHECK(size>0&&(size_t)size<sizeof(buffer),101);
    CHECK(thread_syscall4(SYS_write,1,(uintptr_t)buffer,size,0)==size,102);
}
/* Async-signal-safe diagnostics: no stdio, allocation, lock or shared buffer. */
struct line {char bytes[512];unsigned used;};
static void word(struct line *b,const char *text)
{
    while(*text){CHECK(b->used+1<sizeof(b->bytes),201);b->bytes[b->used++]=*text++;}
}
static void number(struct line *b,const char *key,unsigned long value)
{
    char digits[24];unsigned count=0;word(b,key);
    do{digits[count++]='0'+value%10;value/=10;}while(value);
    while(count){char x[]={digits[--count],0};word(b,x);}
}
static void handler_marker(const char *tag,int ordinal,ucontext_t *c,int inspect)
{
    struct line b={0};word(&b,tag);word(&b," arch=" PROBE_ARCH);
    number(&b," form=",form);number(&b," abi=",abi);number(&b," domain=",domain);number(&b," round=",round_id);number(&b," case=",case_id);
    number(&b," pid=",state.pid);number(&b," tid=",state.target);number(&b," ordinal=",ordinal);
    number(&b," pc=",(uintptr_t)CTX_PC(c));number(&b," inspected=",inspect);
    if(inspect){number(&b," number=",(uintptr_t)CTX_NUMBER(c));number(&b," address=",(uintptr_t)CTX_ADDRESS(c));
        number(&b," operation=",(uintptr_t)CTX_OPERATION(c));number(&b," value=",(uintptr_t)CTX_VALUE(c));number(&b," timeout=",(uintptr_t)CTX_TIMEOUT(c));
#if defined(__powerpc__)
        number(&b," cr=",c->uc_regs->gregs[38]);number(&b," diagnostic_result=",c->uc_regs->gregs[43]);number(&b," orig_r3=",c->uc_regs->gregs[34]);
#elif defined(__arm__)
        number(&b," cpsr=",c->uc_mcontext.arm_cpsr);
#endif
    }
    word(&b,"\n");CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b.bytes,b.used,0)==(long)b.used,202);
}
static int64_t now(void)
{
    struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,103);
    return (int64_t)t.tv_sec*1000000000+t.tv_nsec;
}
static void wait_word(_Atomic int *p,int value)
{
    int64_t start=now();while(load(p)!=value)CHECK(now()-start<5000000000LL,104);
}
static void delay(int64_t ns){int64_t start=now();while(now()-start<ns){}}
static int restarting(void){return case_id==1||(case_id>=4&&case_id<=9)||case_id==16;}
static int caught_in_wait(void){return case_id<=9||case_id==16;}
static void encode_timeout(int64_t ns)
{
    if(state.wide){int64_t values[2]={ns/1000000000,ns%1000000000};memcpy(state.timeout.value,values,16);}
    else{int32_t values[2]={(int32_t)(ns/1000000000),(int32_t)(ns%1000000000)};memcpy(state.timeout.value,values,8);}
}
static void inspect_context(ucontext_t *c)
{
    int restart=restarting();CHECK((uintptr_t)CTX_PC(c)==(restart?state.site:state.resume),203);
    CHECK((uintptr_t)CTX_OPERATION(c)==state.operation&&(uintptr_t)CTX_VALUE(c)==state.expected,204);
    if(restart){
        CHECK((uintptr_t)CTX_NUMBER(c)==state.number&&(uintptr_t)CTX_ADDRESS(c)==(uintptr_t)state.word,205);
        CHECK((uintptr_t)CTX_TIMEOUT(c)==0,206);
#if defined(__powerpc__)
        CHECK((c->uc_regs->gregs[38]&0x10000000u)&&c->uc_regs->gregs[43]==0,207);
        CHECK(c->uc_regs->gregs[34]==(uintptr_t)state.word&&c->uc_regs->gregs[40]==0xc00,208);
#endif
    }else{
        CHECK(context_result(c)==-EINTR,209);
#if defined(__mips__)
        CHECK((uintptr_t)CTX_TIMEOUT(c)==1,210);
#else
        CHECK((uintptr_t)CTX_TIMEOUT(c)==(uintptr_t)state.time_pointer,210);
#endif
    }
#if defined(__arm__)
    CHECK(((c->uc_mcontext.arm_cpsr&0x20)!=0)==(form==1),211);
#endif
}
static void handle(int signal,siginfo_t *info,void *context)
{
    int saved=errno;ucontext_t *c=context;sigset_t mask;
    CHECK(role==1&&info&&c&&thread_syscall4(SYS_gettid,0,0,0,0)==state.target,212);
    CHECK(info->si_signo==signal&&info->si_errno==0&&info->si_code==SI_TKILL,213);
    CHECK(info->si_pid==state.pid&&info->si_uid==state.uid,214);
    ++depth;CHECK(sigprocmask(SIG_SETMASK,0,&mask)==0&&sigismember(&mask,signal)==1,215);
#if defined(__powerpc__)
    CHECK(c->uc_regs!=0,216);
#endif
    if(signal==SIGUSR2){
        CHECK(case_id==16&&depth==2&&load(&state.nested)==0,217);
        handler_marker("FUTEX_SIGNAL_NESTED",1,c,0);store(&state.nested,1);--depth;errno=saved;return;
    }
    CHECK(signal==SIGUSR1&&depth==1,218);int ordinal=load(&state.handled)+1;
    CHECK(ordinal==1||(case_id==9&&ordinal==2),219);
    if(caught_in_wait())inspect_context(c);else CHECK(load(&state.done)==1,220);
    handler_marker("FUTEX_SIGNAL_HANDLE",ordinal,c,caught_in_wait());
    if(case_id==4)store(state.word,alternate_value);
    if(case_id==5){CTX_PC(c)=state.resume;context_success(c,77);}
    if(case_id==6)CTX_NUMBER(c)=SYS_getpid;
    if(case_id==7)CTX_VALUE(c)=alternate_value;
    if(case_id==8){CTX_ADDRESS(c)=(uintptr_t)state.alternate;CTX_VALUE(c)=alternate_value;}
    if(case_id==16){
        CHECK(thread_syscall4(SYS_tgkill,state.pid,state.target,SIGUSR2,0)==0,221);CHECK(load(&state.nested)==1,222);
    }
    handler_marker("FUTEX_SIGNAL_HANDLER_RETURN",ordinal,c,caught_in_wait());
    store(&state.handled,ordinal);--depth;errno=saved;
}
static void *waiter(void *unused)
{
    (void)unused;role=1;state.target=(pid_t)thread_syscall4(SYS_gettid,0,0,0,0);
    CHECK(state.target>0&&state.target!=state.pid,105);
    sigset_t mask;CHECK(sigemptyset(&mask)==0,106);
    if(case_id==14)CHECK(sigaddset(&mask,SIGUSR1)==0,107);
    CHECK(sigprocmask(SIG_SETMASK,&mask,0)==0,108);
    store(&state.ready,1);wait_word(&state.go,1);
    marker("FUTEX_SIGNAL_ATTEMPT arch=%s form=%d abi=%d domain=%d round=%d case=%d pid=%ld tid=%ld number=%lu address=%lu operation=%lu value=%lu timeout=%lu\n",
        PROBE_ARCH,form,abi,domain,round_id,case_id,(long)state.pid,(long)state.target,state.number,(unsigned long)(uintptr_t)state.word,state.operation,state.expected,(unsigned long)(uintptr_t)state.time_pointer);
    errno=111;int64_t start=now();store(&state.entered,1);
#if defined(__arm__)
    if(form==1)state.result=futex_signal_thumb(state.number,state.word,state.operation,state.expected,state.time_pointer,0);
    else
#endif
    state.result=futex_signal_raw(state.number,state.word,state.operation,state.expected,state.time_pointer,
#if defined(__powerpc__)
        form
#else
        0
#endif
    );
    state.error=errno;state.elapsed=now()-start;
    marker("FUTEX_SIGNAL_RETURN arch=%s form=%d abi=%d domain=%d round=%d case=%d result=%ld error=%d elapsed=%llu\n",
        PROBE_ARCH,form,abi,domain,round_id,case_id,state.result,state.error,(unsigned long long)state.elapsed);
    store(&state.done,1);
    if(case_id==12||case_id==13)wait_word(&state.handled,1);
    if(case_id==14){
        CHECK(sigpending(&mask)==0&&sigismember(&mask,SIGUSR1)==1&&load(&state.handled)==0,109);
        marker("FUTEX_SIGNAL_UNMASK arch=%s form=%d abi=%d domain=%d round=%d case=%d\n",PROBE_ARCH,form,abi,domain,round_id,case_id);
        CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0&&load(&state.handled)==1,110);
    }
    return (void *)(uintptr_t)0x1875;
}
static void confirm_wait(int generation)
{
    wait_word(&state.entered,1);
    void *address=case_id==8&&generation>1?(void *)state.alternate:(void *)state.word;
    unsigned long expected=case_id==8&&generation>1?alternate_value:state.expected;
#ifdef FUTEX_SIGNAL_LINUX_REFERENCE
    char path[128];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)state.target)>0,111);
    int64_t start=now();int observed=0;
    while(!observed){
        char buffer[256];int fd=open(path,O_RDONLY);CHECK(fd>=0,112);
        ssize_t size=read(fd,buffer,sizeof(buffer)-1);CHECK(size>=0&&close(fd)==0,113);buffer[size]=0;
        long nr=-1;unsigned long a=0,op=0,value=0,timeout=0;
        if(sscanf(buffer,"%ld %lx %lx %lx %lx",&nr,&a,&op,&value,&timeout)==5)
            observed=nr==(long)state.number&&a==(unsigned long)(uintptr_t)address&&op==state.operation&&value==expected&&timeout==(unsigned long)(uintptr_t)state.time_pointer;
        CHECK(!load(&state.done)&&now()-start<5000000000LL,114);
    }
    marker("FUTEX_SIGNAL_LINUX_WAIT arch=%s form=%d abi=%d domain=%d round=%d case=%d pid=%ld tid=%ld generation=%d address=%lu value=%lu\n",
        PROBE_ARCH,form,abi,domain,round_id,case_id,(long)state.pid,(long)state.target,generation,(unsigned long)(uintptr_t)address,expected);
#else
    (void)generation;(void)address;(void)expected;delay(60000000);
#endif
    CHECK(!load(&state.done),115);
}
static void send_signal(int ordinal,int delivered)
{
    marker("FUTEX_SIGNAL_SEND arch=%s form=%d abi=%d domain=%d round=%d case=%d pid=%ld tid=%ld ordinal=%d signal=%d\n",
        PROBE_ARCH,form,abi,domain,round_id,case_id,(long)state.pid,(long)state.target,ordinal,SIGUSR1);
    CHECK(thread_syscall4(SYS_tgkill,state.pid,state.target,SIGUSR1,0)==0,116);
    if(delivered)wait_word(&state.handled,ordinal);
}
static void wake(void *address,int expected)
{
    marker("FUTEX_SIGNAL_WAKE arch=%s form=%d abi=%d domain=%d round=%d case=%d address=%lu operation=%lu expected=%d\n",
        PROBE_ARCH,form,abi,domain,round_id,case_id,(unsigned long)(uintptr_t)address,state.operation|1,expected);
    CHECK(thread_syscall4(state.number,(uintptr_t)address,state.operation|1,1,0)==expected,117);
}
static void run_case(void)
{
    memset(&state,0,sizeof(state));state.pid=getpid();state.uid=getuid();state.number=SYS_futex;state.operation=domain?128:0;
    state.wide=sizeof(long)==8;
#ifdef SYS_futex_time64
    if(abi||SYS_futex==SYS_futex_time64){state.number=SYS_futex_time64;state.wide=1;}
#endif
    state.expected=initial_value+(case_id==18);
    state.site=(uintptr_t)futex_signal_site;state.resume=(uintptr_t)futex_signal_resume;
#if defined(__arm__)
    if(form){state.site=(uintptr_t)futex_signal_thumb_site;state.resume=(uintptr_t)futex_signal_thumb_resume;}
#endif
    state.mapping=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(state.mapping!=MAP_FAILED,118);memset(state.mapping,0xa5,4096);
    state.word=(_Atomic uint32_t *)(state.mapping+64);state.alternate=(_Atomic uint32_t *)(state.mapping+128);
    store(state.word,initial_value);store(state.alternate,alternate_value);
    memset(&state.timeout,0xa5,sizeof(state.timeout));
    state.timed=case_id==2||case_id==3||case_id==10||case_id==12||case_id==17;
    state.duration=case_id==17?0:case_id==10||case_id==12?160000000:500000000;
    encode_timeout(state.duration);state.time_pointer=state.timed?state.timeout.value:0;
    unsigned char expected_timeout[16];memcpy(expected_timeout,state.timeout.value,16);
    struct sigaction action={0};action.sa_sigaction=handle;action.sa_flags=SA_SIGINFO;
    if(case_id!=0&&case_id!=2)action.sa_flags|=SA_RESTART;
    CHECK(sigemptyset(&action.sa_mask)==0&&sigaction(SIGUSR1,&action,0)==0&&sigaction(SIGUSR2,&action,0)==0,119);
    if(case_id==15){action.sa_handler=SIG_IGN;CHECK(sigaction(SIGUSR1,&action,0)==0,120);}
    sigset_t mask;CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,121);
    pthread_t thread;CHECK(pthread_create(&thread,0,waiter,0)==0,122);wait_word(&state.ready,1);
    marker("FUTEX_SIGNAL_CASE_BEGIN arch=%s form=%d abi=%d domain=%d round=%d case=%d pid=%ld tid=%ld number=%lu address=%lu alternate=%lu operation=%lu value=%lu timeout=%lu format=%s timed=%d duration=%llu site=%lu resume=%lu wait=%d\n",
        PROBE_ARCH,form,abi,domain,round_id,case_id,(long)state.pid,(long)state.target,state.number,(unsigned long)(uintptr_t)state.word,
        (unsigned long)(uintptr_t)state.alternate,state.operation,state.expected,(unsigned long)(uintptr_t)state.time_pointer,state.wide?"time64":"time32",state.timed,
        (unsigned long long)state.duration,(unsigned long)state.site,(unsigned long)state.resume,case_id<17);
    store(&state.go,1);
    if(case_id<17){
        confirm_wait(1);
        if(caught_in_wait()){
            send_signal(1,1);
            if(case_id==9){confirm_wait(2);send_signal(2,1);}
            if(case_id==1||case_id==8||case_id==9||case_id==16){
                confirm_wait(case_id==9?3:2);
                if(case_id==8)wake(state.word,0);
                wake(case_id==8?(void *)state.alternate:(void *)state.word,1);
            }
        }else if(case_id==10){
            marker("FUTEX_SIGNAL_MUTATE_TIMEOUT arch=%s form=%d abi=%d domain=%d round=%d case=%d\n",PROBE_ARCH,form,abi,domain,round_id,case_id);
            encode_timeout(2000000000LL);memcpy(expected_timeout,state.timeout.value,16);
        }else if(case_id==12){wait_word(&state.done,1);send_signal(1,1);}
        else{
            if(case_id==14||case_id==15){send_signal(1,0);delay(20000000);CHECK(load(&state.handled)==0&&!load(&state.done),123);}
            wake(state.word,1);
            if(case_id==13){wait_word(&state.done,1);send_signal(1,1);}
        }
    }
    wait_word(&state.done,1);void *joined=0;CHECK(pthread_join(thread,&joined)==0&&joined==(void *)(uintptr_t)0x1875,124);
    long expected=case_id==0||case_id==2||case_id==3?-EINTR:case_id==4||case_id==7||case_id==18?-EAGAIN:case_id==5?77:case_id==6?state.pid:case_id==10||case_id==12||case_id==17?-ETIMEDOUT:0;
    CHECK(state.result==expected&&state.error==111,125);
    int handlers=caught_in_wait()||case_id==12||case_id==13||case_id==14;
    CHECK(load(&state.handled)==handlers+(case_id==9)&&load(&state.nested)==(case_id==16),126);
    if(case_id==2||case_id==3)CHECK(state.elapsed<state.duration,127);
    if(case_id==10||case_id==12)CHECK(state.elapsed>=state.duration&&state.elapsed<state.duration+1000000000,128);
    CHECK(memcmp(state.timeout.value,expected_timeout,16)==0,129);
    for(unsigned i=0;i<16;++i)CHECK(state.timeout.before[i]==0xa5&&state.timeout.after[i]==0xa5,130);
    CHECK(load(state.word)==(case_id==4?alternate_value:initial_value)&&load(state.alternate)==alternate_value,131);
    for(unsigned i=0;i<4096;++i)if(!(i>=64&&i<68)&&!(i>=128&&i<132))CHECK(state.mapping[i]==0xa5,132);
    wake(state.word,0);wake(state.alternate,0);
    CHECK(munmap(state.mapping,4096)==0,133);
    marker("FUTEX_SIGNAL_CASE_PASS arch=%s form=%d abi=%d domain=%d round=%d case=%d\n",PROBE_ARCH,form,abi,domain,round_id,case_id);
}
int main(void)
{
    CHECK(__atomic_always_lock_free(sizeof(state.handled),&state.handled),140);
    for(domain=0;domain<2;++domain)for(abi=0;abi<abis;++abi)for(form=0;form<forms;++form){
        pid_t child=fork();CHECK(child>=0,141);
        if(!child){
            for(round_id=0;round_id<rounds;++round_id)for(case_id=0;case_id<cases;++case_id)run_case();
            thread_syscall4(SYS_exit_group,0,0,0,0);fail(142);
        }
        int status=-1;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0,143);
    }
#ifdef FUTEX_SIGNAL_LINUX_REFERENCE
    marker("FUTEX_SIGNAL_LINUX_REFERENCE_PASS arch=%s forms=%d abis=%d domains=2 rounds=2 cases=%d initial_waits=%d parent=1\n",PROBE_ARCH,forms,abis,forms*abis*76,forms*abis*68);
#else
    marker("FUTEX_SIGNAL_PASS arch=%s forms=%d abis=%d domains=2 rounds=2 cases=%d initial_waits=%d parent=1\n",PROBE_ARCH,forms,abis,forms*abis*76,forms*abis*68);
#endif
    return 0;
}
