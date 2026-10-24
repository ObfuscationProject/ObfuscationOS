#ifndef SIGNAL_WAIT_GUEST_H
#define SIGNAL_WAIT_GUEST_H
#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
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
#include "pipe_vector_context.h"
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
#error "Unsupported synchronous signal wait profile"
#endif
#if defined(__arm__) || defined(__powerpc__)
enum {raw_forms=2};
#else
enum {raw_forms=1};
#endif
#if defined(__i386__) || defined(__arm__) || (defined(__mips__)&&!defined(__mips64)) || defined(__powerpc__)
enum {raw_time_begin=0,raw_time_end=2};
#elif defined(__riscv) && __riscv_xlen==32
enum {raw_time_begin=1,raw_time_end=2};
#else
enum {raw_time_begin=0,raw_time_end=1};
#endif
#if defined(__mips__)
enum {kernel_set_bytes=16,maximum_signal=128};
#else
enum {kernel_set_bytes=8,maximum_signal=64};
#endif
#if defined(__powerpc__) && defined(__clang__)
#define load(p) __c11_atomic_load((p),__ATOMIC_SEQ_CST)
#define store(p,v) __c11_atomic_store((p),(v),__ATOMIC_SEQ_CST)
#define add(p,v) __c11_atomic_fetch_add((p),(v),__ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p),__ATOMIC_SEQ_CST)
#define store(p,v) __atomic_store_n((p),(v),__ATOMIC_SEQ_CST)
#define add(p,v) __atomic_fetch_add((p),(v),__ATOMIC_SEQ_CST)
#endif
enum {all_bits=31,mask_command=1,pending_command=2,wait_command=3,exit_command=4,exec_command=5};
static int family,api,timeabi,form,restart,case_id,dirty;
static const char *image_path;
static _Thread_local int actor=-1;
static _Thread_local unsigned call_ordinal,send_ordinal,pending_ordinal;
struct operation {
 sigset_t set_storage;const sigset_t *set;void *info,*timeout;size_t size;
 union {int64_t wide[2];int32_t narrow[4];struct timespec libc;} time_storage;
 _Alignas(16) unsigned char guarded[144];unsigned set_bits;
 int expected,code,check_info,check_inputs,any_signal,library,timed_override;
 pid_t sender;uid_t uid;unsigned expected_mask;
 _Atomic int entered,done;long value;int error;
};
struct worker {pthread_t thread;pid_t tid;int live;_Atomic int command,ack;unsigned argument,seq;struct operation op;};
struct handler_expectation {int signal,code;pid_t sender;uid_t uid;unsigned live,saved;};
static struct {
 pid_t pid;uid_t uid;int signals[5];struct worker workers[2];
 struct handler_expectation expected[3][8];unsigned expected_count[3];_Atomic unsigned handled[3],handler_done[3];
 uintptr_t site,resume;unsigned replacement_mask;unsigned char *mapping;
} state;
static __attribute__((noreturn)) void fail(int code)
{char b[]="SIGNAL_WAIT_FAIL code=0000\n";unsigned n=sizeof("SIGNAL_WAIT_FAIL code=")-1;for(unsigned i=0;i<4;++i){b[n+3-i]='0'+code%10;code/=10;}thread_syscall4(SYS_write,1,(uintptr_t)b,sizeof(b)-1,0);thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}}
#define CHECK(c) do{if(!(c))fail(__LINE__);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{char b[2048];va_list ap;va_start(ap,format);int n=vsnprintf(b,sizeof(b),format,ap);va_end(ap);CHECK(n>0&&(size_t)n<sizeof(b));CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b,n,0)==n);}
#define KEY "arch=%s family=%d api=%d time=%d form=%d restart=%d case=%d"
#define VALUES PROBE_ARCH,family,api,timeabi,form,restart,case_id
static int role(int a){CHECK(a==0||a==1||a==9);return a==9?2:a;}
static pid_t tid(void){return thread_syscall4(SYS_gettid,0,0,0,0);}
static int64_t now(void){struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void delay(int64_t n){int64_t begin=now();while(now()-begin<n){}}
static void wait_int(_Atomic int *p,int value){int64_t begin=now();while(load(p)!=value)CHECK(now()-begin<5000000000LL);}
static void wait_count(_Atomic unsigned *p,unsigned value){int64_t begin=now();while(load(p)<value)CHECK(now()-begin<5000000000LL);CHECK(load(p)==value);}
static void event(const char *tag,long value,long extra){marker("SIGNAL_WAIT_EVENT " KEY " actor=%d tag=%s value=%ld extra=%ld\n",VALUES,actor,tag,value,extra);}
static void numbers(void){state.signals[0]=SIGUSR1;state.signals[1]=SIGUSR2;state.signals[2]=SIGRTMIN;state.signals[3]=SIGRTMIN+1;state.signals[4]=SIGWINCH;}
static unsigned bits(const sigset_t *p){unsigned value=0;for(unsigned i=0;i<5;++i)if(sigismember(p,state.signals[i])==1)value|=1u<<i;return value;}
static sigset_t make_mask(unsigned value){sigset_t p;CHECK(value<=all_bits&&sigemptyset(&p)==0);for(unsigned i=0;i<5;++i)if(value&(1u<<i))CHECK(sigaddset(&p,state.signals[i])==0);return p;}
static unsigned current_mask(void){sigset_t p;CHECK(sigprocmask(SIG_SETMASK,0,&p)==0);return bits(&p);}
static void mask(unsigned value){sigset_t p=make_mask(value);CHECK(sigprocmask(SIG_SETMASK,&p,0)==0&&current_mask()==value);marker("SIGNAL_WAIT_MASK " KEY " actor=%d bits=%u\n",VALUES,actor,value);}
static void pending(unsigned value){sigset_t p;CHECK(sigpending(&p)==0&&bits(&p)==value);marker("SIGNAL_WAIT_PENDING " KEY " actor=%d ordinal=%u bits=%u mask=%u\n",VALUES,actor,pending_ordinal++,value,current_mask());}
static uint64_t word(const sigset_t *p,unsigned i){uint64_t v=0;if(i*8<kernel_set_bytes)memcpy(&v,(const unsigned char *)p+i*8,8);return v;}
static long timed_number(void){
#ifdef SYS_rt_sigtimedwait_time64
 if(timeabi==1)return SYS_rt_sigtimedwait_time64;
#endif
#ifdef SYS_rt_sigtimedwait
 return SYS_rt_sigtimedwait;
#else
 return SYS_rt_sigtimedwait_time64;
#endif
}
static long operation_number(void){return family?SYS_rt_sigsuspend:timed_number();}
static long requested_number(const struct operation *op){
 if(op->timed_override)return timed_number();
#ifdef SYS_rt_sigtimedwait_time64
 if(!family&&api&&op->timeout&&op->time_storage.libc.tv_sec>INT32_MAX)return SYS_rt_sigtimedwait_time64;
#endif
 (void)op;return operation_number();}
static long trap(long number,unsigned long args[6]){
#if defined(__arm__)
 if(form)return poll_signal_thumb(number,args,0);
#endif
 return poll_signal_raw(number,args,form);
}
static size_t time_bytes(void){return api?sizeof(struct timespec):timeabi==1||sizeof(long)==8?16:8;}
static void timeout_value(struct operation *op,int64_t seconds,int64_t ns)
{memset(&op->time_storage,0,sizeof(op->time_storage));if(api){op->time_storage.libc.tv_sec=seconds;op->time_storage.libc.tv_nsec=ns;}else if(time_bytes()==16){op->time_storage.wide[0]=seconds;op->time_storage.wide[1]=ns;}else{op->time_storage.narrow[0]=seconds;op->time_storage.narrow[1]=ns;}op->timeout=&op->time_storage;}
static void prepare(struct operation *op,unsigned wanted,int64_t seconds,int64_t ns,int expected,int code,pid_t sender,uid_t uid)
{memset(op,0,sizeof(*op));op->set_storage=make_mask(wanted);op->set=&op->set_storage;op->set_bits=wanted;op->info=op->guarded+8;memset(op->guarded,0xa5,sizeof(op->guarded));op->size=kernel_set_bytes;op->expected=expected;op->code=code;op->sender=sender;op->uid=uid;op->check_info=1;op->check_inputs=1;op->expected_mask=current_mask();if(seconds>=0)timeout_value(op,seconds,ns);}
static uint32_t checksum(const unsigned char *p,size_t n){uint32_t v=5381;for(size_t i=0;i<n;++i)v=(v*33)^p[i];return v;}
static void expected_info(unsigned char out[128],int signal,int code,pid_t pid,uid_t uid)
{memset(out,0,128);int32_t number=signal,error=0,value=code;uint32_t sender=pid,user=uid;memcpy(out,&number,4);
#if defined(__mips__)
 memcpy(out+4,&value,4);memcpy(out+8,&error,4);
#else
 memcpy(out+4,&error,4);memcpy(out+8,&value,4);
#endif
 unsigned offset=sizeof(void *)==8?16:12;memcpy(out+offset,&sender,4);memcpy(out+offset+4,&user,4);}
static void call_wait(struct operation *op)
{
 unsigned retries=0;
retry:
 ;int suspend=family&&!op->timed_override;unsigned ordinal=call_ordinal++;unsigned before=current_mask();unsigned char saved_set[16],saved_time[32];size_t time_size=time_bytes();
 if(op->check_inputs){memcpy(saved_set,op->set,kernel_set_bytes);if(op->timeout)memcpy(saved_time,op->timeout,time_size);}
 uint64_t w0=op->check_inputs?word(op->set,0):0,w1=op->check_inputs?word(op->set,1):0;
 marker("SIGNAL_WAIT_BEGIN " KEY " actor=%d ordinal=%u pid=%ld tid=%ld syscall=%ld set=%lu info=%lu timeout=%lu size=%lu wanted=%u word0=%" PRIu64 " word1=%" PRIu64 " mask=%u expected=%d library=%d site=%lu resume=%lu\n",VALUES,actor,ordinal,(long)getpid(),(long)tid(),requested_number(op),(unsigned long)(uintptr_t)op->set,(unsigned long)(uintptr_t)(suspend?0:op->info),(unsigned long)(uintptr_t)(suspend?0:op->timeout),(unsigned long)op->size,op->set_bits,w0,w1,before,op->expected,op->library,(unsigned long)state.site,(unsigned long)state.resume);
 unsigned long args[6]={(uintptr_t)op->set,suspend?op->size:(uintptr_t)op->info,suspend?0:(uintptr_t)op->timeout,suspend?0:op->size,0,0};
 errno=222;store(&op->entered,1);long value;
 if(!api)value=trap(requested_number(op),args);
 else if(suspend)value=sigsuspend(op->set);
 else if(op->library==1)value=sigwaitinfo(op->set,op->info);
 else if(op->library==2){int received=0;int ret=sigwait(op->set,&received);CHECK(ret==0);value=received;}
 else value=sigtimedwait(op->set,op->info,op->timeout);
 int error=errno;op->value=value;op->error=error;
 marker("SIGNAL_WAIT_RETURN " KEY " actor=%d ordinal=%u value=%ld errno=%d mask=%u\n",VALUES,actor,ordinal,value,error,current_mask());
 CHECK(current_mask()==op->expected_mask);
 int shared_retry=op->any_signal&&!api&&value==-EINTR;
 if(op->any_signal)CHECK(value==SIGUSR1||value==SIGUSR2||shared_retry);else CHECK(value==(api&&op->expected<0?-1:op->expected));
 CHECK(error==(api&&op->expected<0?-op->expected:222));
 if(op->check_inputs){CHECK(memcmp(saved_set,op->set,kernel_set_bytes)==0||op->info==(const void *)op->set);if(op->timeout)CHECK(memcmp(saved_time,op->timeout,time_size)==0);}
 if(op->check_info&&op->info&&op->library!=2){
  if(value>0){unsigned char wanted[128];expected_info(wanted,(int)value,op->code,op->sender,op->uid);CHECK(memcmp(op->info,wanted,128)==0);marker("SIGNAL_WAIT_INFO " KEY " actor=%d ordinal=%u signal=%ld code=%d sender=%ld uid=%lu bytes=128 checksum=%" PRIu32 "\n",VALUES,actor,ordinal,value,op->code,(long)op->sender,(unsigned long)op->uid,checksum(op->info,128));}
  else if(op->info==op->guarded+8)for(unsigned i=8;i<136;++i)CHECK(op->guarded[i]==0xa5);
 }
 if(op->info==op->guarded+8){for(unsigned i=0;i<8;++i)CHECK(op->guarded[i]==0xa5&&op->guarded[i+136]==0xa5);event("INFO_GUARDS",ordinal,16);}
 event("WAIT_CHECKED",ordinal,shared_retry?-EINTR:op->expected);
 if(shared_retry){CHECK(++retries<8);event("RAW_SHARED_RETRY",ordinal,retries);goto retry;}store(&op->done,1);
}
static void send_signal(int process,pid_t target,int signal)
{unsigned ordinal=send_ordinal++;marker("SIGNAL_WAIT_SEND " KEY " actor=%d ordinal=%u pid=%ld tid=%ld process=%d target=%ld signal=%d uid=%lu\n",VALUES,actor,ordinal,(long)getpid(),(long)tid(),process,(long)target,signal,(unsigned long)getuid());CHECK(process?kill(target,signal)==0:thread_syscall4(SYS_tgkill,getpid(),target,signal,0)==0);marker("SIGNAL_WAIT_SENT " KEY " actor=%d ordinal=%u\n",VALUES,actor,ordinal);}
static void want_handler(int who,int signal,int code,unsigned live,unsigned saved)
{unsigned r=role(who),n=state.expected_count[r]++;CHECK(n<8);state.expected[r][n]=(struct handler_expectation){signal,code,state.pid,state.uid,live,saved};}
static __attribute__((noreturn)) void replace_image(unsigned expected_mask);
static void handler(int signal,siginfo_t *info,void *context)
{
 int error=errno;unsigned r=role(actor),n=add(&state.handled[r],1);CHECK(n<state.expected_count[r]&&info&&context);struct handler_expectation e=state.expected[r][n];ucontext_t *c=context;
 CHECK(signal==e.signal&&info->si_signo==signal&&info->si_code==e.code&&info->si_pid==e.sender&&info->si_uid==e.uid&&info->si_errno==0);
 CHECK(getpid()==state.pid&&tid()==(actor==9?state.pid:state.workers[actor].tid));CHECK(current_mask()==e.live&&bits(&c->uc_sigmask)==e.saved&&context_result(c)==-EINTR);
 if(!api)CHECK((uintptr_t)CTX_PC(c)==state.resume);
 unsigned long abi=0;
#if defined(__mips__)
 abi=c->uc_mcontext.gregs[7];CHECK(abi==1);
#elif defined(__powerpc__)
 abi=c->uc_regs->gregs[38];CHECK(abi&0x10000000);
#elif defined(__arm__)
 abi=c->uc_mcontext.arm_cpsr;if(!api)CHECK(((abi&0x20)!=0)==(form!=0));
#endif
 marker("SIGNAL_WAIT_HANDLE " KEY " actor=%d ordinal=%u pid=%ld tid=%ld signal=%d code=%d sender=%ld uid=%lu live=%u saved=%u pc=%lu result=%ld abi=%lu\n",VALUES,actor,n,(long)getpid(),(long)tid(),signal,info->si_code,(long)info->si_pid,(unsigned long)info->si_uid,current_mask(),bits(&c->uc_sigmask),(unsigned long)(uintptr_t)CTX_PC(c),context_result(c),abi);
 if(family&&case_id==12){pid_t child=fork();CHECK(child>=0);if(!child){actor=8;sigset_t p;CHECK(current_mask()==e.live&&sigpending(&p)==0&&bits(&p)==0);marker("SIGNAL_WAIT_HANDLER_FORK " KEY " actor=8 pid=%ld parent=%ld mask=%u pending=0\n",VALUES,(long)getpid(),(long)state.pid,current_mask());_Exit(17);}int status;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==17);event("HANDLER_REAP",child,17);}
 if(family&&case_id==13)replace_image(e.live);
 if(family&&case_id==16){event("HANDLER_EXIT",tid(),e.live);pthread_exit((void *)(uintptr_t)0x996);fail(__LINE__);}
 event("HANDLER_RETURN",signal,n);store(&state.handler_done[r],n+1);errno=error;
}
static void action(int signal,int kind)
{struct sigaction a={0};a.sa_sigaction=handler;a.sa_mask=make_mask(4);a.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0);if(kind==0)a.sa_handler=SIG_DFL;else if(kind==1)a.sa_handler=SIG_IGN;CHECK(sigaction(signal,&a,0)==0);marker("SIGNAL_WAIT_ACTION " KEY " actor=%d signal=%d kind=%d\n",VALUES,actor,signal,kind);}
static void *worker_main(void *arg)
{actor=(int)(uintptr_t)arg;call_ordinal=send_ordinal=pending_ordinal=0;struct worker *w=&state.workers[actor];w->tid=tid();CHECK(current_mask()==all_bits);store(&w->ack,-1);for(;;){int c=load(&w->command);if(c<=0||c==load(&w->ack)){(void)now();continue;}unsigned op=(unsigned)c&255,arg=w->argument;
 if(op==mask_command)mask(arg);else if(op==pending_command)pending(arg);else if(op==wait_command)call_wait(&w->op);else if(op==exec_command)replace_image(arg);else if(op==exit_command){event("THREAD_EXIT",w->tid,(unsigned)c>>8);store(&w->ack,c);return (void *)(uintptr_t)0x995;}else fail(__LINE__);
 marker("SIGNAL_WAIT_ACK " KEY " actor=%d seq=%u operation=%u argument=%u\n",VALUES,actor,(unsigned)c>>8,op,arg);store(&w->ack,c);}}
