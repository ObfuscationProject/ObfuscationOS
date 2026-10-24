#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <sys/uio.h>
#include <limits.h>
#include "thread_syscall.h"
#include "poll_signal_raw.h"
#include "pipe_vector_context.h"
/* Six-argument trap and context helpers retain the sealed poll/futex attribution. */
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
#error "Unsupported automatic SIGPIPE profile"
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
enum {cases=14,capacity=4096,mapping_bytes=16384};
static int vector,variant,form,restart,resumed,case_id;
static _Thread_local int actor=-1;
static struct {
 pid_t pid,tid,sibling;uid_t uid;int fd[2];unsigned char *mapping;struct iovec vectors[3];unsigned long args[6];uintptr_t site,resume;
 _Atomic int ready,go,entered,done,handled,usrhandled,sibling_ready,check_sibling,sibling_checked,stop;long result;int error;
} state;
static long operation(void){return vector?SYS_writev:SYS_write;}
static int deferred(void){return case_id>=3&&case_id<=8;}
static int fatal(void){return case_id==0||case_id==4;}
static int blocked(void){return resumed&&case_id<10;}
static __attribute__((noreturn)) void fail(int code)
{char b[]="PIPE_SIGPIPE_FAIL code=000\n";unsigned p=sizeof("PIPE_SIGPIPE_FAIL code=")-1;b[p]='0'+code/100%10;b[p+1]='0'+code/10%10;b[p+2]='0'+code%10;thread_syscall4(SYS_write,1,(uintptr_t)b,sizeof(b)-1,0);thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{char b[1536];va_list ap;va_start(ap,format);int n=vsnprintf(b,sizeof(b),format,ap);va_end(ap);CHECK(n>0&&(size_t)n<sizeof(b),101);CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b,n,0)==n,102);}
static int64_t now(void){struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,103);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void delay(int64_t ns){int64_t t=now();while(now()-t<ns){}}
static void wait_word(_Atomic int *p,int value){int64_t t=now();while(load(p)!=value)CHECK(now()-t<5000000000LL,104);}
#define KEY "arch=%s vector=%d variant=%d form=%d restart=%d resumed=%d case=%d"
#define VALUES PROBE_ARCH,vector,variant,form,restart,resumed,case_id
static void event(const char *tag,int ordinal,long value)
{marker("PIPE_SIGPIPE_%s " KEY " actor=%d ordinal=%d value=%ld\n",tag,VALUES,actor,ordinal,value);}
static long raw(void){
#if defined(__arm__)
 if(form)return poll_signal_thumb(operation(),state.args,0);
#endif
 return poll_signal_raw(operation(),state.args,form);
}
static long invoke(void){return variant?(vector?writev((int)state.args[0],(void *)(uintptr_t)state.args[1],(int)state.args[2]):write((int)state.args[0],(void *)(uintptr_t)state.args[1],state.args[2])):raw();}
static void pending(int pipe_expected,int usr_expected)
{sigset_t p;CHECK(sigpending(&p)==0&&sigismember(&p,SIGPIPE)==pipe_expected&&sigismember(&p,SIGUSR1)==usr_expected,105);event("PENDING",0,pipe_expected+2*usr_expected);}
static void handle(int signal,siginfo_t *info,void *context)
{
 int saved=errno;ucontext_t *c=context;CHECK(actor==0&&thread_syscall4(SYS_gettid,0,0,0,0)==state.tid&&info&&c,201);
 CHECK(info->si_signo==signal&&info->si_errno==0&&info->si_pid==state.pid&&info->si_uid==state.uid,202);
 int inspected=signal==SIGPIPE&&!deferred();CHECK(info->si_code==((case_id==7||signal==SIGUSR1)?SI_TKILL:SI_USER),203);
 CHECK(signal==SIGPIPE||signal==SIGUSR1&&case_id==8,204);
 if(signal==SIGPIPE){CHECK(!load(&state.handled),205);if(inspected){CHECK(context_result(c)==-EPIPE,206);CHECK((uintptr_t)CTX_BUFFER(c)==state.args[1]&&(uintptr_t)CTX_COUNT(c)==state.args[2],207);if(!variant)CHECK((uintptr_t)CTX_PC(c)==state.resume,208);
#if defined(__arm__)
 if(!variant)CHECK(((c->uc_mcontext.arm_cpsr&0x20)!=0)==(form==1),209);
#endif
 }else CHECK(load(&state.done),210);store(&state.handled,1);}else {CHECK(!load(&state.usrhandled)&&load(&state.done)&&load(&state.handled),211);store(&state.usrhandled,1);}
 unsigned long abi=0;
#if defined(__mips__)
 abi=c->uc_mcontext.gregs[7];
#elif defined(__powerpc__)
 abi=c->uc_regs->gregs[38];
#elif defined(__arm__)
 abi=c->uc_mcontext.arm_cpsr;
#endif
 marker("PIPE_SIGPIPE_HANDLE " KEY " actor=0 pid=%ld tid=%ld signal=%d code=%d sender=%ld uid=%lu inspected=%d pc=%lu result=%ld a1=%lu a2=%lu abi=%lu\n",VALUES,(long)state.pid,(long)state.tid,signal,info->si_code,(long)info->si_pid,(unsigned long)info->si_uid,inspected,(unsigned long)(uintptr_t)CTX_PC(c),inspected?context_result(c):0,inspected?(unsigned long)(uintptr_t)CTX_BUFFER(c):0,inspected?(unsigned long)(uintptr_t)CTX_COUNT(c):0,abi);
 if(case_id==9){CHECK(inspected,212);context_success(c,77);event("EDIT",0,77);}event("HANDLER_RETURN",0,signal);errno=saved;
}
static void *sibling(void *unused)
{(void)unused;actor=1;state.sibling=thread_syscall4(SYS_gettid,0,0,0,0);sigset_t mask;CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,106);store(&state.sibling_ready,1);wait_word(&state.check_sibling,1);pending(0,0);event("SIBLING",0,state.sibling);store(&state.sibling_checked,1);wait_word(&state.stop,1);return (void *)(uintptr_t)0x4192;}
static void sibling_proof(void){store(&state.check_sibling,1);wait_word(&state.sibling_checked,1);}
static void *worker(void *unused)
{
 (void)unused;actor=0;state.tid=thread_syscall4(SYS_gettid,0,0,0,0);sigset_t mask;CHECK(sigemptyset(&mask)==0,107);if(deferred())CHECK(sigaddset(&mask,SIGPIPE)==0,108);if(case_id==8)CHECK(sigaddset(&mask,SIGUSR1)==0,109);CHECK(sigprocmask(SIG_SETMASK,&mask,0)==0,110);store(&state.ready,1);wait_word(&state.go,1);
 if(case_id==7||case_id==8){int signal=case_id==7?SIGPIPE:SIGUSR1;event("QUEUE",0,signal);CHECK(thread_syscall4(SYS_tgkill,state.pid,state.tid,signal,0)==0,111);pending(case_id==7,case_id==8);}
 event("ATTEMPT",0,operation());errno=111;store(&state.entered,1);state.result=invoke();state.error=errno;event("RETURN",0,state.result);event("ERRNO",0,state.error);
 int code=case_id==11?EBADF:case_id==12?EFAULT:case_id==13?EAGAIN:EPIPE;long expected=case_id==9?77:case_id==10?0:variant?-1:-code;
 CHECK(state.result==expected&&state.error==(variant&&expected==-1?code:111),112);CHECK(case_id!=0,113);store(&state.done,1);
 if(case_id==6){event("ATTEMPT",1,operation());errno=111;long n=invoke();event("RETURN",1,n);event("ERRNO",1,errno);CHECK(n==(variant?-1:-EPIPE)&&errno==(variant?EPIPE:111),114);}
 if(deferred()){
  pending(1,case_id==8);CHECK(!load(&state.handled)&&!load(&state.usrhandled),115);sibling_proof();
  if(case_id==5){struct sigaction a={0};a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0);CHECK(sigemptyset(&a.sa_mask)==0&&sigaction(SIGPIPE,&a,0)==0,116);event("ACTION_CAUGHT",0,SIGPIPE);}
  event("UNMASK",0,SIGPIPE);CHECK(sigdelset(&mask,SIGPIPE)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,117);CHECK(case_id!=4&&load(&state.handled)==1,118);pending(0,case_id==8);
  if(case_id==8){event("UNMASK",1,SIGUSR1);CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0&&load(&state.usrhandled)==1,119);pending(0,0);}
 }else {pending(0,0);sibling_proof();CHECK(load(&state.handled)==(case_id==1||case_id==9)&&!load(&state.usrhandled),120);}
 event("WORKER_PASS",0,load(&state.handled)+2*load(&state.usrhandled));return (void *)(uintptr_t)0x4191;
}
static void confirm_wait(void)
{
 wait_word(&state.entered,1);
#ifdef PIPE_SIGPIPE_LINUX_REFERENCE
 char path[128];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)state.tid)>0,121);int64_t start=now();int seen=0;while(!seen){char b[384];int fd=open(path,O_RDONLY);CHECK(fd>=0,122);ssize_t n=read(fd,b,sizeof(b)-1);CHECK(n>=0&&close(fd)==0,123);b[n]=0;long nr=-1;unsigned long a[6]={0};if(sscanf(b,"%ld %lx %lx %lx %lx %lx %lx",&nr,a,a+1,a+2,a+3,a+4,a+5)==7){seen=nr==operation();for(unsigned i=0;i<3;++i)seen=seen&&a[i]==state.args[i];}CHECK(!load(&state.done)&&now()-start<5000000000LL,124);}marker("PIPE_SIGPIPE_LINUX_WAIT " KEY " pid=%ld tid=%ld syscall=%ld\n",VALUES,(long)state.pid,(long)state.tid,operation());
