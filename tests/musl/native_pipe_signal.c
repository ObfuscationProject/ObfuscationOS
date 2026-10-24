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
#include "pipe_signal_raw.h"

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
#error "Unsupported pipe signal profile"
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
enum { rounds=3, cases=12 };
static int form,round_id,case_id;
static _Thread_local int role,depth;
static struct {
    int original[2],replacement[2],duplicate;
    unsigned char *mapping,*destination,*alternate;
    unsigned long count;
    uintptr_t site,resume;
    pid_t pid,reader;
    uid_t uid;
    long result;
    int error;
    _Atomic int ready,go,entered,done,handled,nested;
} state;
static __attribute__((noreturn)) void fail(int code)
{
    char text[]="PIPE_SIGNAL_FAIL code=000 form=0 round=0 case=00 role=0\n";
    unsigned p=sizeof("PIPE_SIGNAL_FAIL code=")-1;
    text[p]='0'+code/100%10;text[p+1]='0'+code/10%10;text[p+2]='0'+code%10;
    text[sizeof("PIPE_SIGNAL_FAIL code=000 form=")-1]='0'+form;
    text[sizeof("PIPE_SIGNAL_FAIL code=000 form=0 round=")-1]='0'+round_id;
    p=sizeof("PIPE_SIGNAL_FAIL code=000 form=0 round=0 case=")-1;
    text[p]='0'+case_id/10;text[p+1]='0'+case_id%10;
    text[sizeof("PIPE_SIGNAL_FAIL code=000 form=0 round=0 case=00 role=")-1]='0'+role;
    thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0);
    thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
