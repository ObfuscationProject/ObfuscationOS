#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
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
#include "child_wait_context.h"
/* Exact raw trap/context helpers are attributed to the sealed poll signal guest. */
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
#error "Unsupported child wait profile"
#endif
#if defined(__arm__) || defined(__powerpc__)
enum {raw_forms=2};
#else
enum {raw_forms=1};
#endif
#if defined(__mips__)
enum {mask_bytes=16};
#else
enum {mask_bytes=8};
#endif
#if defined(__powerpc__) && defined(__clang__)
#define load(p) __c11_atomic_load((p),__ATOMIC_SEQ_CST)
#define store(p,v) __c11_atomic_store((p),(v),__ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p),__ATOMIC_SEQ_CST)
#define store(p,v) __atomic_store_n((p),(v),__ATOMIC_SEQ_CST)
#endif
/* wait4 is intentionally absent on RV32; musl uses the waitid WEXITED subset. */
#if defined(__riscv) && __riscv_xlen==32
#define WAIT_NR SYS_waitid
#define WAIT_SIGINFO 1
#else
#define WAIT_NR SYS_wait4
#define WAIT_SIGINFO 0
#endif
enum {variants=2,cases=22};
static int variant,form,restart,case_id,monitor_fd=-1,dirty;
static const char *image_path;
static _Thread_local int actor=-1,depth;
struct worker {pid_t tid;unsigned char *page;unsigned long args[6];long result;int error;_Atomic int ready,go,entered,done,handled,nested,phase;};
static struct {pid_t pid,child[2];uid_t uid;int gate[2][2];struct worker w[2];uintptr_t site,resume;int any,children,workers;_Atomic int complete;} state;
static __attribute__((noreturn)) void fail(int code)
{
 char text[]="CHILD_WAIT_FAIL code=000 variant=0 form=0 restart=0 case=00 actor=0\n";
 unsigned p=sizeof("CHILD_WAIT_FAIL code=")-1;text[p]='0'+code/100%10;text[p+1]='0'+code/10%10;text[p+2]='0'+code%10;
 text[sizeof("CHILD_WAIT_FAIL code=000 variant=")-1]='0'+variant;text[sizeof("CHILD_WAIT_FAIL code=000 variant=0 form=")-1]='0'+form;text[sizeof("CHILD_WAIT_FAIL code=000 variant=0 form=0 restart=")-1]='0'+restart;
 p=sizeof("CHILD_WAIT_FAIL code=000 variant=0 form=0 restart=0 case=")-1;text[p]='0'+case_id/10;text[p+1]='0'+case_id%10;
 text[sizeof("CHILD_WAIT_FAIL code=000 variant=0 form=0 restart=0 case=00 actor=")-1]='0'+(actor<0?9:actor);
 thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0);thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...){char b[1024];va_list ap;va_start(ap,format);int n=vsnprintf(b,sizeof(b),format,ap);va_end(ap);CHECK(n>0&&(size_t)n<sizeof(b),101);CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b,n,0)==n,102);}