#else
 delay(60000000);
#endif
 CHECK(!load(&state.done),125);
}
static void run_case(void)
{
 memset(&state,0,sizeof(state));actor=9;state.pid=getpid();state.uid=getuid();state.site=(uintptr_t)poll_signal_site;state.resume=(uintptr_t)poll_signal_resume;
#if defined(__arm__)
 if(form){state.site=(uintptr_t)poll_signal_thumb_site;state.resume=(uintptr_t)poll_signal_thumb_resume;}
#endif
 sigset_t mask;CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,126);struct sigaction a={0};a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0);CHECK(sigemptyset(&a.sa_mask)==0&&sigaction(SIGUSR1,&a,0)==0,127);if(case_id==0||case_id==4)a.sa_handler=SIG_DFL;else if(case_id==2||case_id==5)a.sa_handler=SIG_IGN;CHECK(sigaction(SIGPIPE,&a,0)==0,128);
 state.mapping=mmap(0,mapping_bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);CHECK(state.mapping!=MAP_FAILED,129);memset(state.mapping,0xa5,mapping_bytes);memset(state.mapping+64,65,13);memset(state.mapping+8192+64,66,19);state.vectors[0]=(struct iovec){(void *)1,0};state.vectors[1]=(struct iovec){state.mapping+64,13};state.vectors[2]=(struct iovec){state.mapping+8192+64,19};
 CHECK(pipe(state.fd)==0,130);
