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
#include <sys/ioctl.h>
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
#error "Unsupported process-shared signal profile"
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

#if defined(__powerpc__) && defined(__clang__)
#define add(p,v) __c11_atomic_fetch_add((p),(v),__ATOMIC_SEQ_CST)
#else
#define add(p,v) __atomic_fetch_add((p),(v),__ATOMIC_SEQ_CST)
#endif
#ifdef SYS_setresuid32
#define SETRESUID SYS_setresuid32
#define GETRESUID SYS_getresuid32
#else
#define SETRESUID SYS_setresuid
#define GETRESUID SYS_getresuid
#endif
#if defined(__mips__)
enum {maximum_signal=128};
#else
enum {maximum_signal=64};
#endif
enum {cases=33,all_bits=31,slots=5};
enum {cmd_mask=1,cmd_query,cmd_exit,cmd_send_exit,cmd_read,cmd_exec,cmd_survive,cmd_kill};
static int variant,form,restart,case_id,dirty;
static const char *image_path;
static _Thread_local int actor=-1;
static _Thread_local unsigned call_serial,query_serial;
struct expected {int signal,code;pid_t sender;uid_t uid;};
struct worker {pid_t tid;pthread_t thread;int live;_Atomic int command,ack;unsigned argument;_Atomic int entered,phase,done;unsigned char guarded[3];};
static struct {
 pid_t pid;uid_t uid;int signal[slots];struct worker worker[2];
 struct expected expected[3][64];unsigned expected_count[3];_Atomic unsigned handled[3],any_handled;
 _Atomic int leader_entered,leader_exiting;int pipe[2][2];uintptr_t read_site,read_resume;
} state;
static __attribute__((noreturn)) void fail(int code)
{char b[]="PROCESS_SIGNAL_FAIL code=000\n";unsigned p=sizeof("PROCESS_SIGNAL_FAIL code=")-1;b[p]='0'+code/100%10;b[p+1]='0'+code/10%10;b[p+2]='0'+code%10;thread_syscall4(SYS_write,1,(uintptr_t)b,sizeof(b)-1,0);thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}}
#define CHECK(c) do{if(!(c))fail(__LINE__);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{char b[1536];va_list ap;va_start(ap,format);int n=vsnprintf(b,sizeof(b),format,ap);va_end(ap);CHECK(n>0&&(size_t)n<sizeof(b));CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b,n,0)==n);}
#define KEY "arch=%s variant=%d form=%d restart=%d case=%d"
#define VALUES PROBE_ARCH,variant,form,restart,case_id
static int role_index(int role){CHECK(role==0||role==1||role==9);return role==9?2:role;}
static pid_t tid(void){return thread_syscall4(SYS_gettid,0,0,0,0);}
static int64_t now(void){struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void delay(int64_t n){int64_t start=now();while(now()-start<n){}}
static void wait_int(_Atomic int *p,int value){int64_t start=now();while(load(p)!=value)CHECK(now()-start<5000000000LL);}
static void wait_handled(int role,unsigned count){int64_t start=now();while(load(&state.handled[role_index(role)])<count)CHECK(now()-start<5000000000LL);CHECK(load(&state.handled[role_index(role)])==count);}
static void event(const char *tag,long value,long extra){marker("PROCESS_SIGNAL_EVENT " KEY " actor=%d tag=%s value=%ld extra=%ld\n",VALUES,actor,tag,value,extra);}
static unsigned bits(const sigset_t *set){unsigned result=0;for(unsigned i=0;i<slots;++i)if(sigismember(set,state.signal[i])==1)result|=1u<<i;return result;}
static unsigned current_mask(void){sigset_t old;CHECK(sigprocmask(SIG_SETMASK,0,&old)==0);return bits(&old);}
static sigset_t make_mask(unsigned value){sigset_t mask;CHECK(value<=all_bits&&sigemptyset(&mask)==0);for(unsigned i=0;i<slots;++i)if(value&(1u<<i))CHECK(sigaddset(&mask,state.signal[i])==0);return mask;}
static void mask(unsigned value){sigset_t next=make_mask(value);CHECK(sigprocmask(SIG_SETMASK,&next,0)==0&&current_mask()==value);marker("PROCESS_SIGNAL_MASK " KEY " actor=%d bits=%u\n",VALUES,actor,value);}
static void pending(unsigned wanted){sigset_t p;CHECK(sigemptyset(&p)==0&&sigpending(&p)==0);unsigned actual=bits(&p),blocked=current_mask();CHECK(actual==wanted&&(actual&~blocked)==0);marker("PROCESS_SIGNAL_PENDING " KEY " actor=%d ordinal=%u bits=%u mask=%u\n",VALUES,actor,query_serial++,actual,blocked);}
static void expect(int role,int signal,int code,pid_t sender,uid_t uid){unsigned i=role_index(role),n=state.expected_count[i]++;CHECK(n<64);state.expected[i][n]=(struct expected){signal,code,sender,uid};}
static void ordinary(int role,int signal,int code){expect(role,signal,code,state.pid,state.uid);}
static long trap(long number,unsigned long *args){
#if defined(__arm__)
 if(form)return poll_signal_thumb(number,args,0);
#endif
 return poll_signal_raw(number,args,form);
}
static void send_kill(pid_t target,int signal,int error)
{
 unsigned ordinal=call_serial++;pid_t me=getpid(),thread=tid();uid_t uid=getuid(),effective=geteuid();
 marker("PROCESS_SIGNAL_KILL_BEGIN " KEY " actor=%d ordinal=%u pid=%ld tid=%ld uid=%lu effective=%lu target=%ld signal=%d syscall=%ld\n",VALUES,actor,ordinal,(long)me,(long)thread,(unsigned long)uid,(unsigned long)effective,(long)target,signal,(long)SYS_kill);
 unsigned long args[6]={(unsigned long)target,(unsigned long)(long)signal,0,0x1357,0,0};errno=222;long value=variant?kill(target,signal):trap(SYS_kill,args);int actual=errno;
 CHECK(value==(error?(variant?-1:-error):0)&&actual==(variant&&error?error:222));
 marker("PROCESS_SIGNAL_KILL_END " KEY " actor=%d ordinal=%u value=%ld errno=%d\n",VALUES,actor,ordinal,value,actual);
}
static void direct(pid_t target,int signal){marker("PROCESS_SIGNAL_DIRECT " KEY " actor=%d pid=%ld tid=%ld target=%ld signal=%d\n",VALUES,actor,(long)getpid(),(long)tid(),(long)target,signal);CHECK(thread_syscall4(SYS_tgkill,state.pid,target,signal,0)==0);}
static void handle(int signal,siginfo_t *info,void *context)
{
 int saved=errno;unsigned role=role_index(actor),n=add(&state.handled[role],1);CHECK(info&&context&&info->si_signo==signal&&info->si_errno==0);CHECK(getpid()==state.pid&&tid()==(actor==9?state.pid:state.worker[actor].tid));
 if(case_id==7){CHECK(actor!=9&&add(&state.any_handled,1)==0&&n==0);CHECK(signal==SIGUSR1&&info->si_code==SI_USER&&info->si_pid==state.pid&&info->si_uid==state.uid);}
 else {CHECK(n<state.expected_count[role]);struct expected e=state.expected[role][n];CHECK(signal==e.signal&&info->si_code==e.code&&info->si_pid==e.sender&&info->si_uid==e.uid);}
 CHECK(current_mask()==all_bits);ucontext_t *c=context;int inspected=case_id==23;unsigned long number=0,a0=0,a1=0,a2=0,a3=0,abi=0;long result=0;
 if(inspected){struct worker *w=&state.worker[0];CHECK(actor==0&&signal==SIGUSR1);number=(uintptr_t)CTX_NUMBER(c);a0=(uintptr_t)CTX_FD(c);a1=(uintptr_t)CTX_BUFFER(c);a2=(uintptr_t)CTX_COUNT(c);a3=(uintptr_t)CTX_TIMEOUT(c);result=restart?0:context_result(c);CHECK(a1==(uintptr_t)(w->guarded+1)&&a2==1);if(restart){CHECK(number==SYS_read&&a0==(unsigned)state.pipe[0][0]);if(!variant)CHECK(a3==0x1357);}else CHECK(result==-EINTR);if(!variant)CHECK((uintptr_t)CTX_PC(c)==(restart?state.read_site:state.read_resume));
#if defined(__mips__)
 abi=c->uc_mcontext.gregs[7];
#elif defined(__powerpc__)
 abi=c->uc_regs->gregs[38];
#elif defined(__arm__)
 abi=c->uc_mcontext.arm_cpsr;if(!variant)CHECK(((abi&0x20)!=0)==(form!=0));
#endif
 }
 marker("PROCESS_SIGNAL_HANDLE " KEY " actor=%d ordinal=%u pid=%ld tid=%ld signal=%d code=%d sender=%ld uid=%lu mask=%u pc=%lu inspected=%d again=%d result=%ld number=%lu a0=%lu a1=%lu a2=%lu a3=%lu abi=%lu\n",VALUES,actor,n,(long)getpid(),(long)tid(),signal,info->si_code,(long)info->si_pid,(unsigned long)info->si_uid,current_mask(),(unsigned long)(uintptr_t)CTX_PC(c),inspected,inspected&&restart,result,number,a0,a1,a2,a3,abi);
 errno=saved;
}
static void disposition(int signal,int kind,int publish)
{struct sigaction a={0};a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0);a.sa_mask=make_mask(all_bits);if(kind==0)a.sa_handler=SIG_DFL;else if(kind==1)a.sa_handler=SIG_IGN;CHECK(sigaction(signal,&a,0)==0);if(publish)marker("PROCESS_SIGNAL_ACTION " KEY " actor=%d signal=%d kind=%d\n",VALUES,actor,signal,kind);}
static void initialize_signals(void){state.signal[0]=SIGUSR1;state.signal[1]=SIGUSR2;state.signal[2]=SIGRTMIN;state.signal[3]=SIGRTMIN+1;state.signal[4]=SIGWINCH;for(unsigned i=0;i<slots;++i)disposition(state.signal[i],2,0);sigset_t set=make_mask(all_bits);CHECK(sigprocmask(SIG_SETMASK,&set,0)==0);}
static __attribute__((noreturn)) void replace_image(void)
{char v[16],f[16],r[16],c[16],pid[24],uid[24];snprintf(v,sizeof(v),"%d",variant);snprintf(f,sizeof(f),"%d",form);snprintf(r,sizeof(r),"%d",restart);snprintf(c,sizeof(c),"%d",case_id);snprintf(pid,sizeof(pid),"%ld",(long)state.pid);snprintf(uid,sizeof(uid),"%lu",(unsigned long)state.uid);char *args[]={(char *)image_path,"process-replaced",v,f,r,c,pid,uid,0};char *env[]={0};CHECK(dirty==1);event("EXEC_COMMIT",state.pid,tid());thread_syscall4(SYS_execve,(uintptr_t)image_path,(uintptr_t)args,(uintptr_t)env,0);fail(__LINE__);}
static void pipe_read(int which)
{
 struct worker *w=&state.worker[which];unsigned long args[6]={(unsigned long)state.pipe[0][0],(uintptr_t)(w->guarded+1),1,0x1357,0,0};memset(w->guarded,0xa5,sizeof(w->guarded));
 marker("PROCESS_SIGNAL_READ_BEGIN " KEY " actor=%d fd=%d input=%lu bytes=1 site=%lu resume=%lu syscall=%ld\n",VALUES,actor,state.pipe[0][0],(unsigned long)(uintptr_t)(w->guarded+1),(unsigned long)state.read_site,(unsigned long)state.read_resume,(long)SYS_read);store(&w->entered,1);errno=222;long result=variant?read(state.pipe[0][0],w->guarded+1,1):trap(SYS_read,args);int error=errno;
 if(case_id!=23)fail(__LINE__);
 marker("PROCESS_SIGNAL_READ_RETURN " KEY " actor=%d ordinal=0 value=%ld errno=%d\n",VALUES,actor,result,error);
 if(!restart){CHECK(result==(variant?-1:-EINTR)&&error==(variant?EINTR:222));event("READ_RETRY",state.pipe[0][0],1);store(&w->phase,1);errno=222;result=variant?read(state.pipe[0][0],w->guarded+1,1):trap(SYS_read,args);error=errno;marker("PROCESS_SIGNAL_READ_RETURN " KEY " actor=%d ordinal=1 value=%ld errno=%d\n",VALUES,actor,result,error);}
 CHECK(result==1&&error==222&&w->guarded[0]==0xa5&&w->guarded[1]=='Q'&&w->guarded[2]==0xa5);CHECK(load(&state.handled[0])==1);event("READ_PASS",81,3);store(&w->done,1);
}
static void *worker(void *argument)
{
 actor=(int)(uintptr_t)argument;call_serial=query_serial=0;struct worker *w=&state.worker[actor];w->tid=tid();CHECK(current_mask()==all_bits);store(&w->ack,-1);
 for(;;){int command=load(&w->command);if(command<=0||command==load(&w->ack)){(void)now();continue;}unsigned operation=(unsigned)command&255u,seq=(unsigned)command>>8,arg=w->argument;
  if(operation==cmd_mask)mask(arg);
  else if(operation==cmd_query)pending(arg);
  else if(operation==cmd_exit||operation==cmd_send_exit){if(operation==cmd_send_exit)send_kill(state.pid,SIGUSR1,0);event("THREAD_EXIT",w->tid,seq);store(&w->ack,command);return (void *)(uintptr_t)0x817;}
  else if(operation==cmd_read){mask(arg);pipe_read(actor);}
  else if(operation==cmd_exec)replace_image();
  else if(operation==cmd_survive){wait_int(&state.leader_exiting,1);delay(80000000);mask(all_bits-1);send_kill(state.pid,SIGUSR1,0);wait_handled(actor,1);pending(0);event("SURVIVOR_PASS",state.pid,w->tid);marker("PROCESS_SIGNAL_CASE_PASS " KEY "\n",VALUES);return (void *)(uintptr_t)0x817;}
  else if(operation==cmd_kill){wait_int(&state.worker[0].entered,1);wait_int(&state.leader_entered,1);delay(80000000);event("GROUP_AWAIT",case_id==32?1:2,case_id==32);send_kill(case_id==25?state.worker[0].tid:state.pid,SIGKILL,0);fail(__LINE__);}
  else fail(__LINE__);
  marker("PROCESS_SIGNAL_COMMAND_ACK " KEY " actor=%d seq=%u operation=%u argument=%u\n",VALUES,actor,seq,operation,arg);store(&w->ack,command);
 }
}
static unsigned command_sequence[2];
static void spawn(int which)
{struct worker *w=&state.worker[which];CHECK(!w->live);pthread_attr_t a;CHECK(pthread_attr_init(&a)==0&&pthread_attr_setstacksize(&a,65536)==0&&pthread_attr_setguardsize(&a,4096)==0);CHECK(pthread_create(&w->thread,&a,worker,(void *)(uintptr_t)which)==0&&pthread_attr_destroy(&a)==0);w->live=1;wait_int(&w->ack,-1);marker("PROCESS_SIGNAL_THREAD " KEY " actor=%d tid=%ld mask=%u\n",VALUES,which,(long)w->tid,all_bits);}
static int start(int which,unsigned operation,unsigned argument)
{struct worker *w=&state.worker[which];CHECK(w->live);unsigned seq=++command_sequence[which];int command=(int)(seq<<8|operation);w->argument=argument;marker("PROCESS_SIGNAL_COMMAND_BEGIN " KEY " actor=9 target=%d seq=%u operation=%u argument=%u\n",VALUES,which,seq,operation,argument);store(&w->command,command);return command;}
static void finish_command(int which,int command){wait_int(&state.worker[which].ack,command);marker("PROCESS_SIGNAL_COMMAND_END " KEY " actor=9 target=%d seq=%u operation=%u argument=%u\n",VALUES,which,(unsigned)command>>8,(unsigned)command&255u,state.worker[which].argument);}
static void command(int which,unsigned op,unsigned arg){int c=start(which,op,arg);finish_command(which,c);}
static void join_worker(int which)
{struct worker *w=&state.worker[which];CHECK(w->live);void *value=0;CHECK(pthread_join(w->thread,&value)==0&&value==(void *)(uintptr_t)0x817);w->live=0;event("JOIN",which,w->tid);}
static void pending_all(unsigned leader,unsigned first,unsigned second){pending(leader);if(state.worker[0].live)command(0,cmd_query,first);if(state.worker[1].live)command(1,cmd_query,second);}
static void wait_child(pid_t child,int code){int status=-1;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==code);marker("PROCESS_SIGNAL_CHILD_REAP " KEY " actor=9 pid=%ld status=%d\n",VALUES,(long)child,code);}
static pid_t sender_child(int credentials,int denied)
{
 pid_t child=fork();CHECK(child>=0);if(!child){actor=8;call_serial=0;if(credentials){unsigned real=denied?1102:1101,effective=denied?1102:0;CHECK(thread_syscall4(SETRESUID,real,effective,effective,0)==0);uid_t ids[3]={0};CHECK(thread_syscall4(GETRESUID,(uintptr_t)ids,(uintptr_t)(ids+1),(uintptr_t)(ids+2),0)==0&&ids[0]==real&&ids[1]==effective&&ids[2]==effective);marker("PROCESS_SIGNAL_CREDENTIALS " KEY " actor=8 pid=%ld real=%u effective=%u saved=%u\n",VALUES,(long)getpid(),ids[0],ids[1],ids[2]);}
  if(denied){send_kill(state.pid,0,EPERM);send_kill(state.pid,SIGUSR1,EPERM);send_kill(state.pid,maximum_signal+1,EINVAL);}else send_kill(state.pid,SIGUSR1,0);event("SENDER_EXIT",getpid(),getuid());_Exit(17);
 }
 wait_child(child,17);return child;
}
static void special_zombie(void)
{
 int gate[2];CHECK(pipe(gate)==0);event("ZOMBIE_GATE",gate[0],gate[1]);pid_t child=fork();CHECK(child>=0);if(!child){CHECK(close(gate[0])==0&&write(gate[1],"Z",1)==1);_Exit(17);}CHECK(close(gate[1])==0);unsigned char byte;CHECK(read(gate[0],&byte,1)==1&&byte=='Z'&&read(gate[0],&byte,1)==0&&close(gate[0])==0);event("ZOMBIE_EOF",child,17);send_kill(child,0,0);send_kill(child,SIGUSR1,0);send_kill(child,maximum_signal+1,EINVAL);wait_child(child,17);send_kill(child,0,ESRCH);send_kill(child,maximum_signal+1,ESRCH);send_kill(child,-1,ESRCH);
}
static void announce_pipe(int which)
{CHECK(pipe(state.pipe[which])==0);marker("PROCESS_SIGNAL_PIPE " KEY " actor=9 role=%d readfd=%d writefd=%d\n",VALUES,which,state.pipe[which][0],state.pipe[which][1]);}
static void run_case(void)
{
 memset(&state,0,sizeof(state));memset(command_sequence,0,sizeof(command_sequence));actor=9;call_serial=query_serial=0;dirty=1;state.pid=getpid();state.uid=getuid();initialize_signals();state.read_site=(uintptr_t)poll_signal_site;state.read_resume=(uintptr_t)poll_signal_resume;
#if defined(__arm__)
 if(form){state.read_site=(uintptr_t)poll_signal_thumb_site;state.read_resume=(uintptr_t)poll_signal_thumb_resume;}
#endif
 marker("PROCESS_SIGNAL_CASE_BEGIN " KEY " pid=%ld uid=%lu usr1=%d usr2=%d rt1=%d rt2=%d winch=%d maximum=%d kill=%ld read=%ld site=%lu resume=%lu\n",VALUES,(long)state.pid,(unsigned long)state.uid,SIGUSR1,SIGUSR2,state.signal[2],state.signal[3],SIGWINCH,maximum_signal,(long)SYS_kill,(long)SYS_read,(unsigned long)state.read_site,(unsigned long)state.read_resume);
 spawn(0);if(case_id!=9&&case_id!=18)spawn(1);pending_all(0,0,0);
 int rt=state.signal[2];
 switch(case_id){
 case 0:{pid_t retired=state.worker[0].tid;send_kill(state.pid,0,0);send_kill(retired,0,0);send_kill(state.pid,-1,EINVAL);send_kill(retired,maximum_signal+1,EINVAL);pending_all(0,0,0);command(0,cmd_exit,0);join_worker(0);send_kill(retired,0,ESRCH);send_kill(retired,maximum_signal+1,ESRCH);special_zombie();break;}
 case 1:ordinary(9,SIGUSR1,SI_TKILL);ordinary(9,SIGUSR1,SI_USER);send_kill(state.pid,SIGUSR1,0);direct(state.pid,SIGUSR1);pending_all(1,1,1);mask(all_bits-1);wait_handled(9,2);break;
 case 2:ordinary(9,SIGUSR2,SI_TKILL);ordinary(9,SIGUSR1,SI_USER);send_kill(state.pid,SIGUSR1,0);direct(state.pid,SIGUSR2);pending_all(3,1,1);mask(all_bits-3);wait_handled(9,2);break;
 case 3:ordinary(9,SIGUSR1,SI_USER);ordinary(9,SIGUSR2,SI_USER);send_kill(state.pid,SIGUSR2,0);send_kill(state.pid,SIGUSR1,0);pending_all(3,3,3);mask(all_bits-3);wait_handled(9,2);break;
 case 4:ordinary(9,SIGUSR2,SI_USER);ordinary(9,SIGUSR1,SI_TKILL);direct(state.pid,SIGUSR1);send_kill(state.pid,SIGUSR2,0);pending_all(3,2,2);mask(all_bits-2);wait_handled(9,1);pending_all(1,0,0);mask(all_bits-3);wait_handled(9,2);break;
 case 5:ordinary(0,SIGUSR1,SI_USER);send_kill(state.pid,SIGUSR1,0);pending_all(1,1,1);command(0,cmd_mask,all_bits-1);wait_handled(0,1);break;
 case 6:ordinary(1,SIGUSR1,SI_USER);command(1,cmd_mask,all_bits-1);send_kill(state.worker[0].tid,SIGUSR1,0);wait_handled(1,1);break;
 case 7:command(0,cmd_mask,all_bits-1);command(1,cmd_mask,all_bits-1);send_kill(state.pid,SIGUSR1,0);{int64_t t=now();while(!load(&state.any_handled))CHECK(now()-t<5000000000LL);CHECK(load(&state.any_handled)==1);}break;
 case 8:ordinary(0,SIGUSR2,SI_TKILL);ordinary(0,SIGUSR1,SI_USER);direct(state.worker[0].tid,SIGUSR2);send_kill(state.pid,SIGUSR1,0);pending_all(1,3,1);command(0,cmd_mask,all_bits-3);wait_handled(0,2);break;
 case 9:ordinary(1,SIGUSR1,SI_USER);ordinary(9,SIGUSR2,SI_TKILL);direct(state.pid,SIGUSR2);send_kill(state.pid,SIGUSR1,0);spawn(1);pending_all(3,1,1);command(1,cmd_mask,all_bits-1);wait_handled(1,1);pending_all(2,0,0);mask(all_bits-2);wait_handled(9,1);break;
 case 10:ordinary(9,SIGUSR1,SI_USER);command(0,cmd_send_exit,0);join_worker(0);pending_all(1,0,1);mask(all_bits-1);wait_handled(9,1);break;
 case 11:{pid_t child=sender_child(0,0);expect(9,SIGUSR1,SI_USER,child,state.uid);send_kill(state.pid,SIGUSR1,0);pending_all(1,1,1);mask(all_bits-1);wait_handled(9,1);break;}
 case 12:{ordinary(9,SIGUSR2,SI_TKILL);ordinary(9,SIGUSR1,SI_USER);direct(state.pid,SIGUSR2);send_kill(state.pid,SIGUSR1,0);pid_t child=fork();CHECK(child>=0);if(!child){actor=8;query_serial=0;sigset_t p;struct sigaction a;CHECK(sigpending(&p)==0&&bits(&p)==0&&current_mask()==all_bits&&sigaction(SIGUSR1,0,&a)==0&&a.sa_sigaction==handle);marker("PROCESS_SIGNAL_FORK_EMPTY " KEY " actor=8 pid=%ld parent=%ld mask=%u caught=1 pending=0\n",VALUES,(long)getpid(),(long)state.pid,all_bits);_Exit(17);}wait_child(child,17);pending_all(3,1,1);mask(all_bits-3);wait_handled(9,2);break;}
 case 13:case 14:case 15:case 16:{int blocked=case_id==14||case_id==16,nonleader=case_id>=15;disposition(SIGUSR1,1,1);if(!blocked){if(nonleader)command(0,cmd_mask,all_bits-1);else mask(all_bits-1);}send_kill(nonleader?state.worker[0].tid:state.pid,SIGUSR1,0);pending_all(blocked,blocked,blocked);disposition(SIGUSR1,2,1);if(blocked){int recipient=nonleader?1:0;ordinary(recipient,SIGUSR1,SI_USER);command(recipient,cmd_mask,all_bits-1);wait_handled(recipient,1);}break;}
 case 17:direct(state.pid,SIGUSR1);direct(state.worker[0].tid,SIGUSR1);send_kill(state.pid,SIGUSR1,0);pending_all(1,1,1);disposition(SIGUSR1,1,1);pending_all(0,0,0);disposition(SIGUSR1,2,1);mask(all_bits-1);command(0,cmd_mask,all_bits-1);break;
 case 18:ordinary(0,SIGUSR1,SI_USER);start(0,cmd_survive,0);event("LEADER_EXIT",state.pid,0);store(&state.leader_exiting,1);pthread_exit((void *)(uintptr_t)0x817);fail(__LINE__);
 case 19:for(int i=0;i<3;++i){ordinary(9,rt,SI_USER);send_kill(state.pid,rt,0);}pending_all(4,4,4);mask(all_bits-4);wait_handled(9,3);break;
 case 20:case 21:{int receiver=case_id==20?9:0;direct(receiver==9?state.pid:state.worker[0].tid,SIGUSR2);send_kill(state.pid,SIGUSR1,0);if(case_id==21)direct(state.pid,rt);disposition(SIGWINCH,1,1);pending_all(case_id==20?3:5,case_id==20?1:3,1);if(case_id==20)replace_image();else{start(0,cmd_exec,0);delay(5000000000LL);fail(__LINE__);}break;}
 case 22:ordinary(9,SIGUSR1,SI_USER);direct(state.worker[0].tid,SIGUSR2);send_kill(state.worker[0].tid,SIGUSR1,0);pending_all(1,3,1);command(0,cmd_exit,0);join_worker(0);pending_all(1,0,1);mask(all_bits-1);wait_handled(9,1);break;
 case 23:{ordinary(0,SIGUSR1,SI_USER);announce_pipe(0);int c=start(0,cmd_read,all_bits-1);wait_int(&state.worker[0].entered,1);delay(80000000);event("READ_AWAIT",0,state.worker[0].tid);send_kill(state.worker[1].tid,SIGUSR1,0);wait_handled(0,1);if(!restart)wait_int(&state.worker[0].phase,1);delay(80000000);CHECK(!load(&state.worker[0].done));event("READ_AWAIT",1,state.worker[0].tid);event("READ_RELEASE",state.pipe[0][1],81);CHECK(write(state.pipe[0][1],"Q",1)==1);finish_command(0,c);CHECK(close(state.pipe[0][0])==0&&close(state.pipe[0][1])==0);break;}
 case 24:case 25:case 32:{announce_pipe(0);start(0,cmd_read,all_bits);wait_int(&state.worker[0].entered,1);if(case_id!=32)announce_pipe(1);start(1,cmd_kill,0);unsigned char byte=0xa5;int fd=case_id==32?0:state.pipe[1][0];marker("PROCESS_SIGNAL_LEADER_READ " KEY " actor=9 fd=%d console=%d input=%lu bytes=1\n",VALUES,fd,case_id==32,(unsigned long)(uintptr_t)&byte);store(&state.leader_entered,1);CHECK(read(fd,&byte,1)==-999);fail(__LINE__);}
 case 26:{CHECK(getuid()==0&&geteuid()==0);pid_t child=sender_child(1,0);expect(9,SIGUSR1,SI_USER,child,1101);pending_all(1,1,1);mask(all_bits-1);wait_handled(9,1);break;}
 case 27:CHECK(getuid()==0&&geteuid()==0);sender_child(1,1);pending_all(0,0,0);break;
 case 28:disposition(SIGWINCH,0,1);send_kill(state.worker[0].tid,SIGWINCH,0);pending_all(16,16,16);ordinary(0,SIGWINCH,SI_USER);disposition(SIGWINCH,2,1);command(0,cmd_mask,all_bits-16);wait_handled(0,1);break;
 case 29:case 30:case 31:{if(case_id==30)expect(9,rt+1,SI_USER,0,0);for(int i=0;i<32;++i){ordinary(9,rt,SI_USER);send_kill(state.pid,rt,0);}if(case_id==29)send_kill(state.pid,rt,0);else{send_kill(state.pid,rt+1,0);send_kill(state.pid,rt+1,0);}pending_all(case_id==29?4:12,case_id==29?4:12,case_id==29?4:12);if(case_id==30){mask(all_bits-8);wait_handled(9,1);pending_all(4,4,4);}mask(all_bits-4);wait_handled(9,case_id==30?33:32);if(case_id==31){mask(all_bits);pending_all(8,8,8);ordinary(9,rt+1,SI_USER);send_kill(state.pid,rt+1,0);mask(all_bits-8);wait_handled(9,33);}break;}
 default:fail(__LINE__);
 }
 mask(all_bits);for(int i=0;i<2;++i)if(state.worker[i].live)command(i,cmd_mask,all_bits);pending_all(0,0,0);
 for(int i=0;i<3;++i){unsigned got=load(&state.handled[i]);CHECK(case_id==7?(i==2?got==0:got<=1):got==state.expected_count[i]);marker("PROCESS_SIGNAL_TOTAL " KEY " actor=%d handlers=%u\n",VALUES,i==2?9:i,got);}if(case_id==7)CHECK(load(&state.any_handled)==1);
 for(int i=0;i<2;++i)if(state.worker[i].live){command(i,cmd_exit,0);join_worker(i);}marker("PROCESS_SIGNAL_CASE_PASS " KEY "\n",VALUES);
}
static int replacement(int argc,char **argv)
{
 CHECK(argc==8&&dirty==0&&state.pid==0&&actor==-1);variant=atoi(argv[2]);form=atoi(argv[3]);restart=atoi(argv[4]);case_id=atoi(argv[5]);state.pid=atol(argv[6]);state.uid=strtoul(argv[7],0,10);actor=9;CHECK((case_id==20||case_id==21)&&getpid()==state.pid&&tid()==state.pid&&getuid()==state.uid);state.signal[0]=SIGUSR1;state.signal[1]=SIGUSR2;state.signal[2]=SIGRTMIN;state.signal[3]=SIGRTMIN+1;state.signal[4]=SIGWINCH;struct sigaction a;CHECK(sigaction(SIGUSR1,0,&a)==0&&a.sa_handler==SIG_DFL&&sigaction(SIGUSR2,0,&a)==0&&a.sa_handler==SIG_DFL&&sigaction(SIGWINCH,0,&a)==0&&a.sa_handler==SIG_IGN);CHECK(current_mask()==all_bits);event("EXEC_REPLACED",state.pid,tid());pending(3);ordinary(9,SIGUSR2,SI_TKILL);ordinary(9,SIGUSR1,SI_USER);for(unsigned i=0;i<4;++i)disposition(state.signal[i],2,1);mask(all_bits-3);wait_handled(9,2);mask(all_bits);pending(0);event("EXEC_CHECKED",2,all_bits);return 0;
}
int main(int argc,char **argv)
{
 CHECK(argc==1||argc==8);image_path=argv[0];if(argc==8)return replacement(argc,argv);CHECK(__atomic_always_lock_free(sizeof(state.handled[0]),&state.handled[0]));int groups=0,executed=0;
 for(variant=0;variant<2;++variant)for(form=0;form<(variant?1:raw_forms);++form)for(restart=0;restart<2;++restart){++groups;for(case_id=0;case_id<cases;++case_id){
#ifdef PROCESS_SIGNAL_LINUX_REFERENCE
 if(case_id==26||case_id==27||case_id>=29){marker("PROCESS_SIGNAL_LINUX_SKIP " KEY " reason=%s\n",VALUES,case_id==26||case_id==27?"native-credential-policy":case_id==32?"native-console-input-contract":"private-realtime-capacity-policy");continue;}
#endif
 pid_t child=fork();CHECK(child>=0);if(!child){run_case();_Exit(0);}int status=-1;CHECK(waitpid(child,&status,0)==child);int fatal=case_id==24||case_id==25||case_id==32;CHECK(fatal?(WIFSIGNALED(status)&&WTERMSIG(status)==SIGKILL):(WIFEXITED(status)&&WEXITSTATUS(status)==0));marker("PROCESS_SIGNAL_PARENT_PASS " KEY " pid=%ld signal=%d\n",VALUES,(long)child,fatal?SIGKILL:0);++executed;}}
#ifdef PROCESS_SIGNAL_LINUX_REFERENCE
 marker("PROCESS_SIGNAL_LINUX_REFERENCE_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,executed);
#else
 marker("PROCESS_SIGNAL_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,executed);
#endif
 return 0;
}
