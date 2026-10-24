/* Executed synchronous signal-wait ABI and lifecycle assertions. */
#include "signal_wait_guest.h"

static void worker_pending(int which,unsigned value){command(which,pending_command,value);}
static void worker_mask(int which,unsigned value){command(which,mask_command,value);}
static void empty_poll(unsigned wanted){receive_now(wanted,-EAGAIN,0,0,0);}
static int begin_wait(int which){int c=start(which,wait_command,0);observe_wait(which,0);return c;}
static void release_wait(int which,int c,int process,int signal)
{send_signal(process,state.workers[which].tid,signal);finish_command(which,c);}
static void tick_still_waiting(int which,unsigned phase)
{delay(20000000);observe_wait(which,phase);CHECK(!load(&state.workers[which].op.done));}
static void timed_cases(void)
{
 struct operation op;int c=0;
 switch(case_id){
 case 0:{
  prepare(&op,1,0,0,-EINVAL,0,0,0);op.set=(void *)1;op.size=kernel_set_bytes-1;op.check_inputs=0;call_wait(&op);
  op.size=kernel_set_bytes;op.expected=-EFAULT;op.set=0;call_wait(&op);
  unsigned char *p=pages();protect(p+4096,0);op.set=(void *)(p+4096-kernel_set_bytes/2);call_wait(&op);protect(p+4096,1);pending(0);break;}
 case 1:
  send_signal(0,state.pid,SIGUSR1);pending(1);prepare(&op,1,0,0,-EFAULT,0,0,0);op.timeout=(void *)1;op.check_inputs=0;call_wait(&op);pending(1);
  receive_now(1,SIGUSR1,SI_TKILL,state.pid,state.uid);break;
 case 2:{
  send_signal(0,state.pid,SIGUSR1);pending(1);prepare(&op,1,0,0,-EINVAL,0,0,0);
  int64_t values[][2]={{-1,0},{0,-1},{0,1000000000LL},{0,4294967296LL}};
  unsigned count=sizeof(long)==8?4:3;
  for(unsigned i=0;i<count;++i){timeout_value(&op,values[i][0],values[i][1]);call_wait(&op);pending(1);}
  receive_now(1,SIGUSR1,SI_TKILL,state.pid,state.uid);break;}
 case 3:
  prepare(&op,0,0,0,-EAGAIN,0,0,0);op.info=(void *)1;op.check_info=0;call_wait(&op);
  CHECK(sigaddset(&op.set_storage,SIGKILL)==0&&sigaddset(&op.set_storage,SIGSTOP)==0);call_wait(&op);pending(0);break;
 case 4:
  send_signal(0,state.pid,SIGUSR1);pending(1);receive_now(1,SIGUSR1,SI_TKILL,state.pid,state.uid);pending(0);break;
 case 5:{
  pid_t sender=sender_child(SIGUSR1,0);pending(1);receive_now(1,SIGUSR1,SI_USER,sender,state.uid);pending(0);break;}
 case 6:
  send_signal(1,state.pid,SIGUSR1);send_signal(0,state.pid,SIGUSR1);pending(1);
  receive_now(3,SIGUSR1,SI_TKILL,state.pid,state.uid);pending(1);receive_now(3,SIGUSR1,SI_USER,state.pid,state.uid);
  send_signal(1,state.pid,SIGUSR1);send_signal(0,state.pid,SIGUSR2);pending(3);
  receive_now(3,SIGUSR2,SI_TKILL,state.pid,state.uid);receive_now(3,SIGUSR1,SI_USER,state.pid,state.uid);
  send_signal(0,state.pid,SIGUSR2);send_signal(0,state.pid,SIGUSR1);
  receive_now(3,SIGUSR1,SI_TKILL,state.pid,state.uid);receive_now(3,SIGUSR2,SI_TKILL,state.pid,state.uid);
  send_signal(1,state.pid,SIGUSR2);send_signal(1,state.pid,SIGUSR1);
  receive_now(3,SIGUSR1,SI_USER,state.pid,state.uid);receive_now(3,SIGUSR2,SI_USER,state.pid,state.uid);empty_poll(3);break;
 case 7:
  action(SIGUSR1,1);send_signal(0,state.pid,SIGUSR1);pending(1);receive_now(1,SIGUSR1,SI_TKILL,state.pid,state.uid);break;
 case 8:
  action(SIGUSR1,0);send_signal(0,state.pid,SIGUSR1);pending(1);receive_now(1,SIGUSR1,SI_TKILL,state.pid,state.uid);break;
 case 9:
  send_signal(0,state.pid,SIGUSR1);prepare(&op,1,0,0,SIGUSR1,SI_TKILL,state.pid,state.uid);op.info=0;call_wait(&op);empty_poll(1);
  if(api){send_signal(0,state.pid,SIGUSR1);prepare(&op,1,-1,0,SIGUSR1,SI_TKILL,state.pid,state.uid);op.library=1;call_wait(&op);
   send_signal(0,state.pid,SIGUSR1);prepare(&op,1,-1,0,SIGUSR1,SI_TKILL,state.pid,state.uid);op.library=2;call_wait(&op);empty_poll(1);}break;
 case 10:
  send_signal(0,state.pid,SIGUSR1);prepare(&op,1,0,0,SIGUSR1,SI_TKILL,state.pid,state.uid);op.info=&op.set_storage;call_wait(&op);empty_poll(1);break;
 case 11:
  send_signal(0,state.pid,SIGUSR1);prepare(&op,1,0,0,-EFAULT,0,0,0);op.info=(void *)1;op.check_info=0;call_wait(&op);pending(0);empty_poll(1);break;
 case 12:{
  unsigned char *p=pages();protect(p+4096,0);send_signal(0,state.pid,SIGUSR1);prepare(&op,1,0,0,-EFAULT,0,0,0);op.info=p+4096-64;op.check_info=0;call_wait(&op);CHECK(p[4096-65]==0xa5);protect(p+4096,1);CHECK(p[4096+64]==0xa5);event("STRADDLE_GUARDS",2,0);pending(0);empty_poll(1);break;}
 case 13:
  spawn(0);worker_request(0,1,0,250000000,-EAGAIN,0);c=begin_wait(0);finish_command(0,c);worker_pending(0,0);break;
 case 14:case 15:
  spawn(0);worker_request(0,1,-1,0,SIGUSR1,case_id==14?SI_TKILL:SI_USER);c=begin_wait(0);release_wait(0,c,case_id==15,SIGUSR1);worker_pending(0,0);break;
 case 16:{
  spawn(0);spawn(1);worker_request(0,3,-1,0,SIGUSR1,SI_USER);worker_request(1,3,-1,0,SIGUSR1,SI_USER);
  state.workers[0].op.any_signal=state.workers[1].op.any_signal=1;int c0=begin_wait(0),c1=begin_wait(1);send_signal(1,state.pid,SIGUSR1);
  int64_t begin=now();while(!load(&state.workers[0].op.done)&&!load(&state.workers[1].op.done))CHECK(now()-begin<5000000000LL);
  int winner=load(&state.workers[0].op.done)?0:1;CHECK(!load(&state.workers[1-winner].op.done));CHECK(state.workers[winner].op.value==SIGUSR1);event("WINNER",winner,SIGUSR1);
  observe_wait(1-winner,1);send_signal(1,state.pid,SIGUSR2);finish_command(0,c0);finish_command(1,c1);CHECK(state.workers[1-winner].op.value==SIGUSR2);worker_pending(0,0);worker_pending(1,0);break;}
 case 17:
  spawn(0);worker_mask(0,29);want_handler(0,SIGUSR2,SI_TKILL,31,29);worker_request(0,1,-1,0,api?SIGUSR1:-EINTR,SI_TKILL);state.workers[0].op.expected_mask=29;c=begin_wait(0);
  send_signal(0,state.workers[0].tid,SIGUSR2);wait_count(&state.handler_done[0],1);if(api){observe_wait(0,1);send_signal(0,state.workers[0].tid,SIGUSR1);}finish_command(0,c);worker_mask(0,31);break;
 case 18:
  spawn(0);worker_mask(0,15);
  for(unsigned kind=0;kind<2;++kind){action(SIGWINCH,kind);worker_request(0,1,-1,0,api?SIGUSR1:-EINTR,SI_TKILL);state.workers[0].op.expected_mask=15;c=begin_wait(0);
   send_signal(1,state.workers[0].tid,SIGWINCH);pending(0);tick_still_waiting(0,1);event("IGNORED_DROP_OBSERVED",kind,0);
   send_signal(1,state.pid,SIGWINCH);if(api){tick_still_waiting(0,2);send_signal(0,state.workers[0].tid,SIGUSR1);}finish_command(0,c);pending(0);CHECK(load(&state.handled[0])==0);event("IGNORED_INTERRUPT_OBSERVED",kind,api);}
  worker_mask(0,31);break;
 case 19:{
  unsigned char *p=pages();sigset_t m=make_mask(1);memcpy(p,&m,sizeof(m));spawn(0);worker_request(0,1,-1,0,SIGUSR1,SI_TKILL);state.workers[0].op.set=(void *)p;state.workers[0].op.check_inputs=0;c=begin_wait(0);
  m=make_mask(2);memcpy(p,&m,sizeof(m));event("MUTATE_SET",(long)(uintptr_t)p,2);protect(p,0);release_wait(0,c,0,SIGUSR1);protect(p,1);break;}
 case 20:
  spawn(0);worker_request(0,1,0,250000000,-EAGAIN,0);state.workers[0].op.check_inputs=0;c=begin_wait(0);timeout_value(&state.workers[0].op,10,0);event("MUTATE_TIMEOUT",10,0);finish_command(0,c);break;
 case 21:{
  pid_t senders[3];for(unsigned i=0;i<3;++i)senders[i]=sender_child(state.signals[2],i);pending(4);
  for(unsigned i=0;i<3;++i){receive_now(4,state.signals[2],SI_USER,senders[i],state.uid);}empty_poll(4);break;}
 case 22:case 23:
#ifndef SIGNAL_WAIT_LINUX_REFERENCE
  for(unsigned i=0;i<32;++i){send_signal(1,state.pid,state.signals[2]);}send_signal(1,state.pid,state.signals[3]);pending(12);
  if(case_id==22){receive_now(8,state.signals[3],SI_USER,0,0);for(unsigned i=0;i<32;++i)receive_now(4,state.signals[2],SI_USER,state.pid,state.uid);}
  else{receive_now(4,state.signals[2],SI_USER,state.pid,state.uid);send_signal(1,state.pid,state.signals[3]);receive_now(8,state.signals[3],SI_USER,state.pid,state.uid);for(unsigned i=0;i<31;++i)receive_now(4,state.signals[2],SI_USER,state.pid,state.uid);}
  empty_poll(12);break;
#else
  fail(__LINE__);
#endif
 case 24:case 25:
  action(SIGUSR1,1);spawn(0);worker_request(0,1,-1,0,SIGUSR1,case_id==24?SI_TKILL:SI_USER);c=begin_wait(0);release_wait(0,c,case_id==25,SIGUSR1);break;
 case 26:
  action(SIGUSR1,1);spawn(0);worker_request(0,1,-1,0,SIGUSR1,SI_USER);c=begin_wait(0);mask(30);send_signal(1,state.pid,SIGUSR1);tick_still_waiting(0,1);pending(0);mask(31);release_wait(0,c,1,SIGUSR1);break;
 case 27:
  spawn(0);send_signal(0,state.workers[0].tid,SIGUSR2);worker_pending(0,2);worker_request(0,1,-1,0,SIGUSR1,SI_TKILL);c=begin_wait(0);action(SIGUSR2,1);tick_still_waiting(0,1);release_wait(0,c,0,SIGUSR1);worker_pending(0,0);break;
 case 28:
  spawn(0);spawn(1);worker_request(0,1,-1,0,SIGUSR1,SI_TKILL);begin_wait(0);start(1,exec_command,31);for(;;)(void)now();
 case 29:
  spawn(0);worker_request(0,1,-1,0,SIGUSR1,SI_TKILL);begin_wait(0);send_signal(1,state.workers[0].tid,SIGKILL);fail(__LINE__);
 case 30:{
  spawn(0);worker_request(0,1,-1,0,SIGUSR1,SI_TKILL);c=begin_wait(0);pid_t child=fork();CHECK(child>=0);
  if(!child){actor=8;sigset_t p;CHECK(current_mask()==31&&sigpending(&p)==0&&bits(&p)==0);event("FORK_EMPTY",getpid(),current_mask());_Exit(17);}
  int status;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==17);event("FORK_REAP",child,17);
  spawn(1);worker_request(1,2,-1,0,SIGUSR2,SI_TKILL);int c1=begin_wait(1);release_wait(1,c1,0,SIGUSR2);tick_still_waiting(0,1);release_wait(0,c,0,SIGUSR1);break;}
 case 31:{
  int64_t seconds=api?((int64_t)INT32_MAX+10):(time_bytes()==16?INT64_MAX:INT32_MAX);
  int64_t nanoseconds=!api&&timeabi==1&&sizeof(long)==4?4294967296LL:0;
  spawn(0);worker_request(0,1,seconds,nanoseconds,SIGUSR1,SI_TKILL);event("HUGE_TIMEOUT",sizeof(long),timeabi);c=begin_wait(0);release_wait(0,c,0,SIGUSR1);break;}
 default:fail(__LINE__);
 }
}

