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
#include <unistd.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include "thread_syscall.h"

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
#if __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__NO_FPRS__)
#error "PPC guest requires big-endian PPC32 scalar soft-float"
#endif
#else
#error "Unsupported pipe read profile"
#endif

#if defined(__powerpc__) && defined(__clang__)
#define load(p) __c11_atomic_load((p),__ATOMIC_SEQ_CST)
#define store(p,v) __c11_atomic_store((p),(v),__ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p),__ATOMIC_SEQ_CST)
#define store(p,v) __atomic_store_n((p),(v),__ATOMIC_SEQ_CST)
#endif

enum { rounds=4, cases=8 };
static int form, round_id, case_id;
static _Thread_local int role;
static struct {
    int original[2], replacement[2], duplicate;
    unsigned char *mapping, *destination;
    size_t count;
    pid_t pid, reader;
    long result;
    int error;
    _Atomic int ready, go, entered, done;
} state;

static __attribute__((noreturn)) void fail(int code)
{
    char text[]="PIPE_READ_FAIL code=000 form=0 round=0 case=0 role=0\n";
    unsigned p=sizeof("PIPE_READ_FAIL code=")-1;
    text[p]='0'+code/100%10;text[p+1]='0'+code/10%10;text[p+2]='0'+code%10;
    text[sizeof("PIPE_READ_FAIL code=000 form=")-1]='0'+form;
    text[sizeof("PIPE_READ_FAIL code=000 form=0 round=")-1]='0'+round_id;
    text[sizeof("PIPE_READ_FAIL code=000 form=0 round=0 case=")-1]='0'+case_id;
    text[sizeof("PIPE_READ_FAIL code=000 form=0 round=0 case=0 role=")-1]='0'+role;
    thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0);
    thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do {if(!(c))fail(n);} while(0)
static void marker(const char *format,...)
{
    char buffer[384];va_list values;va_start(values,format);
    int size=vsnprintf(buffer,sizeof(buffer),format,values);va_end(values);
    CHECK(size>0&&(size_t)size<sizeof(buffer),101);
    CHECK(thread_syscall4(SYS_write,1,(uintptr_t)buffer,(uintptr_t)size,0)==size,102);
}
static int64_t now(void)
{
    struct timespec value;CHECK(clock_gettime(CLOCK_MONOTONIC,&value)==0,103);
    return (int64_t)value.tv_sec*1000000000+value.tv_nsec;
}
static void wait_word(_Atomic int *word,int value)
{
    int64_t start=now();while(load(word)!=value)CHECK(now()-start<5000000000LL,104);
}
static void delay(int64_t duration)
{
    int64_t start=now();while(now()-start<duration){}
}
static void nonblocking(int fd)
{
    int flags=fcntl(fd,F_GETFL);CHECK(flags>=0,105);CHECK(fcntl(fd,F_SETFL,flags|O_NONBLOCK)==0,106);
}
static void *reader(void *unused)
{
    (void)unused;role=1;state.reader=(pid_t)thread_syscall4(SYS_gettid,0,0,0,0);
    CHECK(state.reader>0&&state.reader!=state.pid,107);store(&state.ready,1);wait_word(&state.go,1);
    marker("PIPE_READ_ATTEMPT arch=%s form=%d round=%d case=%d pid=%ld tid=%ld fd=%d buffer=%lu count=%lu\n",
        PROBE_ARCH,form,round_id,case_id,(long)state.pid,(long)state.reader,state.original[0],
        (unsigned long)(uintptr_t)state.destination,(unsigned long)state.count);
    errno=111;store(&state.entered,1);
    if(form==0){state.result=read(state.original[0],state.destination,state.count);state.error=errno;}
    else {
        long raw=thread_syscall4(SYS_read,(uintptr_t)state.original[0],(uintptr_t)state.destination,state.count,0);
        CHECK(errno==111,108);state.result=raw<0?-1:raw;state.error=raw<0?(int)-raw:111;
    }
    store(&state.done,1);return (void *)(uintptr_t)0x1875;
}

/* Opportunity is not evidence. The OS collector must observe the owned arm
 * between ATTEMPT and MUTATE. The separate host reference confirms the Linux
 * blocked syscall through /proc before mutating the shared descriptor table. */
static void confirm_opportunity(void)
{
    wait_word(&state.entered,1);
#ifdef PIPE_LINUX_REFERENCE
    char path[96];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)state.reader)>0,109);
    int64_t start=now();int observed=0;
    while(!observed){
        char buffer[256];int fd=open(path,O_RDONLY);CHECK(fd>=0,110);
        ssize_t size=read(fd,buffer,sizeof(buffer)-1);CHECK(size>=0&&close(fd)==0,111);buffer[size]=0;
        long number=-1;unsigned long a=0,b=0,c=0;
        if(sscanf(buffer,"%ld %lx %lx %lx",&number,&a,&b,&c)==4)
            observed=number==SYS_read&&a==(unsigned long)state.original[0]&&b==(unsigned long)(uintptr_t)state.destination&&c==state.count;
        CHECK(now()-start<5000000000LL&&!load(&state.done),112);
    }
    marker("PIPE_READ_LINUX_WAIT form=%d round=%d case=%d pid=%ld tid=%ld\n",form,round_id,case_id,(long)state.pid,(long)state.reader);
#else
    delay(60000000);