static void spawn(int which)
{struct worker *w=&state.workers[which];CHECK(!w->live);pthread_attr_t attr;CHECK(pthread_attr_init(&attr)==0&&pthread_attr_setstacksize(&attr,65536)==0&&pthread_attr_setguardsize(&attr,4096)==0);CHECK(pthread_create(&w->thread,&attr,worker_main,(void *)(uintptr_t)which)==0&&pthread_attr_destroy(&attr)==0);w->live=1;wait_int(&w->ack,-1);marker("SIGNAL_WAIT_THREAD " KEY " actor=%d tid=%ld mask=31\n",VALUES,which,(long)w->tid);}
static int start(int which,unsigned op,unsigned arg)
{struct worker *w=&state.workers[which];CHECK(w->live);unsigned seq=++w->seq;int c=(int)(seq<<8|op);w->argument=arg;marker("SIGNAL_WAIT_COMMAND " KEY " actor=9 target=%d seq=%u operation=%u argument=%u\n",VALUES,which,seq,op,arg);store(&w->command,c);return c;}
static void finish_command(int which,int c)
{wait_int(&state.workers[which].ack,c);marker("SIGNAL_WAIT_COMMAND_DONE " KEY " actor=9 target=%d seq=%u operation=%u argument=%u\n",VALUES,which,(unsigned)c>>8,(unsigned)c&255,state.workers[which].argument);}
static void command(int which,unsigned op,unsigned arg){int c=start(which,op,arg);finish_command(which,c);}
static void join_worker(int which,int from_handler)
{struct worker *w=&state.workers[which];void *value=0;CHECK(w->live&&pthread_join(w->thread,&value)==0&&value==(void *)(uintptr_t)(from_handler?0x996:0x995));w->live=0;event("JOIN",which,w->tid);}
static void observe_wait(int which,unsigned phase)
{
 struct worker *w=&state.workers[which];wait_int(&w->op.entered,1);
#ifdef SIGNAL_WAIT_LINUX_REFERENCE
 char path[128],line[512];snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)w->tid);int64_t begin=now();long number=-1;unsigned long set=0,info=0,timeout=0,size=0,pc=0;
 for(;;){FILE *f=fopen(path,"r");if(f){if(fgets(line,sizeof(line),f)){unsigned long unused,sp;int fields=sscanf(line,"%ld %lx %lx %lx %lx %lx %lx %lx %lx",&number,&set,&info,&timeout,&size,&unused,&unused,&sp,&pc);if(fields==9&&number==requested_number(&w->op)){fclose(f);break;}}fclose(f);}CHECK(!load(&w->op.done)&&now()-begin<5000000000LL);}
 marker("SIGNAL_WAIT_LINUX_WAIT " KEY " actor=9 target=%d phase=%u tid=%ld syscall=%ld set=%lu info=%lu timeout=%lu size=%lu pc=%lu\n",VALUES,which,phase,(long)w->tid,number,set,info,timeout,size,pc);
