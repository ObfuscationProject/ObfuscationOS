#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <poll.h>
#include <sys/select.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* Retain nonempty TLS so the explicit SDK18 negative reaches its adapter. */
static _Thread_local volatile int probe_tls=19;

/* Integer-only diagnostics keep this probe independent of unfinished MIPS64
   long-double compiler runtime support pulled in by musl printf. */
static void emit(const char *text)
{
    size_t length=strlen(text);
    if(write(1,text,length)!=(ssize_t)length)_exit(91);
}
static void number(int64_t value)
{
    char buffer[24];unsigned count=0;uint64_t magnitude=(uint64_t)value;
    if(value<0){emit("-");magnitude=0-magnitude;}
    do{buffer[count++]=(char)('0'+magnitude%10);magnitude/=10;}while(magnitude);
    for(unsigned i=0;i<count/2;++i){char c=buffer[i];buffer[i]=buffer[count-i-1];buffer[count-i-1]=c;}
    if(write(1,buffer,count)!=(ssize_t)count)_exit(92);
}
static void field(const char *name,int64_t value){emit(name);number(value);}
static void pair(const char *name,struct timespec value){field(name,value.tv_sec);field(":",value.tv_nsec);}
#define CHECK(x) do { if (!(x)) { int error=errno;field("CLOCK_SET_MUSL_FAIL line=",__LINE__);field(" errno=",error);emit("\n");return 1; } } while(0)
#if defined(SYS_clock_settime)
#define RAW_SET SYS_clock_settime
#else
#define RAW_SET SYS_clock_settime64
#endif