#endif
    CHECK(!load(&state.done),113);
}
static pthread_t setup(void)
{
    memset(&state,0,sizeof(state));state.duplicate=-1;state.pid=getpid();state.count=case_id==2?8:case_id==5?0:1;
    CHECK(pipe(state.original)==0&&pipe(state.replacement)==0,114);
    state.mapping=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(state.mapping!=MAP_FAILED,115);memset(state.mapping,0xa5,4096);state.destination=state.mapping+64;
    if(case_id!=1&&case_id!=7){state.duplicate=dup(state.original[0]);CHECK(state.duplicate>=0,116);}
    if(case_id==6)nonblocking(state.original[0]);
    pthread_t thread;CHECK(pthread_create(&thread,0,reader,0)==0,117);wait_word(&state.ready,1);
    marker("PIPE_READ_CASE_BEGIN arch=%s form=%d round=%d case=%d pid=%ld tid=%ld fd=%d buffer=%lu count=%lu wait=%d\n",
        PROBE_ARCH,form,round_id,case_id,(long)state.pid,(long)state.reader,state.original[0],
        (unsigned long)(uintptr_t)state.destination,(unsigned long)state.count,case_id<5||case_id==7);
    store(&state.go,1);return thread;
}
static void unchanged(size_t count)
{
    for(size_t i=0;i<4096;++i)if(i<64||i>=64+count)CHECK(state.mapping[i]==0xa5,118);
}
static void pass(void)
{
    marker("PIPE_READ_CASE_PASS arch=%s form=%d round=%d case=%d\n",PROBE_ARCH,form,round_id,case_id);
}
static void normal_case(void)
{
    pthread_t thread=setup();
    if(case_id<5){
        confirm_opportunity();
        marker("PIPE_READ_MUTATE arch=%s form=%d round=%d case=%d pid=%ld tid=%ld\n",PROBE_ARCH,form,round_id,case_id,(long)state.pid,(long)state.reader);
        if(case_id==1)CHECK(close(state.original[0])==0,119);
        CHECK(dup2(state.replacement[0],state.original[0])==state.original[0],120);
        if(case_id==4)CHECK(mprotect(state.mapping,4096,PROT_READ)==0,121);
        CHECK(write(state.replacement[1],"B",1)==1,122);
        marker("PIPE_READ_REPLACEMENT_READY arch=%s form=%d round=%d case=%d\n",PROBE_ARCH,form,round_id,case_id);
        delay(20000000);CHECK(!load(&state.done),123);
        marker("PIPE_READ_ORIGINAL_READY arch=%s form=%d round=%d case=%d\n",PROBE_ARCH,form,round_id,case_id);
        if(case_id==3){CHECK(close(state.original[1])==0,124);state.original[1]=-1;}
        else CHECK(write(state.original[1],case_id==2?"ARC":"A",case_id==2?3:1)==(case_id==2?3:1),125);
    }
    wait_word(&state.done,1);void *value=0;CHECK(pthread_join(thread,&value)==0&&value==(void *)(uintptr_t)0x1875,126);
    if(case_id==4||case_id==6)CHECK(state.result==-1&&state.error==(case_id==4?EFAULT:EAGAIN),127);
    else CHECK(state.result==(case_id==2?3:case_id==3||case_id==5?0:1)&&state.error==111,128);
    size_t consumed=case_id==0||case_id==1?1:case_id==2?3:0;
    if(consumed)CHECK(memcmp(state.destination,case_id==2?"ARC":"A",consumed)==0,129);
    unchanged(consumed);
    if(case_id<5){
        char value=0;nonblocking(state.replacement[0]);CHECK(read(state.replacement[0],&value,1)==1&&value=='B',130);
        errno=0;CHECK(read(state.replacement[0],&value,1)==-1&&errno==EAGAIN,131);
        if(state.duplicate>=0){
            nonblocking(state.duplicate);errno=0;ssize_t left=read(state.duplicate,&value,1);
            if(case_id==4)CHECK(left==1&&value=='A',132);
            else if(case_id==3)CHECK(left==0,133);
            else CHECK(left==-1&&errno==EAGAIN,134);
        }
    }
    CHECK(close(state.original[0])==0&&close(state.replacement[0])==0&&close(state.replacement[1])==0,135);
    if(state.original[1]>=0)CHECK(close(state.original[1])==0,136);
    if(state.duplicate>=0)CHECK(close(state.duplicate)==0,137);
    CHECK(munmap(state.mapping,4096)==0,138);pass();
}
static void lifecycle_case(void)
{
    pid_t child=fork();CHECK(child>=0,139);
    if(!child){
        (void)setup();confirm_opportunity();
        marker("PIPE_READ_EXIT_GROUP arch=%s form=%d round=%d case=%d pid=%ld tid=%ld\n",PROBE_ARCH,form,round_id,case_id,(long)state.pid,(long)state.reader);
        thread_syscall4(SYS_exit_group,0,0,0,0);fail(140);
    }
    int status=-1;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0,141);pass();
}
int main(void)
{
    struct sigaction action={0};action.sa_handler=SIG_IGN;CHECK(sigemptyset(&action.sa_mask)==0&&sigaction(SIGPIPE,&action,0)==0,142);
    for(form=0;form<2;++form){
        pid_t child=fork();CHECK(child>=0,143);
        if(!child){
            for(round_id=0;round_id<rounds;++round_id)for(case_id=0;case_id<cases;++case_id){
                if(case_id==7)lifecycle_case();else normal_case();
            }
            thread_syscall4(SYS_exit_group,0,0,0,0);fail(144);
        }
        int status=-1;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0,145);
    }
#ifdef PIPE_LINUX_REFERENCE
    marker("PIPE_READ_LINUX_REFERENCE_PASS arch=%s forms=2 rounds=4 cases=64 waits=48 efault=8 parent=1\n",PROBE_ARCH);
#else
    marker("PIPE_READ_PASS arch=%s forms=2 rounds=4 cases=64 waits=48 efault=8 parent=1\n",PROBE_ARCH);
#endif
    return 0;
}
