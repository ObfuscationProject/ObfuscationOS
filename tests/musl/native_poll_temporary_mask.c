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
#error "Unsupported temporary-mask profile"
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
struct lane {unsigned long number;int select,wide;};
static const struct lane lanes[]={
#ifdef SYS_ppoll
 {SYS_ppoll,0,sizeof(long)==8},
#endif
#if defined(SYS_ppoll_time64) && (!defined(SYS_ppoll) || SYS_ppoll_time64!=SYS_ppoll)
 {SYS_ppoll_time64,0,1},
#endif
#ifdef SYS_pselect6
 {SYS_pselect6,1,sizeof(long)==8},
#endif
#if defined(SYS_pselect6_time64) && (!defined(SYS_pselect6) || SYS_pselect6_time64!=SYS_pselect6)
 {SYS_pselect6_time64,1,1},
#endif
};
enum {variants=sizeof(lanes)/sizeof(lanes[0]),normal_cases=21,cases=25};
struct mask {unsigned long words[mask_bytes/sizeof(long)];};
static int variant,form,case_id,restart;
static _Thread_local int role,depth;
static struct {
 unsigned char *output_page,*timeout_page,*mask_page;
 struct pollfd *fds;fd_set *reads;struct mask *temporary,original,clean_temporary;
 unsigned long args[6],pair[2];int descriptors[2],kind;long result;int error;
 uintptr_t site,resume;pid_t pid,target;uid_t uid;int64_t duration,elapsed;
 _Atomic int ready,go,entered,done,handled,nested,phase;
} state;
static __attribute__((noreturn)) void fail(int code)
{
 char text[]="POLL_TEMP_FAIL code=000 variant=0 form=0 restart=0 case=00 role=0\n";
 unsigned p=sizeof("POLL_TEMP_FAIL code=")-1;text[p]='0'+code/100%10;text[p+1]='0'+code/10%10;text[p+2]='0'+code%10;
 text[sizeof("POLL_TEMP_FAIL code=000 variant=")-1]='0'+variant;
 text[sizeof("POLL_TEMP_FAIL code=000 variant=0 form=")-1]='0'+form;
 text[sizeof("POLL_TEMP_FAIL code=000 variant=0 form=0 restart=")-1]='0'+restart;
 p=sizeof("POLL_TEMP_FAIL code=000 variant=0 form=0 restart=0 case=")-1;text[p]='0'+case_id/10;text[p+1]='0'+case_id%10;
 text[sizeof("POLL_TEMP_FAIL code=000 variant=0 form=0 restart=0 case=00 role=")-1]='0'+role;
 thread_syscall4(SYS_write,1,(uintptr_t)text,sizeof(text)-1,0);thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{
 char text[1024];va_list ap;va_start(ap,format);int n=vsnprintf(text,sizeof(text),format,ap);va_end(ap);
 CHECK(n>0&&(size_t)n<sizeof(text),101);CHECK(thread_syscall4(SYS_write,1,(uintptr_t)text,n,0)==n,102);
}
struct line {char bytes[768];unsigned used;};
static void word(struct line *b,const char *s){while(*s){CHECK(b->used+1<sizeof(b->bytes),201);b->bytes[b->used++]=*s++;}}
static void number(struct line *b,const char *key,unsigned long value){char digits[24];unsigned n=0;word(b,key);do{digits[n++]='0'+value%10;value/=10;}while(value);while(n){char x[]={digits[--n],0};word(b,x);}}
static void bit(struct mask *m,int signal,int set){unsigned n=(signal-1)/(8*sizeof(long)),b=(signal-1)%(8*sizeof(long));if(n<mask_bytes/sizeof(long)){if(set)m->words[n]|=1ul<<b;else m->words[n]&=~(1ul<<b);}}
static unsigned signature(const struct mask *m){const int signals[]={SIGUSR1,SIGUSR2,SIGTERM,SIGHUP,SIGKILL,SIGSTOP,62,63,99,100};unsigned out=0;for(unsigned i=0;i<10;++i){unsigned n=(signals[i]-1)/(8*sizeof(long)),b=(signals[i]-1)%(8*sizeof(long));if(n<mask_bytes/sizeof(long)&&((m->words[n]>>b)&1))out|=1u<<i;}return out;}
static struct mask active(void){struct mask m={0};CHECK(thread_syscall4(SYS_rt_sigprocmask,SIG_SETMASK,0,(uintptr_t)&m,mask_bytes)==0,202);return m;}
static void replace(const struct mask *m){CHECK(thread_syscall4(SYS_rt_sigprocmask,SIG_SETMASK,(uintptr_t)m,0,mask_bytes)==0,203);}
static void same(struct mask a,struct mask b,int code){CHECK(memcmp(&a,&b,sizeof(a))==0,code);}
static int64_t now(void){struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,103);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void wait_word(_Atomic int *p,int value){int64_t start=now();while(load(p)!=value)CHECK(now()-start<5000000000LL,104);}
static void delay(int64_t ns){int64_t start=now();while(now()-start<ns){}}
static long raw(const unsigned long *args){
#if defined(__arm__)
 if(form)return poll_signal_thumb(lanes[variant].number,args,0);
#endif
 return poll_signal_raw(lanes[variant].number,args,form);
}
static void time_value(void *p,int64_t ns){if(lanes[variant].wide){int64_t t[2]={ns/1000000000,ns%1000000000};memcpy(p,t,16);}else{int32_t t[2]={ns/1000000000,ns%1000000000};memcpy(p,t,8);}}
static int64_t remaining(void){int64_t s,n;if(lanes[variant].wide){int64_t t[2];memcpy(t,state.timeout_page+64,16);s=t[0];n=t[1];}else{int32_t t[2];memcpy(t,state.timeout_page+64,8);s=t[0];n=t[1];}CHECK(s>=0&&n>=0&&n<1000000000,105);return s*1000000000+n;}
static void handler_marker(const char *tag,ucontext_t *c,struct mask saved,struct mask current)
{
 struct line b={0};word(&b,tag);word(&b," arch=" PROBE_ARCH);number(&b," variant=",variant);number(&b," form=",form);number(&b," restart=",restart);number(&b," case=",case_id);number(&b," pid=",state.pid);number(&b," tid=",state.target);number(&b," depth=",depth);number(&b," pc=",(uintptr_t)CTX_PC(c));number(&b," result=",(uintptr_t)CTX_RESULT(c));number(&b," saved=",signature(&saved));number(&b," active=",signature(&current));
#if defined(__mips__)
 number(&b," a3=",c->uc_mcontext.gregs[7]);
#elif defined(__powerpc__)
 number(&b," cr=",c->uc_regs->gregs[38]);number(&b," diagnostic_result=",c->uc_regs->gregs[43]);
#elif defined(__arm__)
 number(&b," cpsr=",c->uc_mcontext.arm_cpsr);
#endif
 word(&b,"\n");CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b.bytes,b.used,0)==(long)b.used,204);
}
static void handle(int signal,siginfo_t *info,void *context)
{
 int saved_errno=errno;ucontext_t *c=context;struct mask saved,current=active(),expected;
 CHECK(role==1&&info&&c&&thread_syscall4(SYS_gettid,0,0,0,0)==state.target,205);
 CHECK(info->si_signo==signal&&info->si_errno==0&&info->si_code==SI_TKILL&&info->si_pid==state.pid&&info->si_uid==state.uid,206);
 ++depth;memcpy(&saved,&c->uc_sigmask,sizeof(saved));
#if defined(__powerpc__)
 CHECK(c->uc_regs!=0,207);
#endif
 expected=state.clean_temporary;bit(&expected,SIGUSR1,case_id!=20);if(case_id==20)bit(&expected,SIGHUP,1);
 if(signal==SIGUSR2){
  CHECK(case_id==16&&depth==2&&!load(&state.nested),208);same(saved,expected,209);
  struct mask inner={0};bit(&inner,SIGTERM,1);bit(&inner,62,1);bit(&inner,99,1);bit(&inner,SIGUSR2,1);same(current,inner,210);
  CHECK(context_result(c)==-EINTR&&(uintptr_t)CTX_PC(c)==state.resume,211);handler_marker("POLL_TEMP_NESTED",c,saved,current);store(&state.nested,1);--depth;errno=saved_errno;return;
 }
 CHECK(signal==SIGUSR1&&depth==1&&!load(&state.handled),212);
 /* A poll output-copy fault restores immediately, before handler selection. */
 if(case_id==3&&!state.kind){expected=state.original;bit(&expected,SIGUSR1,1);}
 same(saved,state.original,213);same(current,expected,214);
 CHECK(context_result(c)==-(case_id==3&&!state.kind?EFAULT:EINTR)&&(uintptr_t)CTX_PC(c)==state.resume,215);
#if defined(__arm__)
 CHECK(((c->uc_mcontext.arm_cpsr&0x20)!=0)==(form==1),216);
#endif
 handler_marker("POLL_TEMP_HANDLE",c,saved,current);
 if(case_id==23){handler_marker("POLL_TEMP_HANDLER_EXIT",c,saved,current);thread_syscall4(SYS_exit_group,0,0,0,0);fail(217);}
 if(case_id==24){store(&state.handled,1);pthread_exit((void *)(uintptr_t)0x2875);fail(218);}
 if(case_id==16){
  struct mask inner={0};bit(&inner,SIGTERM,1);bit(&inner,62,1);bit(&inner,99,1);
  unsigned long pair[2]={(uintptr_t)&inner,mask_bytes},args[6];memcpy(args,state.args,sizeof(args));
  unsigned long timeout[4]={0};time_value(timeout,500000000);if(state.kind){args[4]=(uintptr_t)timeout;args[5]=(uintptr_t)pair;}else{args[2]=(uintptr_t)timeout;args[3]=(uintptr_t)&inner;}
  handler_marker("POLL_TEMP_NEST_BEGIN",c,saved,current);store(&state.phase,2);CHECK(raw(args)==-EINTR&&load(&state.nested)==1,219);same(active(),current,220);handler_marker("POLL_TEMP_NEST_RETURN",c,saved,current);
 }
 if(case_id==17){bit(&saved,SIGTERM,0);bit(&saved,SIGHUP,1);memcpy(&c->uc_sigmask,&saved,sizeof(saved));}
 handler_marker("POLL_TEMP_HANDLER_RETURN",c,saved,current);store(&state.handled,1);--depth;errno=saved_errno;
}
static void *waiter(void *unused)
{
 (void)unused;role=1;state.target=thread_syscall4(SYS_gettid,0,0,0,0);CHECK(state.target>0&&state.target!=state.pid,106);replace(&state.original);store(&state.ready,1);wait_word(&state.go,1);
 marker("POLL_TEMP_ATTEMPT arch=%s variant=%d form=%d restart=%d case=%d pid=%ld tid=%ld a0=%lu a1=%lu a2=%lu a3=%lu a4=%lu a5=%lu\n",PROBE_ARCH,variant,form,restart,case_id,(long)state.pid,(long)state.target,state.args[0],state.args[1],state.args[2],state.args[3],state.args[4],state.args[5]);
 errno=111;int64_t start=now();store(&state.entered,1);state.result=raw(state.args);state.error=errno;state.elapsed=now()-start;
 struct mask expected=state.original,current=active();if(case_id==17){bit(&expected,SIGTERM,0);bit(&expected,SIGHUP,1);}same(current,expected,107);
 marker("POLL_TEMP_RETURN arch=%s variant=%d form=%d restart=%d case=%d result=%ld error=%d restored=%u elapsed=%llu remaining=%lld\n",PROBE_ARCH,variant,form,restart,case_id,state.result,state.error,signature(&current),(unsigned long long)state.elapsed,(long long)remaining());
 if(case_id==14){struct mask pending={0};CHECK(thread_syscall4(SYS_rt_sigpending,(uintptr_t)&pending,mask_bytes,0,0)==0,108);CHECK(signature(&pending)==1&&!load(&state.handled),109);marker("POLL_TEMP_PENDING arch=%s variant=%d form=%d restart=%d case=%d mask=%u\n",PROBE_ARCH,variant,form,restart,case_id,signature(&pending));}
 store(&state.done,1);return (void *)(uintptr_t)0x2875;
}
static void confirm_wait(int nested)
{
 if(nested)wait_word(&state.phase,2);else wait_word(&state.entered,1);
#ifdef POLL_TEMP_LINUX_REFERENCE
 char path[128];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)state.target)>0,110);int64_t start=now();int observed=0;
 while(!observed){char buffer[384];int fd=open(path,O_RDONLY);CHECK(fd>=0,111);ssize_t n=read(fd,buffer,sizeof(buffer)-1);CHECK(n>=0&&close(fd)==0,112);buffer[n]=0;
 long nr=-1;unsigned long a[6]={0};if(sscanf(buffer,"%ld %lx %lx %lx %lx %lx %lx",&nr,a,a+1,a+2,a+3,a+4,a+5)==7){observed=nr==(long)lanes[variant].number;if(!nested)for(unsigned i=0;i<6;++i)observed=observed&&a[i]==state.args[i];}
 CHECK(!load(&state.done)&&now()-start<5000000000LL,113);}
 marker("POLL_TEMP_LINUX_WAIT arch=%s variant=%d form=%d restart=%d case=%d nested=%d pid=%ld tid=%ld syscall=%lu\n",PROBE_ARCH,variant,form,restart,case_id,nested,(long)state.pid,(long)state.target,lanes[variant].number);
