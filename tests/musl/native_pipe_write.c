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
#include "thread_syscall.h"
#include "poll_signal_raw.h"
#include "pipe_write_context.h"
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
#error "Unsupported scalar pipe write profile"
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
enum {variants=2,cases=25,capacity=4096,mapping_bytes=12288};
static int variant,form,restart,case_id,dirty;
static const char *image_path;
static _Thread_local int actor=-1,depth;
static struct {
 pid_t pid,tid;uid_t uid;int pipe[2][2],replacement[2],saved;
 unsigned char *mapping,*input[2];unsigned long count,args[6],nested_args[6];
 uintptr_t site,resume;long result;int error;
 _Atomic int ready,go,entered,done,handled,nested,phase,restore;
} state;
static __attribute__((noreturn)) void fail(int code)
{
 char b[]="PIPE_WRITE_FAIL code=000 variant=0 form=0 restart=0 case=00 actor=0\n";
 unsigned p=sizeof("PIPE_WRITE_FAIL code=")-1;b[p]='0'+code/100%10;b[p+1]='0'+code/10%10;b[p+2]='0'+code%10;
 b[sizeof("PIPE_WRITE_FAIL code=000 variant=")-1]='0'+variant;b[sizeof("PIPE_WRITE_FAIL code=000 variant=0 form=")-1]='0'+form;b[sizeof("PIPE_WRITE_FAIL code=000 variant=0 form=0 restart=")-1]='0'+restart;
 p=sizeof("PIPE_WRITE_FAIL code=000 variant=0 form=0 restart=0 case=")-1;b[p]='0'+case_id/10;b[p+1]='0'+case_id%10;b[sizeof("PIPE_WRITE_FAIL code=000 variant=0 form=0 restart=0 case=00 actor=")-1]='0'+(actor<0?9:actor);
 thread_syscall4(SYS_write,1,(uintptr_t)b,sizeof(b)-1,0);thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{char b[1024];va_list ap;va_start(ap,format);int n=vsnprintf(b,sizeof(b),format,ap);va_end(ap);CHECK(n>0&&(size_t)n<sizeof(b),101);CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b,n,0)==n,102);}