struct line {char bytes[768];unsigned used;};
static void word(struct line *b,const char *s){while(*s){CHECK(b->used+1<sizeof(b->bytes),201);b->bytes[b->used++]=*s++;}}
static void number(struct line *b,const char *key,unsigned long value){char d[24];unsigned n=0;word(b,key);do{d[n++]='0'+value%10;value/=10;}while(value);while(n)b->bytes[b->used++]=d[--n];}
static int64_t now(void){struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,103);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void delay(int64_t ns){int64_t start=now();while(now()-start<ns){}}
static void wait_word(_Atomic int *p,int value){int64_t start=now();while(load(p)!=value)CHECK(now()-start<5000000000LL,104);}
static long raw(unsigned long *args){
#if defined(__arm__)
 if(form)return poll_signal_thumb(WAIT_NR,args,0);
#endif
 return poll_signal_raw(WAIT_NR,args,form);
}
static void arguments(unsigned long *a,pid_t selector,void *out,int nohang){memset(a,0,6*sizeof(*a));
#if WAIT_SIGINFO
 a[0]=selector==-1?P_ALL:P_PID;a[1]=selector==-1?0:(unsigned long)selector;a[2]=(uintptr_t)out;a[3]=WEXITED|(nohang?WNOHANG:0);
#else
 a[0]=selector;a[1]=(uintptr_t)out;a[2]=nohang?WNOHANG:0;
#endif
}
static pid_t selector(void){return state.any?-1:state.child[0];}
static long invoke(struct worker *w){return variant?waitpid(case_id==8?state.pid:selector(),(int *)(w->page+64),case_id==7?WNOHANG:0):raw(w->args);}
static int caught(void){return case_id<=2||case_id==10||case_id==11||case_id==12||case_id==13||case_id==17||case_id==21;}
static int effective_restart(void){return case_id==10?!restart:restart;}
static void event(const char *tag,int ordinal,long value)
{marker("CHILD_WAIT_%s arch=%s variant=%d form=%d restart=%d case=%d actor=%d ordinal=%d value=%ld\n",tag,PROBE_ARCH,variant,form,restart,case_id,actor<0?9:actor,ordinal,value);}
static void context_marker(const char *tag,ucontext_t *c,int inspected)
{
 struct line b={0};word(&b,tag);word(&b," arch=" PROBE_ARCH);number(&b," variant=",variant);number(&b," form=",form);number(&b," restart=",restart);number(&b," case=",case_id);number(&b," actor=",actor);number(&b," pid=",state.pid);number(&b," tid=",state.w[actor].tid);number(&b," depth=",depth);number(&b," inspected=",inspected);number(&b," pc=",(uintptr_t)CTX_PC(c));
 if(inspected){number(&b," number=",(uintptr_t)CTX_NUMBER(c));number(&b," result=",(uintptr_t)CTX_RESULT(c));number(&b," a0=",(uintptr_t)CTX_FD(c));number(&b," a1=",(uintptr_t)CTX_BUFFER(c));number(&b," a2=",(uintptr_t)CTX_COUNT(c));number(&b," a3=",(uintptr_t)CTX_TIMEOUT(c));
#if defined(__powerpc__)
 number(&b," cr=",c->uc_regs->gregs[38]);number(&b," diagnostic_result=",c->uc_regs->gregs[43]);number(&b," orig_r3=",c->uc_regs->gregs[34]);
#elif defined(__arm__)
 number(&b," cpsr=",c->uc_mcontext.arm_cpsr);
#endif
 }
 word(&b,"\n");CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b.bytes,b.used,0)==(long)b.used,202);
}
static uid_t expected_uid(void){return WAIT_SIGINFO&&!variant?(state.uid?state.uid:1001):state.uid;}
static void output(struct worker *w,pid_t child,int status,int ordinal)
{
 if(variant||!WAIT_SIGINFO){int v;memcpy(&v,w->page+64,4);CHECK(v==status,105);}
 else{siginfo_t *info=(siginfo_t *)(w->page+64);CHECK(info->si_signo==SIGCHLD&&info->si_errno==0&&info->si_code==CLD_EXITED&&info->si_pid==child&&info->si_uid==expected_uid()&&info->si_status==(status>>8),106);
  unsigned char bytes[128]={0};int values[]={SIGCHLD,0,CLD_EXITED,child,(int)expected_uid(),status>>8};memcpy(bytes,values,sizeof(values));CHECK(memcmp(bytes,info,128)==0,107);}
 for(unsigned i=0;i<4096;++i)if(i<64||i>=64+(variant||!WAIT_SIGINFO?4:128))CHECK(w->page[i]==0xa5,108);
 marker("CHILD_WAIT_OUTPUT arch=%s variant=%d form=%d restart=%d case=%d actor=%d ordinal=%d child=%ld status=%d uid=%lu bytes=%d\n",PROBE_ARCH,variant,form,restart,case_id,actor,ordinal,(long)child,status,(unsigned long)expected_uid(),variant||!WAIT_SIGINFO?4:128);
}
static void reap_raw(struct worker *w,pid_t child,int ordinal)
{
 unsigned long a[6];arguments(a,child,w->page+64,0);event("RETRY",ordinal,child);long v=variant?waitpid(child,(int *)(w->page+64),0):raw(a);CHECK(v==(variant||!WAIT_SIGINFO?child:0),109);output(w,child,(42+(child==state.child[1]))<<8,ordinal);
}
static void inspect(ucontext_t *c,struct worker *w,int again,int nested)
{
 if(variant){if(!again)CHECK(context_result(c)==-EINTR,203);return;}
 CHECK((uintptr_t)CTX_PC(c)==(again?state.site:state.resume),204);
 if(again){CHECK((uintptr_t)CTX_NUMBER(c)==WAIT_NR,205);for(unsigned i=0;i<3;++i){uintptr_t values[]={(uintptr_t)CTX_FD(c),(uintptr_t)CTX_BUFFER(c),(uintptr_t)CTX_COUNT(c)};CHECK(values[i]==w->args[i],206);}CHECK((uintptr_t)CTX_TIMEOUT(c)==w->args[3],207);
#if defined(__powerpc__)
 CHECK((c->uc_regs->gregs[38]&0x10000000u)&&c->uc_regs->gregs[43]==0&&c->uc_regs->gregs[34]==w->args[0],208);
#endif
 }else{CHECK(context_result(c)==-EINTR,209);if(!nested){CHECK((uintptr_t)CTX_BUFFER(c)==w->args[1]&&(uintptr_t)CTX_COUNT(c)==w->args[2],210);}}
#if defined(__arm__)
 CHECK(((c->uc_mcontext.arm_cpsr&0x20)!=0)==(form==1),211);
#endif
}
static __attribute__((noreturn)) void replace_image(void)
{
 char v[16],f[16],r[16],c[16],ch[16],fd[16],mon[16];CHECK(dirty==1,110);
 snprintf(v,sizeof(v),"%d",variant);snprintf(f,sizeof(f),"%d",form);snprintf(r,sizeof(r),"%d",restart);snprintf(c,sizeof(c),"%d",case_id);snprintf(ch,sizeof(ch),"%ld",(long)state.child[0]);snprintf(fd,sizeof(fd),"%d",state.gate[0][1]);snprintf(mon,sizeof(mon),"%d",monitor_fd);
 char *args[]={(char *)image_path,"child-replaced",v,f,r,c,ch,fd,mon,0};char *env[]={0};
 CHECK(thread_syscall4(SYS_execve,(uintptr_t)"/bin/no-child-wait-image",(uintptr_t)args,(uintptr_t)env,0)==-ENOENT,111);event("EXEC_FAILED",0,ENOENT);event("EXEC_COMMIT",0,state.pid);thread_syscall4(SYS_execve,(uintptr_t)image_path,(uintptr_t)args,(uintptr_t)env,0);fail(112);
}
static void handle(int signal,siginfo_t *info,void *context)
{
 int saved_errno=errno;ucontext_t *c=context;CHECK(actor==0&&info&&c&&state.w[0].tid==thread_syscall4(SYS_gettid,0,0,0,0),212);CHECK(info->si_signo==signal&&info->si_errno==0&&info->si_code==SI_TKILL&&info->si_pid==state.pid&&info->si_uid==state.uid,213);++depth;struct worker *w=&state.w[0];
 if(signal==SIGUSR2){CHECK((case_id==11||case_id==12)&&depth==2&&!load(&w->nested),214);if(case_id==12)inspect(c,w,0,1);context_marker("CHILD_WAIT_NESTED",c,case_id==12);store(&w->nested,1);--depth;errno=saved_errno;return;}
 CHECK(signal==SIGUSR1&&depth==1&&!load(&w->handled),215);if(caught())inspect(c,w,effective_restart(),0);else CHECK(case_id>=6&&case_id<=9&&load(&w->done),216);context_marker("CHILD_WAIT_HANDLE",c,caught());
 if(case_id==11){CHECK(thread_syscall4(SYS_tgkill,state.pid,w->tid,SIGUSR2,0)==0&&load(&w->nested),217);}
 if(case_id==12){unsigned long a[6];arguments(a,state.child[1],w->page+256,0);event("NEST_ATTEMPT",0,state.child[1]);store(&w->phase,2);CHECK(raw(a)==-EINTR&&load(&w->nested),218);event("NEST_EINTR",0,-EINTR);store(&w->phase,3);CHECK(raw(a)==(WAIT_SIGINFO?0:state.child[1]),219);if(WAIT_SIGINFO){siginfo_t *i=(siginfo_t *)(w->page+256);CHECK(i->si_pid==state.child[1]&&i->si_status==43&&i->si_uid==expected_uid(),220);}else{int v;memcpy(&v,w->page+256,4);CHECK(v==(43<<8),221);}memset(w->page+256,0xa5,128);event("NEST_REAP",0,state.child[1]);}
 if(case_id==13&&!variant&&effective_restart()){CTX_PC(c)=state.resume;context_success(c,77);}
 if(case_id==17){context_marker("CHILD_WAIT_THREAD_EXIT",c,caught());store(&w->handled,1);pthread_exit((void *)(uintptr_t)0x2875);fail(222);}
 if(case_id==21){context_marker("CHILD_WAIT_HANDLER_EXEC",c,caught());replace_image();}
 context_marker("CHILD_WAIT_HANDLER_RETURN",c,caught());store(&w->handled,1);--depth;errno=saved_errno;
}
static void *waiter(void *opaque)
{
 actor=(int)(uintptr_t)opaque;struct worker *w=&state.w[actor];w->tid=thread_syscall4(SYS_gettid,0,0,0,0);sigset_t mask;CHECK(sigemptyset(&mask)==0,113);if(case_id>=6&&case_id<=9)CHECK(sigaddset(&mask,SIGUSR1)==0,114);CHECK(sigprocmask(SIG_SETMASK,&mask,0)==0,115);store(&w->ready,1);wait_word(&w->go,1);
 marker("CHILD_WAIT_ATTEMPT arch=%s variant=%d form=%d restart=%d case=%d actor=%d pid=%ld tid=%ld a0=%lu a1=%lu a2=%lu a3=%lu a4=%lu a5=%lu\n",PROBE_ARCH,variant,form,restart,case_id,actor,(long)state.pid,(long)w->tid,w->args[0],w->args[1],w->args[2],w->args[3],w->args[4],w->args[5]);errno=111;store(&w->entered,1);w->result=invoke(w);w->error=errno;event("RETURN",0,w->result);CHECK(w->error==(variant&&w->result==-1?case_id==3?EFAULT:case_id==8||case_id==14?ECHILD:EINTR:111),116);
 if(caught()){CHECK(load(&w->handled)==1,117);if(!effective_restart()){CHECK(w->result==(variant?-1:-EINTR),118);reap_raw(w,state.child[0],1);}else if(case_id==13&&!variant){CHECK(w->result==77,119);reap_raw(w,state.child[0],1);}else{CHECK(w->result==(variant||!WAIT_SIGINFO?state.child[0]:0),120);output(w,state.child[0],42<<8,0);}}
 else if(case_id==3){CHECK(w->result==(variant?-1:-EFAULT),121);wait_word(&w->phase,1);reap_raw(w,state.child[0],1);}
 else if(case_id==7){CHECK(w->result==0,122);if(!variant&&WAIT_SIGINFO){unsigned char zeros[128]={0};CHECK(memcmp(w->page+64,zeros,128)==0,123);}else{unsigned char sentinel[4]={0xa5,0xa5,0xa5,0xa5};CHECK(memcmp(w->page+64,sentinel,4)==0,124);}}
 else if(case_id==8){CHECK(w->result==(variant?-1:-ECHILD),125);}
 else if(case_id==14){CHECK(w->result==(variant?-1:-ECHILD)||w->result==(variant||!WAIT_SIGINFO?state.child[0]:0),126);if(w->result>=0)output(w,state.child[0],42<<8,0);}
 else if(case_id==15){pid_t child=variant||!WAIT_SIGINFO?(pid_t)w->result:((siginfo_t *)(w->page+64))->si_pid;CHECK(child==state.child[0]||child==state.child[1],127);output(w,child,(child==state.child[0]?42:43)<<8,0);}
 else{CHECK(w->result==(variant||!WAIT_SIGINFO?state.child[0]:0),128);output(w,state.child[0],42<<8,0);if(case_id==16)reap_raw(w,state.child[1],1);}
 store(&w->done,1);
 if(case_id>=6&&case_id<=9){sigset_t pending;CHECK(sigpending(&pending)==0&&sigismember(&pending,SIGUSR1)==1&&!load(&w->handled),129);event("PENDING",0,1);event("UNMASK",0,0);CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0&&load(&w->handled)==1,130);}
 return (void *)(uintptr_t)0x2875;
}
static void confirm_wait(int who,int phase)
{
 struct worker *w=&state.w[who];wait_word(phase?&w->phase:&w->entered,phase?phase:1);
#ifdef CHILD_WAIT_LINUX_REFERENCE
 char path[128];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)w->tid)>0,131);int64_t start=now();int seen=0;while(!seen){char b[384];int fd=open(path,O_RDONLY);CHECK(fd>=0,132);ssize_t n=read(fd,b,sizeof(b)-1);CHECK(n>=0&&close(fd)==0,133);b[n]=0;long nr=-1;unsigned long a[6]={0};if(sscanf(b,"%ld %lx %lx %lx %lx %lx %lx",&nr,a,a+1,a+2,a+3,a+4,a+5)==7){seen=nr==WAIT_NR;if(!variant&&!phase)for(unsigned i=0;i<4;++i)seen=seen&&a[i]==w->args[i];}CHECK(!load(&w->done)&&now()-start<5000000000LL,134);}marker("CHILD_WAIT_LINUX_WAIT arch=%s variant=%d form=%d restart=%d case=%d actor=%d phase=%d pid=%ld tid=%ld syscall=%d\n",PROBE_ARCH,variant,form,restart,case_id,who,phase,(long)state.pid,(long)w->tid,WAIT_NR);