#else
 delay(60000000);
#endif
 CHECK(!load(&state.done),114);
}
static void send_signal(int signal){marker("POLL_TEMP_SEND arch=%s variant=%d form=%d restart=%d case=%d pid=%ld tid=%ld signal=%d\n",PROBE_ARCH,variant,form,restart,case_id,(long)state.pid,(long)state.target,signal);CHECK(thread_syscall4(SYS_tgkill,state.pid,state.target,signal,0)==0,115);}
static void action_marker(const char *action){marker("POLL_TEMP_ACTION arch=%s variant=%d form=%d restart=%d case=%d action=%s\n",PROBE_ARCH,variant,form,restart,case_id,action);}
static int caught(void){return case_id<=3||case_id==15||case_id==16||case_id==17||case_id==19||case_id==20||case_id>=23;}
static void run_case(void)
{
 memset(&state,0,sizeof(state));state.pid=getpid();state.uid=getuid();state.kind=lanes[variant].select;state.duration=case_id==6?0:case_id==5||case_id==18?160000000:500000000;
 state.output_page=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);state.timeout_page=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);state.mask_page=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);CHECK(state.output_page!=MAP_FAILED&&state.timeout_page!=MAP_FAILED&&state.mask_page!=MAP_FAILED,116);
 state.fds=(struct pollfd *)(state.output_page+64);state.reads=(fd_set *)(state.output_page+64);state.temporary=(struct mask *)(state.mask_page+64);CHECK(pipe(state.descriptors)==0&&state.descriptors[0]>=0&&state.descriptors[0]<31,117);
 if(state.kind){FD_ZERO(state.reads);FD_SET(state.descriptors[0],state.reads);}else state.fds[0]=(struct pollfd){state.descriptors[0],POLLIN,0x3333};
 bit(&state.original,SIGTERM,1);bit(&state.original,63,1);bit(&state.original,100,1);if(case_id!=1&&case_id!=3)bit(&state.original,SIGUSR1,1);
 bit(&state.clean_temporary,SIGUSR2,1);bit(&state.clean_temporary,62,1);bit(&state.clean_temporary,99,1);if(case_id==14)bit(&state.clean_temporary,SIGUSR1,1);
 *state.temporary=state.clean_temporary;bit(state.temporary,SIGKILL,1);bit(state.temporary,SIGSTOP,1);time_value(state.timeout_page+64,state.duration);
 state.site=(uintptr_t)poll_signal_site;state.resume=(uintptr_t)poll_signal_resume;