static int around(const struct timespec *value,int64_t seconds)
{
    return value->tv_sec>=seconds && value->tv_sec<=seconds+3 && value->tv_nsec>=0 && value->tv_nsec<1000000000;
}
static int bracket(const char *label,struct timespec requested)
{
    struct timespec before,after,read_before,wall,at;
    CHECK(clock_gettime(CLOCK_MONOTONIC,&before)==0);
    CHECK(clock_settime(CLOCK_REALTIME,&requested)==0);
    CHECK(clock_gettime(CLOCK_MONOTONIC,&after)==0);
    const struct timespec delay={0,20000000};CHECK(nanosleep(&delay,0)==0);
    CHECK(clock_gettime(CLOCK_MONOTONIC,&read_before)==0);
    CHECK(clock_gettime(CLOCK_REALTIME,&wall)==0);
    CHECK(clock_gettime(CLOCK_MONOTONIC,&at)==0);
    CHECK(around(&wall,requested.tv_sec));
    emit("CLOCK_SET_MUSL_SAMPLE label=");emit(label);
    pair(" requested=",requested);pair(" before=",before);pair(" after=",after);
    pair(" read_before=",read_before);pair(" wall=",wall);pair(" at=",at);emit("\n");
    return 0;
}
static int raw_form(long number,int narrow,int denied)
{
    unsigned char *pages=mmap(0,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(pages!=MAP_FAILED && mprotect(pages+4096,4096,PROT_NONE)==0);
    const unsigned width=narrow?8:16;
    int64_t wide[2]={1700000030,314159265};
    int32_t small[2]={1700000030,314159265};
    void *value=narrow?(void *)small:(void *)wide;
    memcpy(pages+4096-width,value,width);
    CHECK(syscall(number,CLOCK_MONOTONIC,(void *)1)==-1 && errno==EINVAL);
    CHECK(syscall(number,CLOCK_REALTIME,(void *)1)==-1 && errno==EFAULT);
    CHECK(syscall(number,CLOCK_REALTIME,pages+4097-width)==-1 && errno==EFAULT);
    CHECK(!memcmp(pages+4096-width,value,width));
    small[1]=1000000000;wide[1]=1000000000;
    CHECK(syscall(number,CLOCK_REALTIME,value)==-1 && errno==EINVAL);
    small[0]=-1;wide[0]=-1;small[1]=wide[1]=0;
    CHECK(syscall(number,CLOCK_REALTIME,value)==-1 && errno==EINVAL);
    small[0]=wide[0]=0;
    CHECK(syscall(number,CLOCK_REALTIME,value)==-1 && errno==(denied?EPERM:EINVAL));
    if(!narrow){
        wide[0]=8277292036LL;
        CHECK(syscall(number,CLOCK_REALTIME,value)==-1 && errno==EINVAL);
        wide[0]=1700000030;
#if __SIZEOF_LONG__ == 8
        wide[1]=0x1234567800000000LL;
        CHECK(syscall(number,CLOCK_REALTIME,value)==-1 && errno==EINVAL);
#else
        wide[1]=0x1234567812b9b0a1LL; /* Linux32 ignores high32 padding, including BE. */
        long result=syscall(number,CLOCK_REALTIME,value);
        CHECK(denied?(result==-1 && errno==EPERM):result==0);
#endif
    }
    CHECK(mprotect(pages,4096,PROT_READ)==0);
    long result=syscall(number,CLOCK_REALTIME,pages+4096-width);
    CHECK(denied?(result==-1 && errno==EPERM):result==0);
    CHECK(munmap(pages,8192)==0);
    field("CLOCK_SET_RAW_PASS number=",number);field(" bytes=",width);
    emit(" authority=");emit(denied?"denied":"root");emit(" copies=pass range=pass padding=");
    emit(narrow?"none":sizeof(long)==4?"ignored-high32":"full64");emit("\n");
    return 0;
}
static int raw_forms(int denied)
{
#ifdef SYS_clock_settime
    CHECK(raw_form(SYS_clock_settime,0,denied)==0);
#endif
#ifdef SYS_clock_settime32
    CHECK(raw_form(SYS_clock_settime32,1,denied)==0);
#endif
#ifdef SYS_clock_settime64
    CHECK(raw_form(SYS_clock_settime64,0,denied)==0);
#endif
    return 0;
}
static int64_t ns(struct timespec value)
{
    return (int64_t)value.tv_sec*1000000000+value.tv_nsec;
}
static int wait_across_sets(int kind)
{
    int gate[2],samples[2];CHECK(pipe(gate)==0 && pipe(samples)==0);
    pid_t parent=getpid(),child=fork();CHECK(child>=0);
    if(!child){
        char token;struct timespec times[2],delay={0,20000000};
        CHECK(read(gate[0],&token,1)==1 && token=='s');
        CHECK(nanosleep(&delay,0)==0 && clock_gettime(CLOCK_MONOTONIC,&times[0])==0);
        struct timespec value={1800000000,123456789};CHECK(clock_settime(CLOCK_REALTIME,&value)==0);
        delay.tv_nsec=10000000;CHECK(nanosleep(&delay,0)==0);
        value.tv_sec=1700000000;CHECK(clock_settime(CLOCK_REALTIME,&value)==0);
        CHECK(clock_gettime(CLOCK_MONOTONIC,&times[1])==0);
        CHECK(write(samples[1],times,sizeof times)==sizeof times);_exit(0);
    }
    struct timespec before,after,delay={0,150000000},times[2];
    CHECK(clock_gettime(CLOCK_MONOTONIC,&before)==0 && write(gate[1],"s",1)==1);
    if(kind==0)CHECK(nanosleep(&delay,0)==0);
    if(kind==1){
        struct timespec deadline=before;deadline.tv_nsec+=150000000;
        if(deadline.tv_nsec>=1000000000){deadline.tv_sec++;deadline.tv_nsec-=1000000000;}
        CHECK(clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&deadline,0)==0);
    }
    if(kind==2)CHECK(poll(0,0,150)==0);
    if(kind==3){struct timeval timeout={0,150000};CHECK(select(0,0,0,0,&timeout)==0);}
    if(kind==4)CHECK(ppoll(0,0,&delay,0)==0);
    if(kind==5)CHECK(pselect(0,0,0,0,&delay,0)==0);
    CHECK(clock_gettime(CLOCK_MONOTONIC,&after)==0);
    CHECK(read(samples[0],times,sizeof times)==sizeof times);
    int status;CHECK(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
    CHECK(ns(after)-ns(before)>=150000000 && ns(after)-ns(before)<3000000000LL);
    CHECK(ns(before)<=ns(times[0]) && ns(times[0])<=ns(times[1]) && ns(times[1])<ns(after));
    CHECK(close(gate[0])==0 && close(gate[1])==0 && close(samples[0])==0 && close(samples[1])==0);
    field("CLOCK_SET_WAIT_PASS kind=",kind);field(" parent=",parent);field(" child=",child);
    field(" before=",ns(before));field(" first=",ns(times[0]));field(" last=",ns(times[1]));
    field(" after=",ns(after));emit("\n");
    return 0;
}
int main(int argc,char **argv)
{
    CHECK(probe_tls==19);
    if(argc==2 && !strcmp(argv[1],"exec-read")){
        struct timespec wall;CHECK(clock_gettime(CLOCK_REALTIME,&wall)==0 && around(&wall,2214176523LL));
        emit("CLOCK_SET_MUSL_EXEC_PASS inherited=software-time\n");return 0;
    }
    if(argc==2 && !strcmp(argv[1],"negative")){
#ifdef SYS_clock_settime
        CHECK(syscall(SYS_clock_settime,CLOCK_REALTIME,(void *)1)==-1 && errno==ENOSYS);
#endif
#ifdef SYS_clock_settime32
        CHECK(syscall(SYS_clock_settime32,CLOCK_REALTIME,(void *)1)==-1 && errno==ENOSYS);
#endif
#ifdef SYS_clock_settime64
        CHECK(syscall(SYS_clock_settime64,CLOCK_REALTIME,(void *)1)==-1 && errno==ENOSYS);
#endif
        emit("CLOCK_SET_MUSL_NEGATIVE_PASS expected=SDK18 errno=ENOSYS\n");return 0;
    }
    const int denied=argc==2 && !strcmp(argv[1],"deny");
    CHECK(argc==1 || denied);
    CHECK(denied?geteuid()!=0:geteuid()==0);
    CHECK(raw_forms(denied)==0);
    struct timespec value={1700000001,123456789};
    if(denied){
        CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EPERM);
        value.tv_nsec=1000000000;CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EINVAL);
        CHECK(syscall(RAW_SET,CLOCK_REALTIME,(void *)1)==-1 && errno==EFAULT);
        emit("CLOCK_SET_MUSL_DENIED_PASS authority=real-process errno=EPERM\n");return 0;
    }
    CHECK(syscall(RAW_SET,CLOCK_MONOTONIC,(void *)1)==-1 && errno==EINVAL);
    CHECK(syscall(RAW_SET,CLOCK_REALTIME,(void *)1)==-1 && errno==EFAULT);
    value.tv_nsec=1000000000;CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EINVAL);
    value=(struct timespec){-1,0};CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EINVAL);
    value=(struct timespec){0,0};CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EINVAL);
    for(int kind=0;kind<6;++kind)CHECK(wait_across_sets(kind)==0);
    CHECK(bracket("time32-date",(struct timespec){1700000001,123456789})==0);
    CHECK(bracket("forward",(struct timespec){1700000101,456789123})==0);
    CHECK(bracket("backward",(struct timespec){1700000002,987654321})==0);
    CHECK(bracket("post2038",(struct timespec){2214176523LL,135791113})==0);
    pid_t child=fork();CHECK(child>=0);
    if(!child){
        char *args[]={"musl-clock-set","exec-read",0};char *env[]={"PATH=/bin",0};
        execve("/bin/musl-clock-set",args,env);_exit(127);
    }
    int status;CHECK(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
    emit("CLOCK_SET_MUSL_PASS setters=pass backwards=pass post2038=pass fork-exec=pass\n");return 0;
}