static void suspend_cases(void)
{
 struct operation op;int c=0;unsigned temporary=24;
 if(case_id==0||case_id==1){
  prepare(&op,temporary,-1,0,case_id?-EFAULT:-EINVAL,0,0,0);op.set=(void *)1;op.check_inputs=0;if(!case_id)op.size=kernel_set_bytes-1;call_wait(&op);
  if(case_id){op.set=0;call_wait(&op);unsigned char *p=pages();protect(p+4096,0);op.set=(void *)(p+4096-kernel_set_bytes/2);call_wait(&op);protect(p+4096,1);}pending(0);return;
 }
 if(case_id>=2&&case_id<=4){
  if(case_id==4){temporary=26;send_signal(0,state.pid,SIGUSR2);}
  send_signal(case_id!=2,state.pid,SIGUSR1);pending(case_id==4?3:1);want_handler(9,SIGUSR1,case_id==2?SI_TKILL:SI_USER,temporary|5,31);
  prepare(&op,temporary,-1,0,-EINTR,0,0,0);call_wait(&op);pending(case_id==4?2:0);
  if(case_id==4){prepare(&op,2,0,0,SIGUSR2,SI_TKILL,state.pid,state.uid);op.timed_override=1;call_wait(&op);}return;
 }
 spawn(0);
 if(case_id==9){
  for(unsigned kind=0;kind<2;++kind){action(SIGWINCH,kind);send_signal(1,state.pid,SIGWINCH);pending(16);worker_request(0,8,-1,0,-EINTR,0);want_handler(0,SIGUSR1,SI_TKILL,13,31);c=begin_wait(0);
   pending(0);event("IGNORED_DRAIN_OWNED",kind,0);tick_still_waiting(0,1);release_wait(0,c,0,SIGUSR1);worker_pending(0,0);}return;
 }
 if(case_id==13)action(SIGWINCH,1);
 int ignored=(case_id==7||case_id==8||case_id==10);int released=ignored?SIGUSR2:SIGUSR1;
 if(case_id==7||case_id==8)action(SIGUSR1,1);
 worker_request(0,temporary,-1,0,-EINTR,0);
 if(case_id==11){unsigned char *p=pages();sigset_t m=make_mask(temporary);memcpy(p,&m,sizeof(m));state.workers[0].op.set=(void *)p;state.workers[0].op.check_inputs=0;}
 if(case_id!=14&&case_id!=15)want_handler(0,released,case_id==6?SI_USER:SI_TKILL,temporary|4|(released==SIGUSR1?1:2),31);
 c=begin_wait(0);
 switch(case_id){
 case 5:case 6:case 12:case 13:case 16:
  send_signal(case_id==6,state.workers[0].tid,released);
  if(case_id==13)for(;;)(void)now();
  if(case_id==16){join_worker(0,1);CHECK(!load(&state.workers[0].op.done));event("HANDLER_EXIT_NO_RETURN",0,0);}else finish_command(0,c);break;
 case 7:case 8:case 10:
  if(case_id==10){action(SIGUSR1,1);}send_signal(case_id==8,state.workers[0].tid,SIGUSR1);tick_still_waiting(0,1);pending(0);event("SUSPEND_IGNORED_DROP",case_id,0);release_wait(0,c,0,SIGUSR2);break;
 case 11:{
  sigset_t m=make_mask(31);memcpy(state.mapping,&m,sizeof(m));event("MUTATE_SET",(long)(uintptr_t)state.mapping,31);protect(state.mapping,0);release_wait(0,c,0,SIGUSR1);protect(state.mapping,1);break;}
 case 14:
  spawn(1);start(1,exec_command,31);for(;;)(void)now();
 case 15:
  send_signal(1,state.workers[0].tid,SIGKILL);fail(__LINE__);
 default:fail(__LINE__);
 }
}