struct line {char bytes[768];unsigned used;};
static void word(struct line *b,const char *s){while(*s){CHECK(b->used+1<sizeof(b->bytes),201);b->bytes[b->used++]=*s++;}}
static void number(struct line *b,const char *key,unsigned long value){char d[24];unsigned n=0;word(b,key);do{d[n++]='0'+value%10;value/=10;}while(value);while(n)b->bytes[b->used++]=d[--n];}
static int64_t now(void){struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,103);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void delay(int64_t ns){int64_t start=now();while(now()-start<ns){}}
static void wait_word(_Atomic int *p,int value){int64_t start=now();while(load(p)!=value)CHECK(now()-start<5000000000LL,104);}
static void event(const char *tag,int ordinal,long value)
{marker("PIPE_WRITE_%s arch=%s variant=%d form=%d restart=%d case=%d actor=%d ordinal=%d value=%ld\n",tag,PROBE_ARCH,variant,form,restart,case_id,actor<0?9:actor,ordinal,value);}
static long raw(unsigned long *args){
#if defined(__arm__)
 if(form)return poll_signal_thumb(SYS_write,args,0);
#endif
 return poll_signal_raw(SYS_write,args,form);
}
static void arguments(unsigned long *a,int fd,void *input,unsigned long count){memset(a,0,6*sizeof(*a));a[0]=fd;a[1]=(uintptr_t)input;a[2]=count;a[3]=0x1357;}
static int caught(void){return case_id==0||case_id==1||case_id==6||case_id==14||case_id==15||case_id==16||case_id==17||case_id==18||case_id==19||case_id==23;}
static int effective_restart(void){return case_id==15?!restart:restart;}
static int immediate(void){return case_id==9||case_id==10||case_id==11||case_id==13;}
static int pending_case(void){return case_id>=8&&case_id<=11;}
static unsigned long transferred(void){return case_id==14?state.count:state.count>capacity?capacity:state.count;}
static void nonblocking(int fd){int flags=fcntl(fd,F_GETFL);CHECK(flags>=0&&fcntl(fd,F_SETFL,flags|O_NONBLOCK)==0,105);}
static void context_marker(const char *tag,ucontext_t *c,int inspected)
{
 struct line b={0};word(&b,tag);word(&b," arch=" PROBE_ARCH);number(&b," variant=",variant);number(&b," form=",form);number(&b," restart=",restart);number(&b," case=",case_id);number(&b," actor=",actor);number(&b," pid=",state.pid);number(&b," tid=",state.tid);number(&b," depth=",depth);number(&b," inspected=",inspected);number(&b," pc=",(uintptr_t)CTX_PC(c));
 if(inspected){number(&b," number=",(uintptr_t)CTX_NUMBER(c));number(&b," result=",(uintptr_t)CTX_RESULT(c));number(&b," a0=",(uintptr_t)CTX_FD(c));number(&b," a1=",(uintptr_t)CTX_BUFFER(c));number(&b," a2=",(uintptr_t)CTX_COUNT(c));number(&b," a3=",(uintptr_t)CTX_TIMEOUT(c));
#if defined(__powerpc__)
 number(&b," cr=",c->uc_regs->gregs[38]);number(&b," diagnostic_result=",c->uc_regs->gregs[43]);number(&b," orig_r3=",c->uc_regs->gregs[34]);
#elif defined(__arm__)
 number(&b," cpsr=",c->uc_mcontext.arm_cpsr);
#endif
 }word(&b,"\n");CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b.bytes,b.used,0)==(long)b.used,202);
}
static void inspect(ucontext_t *c,int again,int nested)
{
 const unsigned long *a=nested?state.nested_args:state.args;
 CHECK((uintptr_t)CTX_BUFFER(c)==a[1]&&(uintptr_t)CTX_COUNT(c)==a[2],203);
 if(!variant||nested){CHECK((uintptr_t)CTX_PC(c)==(again?state.site:state.resume),204);if(again)CHECK((uintptr_t)CTX_TIMEOUT(c)==a[3],205);}
 if(again){CHECK((uintptr_t)CTX_NUMBER(c)==SYS_write&&(uintptr_t)CTX_FD(c)==a[0],206);
#if defined(__powerpc__)
 CHECK((c->uc_regs->gregs[38]&0x10000000u)&&c->uc_regs->gregs[43]==0&&c->uc_regs->gregs[34]==a[0],207);
#endif
 }else CHECK(context_result(c)==-EINTR,208);
#if defined(__arm__)
 if(!variant||nested)CHECK(((c->uc_mcontext.arm_cpsr&0x20)!=0)==(form==1),209);
#endif
}
static __attribute__((noreturn)) void replace_image(void)
{
 char v[16],f[16],r[16],c[16],rd[16],wr[16];CHECK(dirty==1,106);
 snprintf(v,sizeof(v),"%d",variant);snprintf(f,sizeof(f),"%d",form);snprintf(r,sizeof(r),"%d",restart);snprintf(c,sizeof(c),"%d",case_id);snprintf(rd,sizeof(rd),"%d",state.pipe[0][0]);snprintf(wr,sizeof(wr),"%d",state.pipe[0][1]);
 char *args[]={(char *)image_path,"write-replaced",v,f,r,c,rd,wr,0};char *env[]={0};
 CHECK(thread_syscall4(SYS_execve,(uintptr_t)"/bin/no-pipe-write-image",(uintptr_t)args,(uintptr_t)env,0)==-ENOENT,107);event("EXEC_FAILED",0,ENOENT);event("EXEC_COMMIT",0,state.pid);thread_syscall4(SYS_execve,(uintptr_t)image_path,(uintptr_t)args,(uintptr_t)env,0);fail(108);
}
static void handle(int signal,siginfo_t *info,void *context)
{
 int saved=errno;ucontext_t *c=context;CHECK(actor==0&&info&&c&&state.tid==thread_syscall4(SYS_gettid,0,0,0,0),210);CHECK(info->si_signo==signal&&info->si_errno==0&&info->si_code==SI_TKILL&&info->si_pid==state.pid&&info->si_uid==state.uid,211);++depth;
 if(signal==SIGUSR2){CHECK((case_id==16||case_id==17)&&depth==2&&!load(&state.nested),212);if(case_id==17)inspect(c,0,1);context_marker("PIPE_WRITE_NESTED",c,case_id==17);store(&state.nested,1);--depth;errno=saved;return;}
 CHECK(signal==SIGUSR1&&depth==1&&!load(&state.handled),213);if(caught())inspect(c,effective_restart(),0);else CHECK(pending_case()&&load(&state.done),214);context_marker("PIPE_WRITE_HANDLE",c,caught());
 if(case_id==16){event("NEST_SEND",0,SIGUSR2);CHECK(thread_syscall4(SYS_tgkill,state.pid,state.tid,SIGUSR2,0)==0&&load(&state.nested),215);}
 if(case_id==17){event("NEST_ATTEMPT",0,state.pipe[1][1]);store(&state.phase,2);CHECK(raw(state.nested_args)==-EINTR&&load(&state.nested),216);event("NEST_EINTR",0,-EINTR);event("NEST_RETRY",1,state.pipe[1][1]);store(&state.phase,3);CHECK(raw(state.nested_args)==8,217);event("NEST_RETURN",1,8);}
 if(case_id==18&&!variant&&effective_restart()){CTX_PC(c)=state.resume;context_success(c,77);}
 if(case_id==19){context_marker("PIPE_WRITE_THREAD_EXIT",c,caught());store(&state.handled,1);pthread_exit((void *)(uintptr_t)0x2875);fail(218);}
 if(case_id==23){context_marker("PIPE_WRITE_HANDLER_EXEC",c,caught());replace_image();}
 context_marker("PIPE_WRITE_HANDLER_RETURN",c,caught());store(&state.handled,1);--depth;errno=saved;
}
static void attempt_marker(void)
{marker("PIPE_WRITE_ATTEMPT arch=%s variant=%d form=%d restart=%d case=%d actor=0 pid=%ld tid=%ld a0=%lu a1=%lu a2=%lu a3=%lu a4=%lu a5=%lu\n",PROBE_ARCH,variant,form,restart,case_id,(long)state.pid,(long)state.tid,state.args[0],state.args[1],state.args[2],state.args[3],state.args[4],state.args[5]);}
static long invoke(void){return variant?write(state.pipe[0][1],state.input[0],state.count):raw(state.args);}
static void *writer(void *unused)
{
 (void)unused;actor=0;state.tid=thread_syscall4(SYS_gettid,0,0,0,0);sigset_t mask;CHECK(sigemptyset(&mask)==0,109);if(pending_case())CHECK(sigaddset(&mask,SIGUSR1)==0,110);CHECK(sigprocmask(SIG_SETMASK,&mask,0)==0,111);store(&state.ready,1);wait_word(&state.go,1);attempt_marker();errno=111;store(&state.entered,1);state.result=invoke();state.error=errno;event("RETURN",0,state.result);event("ERRNO",0,state.error);
 int code=case_id==3?EFAULT:case_id==10?EAGAIN:case_id==11||case_id==24?EPIPE:EINTR;
 CHECK(state.error==(variant&&state.result==-1?code:111),112);
 if(caught()){
  CHECK(load(&state.handled)==1,113);
  if(!effective_restart()||(case_id==18&&!variant)){CHECK(state.result==(!effective_restart()?(variant?-1:-EINTR):77),114);event("RETRY",1,state.pipe[0][1]);store(&state.phase,1);CHECK(invoke()==(long)transferred(),115);event("RETRY_RETURN",1,transferred());}
  else CHECK(state.result==(long)transferred(),116);
 }else if(case_id==3){CHECK(state.result==(variant?-1:-EFAULT),117);store(&state.phase,1);wait_word(&state.restore,1);event("RETRY",1,state.pipe[0][1]);CHECK(invoke()==(long)state.count,118);event("RETRY_RETURN",1,state.count);}
 else if(case_id==10)CHECK(state.result==(variant?-1:-EAGAIN),119);
 else if(case_id==11||case_id==24)CHECK(state.result==(variant?-1:-EPIPE),120);
 else CHECK(state.result==(long)transferred(),121);
 store(&state.done,1);
 if(pending_case()){sigset_t pending;CHECK(sigpending(&pending)==0&&sigismember(&pending,SIGUSR1)==1&&!load(&state.handled),122);event("PENDING",0,1);event("UNMASK",0,0);CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0&&load(&state.handled)==1,123);}
 return (void *)(uintptr_t)0x2875;
}
static void confirm_wait(int phase)
{
 wait_word(phase?&state.phase:&state.entered,phase?phase:1);
#ifdef PIPE_WRITE_LINUX_REFERENCE
 char path[128];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)state.tid)>0,124);int64_t start=now();int seen=0;while(!seen){char b[384];int fd=open(path,O_RDONLY);CHECK(fd>=0,125);ssize_t n=read(fd,b,sizeof(b)-1);CHECK(n>=0&&close(fd)==0,126);b[n]=0;long nr=-1;unsigned long a[6]={0};if(sscanf(b,"%ld %lx %lx %lx %lx %lx %lx",&nr,a,a+1,a+2,a+3,a+4,a+5)==7){const unsigned long *expected=phase>=2?state.nested_args:state.args;seen=nr==SYS_write;for(unsigned i=0;i<3;++i)seen=seen&&a[i]==expected[i];}CHECK(!load(&state.done)&&now()-start<5000000000LL,127);}marker("PIPE_WRITE_LINUX_WAIT arch=%s variant=%d form=%d restart=%d case=%d actor=0 phase=%d pid=%ld tid=%ld syscall=%d\n",PROBE_ARCH,variant,form,restart,case_id,phase,(long)state.pid,(long)state.tid,SYS_write);
