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
#error "Unsupported complete pipe write profile"
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
enum {cases=26,capacity=4096,mapping_bytes=65536};
static int vector,variant,form,restart,case_id,dirty;
static const char *image_path;
static _Thread_local int actor=-1;
struct writer {pid_t tid;int pipe[2],replacement[2],saved;unsigned char *mapping,*payload[4];struct iovec *vectors,original[5];unsigned long args[6],admitted[6],count;_Atomic int ready,go,entered,done,phase;long result;int error;unsigned read_offset,read_ordinal;};
static struct {pid_t pid;uid_t uid;struct writer w[2];uintptr_t site,resume;_Atomic int handled;} state;
static long operation(void){return vector?SYS_writev:SYS_write;}
static __attribute__((noreturn)) void fail(int code)
{char b[]="PIPE_BLOCKING_FAIL code=000\n";unsigned p=sizeof("PIPE_BLOCKING_FAIL code=")-1;b[p]='0'+code/100%10;b[p+1]='0'+code/10%10;b[p+2]='0'+code%10;thread_syscall4(SYS_write,1,(uintptr_t)b,sizeof(b)-1,0);thread_syscall4(SYS_exit_group,1,0,0,0);for(;;){}}
#define CHECK(c,n) do{if(!(c))fail(n);}while(0)
static __attribute__((format(printf,1,2))) void marker(const char *format,...)
{char b[1536];va_list ap;va_start(ap,format);int n=vsnprintf(b,sizeof(b),format,ap);va_end(ap);CHECK(n>0&&(size_t)n<sizeof(b),101);CHECK(thread_syscall4(SYS_write,1,(uintptr_t)b,n,0)==n,102);}
#define KEY "arch=%s vector=%d variant=%d form=%d restart=%d case=%d"
#define VALUES PROBE_ARCH,vector,variant,form,restart,case_id
static void event(const char *tag,int stream,int ordinal,long value){marker("PIPE_BLOCKING_%s " KEY " actor=%d stream=%d ordinal=%d value=%ld\n",tag,VALUES,actor,stream,ordinal,value);}
static int64_t now(void){struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,103);return (int64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void delay(int64_t ns){int64_t t=now();while(now()-t<ns){}}
static void wait_word(_Atomic int *p,int value){int64_t t=now();while(load(p)!=value)CHECK(now()-t<5000000000LL,104);}
static unsigned char value(unsigned offset,int stream){unsigned char b=(unsigned char)(offset*17u+(offset/4096u)*53u+31u+stream*97u);return case_id==11&&offset>=4096?(unsigned char)(b^0x5a):b;}
static unsigned char original_value(unsigned offset,int stream){return (unsigned char)(offset*17u+(offset/4096u)*53u+31u+stream*97u);}
static long raw(struct writer *w){
#if defined(__arm__)
 if(form)return poll_signal_thumb(operation(),w->args,0);
#endif
 return poll_signal_raw(operation(),w->args,form);
}
static long invoke(struct writer *w){return variant?(vector?writev((int)w->args[0],(void *)(uintptr_t)w->args[1],(int)w->args[2]):write((int)w->args[0],(void *)(uintptr_t)w->args[1],w->args[2])):raw(w);}
static void nonblocking(int fd){int flags=fcntl(fd,F_GETFL);CHECK(flags>=0&&fcntl(fd,F_SETFL,flags|O_NONBLOCK)==0,105);}
static void handle(int signal,siginfo_t *info,void *context)
{
 int saved=errno;ucontext_t *c=context;struct writer *w=&state.w[0];CHECK(actor==0&&info&&c&&thread_syscall4(SYS_gettid,0,0,0,0)==w->tid&&!load(&state.handled),201);CHECK(info->si_signo==signal&&info->si_errno==0&&info->si_pid==state.pid&&info->si_uid==state.uid&&info->si_code==(signal==SIGPIPE?SI_USER:SI_TKILL),202);
 int again=case_id==3&&restart;long expected=case_id==3?-EINTR:case_id==4||case_id==17?4096:case_id==5||case_id==6?8192:case_id==7?-EPIPE:0;CHECK(signal==(case_id==6||case_id==7?SIGPIPE:SIGUSR1),203);
 CHECK((uintptr_t)CTX_BUFFER(c)==w->admitted[1]&&(uintptr_t)CTX_COUNT(c)==w->admitted[2],204);if(!variant)CHECK((uintptr_t)CTX_PC(c)==(again?state.site:state.resume),205);
 if(again){CHECK((uintptr_t)CTX_NUMBER(c)==(uintptr_t)operation()&&(uintptr_t)CTX_FD(c)==w->admitted[0],206);if(!variant)CHECK((uintptr_t)CTX_TIMEOUT(c)==w->admitted[3],207);}else CHECK(context_result(c)==expected,208);
#if defined(__arm__)
 if(!variant)CHECK(((c->uc_mcontext.arm_cpsr&0x20)!=0)==(form==1),209);
#endif
 unsigned long abi=0;
#if defined(__mips__)
 abi=c->uc_mcontext.gregs[7];
#elif defined(__powerpc__)
 abi=c->uc_regs->gregs[38];
#elif defined(__arm__)
 abi=c->uc_mcontext.arm_cpsr;
#endif
 marker("PIPE_BLOCKING_HANDLE " KEY " actor=0 stream=0 pid=%ld tid=%ld signal=%d code=%d sender=%ld uid=%lu again=%d pc=%lu result=%ld number=%lu a0=%lu a1=%lu a2=%lu a3=%lu abi=%lu\n",VALUES,(long)state.pid,(long)w->tid,signal,info->si_code,(long)info->si_pid,(unsigned long)info->si_uid,again,(unsigned long)(uintptr_t)CTX_PC(c),again?0:context_result(c),(unsigned long)(uintptr_t)CTX_NUMBER(c),(unsigned long)(uintptr_t)CTX_FD(c),(unsigned long)(uintptr_t)CTX_BUFFER(c),(unsigned long)(uintptr_t)CTX_COUNT(c),(unsigned long)(uintptr_t)CTX_TIMEOUT(c),abi);
 store(&state.handled,1);if(case_id==17){event("THREAD_EXIT",0,0,4096);pthread_exit((void *)(uintptr_t)0x996);fail(210);}event("HANDLER_RETURN",0,0,signal);errno=saved;
}
static long expected_result(struct writer *w){return case_id==4||case_id==8||case_id==14||case_id==22?4096:case_id==5||case_id==6||case_id==13?8192:case_id==7?(variant?-1:-EPIPE):case_id==23?(variant?-1:-EAGAIN):case_id==24?0:(long)w->count;}
static void *worker(void *arg)
{
 actor=(int)(uintptr_t)arg;struct writer *w=&state.w[actor];w->tid=thread_syscall4(SYS_gettid,0,0,0,0);sigset_t mask;CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,106);store(&w->ready,1);wait_word(&w->go,1);event("ATTEMPT",actor,0,operation());errno=111;store(&w->entered,1);w->result=invoke(w);w->error=errno;event("RETURN",actor,0,w->result);event("ERRNO",actor,0,w->error);
 if(case_id==3&&!restart){CHECK(w->result==(variant?-1:-EINTR)&&w->error==(variant?EINTR:111)&&load(&state.handled),107);event("RETRY",actor,1,operation());errno=111;store(&w->phase,1);w->result=invoke(w);w->error=errno;event("RETURN",actor,1,w->result);event("ERRNO",actor,1,w->error);}
 int code=case_id==7?EPIPE:case_id==23?EAGAIN:0;CHECK(w->result==expected_result(w)&&w->error==(variant&&w->result==-1?code:111),108);CHECK(load(&state.handled)==(case_id==3||case_id==4||case_id==5||case_id==6||case_id==7),109);sigset_t pending;CHECK(sigpending(&pending)==0&&sigismember(&pending,SIGPIPE)==0&&sigismember(&pending,SIGUSR1)==0,110);event("WORKER_PASS",actor,0,w->result);store(&w->done,1);return (void *)(uintptr_t)0x995;
}
static void confirm(int stream,unsigned committed,int phase)
{
 struct writer *w=&state.w[stream];wait_word(&w->entered,1);
#ifdef PIPE_BLOCKING_LINUX_REFERENCE
 char path[128];CHECK(snprintf(path,sizeof(path),"/proc/self/task/%ld/syscall",(long)w->tid)>0,111);int64_t start=now();int seen=0;while(!seen){char b[384];int fd=open(path,O_RDONLY);CHECK(fd>=0,112);ssize_t n=read(fd,b,sizeof(b)-1);CHECK(n>=0&&close(fd)==0,113);b[n]=0;long nr=-1;unsigned long a[6]={0};int available=-1;CHECK(ioctl(w->pipe[0],FIONREAD,&available)==0,114);if(sscanf(b,"%ld %lx %lx %lx %lx %lx %lx",&nr,a,a+1,a+2,a+3,a+4,a+5)==7){seen=nr==operation()&&available==(case_id==21&&phase==1?capacity-1:capacity);for(unsigned i=0;i<3;++i)seen=seen&&a[i]==w->admitted[i];}CHECK(!load(&w->done)&&now()-start<5000000000LL,115);}marker("PIPE_BLOCKING_LINUX_WAIT " KEY " actor=9 stream=%d phase=%d pid=%ld tid=%ld syscall=%ld committed=%u\n",VALUES,stream,phase,(long)state.pid,(long)w->tid,operation(),committed);
#else
 delay(60000000);
#endif
 CHECK(!load(&w->done),116);event("AWAIT",stream,phase,committed);
}
static void read_bytes(int stream,unsigned count,int fill)
{
 struct writer *w=&state.w[stream];unsigned before=w->read_offset;uint32_t checksum=5381;unsigned left=count;marker("PIPE_BLOCKING_READ_BEGIN " KEY " actor=9 stream=%d ordinal=%u fill=%d offset=%u bytes=%u\n",VALUES,stream,w->read_ordinal,fill,before,count);unsigned char b[4096];while(left){unsigned amount=left<sizeof(b)?left:sizeof(b);ssize_t n=read(w->pipe[0],b,amount);CHECK(n>0&&(unsigned)n<=amount,117);for(ssize_t i=0;i<n;++i){CHECK(b[i]==(fill?241:value(w->read_offset,stream)),118);checksum=(checksum*33u)^b[i];if(!fill)++w->read_offset;}left-=n;}
 marker("PIPE_BLOCKING_BYTES " KEY " actor=9 stream=%d ordinal=%u fill=%d offset=%u bytes=%u checksum=%u\n",VALUES,stream,w->read_ordinal++,fill,before,count,checksum);
}
static void finish_stream(int stream)
{struct writer *w=&state.w[stream];while(w->read_offset<w->count){unsigned left=w->count-w->read_offset;unsigned amount=left<capacity?left:capacity;if(left<=capacity)wait_word(&w->done,1);read_bytes(stream,amount,0);if(w->read_offset<w->count){unsigned next=w->read_offset+capacity;if(next<w->count)confirm(stream,next,10+w->read_offset/capacity);else wait_word(&w->done,1);}}}
static void empty(int fd,int stream){unsigned char b;nonblocking(fd);errno=0;CHECK(read(fd,&b,1)==-1&&errno==EAGAIN,119);event("EMPTY",stream,0,fd);}
static void proof(int stream)
{
 struct writer *w=&state.w[stream];for(unsigned off=0;off<mapping_bytes;++off){unsigned char expected=0xa5;for(unsigned page=0;page<4;++page){unsigned start=(unsigned)(w->payload[page]-w->mapping);unsigned logical=page*capacity;unsigned length=w->count>logical?w->count-logical:0;if(length>capacity)length=capacity;if(off>=start&&off<start+length)expected=value(logical+off-start,stream);}if(off>=40960&&off<40960+5*sizeof(struct iovec))continue;CHECK(w->mapping[off]==expected,120);}
 if(case_id!=9||!vector)CHECK(!memcmp(w->vectors,w->original,sizeof(w->original)),121);event("BUFFER",stream,0,mapping_bytes);
}
static void setup_writer(int stream,unsigned count,int full)
{
 struct writer *w=&state.w[stream];w->saved=-1;w->replacement[0]=w->replacement[1]=-1;w->count=count;w->mapping=mmap(0,mapping_bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);CHECK(w->mapping!=MAP_FAILED,122);memset(w->mapping,0xa5,mapping_bytes);for(unsigned page=0;page<4;++page){w->payload[page]=w->mapping+4096+page*(vector?8192:4096);unsigned logical=page*capacity;unsigned n=count>logical?count-logical:0;if(n>capacity)n=capacity;for(unsigned i=0;i<n;++i)w->payload[page][i]=original_value(logical+i,stream);}
 w->vectors=(struct iovec *)(w->mapping+40960);w->vectors[0]=(struct iovec){(void *)1,0};for(unsigned page=0;page<4;++page){unsigned logical=page*capacity;unsigned n=count>logical?count-logical:0;if(n>capacity)n=capacity;w->vectors[page+1]=(struct iovec){w->payload[page],n};}memcpy(w->original,w->vectors,sizeof(w->original));CHECK(pipe(w->pipe)==0,123);
#ifdef PIPE_BLOCKING_LINUX_REFERENCE
 CHECK(fcntl(w->pipe[1],F_SETPIPE_SZ,capacity)==capacity&&fcntl(w->pipe[1],F_GETPIPE_SZ)==capacity,124);
#endif
 if(full){unsigned char b[capacity];memset(b,241,sizeof(b));CHECK(write(w->pipe[1],b,sizeof(b))==capacity,125);}
 if(case_id==12||case_id==13||case_id==14||case_id==15){w->saved=dup(w->pipe[1]);CHECK(w->saved>=0,126);}if(case_id==12||case_id==15)CHECK(pipe(w->replacement)==0,127);if(case_id==22||case_id==23)nonblocking(w->pipe[1]);if(case_id==24){CHECK(close(w->pipe[0])==0,128);w->pipe[0]=-1;}
 w->args[0]=w->pipe[1];w->args[1]=vector?(uintptr_t)w->vectors:(uintptr_t)w->payload[0];w->args[2]=vector?5:count;w->args[3]=0x1357;memcpy(w->admitted,w->args,sizeof(w->args));
}
static void send_signal(int signal){event("SEND",0,0,signal);CHECK(thread_syscall4(SYS_tgkill,state.pid,state.w[0].tid,signal,0)==0,129);}
static __attribute__((noreturn)) void replace_image(void)
{
 char v[16],a[16],f[16],r[16],c[16],rd[16],wr[16];CHECK(dirty==1,130);snprintf(v,sizeof(v),"%d",vector);snprintf(a,sizeof(a),"%d",variant);snprintf(f,sizeof(f),"%d",form);snprintf(r,sizeof(r),"%d",restart);snprintf(c,sizeof(c),"%d",case_id);snprintf(rd,sizeof(rd),"%d",state.w[0].pipe[0]);snprintf(wr,sizeof(wr),"%d",state.w[0].pipe[1]);char *args[]={(char *)image_path,"blocking-replaced",v,a,f,r,c,rd,wr,0};char *env[]={0};CHECK(thread_syscall4(SYS_execve,(uintptr_t)"/bin/no-blocking-image",(uintptr_t)args,(uintptr_t)env,0)==-ENOENT,131);event("EXEC_FAILED",0,0,ENOENT);event("EXEC_COMMIT",0,0,state.pid);thread_syscall4(SYS_execve,(uintptr_t)image_path,(uintptr_t)args,(uintptr_t)env,0);fail(132);
}
static void run_case(void)
{
 memset(&state,0,sizeof(state));actor=9;dirty=1;state.pid=getpid();state.uid=getuid();state.site=(uintptr_t)poll_signal_site;state.resume=(uintptr_t)poll_signal_resume;
#if defined(__arm__)
 if(form){state.site=(uintptr_t)poll_signal_thumb_site;state.resume=(uintptr_t)poll_signal_thumb_resume;}
#endif
 sigset_t mask;CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,133);struct sigaction a={0};a.sa_sigaction=handle;a.sa_flags=SA_SIGINFO|(restart?SA_RESTART:0);CHECK(sigemptyset(&a.sa_mask)==0&&sigaction(SIGPIPE,&a,0)==0,134);if(case_id==16)a.sa_handler=SIG_IGN;if(case_id==20)a.sa_handler=SIG_DFL;CHECK(sigaction(SIGUSR1,&a,0)==0,135);
 unsigned count=case_id==1?12289:case_id==2?8193:case_id==21?4096:case_id==24?0:12288;int full=case_id==1||case_id==3||case_id==7||case_id==12||case_id==14||case_id==15||case_id==21||case_id==23;int streams=case_id==25?2:1;pthread_t threads[2];
 /* Bound both worker mappings within the native 128-page process budget. The
    64 KiB stacks retain headroom for libc formatting and caught signal frames. */
 pthread_attr_t attributes;CHECK(pthread_attr_init(&attributes)==0,164);CHECK(pthread_attr_setstacksize(&attributes,65536)==0,165);CHECK(pthread_attr_setguardsize(&attributes,4096)==0,166);
 for(int i=0;i<streams;++i){setup_writer(i,count,full);CHECK(pthread_create(threads+i,&attributes,worker,(void *)(uintptr_t)i)==0,136);wait_word(&state.w[i].ready,1);}CHECK(pthread_attr_destroy(&attributes)==0,167);
 marker("PIPE_BLOCKING_CASE_BEGIN " KEY " pid=%ld uid=%lu streams=%d count=%u site=%lu resume=%lu syscall=%ld capacity=4096\n",VALUES,(long)state.pid,(unsigned long)state.uid,streams,count,(unsigned long)state.site,(unsigned long)state.resume,operation());for(int i=0;i<streams;++i){struct writer *w=&state.w[i];marker("PIPE_BLOCKING_WRITER " KEY " stream=%d tid=%ld fd=%d readfd=%d saved=%d replacement=%d replacementread=%d input=%lu payload0=%lu payload1=%lu payload2=%lu payload3=%lu argcount=%lu\n",VALUES,i,(long)w->tid,w->pipe[1],w->pipe[0],w->saved,w->replacement[1],w->replacement[0],w->admitted[1],(unsigned long)(uintptr_t)w->payload[0],(unsigned long)(uintptr_t)w->payload[1],(unsigned long)(uintptr_t)w->payload[2],(unsigned long)(uintptr_t)w->payload[3],w->admitted[2]);}
 struct writer *w=&state.w[0];store(&w->go,1);if(case_id<22||case_id==25)confirm(0,full?0:4096,0);
 if(case_id==25){store(&state.w[1].go,1);confirm(1,4096,0);read_bytes(0,4096,0);confirm(0,8192,1);read_bytes(1,4096,0);confirm(1,8192,1);finish_stream(0);finish_stream(1);}
 else if(case_id==2){read_bytes(0,4096,0);confirm(0,8192,1);read_bytes(0,1,0);wait_word(&w->done,1);read_bytes(0,4096,0);}
 else if(case_id==3){send_signal(SIGUSR1);wait_word(&state.handled,1);if(!restart)wait_word(&w->phase,1);confirm(0,0,1);read_bytes(0,4096,1);confirm(0,4096,2);finish_stream(0);}
 else if(case_id==4||case_id==5||case_id==6||case_id==7||case_id==17||case_id==18||case_id==19||case_id==20){
  if(case_id==5||case_id==6||case_id==18||case_id==19||case_id==20){read_bytes(0,4096,0);confirm(0,8192,1);}if(case_id==6||case_id==7){event("CLOSE",0,0,w->pipe[0]);CHECK(close(w->pipe[0])==0,137);w->pipe[0]=-1;}
  else if(case_id==18){proof(0);event("EXIT_GROUP",0,0,8192);thread_syscall4(SYS_exit_group,0,0,0,0);fail(138);}else if(case_id==19){proof(0);replace_image();}else send_signal(SIGUSR1);
  if(case_id==20){delay(5000000000LL);fail(139);}
 }
 else if(case_id==8){event("PROTECT_SUFFIX",0,0,4096);CHECK(mprotect(w->payload[1],4096,PROT_NONE)==0,140);read_bytes(0,4096,0);wait_word(&w->done,1);CHECK(mprotect(w->payload[1],4096,PROT_READ|PROT_WRITE)==0,141);event("RESTORE_SUFFIX",0,0,4096);}
 else if(case_id==9){event("MUTATE_METADATA",0,0,1);if(vector)for(int i=1;i<5;++i)w->vectors[i].iov_base=w->mapping+32768;else w->args[1]=(uintptr_t)w->mapping+32768;finish_stream(0);}
 else if(case_id==10){event("PROTECT_PREFIX",0,0,4096);CHECK(mprotect(w->payload[0],4096,PROT_NONE)==0,142);finish_stream(0);CHECK(mprotect(w->payload[0],4096,PROT_READ|PROT_WRITE)==0,143);event("RESTORE_PREFIX",0,0,4096);}
 else if(case_id==11){event("MUTATE_PAYLOAD",0,0,4096);for(unsigned page=1;page<3;++page)for(unsigned j=0;j<4096;++j)w->payload[page][j]=value(page*4096+j,0);finish_stream(0);}
 else if(case_id==12||case_id==15){event("REPLACE_FD",0,0,w->replacement[1]);CHECK(dup2(w->replacement[1],w->pipe[1])==w->pipe[1],144);if(case_id==15){nonblocking(w->pipe[1]);event("NONBLOCK_REPLACEMENT",0,0,w->pipe[1]);}read_bytes(0,4096,1);confirm(0,4096,1);finish_stream(0);}
 else if(case_id==13||case_id==14){nonblocking(w->saved);event("NONBLOCK_SHARED",0,0,w->saved);read_bytes(0,4096,case_id==14);wait_word(&w->done,1);}
 else if(case_id==16){send_signal(SIGUSR1);delay(20000000);CHECK(!load(&state.handled)&&!load(&w->done),145);event("IGNORED",0,0,1);finish_stream(0);}
 else if(case_id==21){read_bytes(0,1,1);confirm(0,0,1);event("ATOMIC_PENDING",0,0,1);read_bytes(0,4095,1);wait_word(&w->done,1);read_bytes(0,4096,0);}
 else if(case_id==0||case_id==1){if(full){read_bytes(0,4096,1);confirm(0,4096,1);}finish_stream(0);}
 for(int i=0;i<streams;++i){void *joined=0;CHECK(pthread_join(threads[i],&joined)==0&&joined==(void *)(uintptr_t)(case_id==17?0x996:0x995),146);}
 if(case_id==4||case_id==5||case_id==13||case_id==14||case_id==17||case_id==22)read_bytes(0,4096,0);if(case_id==23)read_bytes(0,4096,1);
 for(int i=0;i<streams;++i){struct writer *x=&state.w[i];proof(i);if(x->pipe[0]>=0)empty(x->pipe[0],i);if(x->replacement[0]>=0){empty(x->replacement[0],2);CHECK(write(x->pipe[1],"R",1)==1,147);unsigned char b;CHECK(read(x->replacement[0],&b,1)==1&&b=='R',148);event("REPLACEMENT_BYTE",i,0,'R');CHECK(close(x->replacement[0])==0&&close(x->replacement[1])==0,149);}if(x->saved>=0)CHECK(close(x->saved)==0,150);if(x->pipe[0]>=0)CHECK(close(x->pipe[0])==0,151);CHECK(close(x->pipe[1])==0&&munmap(x->mapping,mapping_bytes)==0,152);}
 marker("PIPE_BLOCKING_CASE_PASS " KEY "\n",VALUES);
}
static int replacement(int argc,char **argv)
{
 CHECK(argc==9&&dirty==0&&state.pid==0&&actor==-1,153);vector=atoi(argv[2]);variant=atoi(argv[3]);form=atoi(argv[4]);restart=atoi(argv[5]);case_id=atoi(argv[6]);state.pid=getpid();actor=9;CHECK(case_id==19&&thread_syscall4(SYS_gettid,0,0,0,0)==state.pid,154);struct sigaction a;CHECK(sigaction(SIGUSR1,0,&a)==0&&a.sa_handler==SIG_DFL,155);struct writer *w=&state.w[0];w->pipe[0]=atoi(argv[7]);w->pipe[1]=atoi(argv[8]);w->read_offset=4096;w->read_ordinal=1;event("EXEC_REPLACED",0,0,state.pid);read_bytes(0,4096,0);empty(w->pipe[0],0);CHECK(write(w->pipe[1],"E",1)==1,156);unsigned char b;CHECK(read(w->pipe[0],&b,1)==1&&b=='E',157);event("EXEC_BYTE",0,0,'E');empty(w->pipe[0],0);CHECK(close(w->pipe[0])==0&&close(w->pipe[1])==0,158);event("EXEC_CHECKED",0,0,state.pid);return 0;
}
int main(int argc,char **argv)
{
 CHECK(argc==1||argc==9,159);image_path=argv[0];if(argc==9)return replacement(argc,argv);CHECK(__atomic_always_lock_free(sizeof(state.handled),&state.handled),160);int groups=0,executed=0;
 for(vector=0;vector<2;++vector)for(variant=0;variant<2;++variant)for(form=0;form<(variant?1:raw_forms);++form)for(restart=0;restart<2;++restart){++groups;for(case_id=0;case_id<cases;++case_id){
#ifdef PIPE_BLOCKING_LINUX_REFERENCE
 if(case_id==2){marker("PIPE_BLOCKING_LINUX_SKIP " KEY " reason=native-final-suffix-capacity-not-linux-page-layout\n",VALUES);continue;}
#endif
 pid_t child=fork();CHECK(child>=0,161);if(!child){run_case();_Exit(0);}int status=-1;CHECK(waitpid(child,&status,0)==child,162);CHECK(case_id==20?(WIFSIGNALED(status)&&WTERMSIG(status)==SIGUSR1):(WIFEXITED(status)&&WEXITSTATUS(status)==0),163);delay(10000000);marker("PIPE_BLOCKING_PARENT_PASS " KEY " pid=%ld signal=%d\n",VALUES,(long)child,case_id==20?SIGUSR1:0);++executed;}}
#ifdef PIPE_BLOCKING_LINUX_REFERENCE
 marker("PIPE_BLOCKING_LINUX_REFERENCE_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,executed);
#else
 marker("PIPE_BLOCKING_PASS arch=%s variants=2 groups=%d cases=%d parent=1\n",PROBE_ARCH,groups,executed);
#endif
 return 0;
}