static void initialize(void)
{
 memset(&state,0,sizeof(state));actor=9;call_ordinal=send_ordinal=pending_ordinal=0;numbers();state.pid=getpid();state.uid=getuid();dirty=1;
 state.site=(uintptr_t)poll_signal_site;state.resume=(uintptr_t)poll_signal_resume;
#if defined(__arm__)
 if(form){state.site=(uintptr_t)poll_signal_thumb_site;state.resume=(uintptr_t)poll_signal_thumb_resume;}
#endif
 marker("SIGNAL_WAIT_CHILD " KEY " pid=%ld tid=%ld uid=%lu size=%d rtmin=%d site=%lu resume=%lu\n",VALUES,(long)state.pid,(long)tid(),(unsigned long)state.uid,kernel_set_bytes,state.signals[2],(unsigned long)state.site,(unsigned long)state.resume);
 mask(31);for(unsigned i=0;i<5;++i)action(state.signals[i],2);pending(0);
}
static void cleanup(void)
{
 for(int i=0;i<2;++i)if(state.workers[i].live){worker_pending(i,0);command(i,exit_command,0);join_worker(i,0);}
 CHECK(current_mask()==31);pending(0);for(unsigned i=0;i<3;++i)CHECK(load(&state.handled[i])==state.expected_count[i]);
 if(state.mapping){CHECK(munmap(state.mapping,3*4096)==0);event("UNMAP",3*4096,0);}
 marker("SIGNAL_WAIT_CASE_PASS " KEY " pid=%ld handlers0=%u handlers1=%u handlers9=%u\n",VALUES,(long)state.pid,load(&state.handled[0]),load(&state.handled[1]),load(&state.handled[2]));
}
static void replacement(int argc,char **argv)
{
 CHECK(argc==10);family=atoi(argv[2]);api=atoi(argv[3]);timeabi=atoi(argv[4]);form=atoi(argv[5]);restart=atoi(argv[6]);case_id=atoi(argv[7]);pid_t previous=atoi(argv[8]);unsigned expected=(unsigned)atoi(argv[9]);
 CHECK(!dirty&&actor==-1&&getpid()==previous&&tid()==previous);actor=9;numbers();CHECK(current_mask()==expected);sigset_t p;CHECK(sigpending(&p)==0&&bits(&p)==0);
 struct sigaction a;CHECK(sigaction(SIGUSR1,0,&a)==0&&a.sa_handler==SIG_DFL);if(family&&case_id==13)CHECK(sigaction(SIGWINCH,0,&a)==0&&a.sa_handler==SIG_IGN);
 marker("SIGNAL_WAIT_REPLACED " KEY " pid=%ld tid=%ld mask=%u pending=0 dirty=0 tls=-1 caught_reset=1 ignored_retained=%d\n",VALUES,(long)getpid(),(long)tid(),current_mask(),family&&case_id==13);_Exit(0);
}
static unsigned completed,excluded;
static void run_case(void)
{
#ifdef SIGNAL_WAIT_LINUX_REFERENCE
 if(!family&&(case_id==22||case_id==23)){marker("SIGNAL_WAIT_EXCLUDED " KEY " reason=private-32-payload-capacity\n",VALUES);++excluded;return;}
#endif
 marker("SIGNAL_WAIT_CASE_BEGIN " KEY " parent=%ld\n",VALUES,(long)getpid());pid_t child=fork();CHECK(child>=0);
 if(!child){initialize();if(family)suspend_cases();else timed_cases();cleanup();_Exit(0);}
 int status;CHECK(waitpid(child,&status,0)==child);int fatal=family?case_id==15:case_id==29;
 CHECK(fatal?(WIFSIGNALED(status)&&WTERMSIG(status)==SIGKILL):(WIFEXITED(status)&&WEXITSTATUS(status)==0));
 marker("SIGNAL_WAIT_PARENT_PASS " KEY " child=%ld exit=%d signal=%d\n",VALUES,(long)child,fatal?-1:0,fatal?SIGKILL:0);++completed;
}
int main(int argc,char **argv)
{
 image_path=argv[0];if(argc>1&&strcmp(argv[1],"wait-replaced")==0){replacement(argc,argv);return 1;}
 CHECK(argc==1);marker("SIGNAL_WAIT_START arch=%s pid=%ld pointer_bits=%u raw_forms=%d raw_time_begin=%d raw_time_end=%d\n",PROBE_ARCH,(long)getpid(),(unsigned)sizeof(void *)*8,raw_forms,raw_time_begin,raw_time_end);
 for(restart=0;restart<2;++restart){family=0;api=0;
  for(timeabi=raw_time_begin;timeabi<raw_time_end;++timeabi)for(form=0;form<raw_forms;++form)for(case_id=0;case_id<32;++case_id)run_case();
  api=1;timeabi=2;form=0;for(case_id=4;case_id<32;++case_id)run_case();
  family=1;api=0;timeabi=3;for(form=0;form<raw_forms;++form)for(case_id=0;case_id<17;++case_id)run_case();
  api=1;form=0;for(case_id=2;case_id<17;++case_id)run_case();
 }
 marker("SIGNAL_WAIT_PASS arch=%s cases=%u excluded=%u semantic_cases=49\n",PROBE_ARCH,completed,excluded);return 0;
}