static void marker(const char *format,...)
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
    number(&b," form=",form);number(&b," round=",round_id);number(&b," case=",case_id);
    number(&b," pid=",state.pid);number(&b," tid=",state.reader);number(&b," ordinal=",ordinal);
    number(&b," pc=",(uintptr_t)CTX_PC(c));number(&b," inspected=",inspect);
    if(inspect){number(&b," number=",(uintptr_t)CTX_NUMBER(c));number(&b," fd=",(uintptr_t)CTX_FD(c));
        number(&b," buffer=",(uintptr_t)CTX_BUFFER(c));number(&b," count=",(uintptr_t)CTX_COUNT(c));
#if defined(__powerpc__)
        number(&b," cr=",c->uc_regs->gregs[38]);number(&b," diagnostic_result=",c->uc_regs->gregs[43]);
        number(&b," orig_r3=",c->uc_regs->gregs[34]);
#elif defined(__arm__)
        number(&b," cpsr=",c->uc_mcontext.arm_cpsr);
#elif defined(__mips__)
        number(&b," a3=",(uintptr_t)c->uc_mcontext.gregs[7]);
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
static int libc_case(void){return case_id>=10;}
static int interrupted_case(void){return case_id==0||case_id==10;}
static uintptr_t instruction_size(ucontext_t *c)
{
#if defined(__i386__) || defined(__x86_64__)
    (void)c;return 2;
#elif defined(__arm__)
    return c->uc_mcontext.arm_cpsr&0x20?2:4;
#else
    (void)c;return 4;
#endif
}
static void inspect_context(ucontext_t *c)
{
    int restart=!interrupted_case();uintptr_t pc=(uintptr_t)CTX_PC(c),width=instruction_size(c);
    if(!libc_case())CHECK(pc==(restart?state.site:state.resume),203);
    CHECK((uintptr_t)CTX_BUFFER(c)==(uintptr_t)state.destination&&(uintptr_t)CTX_COUNT(c)==state.count,204);
    if(restart){
        CHECK((uintptr_t)CTX_NUMBER(c)==SYS_read&&(uintptr_t)CTX_FD(c)==(uintptr_t)state.original[0],205);
#if defined(__mips__)
        if(!libc_case())CHECK(c->uc_mcontext.gregs[7]==0x1357,206);
#elif defined(__powerpc__)
        CHECK((c->uc_regs->gregs[38]&0x10000000u)&&c->uc_regs->gregs[43]==0,207);
        CHECK(c->uc_regs->gregs[34]==(unsigned long)state.original[0]&&c->uc_regs->gregs[40]==0xc00,208);
#endif
    }else CHECK(context_result(c)==-EINTR,209);
#if defined(__arm__)
    if(!libc_case())CHECK(((c->uc_mcontext.arm_cpsr&0x20)!=0)==(form==1),210);
#endif
    /* Exact raw labels are checked above. For musl's private cancellation site,
     * inspect the opcode at the saved restart address or immediately before PC. */
    const unsigned char *p=(const unsigned char *)(restart?pc:pc-width);
#if defined(__x86_64__)
    CHECK(p[0]==0x0f&&p[1]==0x05,211);
#elif defined(__i386__)
    CHECK(p[0]==0xcd&&p[1]==0x80,211);
#else
    uint32_t opcode=0;for(uintptr_t i=0;i<width;++i){
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
        opcode=(opcode<<8)|p[i];
#else
        opcode|=(uint32_t)p[i]<<(8*i);
#endif
    }
#if defined(__aarch64__)
    CHECK((opcode&0xffe0001fu)==0xd4000001u,211);
#elif defined(__arm__)
    CHECK(width==2?(opcode&0xff00)==0xdf00:(opcode&0x0f000000)==0x0f000000&&(opcode>>28)!=15,211);
#elif defined(__riscv)
    CHECK(opcode==0x73,211);
#elif defined(__loongarch64)
    CHECK((opcode&0xffff8000u)==0x002b0000u,211);
#elif defined(__mips__)
    CHECK((opcode&0xfc00003fu)==0x0c,211);
#elif defined(__powerpc__)
    CHECK(opcode==0x44000002,211);
#endif
#endif
}
static void handle(int signal,siginfo_t *info,void *context)
{
    int saved=errno;ucontext_t *c=context;sigset_t mask;
    CHECK(role==1&&info&&c&&thread_syscall4(SYS_gettid,0,0,0,0)==state.reader,212);
    CHECK(info->si_signo==signal&&info->si_errno==0&&info->si_code==SI_TKILL,213);
    CHECK(info->si_pid==state.pid&&info->si_uid==state.uid,214);
    ++depth;CHECK(sigprocmask(SIG_SETMASK,0,&mask)==0&&sigismember(&mask,signal)==1,215);
#if defined(__powerpc__)
    CHECK(c->uc_regs!=0,216);
#endif
    if(signal==SIGUSR2){
        CHECK(case_id==9&&depth==2&&load(&state.nested)==0,217);
        handler_marker("PIPE_SIGNAL_NESTED",1,c,0);store(&state.nested,1);--depth;errno=saved;return;
    }
    CHECK(signal==SIGUSR1&&depth==1,218);int ordinal=load(&state.handled)+1;
    CHECK(ordinal==1||(case_id==8&&ordinal==2),219);
    if(case_id!=7)inspect_context(c);else CHECK(load(&state.done)==1,220);
    handler_marker("PIPE_SIGNAL_HANDLE",ordinal,c,case_id!=7);
    if(case_id==2){CTX_PC(c)=state.resume;context_success(c,77);}
    if(case_id==3)CTX_NUMBER(c)=SYS_getpid;
    if(case_id==4){CTX_FD(c)=state.replacement[0];CTX_BUFFER(c)=(uintptr_t)state.alternate;CTX_COUNT(c)=2;}
    if(case_id==5)CHECK(dup2(state.replacement[0],state.original[0])==state.original[0],221);
    if(case_id==9){
        CHECK(thread_syscall4(SYS_tgkill,state.pid,state.reader,SIGUSR2,0)==0,222);
        CHECK(load(&state.nested)==1,223);
    }
    handler_marker("PIPE_SIGNAL_HANDLER_RETURN",ordinal,c,case_id!=7);
    store(&state.handled,ordinal);--depth;errno=saved;
}
static void *reader(void *unused)
{
    (void)unused;role=1;state.reader=(pid_t)thread_syscall4(SYS_gettid,0,0,0,0);
    CHECK(state.reader>0&&state.reader!=state.pid,105);store(&state.ready,1);wait_word(&state.go,1);
    marker("PIPE_SIGNAL_ATTEMPT arch=%s form=%d round=%d case=%d pid=%ld tid=%ld fd=%d buffer=%lu count=%lu\n",
        PROBE_ARCH,form,round_id,case_id,(long)state.pid,(long)state.reader,state.original[0],(unsigned long)(uintptr_t)state.destination,state.count);
    errno=111;store(&state.entered,1);
    if(libc_case())state.result=read(state.original[0],state.destination,state.count);
#if defined(__arm__)
    else if(form==1)state.result=pipe_signal_thumb(state.original[0],state.destination,state.count,0x1357);
#endif
    else state.result=pipe_signal_raw(state.original[0],state.destination,state.count,
#if defined(__powerpc__)
        form
#else
        0x1357
#endif
    );
    state.error=errno;
    marker("PIPE_SIGNAL_RETURN arch=%s form=%d round=%d case=%d result=%ld error=%d\n",PROBE_ARCH,form,round_id,case_id,state.result,state.error);
    store(&state.done,1);if(case_id==7)wait_word(&state.handled,1);
    return (void *)(uintptr_t)0x1875;
}
static void confirm_wait(int generation)
{
    wait_word(&state.entered,1);
#ifdef PIPE_SIGNAL_LINUX_REFERENCE
    char path[128];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)state.reader)>0,106);
    int64_t start=now();int observed=0;
    while(!observed){
        char buffer[256];int fd=open(path,O_RDONLY);CHECK(fd>=0,107);
        ssize_t size=read(fd,buffer,sizeof(buffer)-1);CHECK(size>=0&&close(fd)==0,108);buffer[size]=0;
        long nr=-1;unsigned long a=0,b=0,n=0;
        if(sscanf(buffer,"%ld %lx %lx %lx",&nr,&a,&b,&n)==4)
            observed=nr==SYS_read&&a==(unsigned long)state.original[0]&&b==(unsigned long)(uintptr_t)state.destination&&n==state.count;
        CHECK(!load(&state.done)&&now()-start<5000000000LL,109);
    }
    marker("PIPE_SIGNAL_LINUX_WAIT arch=%s form=%d round=%d case=%d pid=%ld tid=%ld generation=%d\n",
        PROBE_ARCH,form,round_id,case_id,(long)state.pid,(long)state.reader,generation);
