/* Private live-child fork exhaustion; kernel completion/reclaim joins are separate. */
#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stddef.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include "thread_syscall.h"
#if defined(__x86_64__)
#define ARCH "x86_64"
#elif defined(__i386__)
#define ARCH "i386"
#elif defined(__aarch64__)
#define ARCH "aarch64"
#elif defined(__arm__)
#define ARCH "arm32"
#elif defined(__riscv) && __riscv_xlen == 32
#define ARCH "rv32"
#elif defined(__riscv)
#define ARCH "rv64"
#elif defined(__loongarch64)
#define ARCH "loongarch64"
#elif defined(__mips64)
#define ARCH "mips64"
#elif defined(__mips__)
#define ARCH "mips"
#elif defined(__powerpc__)
#define ARCH "ppc"
#if __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__NO_FPRS__)
#error "PPC requires big-endian scalar soft-float"
#endif
#else
#error "Unsupported child-pressure profile"
#endif
_Static_assert(sizeof(siginfo_t)==128,"target siginfo size");
_Static_assert(offsetof(siginfo_t,si_pid)==(sizeof(void*)==8?16:12),"target siginfo union offset");
enum { CAP=128, FAILURES=3, CHILD_STATUS=37, RECOVERY_STATUS=39 };
static unsigned sequence;
static int wave=-1;
static pid_t children[CAP];
static __attribute__((noreturn)) void fail(unsigned line)
{
    char b[]="CHILD_PRESSURE_FAIL line=0000 wave=0\n";
    unsigned at=sizeof("CHILD_PRESSURE_FAIL line=")-1;
    for(unsigned i=0;i<4;++i){b[at+3-i]='0'+line%10;line/=10;}
    b[sizeof("CHILD_PRESSURE_FAIL line=0000 wave=")-1]='0'+(wave<0?9:wave);
    thread_syscall4(SYS_write,1,(uintptr_t)b,sizeof(b)-1,0);
    thread_syscall4(SYS_exit_group,91,0,0,0);for(;;){}
}
#define CHECK(x) do{if(!(x))fail(__LINE__);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{
    char b[768];va_list ap;va_start(ap,format);int n=vsnprintf(b,sizeof(b),format,ap);va_end(ap);
    CHECK(n>0&&(size_t)n<sizeof(b));CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b,n,0)==n);
}
static void event(const char *op,long a,long b,long c)
{marker("CHILD_PRESSURE_EVENT arch=%s wave=%d seq=%u op=%s a=%ld b=%ld c=%ld\n",ARCH,wave,sequence++,op,a,b,c);}
static int64_t now(void)
{struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void deadline(int64_t begin){CHECK(now()-begin<10000000000LL);}
static sigset_t wanted(void)
{sigset_t s;CHECK(sigemptyset(&s)==0&&sigaddset(&s,SIGCHLD)==0);return s;}
static int pending(void)
{sigset_t s;CHECK(sigpending(&s)==0);return sigismember(&s,SIGCHLD);}
static void policy(int which)
{
    struct sigaction a={0};a.sa_handler=which==1?SIG_IGN:SIG_DFL;a.sa_flags=which==2?SA_NOCLDWAIT:0;
    CHECK(sigemptyset(&a.sa_mask)==0&&sigaction(SIGCHLD,&a,0)==0);
    sigset_t s=wanted();CHECK(sigprocmask(SIG_SETMASK,&s,0)==0);
}
static void absent(const char *op)
{
    sigset_t s=wanted();siginfo_t info;struct timespec zero={0};CHECK(pending()==0);errno=0;
    CHECK(sigtimedwait(&s,&info,&zero)==-1&&errno==EAGAIN);event(op,EAGAIN,1,0);
}
static void receive(const char *via,const pid_t *pids,unsigned count,int status)
{
    sigset_t s=wanted();siginfo_t info;struct timespec zero={0};CHECK(pending()==1);
    CHECK(sigtimedwait(&s,&info,&zero)==SIGCHLD);unsigned found=0;
    for(unsigned i=0;i<count;++i)found+=info.si_pid==pids[i];
    CHECK(found==1&&info.si_signo==SIGCHLD&&info.si_code==CLD_EXITED&&info.si_uid==getuid()&&info.si_status==status);
    unsigned char bytes[128]={0};int32_t signal=SIGCHLD,code=CLD_EXITED;
    uint32_t child=info.si_pid,uid=getuid();unsigned offset=sizeof(void*)==8?16:12;
    memcpy(bytes,&signal,4);
#if defined(__mips__)
    memcpy(bytes+4,&code,4);
#else
    memcpy(bytes+8,&code,4);
#endif
    memcpy(bytes+offset,&child,4);memcpy(bytes+offset+4,&uid,4);memcpy(bytes+offset+8,&status,4);
    CHECK(memcmp(bytes,&info,128)==0);char hex[257];const char *digits="0123456789abcdef";
    for(unsigned i=0;i<128;++i){hex[2*i]=digits[bytes[i]>>4];hex[2*i+1]=digits[bytes[i]&15];}hex[256]=0;
    marker("CHILD_PRESSURE_INFO arch=%s wave=%d seq=%u via=%s signal=%d code=1 child=%ld uid=%lu status=%d bytes=128 hex=%s\n",
           ARCH,wave,sequence++,via,SIGCHLD,(long)info.si_pid,(unsigned long)getuid(),status,hex);
}
static __attribute__((noreturn)) void child(int gate[2],int status)
{
    CHECK(close(gate[1])==0);char c=0;ssize_t n;
    do{n=read(gate[0],&c,1);}while(n<0&&errno==EINTR);
    CHECK(n==1&&c=='R');CHECK(close(gate[0])==0);_Exit(status);
}
static void release(int gate[2],unsigned count)
{
    char bytes[CAP];memset(bytes,'R',sizeof(bytes));CHECK(count>0&&count<=CAP);
    /* At most128 bytes into an empty4096-byte pipe; this must not block. */
    CHECK(write(gate[1],bytes,count)==(ssize_t)count);
}
static void collected(pid_t pid,int automatic,int status,const char *op)
{
    int value=0x12345678;int64_t begin=now();
    for(;;){errno=0;pid_t r=waitpid(pid,&value,WNOHANG);
        if(!automatic&&r==pid){CHECK(value==(status<<8));event(op,pid,value,1);break;}
        if(automatic&&r==-1&&errno==ECHILD){event(op,pid,ECHILD,0);break;}
        CHECK(r==0||(r==-1&&errno==EINTR));deadline(begin);}
}
static void close_gate(int gate[2]){CHECK(close(gate[0])==0&&close(gate[1])==0);}
static void recovery(void)
{
    policy(0);event("RECOVERY_CONFIG",0,1,0);int gate[2];CHECK(pipe(gate)==0);
    event("RECOVERY_BEGIN",0,0,RECOVERY_STATUS);pid_t pid=fork();CHECK(pid>=0);if(!pid)child(gate,RECOVERY_STATUS);
    event("RECOVERY_SPAWN",pid,0,RECOVERY_STATUS);event("RECOVERY_RELEASE",pid,1,RECOVERY_STATUS);release(gate,1);
    collected(pid,0,RECOVERY_STATUS,"RECOVERY_WAIT");receive("recovery",&pid,1,RECOVERY_STATUS);
    absent("RECOVERY_ABSENT");close_gate(gate);
}
static void pressure(void)
{
    policy(wave);event("CONFIG",wave,1,0);absent("INITIAL_ABSENT");int gate[2];CHECK(pipe(gate)==0);
    unsigned count=0,failed=0,attempt=0;
    while(failed<FAILURES){CHECK(attempt<CAP);event("FORK_BEGIN",attempt,count,failed);errno=0;pid_t pid=fork();int error=errno;
        if(!pid)child(gate,CHILD_STATUS);
        if(pid>0){CHECK(failed==0);for(unsigned i=0;i<count;++i)CHECK(children[i]!=pid);
            children[count]=pid;event("SPAWN",pid,count,CHILD_STATUS);++count;}
        else{CHECK(pid==-1&&(error==ENOMEM||error==EAGAIN));++failed;event("FORK_FAIL",attempt,error,failed);}
        ++attempt;}
    CHECK(count>=2);event("EXHAUSTED",count,failed,CAP);
    for(unsigned i=0;i<count;++i){int status=-1;CHECK(waitpid(children[i],&status,WNOHANG)==0);event("LIVE",children[i],0,0);}
    int status=-1;CHECK(waitpid(-1,&status,WNOHANG)==0);event("NO_EXTRA",0,0,0);absent("FAILURE_ABSENT");
    event("RELEASE",count,count,CHILD_STATUS);release(gate,count);
    for(unsigned i=0;i<count;++i)collected(children[i],wave!=0,CHILD_STATUS,wave?"ECHILD":"WAIT");
    CHECK(waitpid(-1,&status,WNOHANG)==-1&&errno==ECHILD);event("EMPTY",ECHILD,0,0);
    if(wave!=1)receive("coalesced",children,count,CHILD_STATUS);
    absent("DRAINED");close_gate(gate);recovery();event("WAVE_DONE",count,FAILURES,1);
}
int main(void)
{
    CHECK(thread_syscall4(SYS_gettid,0,0,0,0)==getpid());
    marker("CHILD_PRESSURE_BEGIN arch=%s pid=%ld uid=%lu cap=128 waves=3 failures=3\n",ARCH,(long)getpid(),(unsigned long)getuid());
    for(wave=0;wave<3;++wave)pressure();
    marker("CHILD_PRESSURE_PASS %s waves=3 exhaustion=3 failed_attempts=9 recoveries=3 bytes=128\n",ARCH);return 0;
}