#ifdef PIPE_SIGPIPE_LINUX_REFERENCE
 CHECK(fcntl(state.fd[1],F_SETPIPE_SZ,capacity)==capacity&&fcntl(state.fd[1],F_GETPIPE_SZ)==capacity,131);
#endif
 if(blocked()||case_id==13){unsigned char b[capacity];memset(b,'F',sizeof(b));CHECK(write(state.fd[1],b,sizeof(b))==capacity,132);}
 if(!blocked()&&case_id<12){CHECK(close(state.fd[0])==0,133);state.fd[0]=-1;}
 if(case_id==13){int f=fcntl(state.fd[1],F_GETFL);CHECK(f>=0&&fcntl(state.fd[1],F_SETFL,f|O_NONBLOCK)==0,134);}
 if(case_id==12)CHECK(mprotect(state.mapping,mapping_bytes,PROT_NONE)==0,135);
 if(case_id==10)for(int i=0;i<3;++i)state.vectors[i].iov_len=0;
 state.args[0]=case_id==11?(unsigned long)-1:(unsigned long)state.fd[1];state.args[1]=vector?(uintptr_t)state.vectors:(uintptr_t)state.mapping+64;state.args[2]=vector?3:case_id==10?0:13;state.args[3]=0x1357;
 pthread_t t,other;CHECK(pthread_create(&other,0,sibling,0)==0&&pthread_create(&t,0,worker,0)==0,136);wait_word(&state.ready,1);wait_word(&state.sibling_ready,1);
 marker("PIPE_SIGPIPE_CASE_BEGIN " KEY " pid=%ld tid=%ld sibling=%ld uid=%lu fd=%d readfd=%d input=%lu bytes=%lu payload0=%lu payload1=%lu site=%lu resume=%lu syscall=%ld capacity=4096\n",VALUES,(long)state.pid,(long)state.tid,(long)state.sibling,(unsigned long)state.uid,(int)state.args[0],state.fd[0],state.args[1],state.args[2],(unsigned long)(uintptr_t)(state.mapping+64),(unsigned long)(uintptr_t)(state.mapping+8192+64),(unsigned long)state.site,(unsigned long)state.resume,operation());
 store(&state.go,1);
 if(blocked()){confirm_wait();event("CLOSE",0,state.fd[0]);CHECK(close(state.fd[0])==0,137);state.fd[0]=-1;}
 if(fatal()){delay(5000000000LL);fail(138);}void *result=0;CHECK(pthread_join(t,&result)==0&&result==(void *)(uintptr_t)0x4191,139);store(&state.stop,1);CHECK(pthread_join(other,&result)==0&&result==(void *)(uintptr_t)0x4192,140);
 if(case_id==12)CHECK(mprotect(state.mapping,mapping_bytes,PROT_READ|PROT_WRITE)==0,141);
 for(unsigned i=0;i<mapping_bytes;++i){unsigned char expected=i>=64&&i<77?65:i>=8256&&i<8275?66:0xa5;CHECK(state.mapping[i]==expected,142);}CHECK(state.vectors[0].iov_base==(void *)1&&state.vectors[0].iov_len==0&&state.vectors[1].iov_base==state.mapping+64&&state.vectors[2].iov_base==state.mapping+8256&&state.vectors[1].iov_len==(case_id==10?0:13)&&state.vectors[2].iov_len==(case_id==10?0:19),143);event("BUFFER",0,mapping_bytes);
 if(case_id==13){unsigned char b[capacity];CHECK(read(state.fd[0],b,sizeof(b))==capacity,144);for(unsigned i=0;i<sizeof(b);++i)CHECK(b[i]=='F',145);event("FILL",0,capacity);}
 if(state.fd[0]>=0){int f=fcntl(state.fd[0],F_GETFL);CHECK(f>=0&&fcntl(state.fd[0],F_SETFL,f|O_NONBLOCK)==0,146);unsigned char b;errno=0;CHECK(read(state.fd[0],&b,1)==-1&&errno==EAGAIN,147);event("EMPTY",0,0);CHECK(close(state.fd[0])==0,148);}
 CHECK(close(state.fd[1])==0&&munmap(state.mapping,mapping_bytes)==0,149);marker("PIPE_SIGPIPE_CASE_PASS " KEY "\n",VALUES);
}
int main(void)
{CHECK(__atomic_always_lock_free(sizeof(state.done),&state.done),150);int groups=0,executed=0;for(vector=0;vector<2;++vector)for(variant=0;variant<2;++variant)for(form=0;form<(variant?1:raw_forms);++form)for(restart=0;restart<2;++restart)for(resumed=0;resumed<2;++resumed){++groups;for(case_id=0;case_id<cases;++case_id){pid_t child=fork();CHECK(child>=0,151);if(!child){run_case();_Exit(0);}int status=-1;CHECK(waitpid(child,&status,0)==child,152);CHECK(fatal()?(WIFSIGNALED(status)&&WTERMSIG(status)==SIGPIPE):(WIFEXITED(status)&&WEXITSTATUS(status)==0),153);delay(10000000);marker("PIPE_SIGPIPE_PARENT_PASS " KEY " pid=%ld signal=%d\n",VALUES,(long)child,fatal()?SIGPIPE:0);++executed;}}
#ifdef PIPE_SIGPIPE_LINUX_REFERENCE
 marker("PIPE_SIGPIPE_LINUX_REFERENCE_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,executed);
#else
 marker("PIPE_SIGPIPE_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,executed);
#endif
 return 0;}