#if defined(__arm__)
 if(form){state.site=(uintptr_t)poll_signal_thumb_site;state.resume=(uintptr_t)poll_signal_thumb_resume;}
#endif
 state.pair[0]=(uintptr_t)state.temporary;state.pair[1]=mask_bytes;
 if(state.kind){state.args[0]=state.descriptors[0]+1;state.args[1]=(uintptr_t)state.reads;state.args[4]=(uintptr_t)(state.timeout_page+64);state.args[5]=(uintptr_t)state.pair;}
 else{state.args[0]=(uintptr_t)state.fds;state.args[1]=1;state.args[2]=(uintptr_t)(state.timeout_page+64);state.args[3]=(uintptr_t)state.temporary;state.args[4]=mask_bytes;}
 if(case_id==8){if(state.kind){FD_ZERO(state.reads);FD_SET(30,state.reads);state.args[0]=31;}else state.fds[0].fd=30;}
 if(case_id==9){if(state.kind)state.pair[0]=1;else state.args[3]=1;}
 if(case_id==10){if(state.kind)state.pair[1]=mask_bytes-1;else state.args[4]=mask_bytes-1;}
 if(case_id==11){if(state.kind){state.args[4]=1;state.pair[1]=mask_bytes-1;}else{state.args[2]=1;state.args[4]=mask_bytes-1;}}
 if(case_id==12){if(state.kind)state.args[1]=1;else state.args[0]=1;}
 struct sigaction a={0};a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0)|(case_id==20?SA_NODEFER:0);CHECK(sigemptyset(&a.sa_mask)==0,118);if(case_id==20)CHECK(sigaddset(&a.sa_mask,SIGHUP)==0,119);CHECK(sigaction(SIGUSR1,&a,0)==0&&sigaction(SIGUSR2,&a,0)==0,120);
 if(case_id==13||case_id==21){a.sa_handler=case_id==13?SIG_IGN:SIG_DFL;CHECK(sigaction(SIGUSR1,&a,0)==0,121);}
 struct mask empty={0};replace(&empty);if(case_id==7)CHECK(write(state.descriptors[1],"R",1)==1,122);
 if(case_id==4)CHECK(fcntl(state.descriptors[0],F_SETFL,O_NONBLOCK)==0,123);
 pthread_t thread;CHECK(pthread_create(&thread,0,waiter,0)==0,124);wait_word(&state.ready,1);
 marker("POLL_TEMP_CASE_BEGIN arch=%s variant=%d form=%d restart=%d case=%d pid=%ld tid=%ld syscall=%lu kind=%s duration=%llu site=%lu resume=%lu fd=%d output=%lu timeout=%lu maskptr=%lu pair=%lu width=%d bytes=%d original=%u temporary=%u\n",PROBE_ARCH,variant,form,restart,case_id,(long)state.pid,(long)state.target,lanes[variant].number,state.kind?"select":"poll",(unsigned long long)state.duration,(unsigned long)state.site,(unsigned long)state.resume,state.descriptors[0],(unsigned long)(uintptr_t)(state.output_page+64),(unsigned long)(uintptr_t)(state.timeout_page+64),(unsigned long)(uintptr_t)state.temporary,(unsigned long)(uintptr_t)state.pair,lanes[variant].wide?64:32,mask_bytes,signature(&state.original),signature(&state.clean_temporary));
 if(case_id==15)send_signal(SIGUSR1);store(&state.go,1);
 if(case_id<=5||case_id==13||case_id==14||case_id>=16){
  confirm_wait(0);
  if(case_id==2){action_marker("mutate-mask");*state.temporary=state.original;}
  if(case_id==3){action_marker("protect-output");CHECK(mprotect(state.output_page,4096,PROT_READ)==0,125);}
  if(case_id==19){action_marker("protect-mask");CHECK(mprotect(state.mask_page,4096,PROT_NONE)==0,126);}
  if(caught()){send_signal(SIGUSR1);if(case_id==16){confirm_wait(1);send_signal(SIGUSR2);}if(case_id==23){delay(5000000000LL);fail(127);}}
  else if(case_id==21){send_signal(SIGUSR1);delay(5000000000LL);fail(128);}
  else if(case_id==22){action_marker("exit-group");thread_syscall4(SYS_exit_group,0,0,0,0);fail(129);}
  else if(case_id==18){action_marker("mutate-timeout");time_value(state.timeout_page+64,2000000000);}
  else if(case_id!=5){if(case_id==13||case_id==14){send_signal(SIGUSR1);delay(20000000);CHECK(!load(&state.handled)&&!load(&state.done),130);}action_marker("ready");CHECK(write(state.descriptors[1],"R",1)==1,131);}
 }
 void *joined=0;CHECK(pthread_join(thread,&joined)==0&&joined==(void *)(uintptr_t)0x2875,132);
 if(case_id!=24){CHECK(load(&state.done)==1,133);long expected=caught()?-(case_id==3&&!state.kind?EFAULT:EINTR):case_id==5||case_id==6||case_id==18?0:case_id==8&&state.kind?-EBADF:case_id==9||case_id==11||case_id==12?-EFAULT:case_id==10?-EINVAL:1;CHECK(state.result==expected&&state.error==111,134);
 CHECK(load(&state.handled)==caught()&&load(&state.nested)==(case_id==16),135);if(case_id==5||case_id==18)CHECK(state.elapsed>=state.duration&&state.elapsed<state.duration+1000000000&&remaining()==0,136);
 if(case_id==8&&!state.kind)CHECK(state.fds[0].revents==POLLNVAL,137);
 }else CHECK(load(&state.handled)==1&&!load(&state.done),138);
 CHECK(close(state.descriptors[0])==0&&close(state.descriptors[1])==0,139);CHECK(munmap(state.output_page,4096)==0&&munmap(state.timeout_page,4096)==0&&munmap(state.mask_page,4096)==0,140);
 marker("POLL_TEMP_CASE_PASS arch=%s variant=%d form=%d restart=%d case=%d\n",PROBE_ARCH,variant,form,restart,case_id);
}
int main(void)
{
 CHECK(__atomic_always_lock_free(sizeof(state.handled),&state.handled),141);int groups=0;
 for(variant=0;variant<variants;++variant)for(form=0;form<raw_forms;++form)for(restart=0;restart<2;++restart){++groups;
  for(int batch=0;batch<4;++batch){pid_t child=fork();CHECK(child>=0,142);if(!child){if(batch==0){for(case_id=0;case_id<normal_cases;++case_id)run_case();case_id=24;run_case();}else{case_id=20+batch;run_case();}thread_syscall4(SYS_exit_group,0,0,0,0);fail(143);}int status=-1;CHECK(waitpid(child,&status,0)==child,144);CHECK(batch==1?(WIFSIGNALED(status)&&WTERMSIG(status)==SIGUSR1):(WIFEXITED(status)&&WEXITSTATUS(status)==0),145);if(batch)marker("POLL_TEMP_EXIT_PASS arch=%s variant=%d form=%d restart=%d case=%d pid=%ld signal=%d\n",PROBE_ARCH,variant,form,restart,20+batch,(long)child,batch==1?SIGUSR1:0);}
 }
#ifdef POLL_TEMP_LINUX_REFERENCE
 marker("POLL_TEMP_LINUX_REFERENCE_PASS arch=%s variants=%d groups=%d cases=%d parent=1\n",PROBE_ARCH,variants,groups,groups*cases);
#else
 marker("POLL_TEMP_PASS arch=%s variants=%d groups=%d cases=%d parent=1\n",PROBE_ARCH,variants,groups,groups*cases);
#endif
 return 0;
}