#else
 delay(60000000);
#endif
 CHECK(!load(&state.done),128);
}
static void send_signal(int signal){event("SEND",0,signal);CHECK(thread_syscall4(SYS_tgkill,state.pid,state.tid,signal,0)==0,129);}
static void make_pipe(int *fds,int full)
{
 CHECK(pipe(fds)==0,130);
#ifdef PIPE_WRITE_LINUX_REFERENCE
 CHECK(fcntl(fds[1],F_SETPIPE_SZ,capacity)==capacity&&fcntl(fds[1],F_GETPIPE_SZ)==capacity,131);
#endif
 if(full){unsigned char filler[capacity];memset(filler,'F',sizeof(filler));CHECK(write(fds[1],filler,sizeof(filler))==capacity,132);}
}
static void read_bytes(int fd,unsigned count,unsigned char value)
{unsigned char b[capacity];while(count){unsigned amount=count<capacity?count:capacity;ssize_t n=read(fd,b,amount);CHECK(n>0&&(unsigned)n<=amount,133);for(ssize_t i=0;i<n;++i)CHECK(b[i]==value,134);count-=n;}}
static void drain(int pipe_id,int ordinal,unsigned count)
{event("DRAIN_BEGIN",ordinal,(pipe_id?10000:0)+count);read_bytes(state.pipe[pipe_id][0],count,'F');event("DRAIN_END",ordinal,(pipe_id?10000:0)+count);}
static void payload(int pipe_id,int fd,unsigned count,unsigned char value)
{read_bytes(fd,count,value);marker("PIPE_WRITE_PAYLOAD arch=%s variant=%d form=%d restart=%d case=%d actor=9 pipe=%d bytes=%u value=%u\n",PROBE_ARCH,variant,form,restart,case_id,pipe_id,count,value);}
static void empty(int pipe_id,int fd)
{unsigned char b;nonblocking(fd);errno=0;CHECK(read(fd,&b,1)==-1&&errno==EAGAIN,135);event("EMPTY",pipe_id,fd);}
static void run_case(void)
{
 memset(&state,0,sizeof(state));state.saved=-1;state.pid=getpid();state.uid=getuid();dirty=1;state.count=case_id==0?1:case_id==1||case_id==12?4096:case_id==13||case_id==14?4097:32;
 state.site=(uintptr_t)poll_signal_site;state.resume=(uintptr_t)poll_signal_resume;
#if defined(__arm__)
 if(form){state.site=(uintptr_t)poll_signal_thumb_site;state.resume=(uintptr_t)poll_signal_thumb_resume;}
#endif
 state.mapping=mmap(0,mapping_bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);CHECK(state.mapping!=MAP_FAILED,136);memset(state.mapping,0xa5,mapping_bytes);state.input[0]=state.mapping+64;state.input[1]=state.mapping+capacity+64;memset(state.input[0],'A',state.count);if(case_id==17)memset(state.input[1],'B',8);
 sigset_t mask;CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,137);struct sigaction a={0};a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0);CHECK(sigemptyset(&a.sa_mask)==0&&sigaction(SIGUSR1,&a,0)==0,138);a.sa_flags=SA_SIGINFO;CHECK(sigaction(SIGUSR2,&a,0)==0,139);a.sa_handler=SIG_IGN;CHECK(sigaction(SIGPIPE,&a,0)==0,140);
 if(case_id==7||case_id==20){a.sa_handler=case_id==7?SIG_IGN:SIG_DFL;CHECK(sigaction(SIGUSR1,&a,0)==0,141);}
 make_pipe(state.pipe[0],case_id!=9&&case_id!=13);if(case_id==17)make_pipe(state.pipe[1],1);
 if(case_id==5||case_id==6){make_pipe(state.replacement,0);state.saved=dup(state.pipe[0][1]);CHECK(state.saved>=0,142);}
 if(case_id==10||case_id==13)nonblocking(state.pipe[0][1]);if(case_id==11){CHECK(close(state.pipe[0][0])==0,143);state.pipe[0][0]=-1;}
 arguments(state.args,state.pipe[0][1],state.input[0],state.count);arguments(state.nested_args,state.pipe[1][1],state.input[1],8);
 pthread_t thread;CHECK(pthread_create(&thread,0,writer,0)==0,144);wait_word(&state.ready,1);
 marker("PIPE_WRITE_CASE_BEGIN arch=%s variant=%d form=%d restart=%d case=%d pid=%ld tid=%ld fd=%d readfd=%d replacement=%d replacementread=%d nestedfd=%d nestedread=%d input=%lu nestedinput=%lu count=%lu site=%lu resume=%lu syscall=%d uid=%lu capacity=%d\n",PROBE_ARCH,variant,form,restart,case_id,(long)state.pid,(long)state.tid,state.pipe[0][1],state.pipe[0][0],case_id==5||case_id==6?state.replacement[1]:-1,case_id==5||case_id==6?state.replacement[0]:-1,case_id==17?state.pipe[1][1]:-1,case_id==17?state.pipe[1][0]:-1,(unsigned long)(uintptr_t)state.input[0],case_id==17?(unsigned long)(uintptr_t)state.input[1]:0,state.count,(unsigned long)state.site,(unsigned long)state.resume,SYS_write,(unsigned long)state.uid,capacity);
 if(pending_case())send_signal(SIGUSR1);store(&state.go,1);
 if(!immediate()){
  confirm_wait(0);
  if(case_id==2){event("MUTATE_INPUT",0,'Z');memset(state.input[0],'Z',state.count);}
  if(case_id==4){event("PROTECT_READ",0,0);CHECK(mprotect(state.mapping,mapping_bytes,PROT_READ)==0,145);}
  if(case_id==5||case_id==6){event("REPLACE_FD",0,state.replacement[1]);CHECK(dup2(state.replacement[1],state.pipe[0][1])==state.pipe[0][1],146);}
  if(case_id==3){event("PROTECT_NONE",0,0);CHECK(mprotect(state.mapping,mapping_bytes,PROT_NONE)==0,147);drain(0,0,capacity);wait_word(&state.phase,1);CHECK(mprotect(state.mapping,mapping_bytes,PROT_READ|PROT_WRITE)==0,148);event("RESTORE_INPUT",0,0);store(&state.restore,1);}
  else if(case_id==20){send_signal(SIGUSR1);delay(5000000000LL);fail(149);}
  else if(case_id==21){event("EXIT_GROUP",0,0);thread_syscall4(SYS_exit_group,0,0,0,0);fail(150);}
  else if(case_id==22)replace_image();
  else if(case_id==24){event("CLOSE_READER",0,state.pipe[0][0]);CHECK(close(state.pipe[0][0])==0,151);state.pipe[0][0]=-1;}
  else if(caught()){
   if(case_id==15){event("CHANGE_ACTION",0,!restart);a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(!restart?SA_RESTART:0);CHECK(sigaction(SIGUSR1,&a,0)==0,152);}
   send_signal(SIGUSR1);
   if(case_id==17){confirm_wait(2);send_signal(SIGUSR2);confirm_wait(3);drain(1,0,capacity);}
   if(case_id==23){delay(5000000000LL);fail(153);}wait_word(&state.handled,1);
   if(case_id!=6&&case_id!=19){delay(60000000);CHECK(!load(&state.done),154);drain(0,0,capacity);}
  }else{
   if(case_id==7){send_signal(SIGUSR1);delay(20000000);CHECK(!load(&state.handled)&&!load(&state.done),155);}
   if(case_id==12){drain(0,0,1);delay(60000000);CHECK(!load(&state.done),156);event("ATOMIC_PENDING",0,1);drain(0,1,capacity-1);}else drain(0,0,capacity);
  }
 }
 if(case_id==14){event("PAYLOAD_BEGIN",0,capacity);payload(0,state.pipe[0][0],capacity,'A');}
 void *joined=0;CHECK(pthread_join(thread,&joined)==0&&joined==(void *)(uintptr_t)0x2875,157);actor=9;
 if(case_id==6||case_id==10||case_id==19)drain(0,0,capacity);
 if(case_id!=10&&case_id!=11&&case_id!=19&&case_id!=24)payload(case_id==6?2:0,case_id==6?state.replacement[0]:state.pipe[0][0],case_id==14?1:transferred(),case_id==2?'Z':'A');
 if(case_id==17)payload(1,state.pipe[1][0],8,'B');
 if(state.pipe[0][0]>=0)empty(0,state.pipe[0][0]);if(case_id==17)empty(1,state.pipe[1][0]);if(case_id==5||case_id==6)empty(2,state.replacement[0]);
 if(case_id==4)CHECK(mprotect(state.mapping,mapping_bytes,PROT_READ|PROT_WRITE)==0,158);
 for(unsigned long i=0;i<state.count;++i)CHECK(state.input[0][i]==(case_id==2?'Z':'A'),159);
 CHECK(munmap(state.mapping,mapping_bytes)==0,160);if(state.pipe[0][0]>=0)CHECK(close(state.pipe[0][0])==0,161);CHECK(close(state.pipe[0][1])==0,162);
 if(case_id==17)CHECK(close(state.pipe[1][0])==0&&close(state.pipe[1][1])==0,163);if(case_id==5||case_id==6)CHECK(close(state.saved)==0&&close(state.replacement[0])==0&&close(state.replacement[1])==0,164);
 marker("PIPE_WRITE_CASE_PASS arch=%s variant=%d form=%d restart=%d case=%d\n",PROBE_ARCH,variant,form,restart,case_id);
}
static int replacement(int argc,char **argv)
{
 CHECK(argc==8&&dirty==0&&state.pid==0&&actor==-1&&depth==0,165);variant=atoi(argv[2]);form=atoi(argv[3]);restart=atoi(argv[4]);case_id=atoi(argv[5]);int rd=atoi(argv[6]),wr=atoi(argv[7]);state.pid=getpid();CHECK(thread_syscall4(SYS_gettid,0,0,0,0)==state.pid,166);actor=9;struct sigaction a;CHECK(sigaction(SIGUSR1,0,&a)==0&&a.sa_handler==SIG_DFL,167);event("EXEC_REPLACED",0,state.pid);read_bytes(rd,capacity,'F');empty(0,rd);CHECK(write(wr,"P",1)==1,168);payload(0,rd,1,'P');empty(0,rd);event("EXEC_CHECKED",0,state.pid);CHECK(close(rd)==0&&close(wr)==0,169);return 0;
}
int main(int argc,char **argv)
{
 CHECK(argc==1||argc==8,170);image_path=argv[0];if(argc==8)return replacement(argc,argv);CHECK(__atomic_always_lock_free(sizeof(state.done),&state.done),171);int groups=0;
 for(variant=0;variant<variants;++variant)for(form=0;form<(variant?1:raw_forms);++form)for(restart=0;restart<2;++restart){++groups;
  for(case_id=0;case_id<cases;++case_id){
   pid_t child=fork();CHECK(child>=0,172);if(!child){run_case();_Exit(0);}int status=-1;CHECK(waitpid(child,&status,0)==child,173);CHECK(case_id==20?(WIFSIGNALED(status)&&WTERMSIG(status)==SIGUSR1):(WIFEXITED(status)&&WEXITSTATUS(status)==0),174);delay(20000000);marker("PIPE_WRITE_PARENT_PASS arch=%s variant=%d form=%d restart=%d case=%d pid=%ld signal=%d\n",PROBE_ARCH,variant,form,restart,case_id,(long)child,case_id==20?SIGUSR1:0);
  }
 }
#ifdef PIPE_WRITE_LINUX_REFERENCE
 marker("PIPE_WRITE_LINUX_REFERENCE_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,groups*cases);
#else
 marker("PIPE_WRITE_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,groups*cases);
#endif
 return 0;
}
