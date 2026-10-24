/* Private lineage/leader-cause observations. Kernel wait order is checked separately. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
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
#error "Unsupported child-lineage profile"
#endif
#if defined(__powerpc__) && defined(__clang__)
#define load(p) __c11_atomic_load((p), __ATOMIC_SEQ_CST)
#define store(p,v) __c11_atomic_store((p), (v), __ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p), __ATOMIC_SEQ_CST)
#define store(p,v) __atomic_store_n((p), (v), __ATOMIC_SEQ_CST)
#endif
_Static_assert(sizeof(siginfo_t) == 128, "target siginfo size");
_Static_assert(offsetof(siginfo_t, si_pid) == (sizeof(void *) == 8 ? 16 : 12), "target siginfo union offset");
static int case_id = -1;
static unsigned sequence;
static int gate[2], report[2];
static _Atomic int ready, command, entered, child_pid, peer_tid, peer_clear, leader_clear;
static __attribute__((noreturn)) void fail(unsigned line)
{
    char b[]="CHILD_LINEAGE_FAIL line=0000 case=0\n";unsigned at=sizeof("CHILD_LINEAGE_FAIL line=")-1;
    for(unsigned i=0;i<4;++i){b[at+3-i]='0'+line%10;line/=10;}
    b[sizeof("CHILD_LINEAGE_FAIL line=0000 case=")-1]='0'+(case_id<0?9:case_id);
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
{marker("CHILD_LINEAGE_EVENT arch=%s case=%d seq=%u op=%s a=%ld b=%ld c=%ld\n",ARCH,case_id,sequence++,op,a,b,c);}
static pid_t tid(void){return thread_syscall4(SYS_gettid,0,0,0,0);}
static int64_t now(void)
{struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void deadline(int64_t begin){CHECK(now()-begin<5000000000LL);}
static void await(_Atomic int *word,int value)
{int64_t begin=now();while(load(word)!=value)deadline(begin);}
static sigset_t set(void)
{sigset_t s;CHECK(sigemptyset(&s)==0&&sigaddset(&s,SIGCHLD)==0);return s;}
static int blocked(void)
{sigset_t s;CHECK(sigprocmask(SIG_SETMASK,0,&s)==0);return sigismember(&s,SIGCHLD);}
static int pending(void)
{sigset_t s;CHECK(sigpending(&s)==0);return sigismember(&s,SIGCHLD);}
static void mask(int block)
{sigset_t s=set();CHECK(sigprocmask(block?SIG_BLOCK:SIG_UNBLOCK,&s,0)==0&&blocked()==block);}
static void configure(void)
{
    struct sigaction a={0};a.sa_handler=SIG_DFL;CHECK(sigemptyset(&a.sa_mask)==0&&sigaction(SIGCHLD,&a,0)==0);
    CHECK(sigaction(SIGTERM,&a,0)==0);sigset_t s;CHECK(sigemptyset(&s)==0&&sigprocmask(SIG_SETMASK,&s,0)==0);
    mask(1);event("CONFIG",0,1,0);
}
static void nonblock(int fd)
{int f=fcntl(fd,F_GETFL);CHECK(f>=0&&fcntl(fd,F_SETFL,f|O_NONBLOCK)==0);}
static void read_exact(int fd,void *data,size_t size)
{
    unsigned char *p=data;size_t done=0;int64_t begin=now();
    while(done<size){ssize_t n=read(fd,p+done,size-done);if(n>0)done+=(size_t)n;
        else CHECK(n==-1&&(errno==EAGAIN||errno==EINTR));deadline(begin);}
}
static void write_exact(int fd,const void *data,size_t size)
{CHECK(write(fd,data,size)==(ssize_t)size);}
static void gate_wait(void)
{char c;read_exact(gate[0],&c,1);CHECK(c=='R');}
static void gate_release(void){write_exact(gate[1],"R",1);}
static void pipes(void)
{CHECK(pipe(gate)==0&&pipe(report)==0);nonblock(gate[0]);nonblock(report[0]);}
static void close_pipes(void)
{CHECK(close(gate[0])==0&&close(gate[1])==0&&close(report[0])==0&&close(report[1])==0);}
static int reap(pid_t child,int expected)
{
    int status=0x12345678;int64_t begin=now();
    for(;;){errno=0;pid_t r=waitpid(child,&status,WNOHANG);if(r==child){CHECK(status==expected);return status;}
        CHECK(r==0||(r==-1&&errno==EINTR));deadline(begin);}
}
static void info(const char *via,const siginfo_t *observed,pid_t child,int status)
{
    unsigned char expected[128]={0};int32_t number=SIGCHLD,code=CLD_EXITED;uint32_t pid=child,uid=getuid();
    unsigned offset=sizeof(void *)==8?16:12;memcpy(expected,&number,4);
#if defined(__mips__)
    memcpy(expected+4,&code,4);
#else
    memcpy(expected+8,&code,4);
#endif
    memcpy(expected+offset,&pid,4);memcpy(expected+offset+4,&uid,4);memcpy(expected+offset+8,&status,4);
    CHECK(memcmp(expected,observed,128)==0);char hex[257];const char digits[]="0123456789abcdef";
    for(unsigned i=0;i<128;++i){hex[2*i]=digits[((const unsigned char *)observed)[i]>>4];hex[2*i+1]=digits[((const unsigned char *)observed)[i]&15];}hex[256]=0;
    marker("CHILD_LINEAGE_INFO arch=%s case=%d seq=%u via=%s signal=%d code=1 child=%ld uid=%lu status=%d bytes=128 hex=%s\n",
           ARCH,case_id,sequence++,via,SIGCHLD,(long)child,(unsigned long)getuid(),status,hex);
}
static void receive(pid_t child,int status)
{
    siginfo_t observed;sigset_t wanted=set();struct timespec zero={0};int64_t begin=now();
    for(;;){errno=0;int value=sigtimedwait(&wanted,&observed,&zero);if(value==SIGCHLD)break;
        CHECK(value==-1&&(errno==EAGAIN||errno==EINTR));deadline(begin);}
    info("wait",&observed,child,status);
}
static void empty(void)
{
    CHECK(pending()==0&&blocked()==1);event("PENDING",0,1,0);
    siginfo_t observed;sigset_t wanted=set();struct timespec zero={0};errno=0;
    CHECK(sigtimedwait(&wanted,&observed,&zero)==-1&&errno==EAGAIN);event("ABSENT",EAGAIN,1,0);
}
static void register_peer(void)
{
    pid_t self=tid();CHECK(self!=getpid());store(&peer_tid,self);store(&peer_clear,self);
    CHECK(thread_syscall4(SYS_set_tid_address,(uintptr_t)&peer_clear,0,0,0)==self);
}
static __attribute__((noreturn)) void raw_exit(int value)
{thread_syscall4(SYS_exit,value,0,0,0);fail(__LINE__);}
static void *creator(void *unused)
{
    (void)unused;register_peer();mask(0);pid_t child=fork();CHECK(child>=0);
    if(!child){gate_wait();_Exit(37);}
    store(&child_pid,child);store(&ready,1);await(&command,1);raw_exit(case_id==1?11:0);
}
static void create(void *(*entry)(void *))
{
    pthread_attr_t attr;pthread_t thread;CHECK(pthread_attr_init(&attr)==0);
    CHECK(pthread_attr_setstacksize(&attr,65536)==0&&pthread_attr_setguardsize(&attr,4096)==0);
    CHECK(pthread_create(&thread,&attr,entry,0)==0&&pthread_attr_destroy(&attr)==0);
    /* Threads use raw exit and explicit clear-TID observations. No pthread_join
       or stack reuse is claimed; the isolated scenario's exit_group reclaims it. */
}
static void lineage(void)
{
    configure();pipes();create(creator);await(&ready,1);pid_t child=load(&child_pid),creator_tid=load(&peer_tid);
    event("THREAD",creator_tid,0,1);event("SPAWN",child,creator_tid,37);
    if(case_id==1){store(&command,1);await(&peer_clear,0);event("CREATOR_EXIT",creator_tid,11,0);}
    event("RELEASE",child,0,0);gate_release();if(case_id==1)receive(child,37);
    CHECK(reap(child,37<<8)==(37<<8));event("WAIT",child,37<<8,1);empty();
    if(case_id==0){CHECK(load(&peer_clear)==creator_tid);store(&command,1);await(&peer_clear,0);event("THREAD_RETIRED",creator_tid,0,0);}
    close_pipes();
}
struct group_report {pid_t child,leader,worker;int cleared;};
static void *last_worker(void *unused)
{
    (void)unused;pid_t worker=tid();await(&leader_clear,0);
    struct group_report r={getpid(),getpid(),worker,load(&leader_clear)};write_exact(report[1],&r,sizeof(r));gate_wait();
    if(case_id==2)raw_exit(23);
    if(case_id==3){thread_syscall4(SYS_exit_group,23,0,0,0);fail(__LINE__);}
    CHECK(kill(getpid(),SIGTERM)==0);int64_t begin=now();for(;;)deadline(begin);
}
static void leader_causes(void)
{
    configure();pipes();pid_t child=fork();CHECK(child>=0);
    if(!child){store(&leader_clear,getpid());CHECK(thread_syscall4(SYS_set_tid_address,(uintptr_t)&leader_clear,0,0,0)==getpid());
        create(last_worker);raw_exit(17);}
    event("SPAWN",child,getpid(),0);struct group_report r;read_exact(report[0],&r,sizeof(r));
    CHECK(r.child==child&&r.leader==child&&r.worker>0&&r.worker!=child&&r.cleared==0);
    event("GROUP",child,child,r.worker);event("LEADER_EXIT",child,17,0);
    int status=-1;CHECK(waitpid(child,&status,WNOHANG)==0&&pending()==0);event("LIVE",child,0,0);
    event("RELEASE",child,r.worker,case_id-2);gate_release();receive(child,17);
    int final=case_id==4?SIGTERM:23<<8;CHECK(reap(child,final)==final);event("WAIT",child,final,1);empty();close_pipes();
}
static void *wait_helper(void *unused)
{
    (void)unused;register_peer();CHECK(blocked()==1);store(&ready,1);await(&entered,1);
    /* Scheduling aid only. Acceptance separately requires native ARM < EXIT
       < COMPLETE/RETIRE. An entered flag or elapsed delay does not prove it. */
    int64_t begin=now();while(now()-begin<20000000LL){}
    gate_release();
    if(case_id==6){int status=reap(load(&child_pid),37<<8);write_exact(report[1],&status,sizeof(status));}
    raw_exit(0);
}
static void wait_masks(void)
{
    configure();pipes();pid_t child=fork();CHECK(child>=0);if(!child){gate_wait();_Exit(37);}
    store(&child_pid,child);event("SPAWN",child,getpid(),37);create(wait_helper);await(&ready,1);
    pid_t helper=load(&peer_tid);event("THREAD",helper,1,1);
    if(case_id==5){
        siginfo_t observed;sigset_t wanted=set();struct timespec timeout={2,0};event("WAIT_BEGIN",getpid(),1,1);
        store(&entered,1);errno=0;int value=sigtimedwait(&wanted,&observed,&timeout);int error=errno;
        CHECK(value==SIGCHLD&&error==0&&blocked()==1);event("WAIT_RETURN",value,error,1);info("active-wait",&observed,child,37);
        await(&peer_clear,0);event("THREAD_RETIRED",helper,0,0);CHECK(reap(child,37<<8)==(37<<8));event("WAIT",child,37<<8,1);
    }else{
        sigset_t temporary;CHECK(sigemptyset(&temporary)==0);struct pollfd fd={report[0],POLLIN,0};struct timespec timeout={2,0};
        event("POLL_BEGIN",getpid(),1,0);store(&entered,1);errno=0;int result=ppoll(&fd,1,&timeout,&temporary);
        CHECK(result==1&&fd.revents==POLLIN&&blocked()==1);event("POLL_RETURN",1,1,fd.revents);
        int status;read_exact(report[0],&status,sizeof(status));CHECK(status==(37<<8));event("READ_REAP",child,status,helper);
        errno=0;CHECK(waitpid(child,0,WNOHANG)==-1&&errno==ECHILD);event("ECHILD",child,ECHILD,0);
        await(&peer_clear,0);event("THREAD_RETIRED",helper,0,0);
    }
    empty();close_pipes();
}
int main(void)
{
    sigset_t s;CHECK(sigemptyset(&s)==0&&sigprocmask(SIG_SETMASK,&s,0)==0);
    struct sigaction a={0};a.sa_handler=SIG_DFL;CHECK(sigemptyset(&a.sa_mask)==0&&sigaction(SIGCHLD,&a,0)==0);
    for(case_id=0;case_id<7;++case_id){
        marker("CHILD_LINEAGE_BEGIN arch=%s case=%d parent=%ld\n",ARCH,case_id,(long)getpid());pid_t child=fork();CHECK(child>=0);
        if(!child){sequence=0;CHECK(tid()==getpid()&&pending()==0);
            marker("CHILD_LINEAGE_CASE arch=%s case=%d pid=%ld uid=%lu\n",ARCH,case_id,(long)getpid(),(unsigned long)getuid());
            if(case_id<2)lineage();else if(case_id<5)leader_causes();else wait_masks();
            marker("CHILD_LINEAGE_DONE arch=%s case=%d pid=%ld events=%u\n",ARCH,case_id,(long)getpid(),sequence);
            thread_syscall4(SYS_exit_group,0,0,0,0);fail(__LINE__);}
        CHECK(reap(child,0)==0);marker("CHILD_LINEAGE_REAP arch=%s case=%d parent=%ld child=%ld status=0\n",ARCH,case_id,(long)getpid(),(long)child);
    }
    marker("CHILD_LINEAGE_PASS %s cases=7 creator=1 replacement=1 leader_causes=3 real_blocked=1 ppoll_mask=1 bytes=128\n",ARCH);
    return 0;
}