#else
    (void)generation;delay(60000000);
#endif
    CHECK(!load(&state.done),110);
}
static void send_signal(int ordinal)
{
    marker("PIPE_SIGNAL_SEND arch=%s form=%d round=%d case=%d pid=%ld tid=%ld ordinal=%d signal=%d\n",
        PROBE_ARCH,form,round_id,case_id,(long)state.pid,(long)state.reader,ordinal,SIGUSR1);
    CHECK(thread_syscall4(SYS_tgkill,state.pid,state.reader,SIGUSR1,0)==0,111);wait_word(&state.handled,ordinal);
}
static void nonblocking(int fd)
{
    int flags=fcntl(fd,F_GETFL);CHECK(flags>=0&&fcntl(fd,F_SETFL,flags|O_NONBLOCK)==0,112);
}
static void empty(int fd)
{
    char c=0;nonblocking(fd);errno=0;CHECK(read(fd,&c,1)==-1&&errno==EAGAIN,113);
}
static void run_case(void)
{
    memset(&state,0,sizeof(state));state.pid=getpid();state.uid=getuid();state.count=case_id==7?8:1;
    state.site=(uintptr_t)pipe_signal_site;state.resume=(uintptr_t)pipe_signal_resume;
#if defined(__arm__)
    if(form){state.site=(uintptr_t)pipe_signal_thumb_site;state.resume=(uintptr_t)pipe_signal_thumb_resume;}
#endif
    CHECK(pipe(state.original)==0&&pipe(state.replacement)==0,114);
    state.duplicate=dup(state.original[0]);CHECK(state.duplicate>=0,115);
    state.mapping=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(state.mapping!=MAP_FAILED,116);memset(state.mapping,0xa5,4096);
    state.destination=state.mapping+64;state.alternate=state.mapping+128;
    if(case_id==4)CHECK(write(state.replacement[1],"BY",2)==2,117);
    if(case_id==5)CHECK(write(state.replacement[1],"B",1)==1,118);
    if(case_id==7)CHECK(write(state.original[1],"ARC",3)==3,119);
    struct sigaction action={0};action.sa_sigaction=handle;action.sa_flags=SA_SIGINFO;
    if(!interrupted_case())action.sa_flags|=SA_RESTART;
    CHECK(sigemptyset(&action.sa_mask)==0&&sigaction(SIGUSR1,&action,0)==0&&sigaction(SIGUSR2,&action,0)==0,120);
    sigset_t mask;CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,121);
    pthread_t thread;CHECK(pthread_create(&thread,0,reader,0)==0,122);wait_word(&state.ready,1);
    marker("PIPE_SIGNAL_CASE_BEGIN arch=%s form=%d round=%d case=%d pid=%ld tid=%ld fd=%d buffer=%lu count=%lu site=%lu resume=%lu replacement=%d alternate=%lu libc=%d wait=%d\n",
        PROBE_ARCH,form,round_id,case_id,(long)state.pid,(long)state.reader,state.original[0],
        (unsigned long)(uintptr_t)state.destination,state.count,(unsigned long)state.site,(unsigned long)state.resume,state.replacement[0],(unsigned long)(uintptr_t)state.alternate,libc_case(),case_id!=7);
    store(&state.go,1);
    if(case_id==7){wait_word(&state.done,1);send_signal(1);}
    else{
        confirm_wait(1);
        if(case_id==6){
            marker("PIPE_SIGNAL_REPLACE arch=%s form=%d round=%d case=%d\n",PROBE_ARCH,form,round_id,case_id);
            CHECK(dup2(state.replacement[0],state.original[0])==state.original[0]&&write(state.replacement[1],"B",1)==1,123);
            delay(20000000);CHECK(!load(&state.done),124);
        }else send_signal(1);
        if(case_id==8){confirm_wait(2);send_signal(2);}
        if(case_id==1||case_id==8||case_id==9||case_id==11)confirm_wait(case_id==8?3:2);
        if(case_id==1||case_id==6||case_id==8||case_id==9||case_id==11){
            marker("PIPE_SIGNAL_ORIGINAL_READY arch=%s form=%d round=%d case=%d\n",PROBE_ARCH,form,round_id,case_id);
            CHECK(write(state.original[1],"A",1)==1,125);
        }
    }
    wait_word(&state.done,1);void *value=0;CHECK(pthread_join(thread,&value)==0&&value==(void *)(uintptr_t)0x1875,126);
    long expected=interrupted_case()?(libc_case()?-1:-EINTR):case_id==2?77:case_id==3?state.pid:case_id==4?2:case_id==7?3:1;
    CHECK(state.result==expected&&state.error==(case_id==10?EINTR:111),127);
    CHECK(load(&state.handled)==(case_id==6?0:case_id==8?2:1)&&load(&state.nested)==(case_id==9),128);
    unsigned consumed=case_id==1||case_id==5||case_id==6||case_id==8||case_id==9||case_id==11?1:case_id==7?3:0;
    if(consumed)CHECK(memcmp(state.destination,case_id==5?"B":case_id==7?"ARC":"A",consumed)==0,129);
    if(case_id==4)CHECK(memcmp(state.alternate,"BY",2)==0,130);
    for(unsigned i=0;i<4096;++i)
        if(!(i>=64&&i<64+consumed)&&!(case_id==4&&i>=128&&i<130))CHECK(state.mapping[i]==0xa5,131);
    empty(state.duplicate);
    if(case_id==6){char c=0;CHECK(read(state.replacement[0],&c,1)==1&&c=='B',132);}
    empty(state.replacement[0]);
    if(case_id==2||case_id==3||case_id==4||case_id==5){
        CHECK(write(state.original[1],"Z",1)==1,133);char c=0;CHECK(read(state.duplicate,&c,1)==1&&c=='Z',134);empty(state.duplicate);
    }
    CHECK(close(state.original[0])==0&&close(state.original[1])==0&&close(state.replacement[0])==0&&close(state.replacement[1])==0&&close(state.duplicate)==0,135);
    CHECK(munmap(state.mapping,4096)==0,136);
    marker("PIPE_SIGNAL_CASE_PASS arch=%s form=%d round=%d case=%d\n",PROBE_ARCH,form,round_id,case_id);
}
int main(void)
{
    CHECK(__atomic_always_lock_free(sizeof(state.handled),&state.handled),140);
    for(form=0;form<forms;++form){
        pid_t child=fork();CHECK(child>=0,141);
        if(!child){
            for(round_id=0;round_id<rounds;++round_id)for(case_id=0;case_id<cases;++case_id)run_case();
            thread_syscall4(SYS_exit_group,0,0,0,0);fail(142);
        }
        int status=-1;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0,143);
    }
#ifdef PIPE_SIGNAL_LINUX_REFERENCE
    marker("PIPE_SIGNAL_LINUX_REFERENCE_PASS arch=%s forms=%d rounds=3 cases=%d initial_waits=%d signals=%d parent=1\n",PROBE_ARCH,forms,forms*36,forms*33,forms*39);
#else
    marker("PIPE_SIGNAL_PASS arch=%s forms=%d rounds=3 cases=%d initial_waits=%d signals=%d parent=1\n",PROBE_ARCH,forms,forms*36,forms*33,forms*39);
#endif
    return 0;
}