#else
 delay(60000000);
#endif
 CHECK(!load(&w->done),135);
}
static void send_signal(int signal){event("SEND",0,signal);CHECK(thread_syscall4(SYS_tgkill,state.pid,state.w[0].tid,signal,0)==0,136);}
static void release_child(int which){event("RELEASE",which,state.child[which]);CHECK(write(state.gate[which][1],"R",1)==1,137);}
static void spawn_child(int which)
{
 CHECK(pipe(state.gate[which])==0,138);pid_t child=fork();CHECK(child>=0,139);if(!child){for(int i=0;i<=which;++i)CHECK(close(state.gate[i][1])==0,140);char b;ssize_t n=read(state.gate[which][0],&b,1);CHECK(n==0||(n==1&&b=='R'),141);if(WAIT_SIGINFO&&!variant)CHECK(setuid(expected_uid())==0,181);if(monitor_fd>=0)CHECK(write(monitor_fd,"D",1)==1,142);_Exit(42+which);}state.child[which]=child;CHECK(close(state.gate[which][0])==0,143);
}
static void run_case(void)
{
 memset(&state,0,sizeof(state));state.pid=getpid();state.uid=getuid();state.any=case_id==1||case_id==15||case_id==16;state.children=case_id==12||case_id==15||case_id==16?2:1;state.workers=case_id==14||case_id==15?2:1;dirty=1;
 state.site=(uintptr_t)poll_signal_site;state.resume=(uintptr_t)poll_signal_resume;
#if defined(__arm__)
 if(form){state.site=(uintptr_t)poll_signal_thumb_site;state.resume=(uintptr_t)poll_signal_thumb_resume;}
#endif
 sigset_t empty;CHECK(sigemptyset(&empty)==0&&sigprocmask(SIG_SETMASK,&empty,0)==0,144);
 struct sigaction a={0};a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0);CHECK(sigemptyset(&a.sa_mask)==0&&sigaction(SIGUSR1,&a,0)==0,145);a.sa_flags=SA_SIGINFO;CHECK(sigaction(SIGUSR2,&a,0)==0,146);
 if(case_id==5||case_id==18){a.sa_handler=case_id==5?SIG_IGN:SIG_DFL;CHECK(sigaction(SIGUSR1,&a,0)==0,147);}
 for(int i=0;i<state.children;++i)spawn_child(i);
 pthread_t threads[2];for(int i=0;i<state.workers;++i){struct worker *w=&state.w[i];w->page=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);CHECK(w->page!=MAP_FAILED,148);memset(w->page,0xa5,4096);arguments(w->args,case_id==8?state.pid:selector(),w->page+64,case_id==7);CHECK(pthread_create(threads+i,0,waiter,(void *)(uintptr_t)i)==0,149);wait_word(&w->ready,1);}
 marker("CHILD_WAIT_CASE_BEGIN arch=%s variant=%d form=%d restart=%d case=%d pid=%ld tid0=%ld tid1=%ld child0=%ld child1=%ld any=%d workers=%d children=%d output0=%lu output1=%lu site=%lu resume=%lu syscall=%d siginfo=%d uid=%lu\n",PROBE_ARCH,variant,form,restart,case_id,(long)state.pid,(long)state.w[0].tid,(long)state.w[1].tid,(long)state.child[0],(long)state.child[1],state.any,state.workers,state.children,(unsigned long)(uintptr_t)(state.w[0].page+64),state.workers==2?(unsigned long)(uintptr_t)(state.w[1].page+64):0,(unsigned long)state.site,(unsigned long)state.resume,WAIT_NR,WAIT_SIGINFO,(unsigned long)state.uid);
 if(case_id==9||case_id==16){for(int i=0;i<state.children;++i)release_child(i);delay(60000000);}
 if(case_id>=6&&case_id<=9)send_signal(SIGUSR1);store(&state.w[0].go,1);
 if(case_id!=7&&case_id!=8&&case_id!=9&&case_id!=16){confirm_wait(0,0);if(state.workers==2){store(&state.w[1].go,1);confirm_wait(1,0);}
  if(case_id==2){event("MUTATE_OUTPUT",0,0);memset(state.w[0].page+64,0x5a,variant||!WAIT_SIGINFO?4:128);}
  if(case_id==3){event("PROTECT_OUTPUT",0,0);CHECK(mprotect(state.w[0].page,4096,PROT_READ)==0,150);release_child(0);delay(60000000);CHECK(mprotect(state.w[0].page,4096,PROT_READ|PROT_WRITE)==0,151);store(&state.w[0].phase,1);}
  else if(case_id==18){send_signal(SIGUSR1);delay(5000000000LL);fail(152);}
  else if(case_id==19){event("EXIT_GROUP",0,0);thread_syscall4(SYS_exit_group,0,0,0,0);fail(153);}
  else if(case_id==20)replace_image();
  else if(caught()){
   if(case_id==10){event("CHANGE_ACTION",0,!restart);a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(!restart?SA_RESTART:0);CHECK(sigaction(SIGUSR1,&a,0)==0,154);}
   send_signal(SIGUSR1);
   if(case_id==12){confirm_wait(0,2);send_signal(SIGUSR2);confirm_wait(0,3);release_child(1);}
   if(case_id==21){delay(5000000000LL);fail(155);}wait_word(&state.w[0].handled,1);
   if(case_id!=17){delay(60000000);CHECK(!load(&state.w[0].done),156);}release_child(0);
  }else{if(case_id==5){send_signal(SIGUSR1);delay(20000000);CHECK(!load(&state.w[0].handled)&&!load(&state.w[0].done),157);}release_child(0);if(case_id==15){delay(60000000);release_child(1);}}
 }
 for(int i=0;i<state.workers;++i){void *joined=0;CHECK(pthread_join(threads[i],&joined)==0&&joined==(void *)(uintptr_t)0x2875,158);}
 actor=9;if(case_id==7||case_id==8){release_child(0);int status;CHECK(waitpid(state.child[0],&status,0)==state.child[0]&&status==(42<<8),159);event("MAIN_REAP",0,state.child[0]);}
 if(case_id==17){int status;CHECK(waitpid(state.child[0],&status,0)==state.child[0]&&status==(42<<8),160);event("MAIN_REAP",0,state.child[0]);}
 if(case_id==14)CHECK((state.w[0].result<0)!=(state.w[1].result<0),161);
 for(int i=0;i<state.workers;++i)CHECK(munmap(state.w[i].page,4096)==0,162);for(int i=0;i<state.children;++i)CHECK(close(state.gate[i][1])==0,163);
 marker("CHILD_WAIT_CASE_PASS arch=%s variant=%d form=%d restart=%d case=%d\n",PROBE_ARCH,variant,form,restart,case_id);
}
static int replacement(int argc,char **argv)
{
 CHECK(argc==9&&dirty==0&&state.pid==0,164);variant=atoi(argv[2]);form=atoi(argv[3]);restart=atoi(argv[4]);case_id=atoi(argv[5]);pid_t child=atoi(argv[6]);int fd=atoi(argv[7]);monitor_fd=atoi(argv[8]);state.pid=getpid();CHECK(thread_syscall4(SYS_gettid,0,0,0,0)==state.pid,165);actor=9;struct sigaction a;CHECK(sigaction(SIGUSR1,0,&a)==0&&a.sa_handler==SIG_DFL,166);event("EXEC_REPLACED",0,child);CHECK(write(fd,"R",1)==1,167);int status=0;CHECK(waitpid(child,&status,0)==child&&status==(42<<8),168);event("EXEC_REAP",0,child);CHECK(close(fd)==0,169);return 0;
}
int main(int argc,char **argv)
{
 CHECK(argc==1||argc==9,170);image_path=argv[0];if(argc==9)return replacement(argc,argv);CHECK(__atomic_always_lock_free(sizeof(state.w[0].done),&state.w[0].done),171);int groups=0;
 for(variant=0;variant<variants;++variant)for(form=0;form<(variant?1:raw_forms);++form)for(restart=0;restart<2;++restart){++groups;
  for(case_id=0;case_id<cases;++case_id){
#ifdef CHILD_WAIT_LINUX_REFERENCE
  /* Linux consumes the child before wait4 output EFAULT; native early admission retains it. */
  if(case_id==3)continue;
#else
  /* RV32 musl copies its private waitid siginfo into status in userspace after reaping. */
  if(WAIT_SIGINFO&&variant&&case_id==3){marker("CHILD_WAIT_CASE_SKIP arch=%s variant=%d form=%d restart=%d case=%d reason=musl-user-status-copy\n",PROBE_ARCH,variant,form,restart,case_id);continue;}
#endif
  int monitor[2];CHECK(pipe(monitor)==0,172);pid_t child=fork();CHECK(child>=0,173);if(!child){CHECK(close(monitor[0])==0,174);monitor_fd=monitor[1];run_case();_Exit(0);}CHECK(close(monitor[1])==0,175);int status=-1;CHECK(waitpid(child,&status,0)==child,176);CHECK(case_id==18?(WIFSIGNALED(status)&&WTERMSIG(status)==SIGUSR1):(WIFEXITED(status)&&WEXITSTATUS(status)==0),177);char bytes[4];int n=0;ssize_t got;while((got=read(monitor[0],bytes+n,sizeof(bytes)-n))>0)n+=got;CHECK(got==0&&n==(case_id==12||case_id==15||case_id==16?2:1),178);for(int i=0;i<n;++i)CHECK(bytes[i]=='D',179);CHECK(close(monitor[0])==0,180);delay(20000000);marker("CHILD_WAIT_PARENT_PASS arch=%s variant=%d form=%d restart=%d case=%d pid=%ld signal=%d descendants=%d\n",PROBE_ARCH,variant,form,restart,case_id,(long)child,case_id==18?SIGUSR1:0,n);}
 }
#ifdef CHILD_WAIT_LINUX_REFERENCE
 marker("CHILD_WAIT_LINUX_REFERENCE_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,groups*(cases-1));
#else
 marker("CHILD_WAIT_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,groups*cases-(WAIT_SIGINFO?2:0));
#endif
 return 0;
}