#else
 delay(40000000);
#endif
 CHECK(!load(&w->op.done));marker("SIGNAL_WAIT_AWAIT " KEY " actor=9 target=%d phase=%u tid=%ld\n",VALUES,which,phase,(long)w->tid);
}
static void worker_request(int which,unsigned wanted,int64_t seconds,int64_t ns,int expected,int code)
{prepare(&state.workers[which].op,wanted,seconds,ns,expected,code,state.pid,state.uid);state.workers[which].op.expected_mask=all_bits;}
static void receive_now(unsigned wanted,int expected,int code,pid_t sender,uid_t uid)
{struct operation op;prepare(&op,wanted,0,0,expected,code,sender,uid);call_wait(&op);}
static pid_t sender_child(int signal,unsigned order)
{pid_t child=fork();CHECK(child>=0);if(!child){actor=8;send_ordinal=order;send_signal(1,state.pid,signal);event("SENDER_EXIT",getpid(),17);_Exit(17);}int status;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==17);event("CHILD_REAP",child,17);return child;}
static unsigned char *pages(void)
{void *p=mmap(0,3*4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);CHECK(p!=MAP_FAILED);memset(p,0xa5,3*4096);state.mapping=p;event("MAP",(long)(uintptr_t)p,3*4096);return p;}
static void protect(void *p,int writable){CHECK(mprotect(p,4096,writable?(PROT_READ|PROT_WRITE):PROT_NONE)==0);event(writable?"UNPROTECT":"PROTECT",(long)(uintptr_t)p,4096);}
static __attribute__((noreturn)) void replace_image(unsigned expected_mask)
{char text[8][24];long values[8]={family,api,timeabi,form,restart,case_id,state.pid,expected_mask};for(unsigned i=0;i<8;++i)snprintf(text[i],sizeof(text[i]),"%ld",values[i]);char *argv[]={(char *)image_path,"wait-replaced",text[0],text[1],text[2],text[3],text[4],text[5],text[6],text[7],0};char *env[]={0};CHECK(dirty&&current_mask()==expected_mask);event("EXEC_COMMIT",state.pid,expected_mask);thread_syscall4(SYS_execve,(uintptr_t)image_path,(uintptr_t)argv,(uintptr_t)env,0);fail(__LINE__);}
#endif
