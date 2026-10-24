#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>

#if defined(__i386__)
#define PROBE_ARCH "i386"
#elif defined(__x86_64__)
#define PROBE_ARCH "x86_64"
#elif defined(__arm__)
#define PROBE_ARCH "arm32"
#elif defined(__aarch64__)
#define PROBE_ARCH "aarch64"
#elif defined(__riscv) && __riscv_xlen == 32
#define PROBE_ARCH "rv32"
#define PROFILE_RV32 1
#elif defined(__riscv) && __riscv_xlen == 64
#define PROBE_ARCH "rv64"
#elif defined(__mips64)
#define PROBE_ARCH "mips64"
#elif defined(__mips__)
#define PROBE_ARCH "mips"
#elif defined(__loongarch64)
#define PROBE_ARCH "loongarch64"
#elif defined(__powerpc__) || defined(__PPC__)
#define PROBE_ARCH "ppc"
#if __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__NO_FPRS__)
#error "PPC guest requires big-endian PPC32 scalar soft-float"
#endif
#else
#error "Unsupported native sleep profile"
#endif
#ifndef PROFILE_RV32
#define PROFILE_RV32 0
#endif
#if (defined(__powerpc__) || defined(__PPC__)) && defined(__clang__)
#define load(p) __c11_atomic_load((p),__ATOMIC_SEQ_CST)
#define store(p,v) __c11_atomic_store((p),(v),__ATOMIC_SEQ_CST)
#define increment(p) __c11_atomic_fetch_add((p),1,__ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p),__ATOMIC_SEQ_CST)
#define store(p,v) __atomic_store_n((p),(v),__ATOMIC_SEQ_CST)
#define increment(p) __atomic_fetch_add((p),1,__ATOMIC_SEQ_CST)
#endif

/* 0/1 are libc contracts; 2/3/4 expose the exact kernel timespec layout. */
union value { struct timespec libc; long words[2]; int64_t wide[2]; unsigned char bytes[16]; };
struct guarded { unsigned char before[16]; union value value; unsigned char after[16]; };
static struct guarded request, remainder;
static int form, test_case;
static _Thread_local int role;
static _Atomic int ready, complete, phase, received;
static pid_t process_id, target_tid;
static uid_t sender_uid;
static int64_t duration, absolute_deadline;

static __attribute__((noreturn)) void fail(int code)
{
    char text[]="SLEEP_SIGNAL_FAIL code=000 form=0 case=00 role=0\n";
    unsigned p=sizeof("SLEEP_SIGNAL_FAIL code=")-1;
    text[p]='0'+code/100%10;text[p+1]='0'+code/10%10;text[p+2]='0'+code%10;
    text[sizeof("SLEEP_SIGNAL_FAIL code=000 form=")-1]='0'+form;
    p=sizeof("SLEEP_SIGNAL_FAIL code=000 form=0 case=")-1;
    text[p]='0'+test_case/10;text[p+1]='0'+test_case%10;
    text[sizeof("SLEEP_SIGNAL_FAIL code=000 form=0 case=00 role=")-1]='0'+role;
    syscall(SYS_write,1,text,sizeof(text)-1);syscall(SYS_exit_group,1);for(;;){}
}
#define CHECK(c,n) do { if(!(c))fail(n); } while(0)
static int64_t now(void)
{
    struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0,101);
    return (int64_t)t.tv_sec*1000000000+t.tv_nsec;
}
static void wait_word(_Atomic int *p,int value)
{
    int64_t start=now();while(load(p)!=value)CHECK(now()-start<5000000000LL,102);
}
static void delay(int64_t interval)
{
    int64_t start=now();while(now()-start<interval){}
}
static int is_clock(void){return form==1||form==3||form==4;}
static int absolute_case(void){return test_case>=11&&test_case<=14;}
static int interruption_count(void)
{
    if(test_case==14)return 2;
    return test_case<=4||test_case==9||test_case==10||test_case==11||test_case==12;
}
static const char *format(void)
{
    return sizeof(long)==8||form==4||(PROFILE_RV32&&form<2)?"time64":"time32";
}
static void encode(struct guarded *p,int64_t ns)
{
    if(form<2){p->value.libc.tv_sec=ns/1000000000;p->value.libc.tv_nsec=ns%1000000000;}
    else if(form==4){p->value.wide[0]=ns/1000000000;p->value.wide[1]=ns%1000000000;}
    else {p->value.words[0]=(long)(ns/1000000000);p->value.words[1]=(long)(ns%1000000000);}
}
static int64_t decode(const struct guarded *p)
{
    int64_t sec,nsec;
    if(form<2){sec=p->value.libc.tv_sec;nsec=p->value.libc.tv_nsec;}
    else if(form==4){sec=p->value.wide[0];nsec=p->value.wide[1];}
    else {sec=p->value.words[0];nsec=p->value.words[1];}
    CHECK(sec>=0&&sec<=10&&nsec>=0&&nsec<1000000000,103);
    return sec*1000000000+nsec;
}
static void guards(const struct guarded *p)
{
    for(unsigned i=0;i<16;++i)CHECK(p->before[i]==0xa5&&p->after[i]==0xa5,104);
    if(form>=2&&form!=4&&sizeof(long)==4)
        for(unsigned i=8;i<16;++i)CHECK(p->value.bytes[i]==0xa5,105);
}
static void handle(int signal,siginfo_t *info,void *context)
{
    int saved=errno;sigset_t mask;
    CHECK(role==0&&signal==SIGUSR1&&info&&context,201);
    CHECK(info->si_signo==SIGUSR1&&info->si_errno==0&&info->si_code==SI_TKILL,202);
    CHECK(info->si_pid==process_id&&info->si_uid==sender_uid,203);
    CHECK(syscall(SYS_gettid)==target_tid,204);
    CHECK(sigprocmask(SIG_SETMASK,0,&mask)==0&&sigismember(&mask,SIGUSR1)==1,205);
    increment(&received);errno=saved;
}
static void *sender(void *unused)
{
    (void)unused;role=1;wait_word(&ready,1);
    if(test_case==8)wait_word(&complete,1);
    else delay(test_case==6||test_case==7?10000000:60000000);
    if(test_case==4)encode(&request,-1000000000); /* The kernel already owns its copied request. */
    CHECK(syscall(SYS_tgkill,process_id,target_tid,SIGUSR1)==0,120);
    if(test_case==14){wait_word(&phase,1);delay(60000000);CHECK(syscall(SYS_tgkill,process_id,target_tid,SIGUSR1)==0,121);}
    return (void *)(uintptr_t)0x1875;
}
static int invoke(void *remain)
{
    int flags=absolute_case()?TIMER_ABSTIME:0;long result;
    errno=111;
    if(form==0)result=nanosleep(&request.value.libc,remain);
    else if(form==1)result=clock_nanosleep(CLOCK_MONOTONIC,flags,&request.value.libc,remain);
    else if(form==2)result=syscall(SYS_nanosleep,&request.value,remain);
    else if(form==3){
#if defined(SYS_clock_nanosleep_time32)
        result=syscall(SYS_clock_nanosleep_time32,CLOCK_MONOTONIC,flags,&request.value,remain);
#elif defined(SYS_clock_nanosleep)
        result=syscall(SYS_clock_nanosleep,CLOCK_MONOTONIC,flags,&request.value,remain);
#else
        fail(122);
#endif
    } else {
#ifdef SYS_clock_nanosleep_time64
        result=syscall(SYS_clock_nanosleep_time64,CLOCK_MONOTONIC,flags,&request.value,remain);
#else
        fail(123);
#endif
    }
    int error=errno;
    if(form==1){CHECK(error==111&&result>=0&&result<=4095,124);return (int)result;}
    CHECK(result==0||result==-1,125);if(!result)CHECK(error==111,126);
    return result?error:0;
}
static void run_case(void)
{
    store(&ready,0);store(&complete,0);store(&phase,0);store(&received,0);
    process_id=getpid();target_tid=(pid_t)syscall(SYS_gettid);sender_uid=getuid();
    struct sigaction action={0};action.sa_sigaction=handle;action.sa_flags=SA_SIGINFO;
    if(test_case==1||test_case==12||test_case==14)action.sa_flags|=SA_RESTART;
    if(test_case==6)action.sa_handler=SIG_IGN;
    CHECK(sigemptyset(&action.sa_mask)==0&&sigaction(SIGUSR1,&action,0)==0,130);
    sigset_t mask;CHECK(sigemptyset(&mask)==0,131);
    if(test_case==7)CHECK(sigaddset(&mask,SIGUSR1)==0,132);
    CHECK(sigprocmask(SIG_SETMASK,&mask,0)==0,133);
    memset(&request,0xa5,sizeof(request));memset(&remainder,0xa5,sizeof(remainder));
    duration=(test_case==5||test_case==6||test_case==7||test_case==8)?80000000:500000000;
    if(test_case==14)duration=300000000;
    if(test_case==15)duration=0;
    int64_t start=now();absolute_deadline=start+duration;
    encode(&request,absolute_case()?(test_case==13?0:absolute_deadline):duration);
    struct guarded saved_remainder=remainder;
    void *remain=&remainder.value;void *mapping=MAP_FAILED;
    if(test_case==2)remain=&request.value;
    if(test_case==3)remain=0;
    if(test_case==9){mapping=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);CHECK(mapping!=MAP_FAILED,134);memset(mapping,0x93,4096);CHECK(mprotect(mapping,4096,PROT_READ)==0,135);remain=mapping;}
    if(test_case==10||absolute_case())remain=(void *)(uintptr_t)1;
    const int count=interruption_count(),fault=test_case==9||test_case==10;
    const char *expected=fault?"efault":count&&test_case!=14?"eintr":"success";
    printf("SLEEP_SIGNAL_CASE_BEGIN arch=%s form=%d case=%d pid=%ld tid=%ld expected=%s format=%s kind=%s interrupts=%d\n",PROBE_ARCH,form,test_case,(long)process_id,(long)target_tid,expected,format(),absolute_case()?"absolute":"relative",count);fflush(stdout);
    int has_sender=test_case!=5&&test_case!=13&&test_case!=15;pthread_t thread;
    if(has_sender)CHECK(pthread_create(&thread,0,sender,0)==0,136);
    start=now();
    if(absolute_case()&&test_case!=13){absolute_deadline=start+duration;encode(&request,absolute_deadline);}
    store(&ready,1);int error=invoke(remain);
    int64_t returned=now();store(&complete,1);
    if(test_case==14){
        CHECK(error==EINTR&&load(&received)==1,137);store(&phase,1);
        error=invoke(remain);CHECK(error==EINTR&&load(&received)==2,138);
        error=invoke(remain);returned=now();CHECK(error==0&&returned>=absolute_deadline&&returned-absolute_deadline<1000000000,139);
    } else if(count){
        CHECK(error==(fault?EFAULT:EINTR)&&load(&received)==1,140);
        CHECK(returned-start<duration,141);
        if(!absolute_case()&&!fault&&test_case!=3){
            int64_t left=decode(test_case==2?&request:&remainder);
            CHECK(left>0&&left<=duration,142);
            CHECK(left+returned-start>=duration-20000000&&left+returned-start<=duration+200000000,143);
        }
    } else {
        CHECK(error==0,144);
        if(test_case!=13)CHECK(returned-start>=duration,145);
        CHECK(memcmp(&remainder,&saved_remainder,sizeof(remainder))==0,146);
        if(test_case==8)wait_word(&received,1);
        else CHECK(load(&received)==0,147);
    }
    if(has_sender){void *joined=0;CHECK(pthread_join(thread,&joined)==0&&joined==(void *)(uintptr_t)0x1875,148);}
    if(test_case==7){
        CHECK(sigpending(&mask)==0&&sigismember(&mask,SIGUSR1)==1,149);
        CHECK(sigemptyset(&mask)==0&&sigprocmask(SIG_SETMASK,&mask,0)==0,150);
        CHECK(load(&received)==1,151);
    }
    if(test_case==6)CHECK(sigpending(&mask)==0&&sigismember(&mask,SIGUSR1)==0,152);
    guards(&request);guards(&remainder);
    if(mapping!=MAP_FAILED){for(unsigned i=0;i<4096;++i)CHECK(((const unsigned char *)mapping)[i]==0x93,153);CHECK(munmap(mapping,4096)==0,154);}
    printf("SLEEP_SIGNAL_CASE_PASS arch=%s form=%d case=%d\n",PROBE_ARCH,form,test_case);fflush(stdout);
}
static int has_case(int candidate)
{
    if(candidate<=8||candidate==15)return 1;
    if(candidate==9||candidate==10)return form>=2;
    return is_clock();
}
int main(void)
{
    CHECK(__atomic_always_lock_free(sizeof(received),&received),160);
    int forms=0,cases=0,interrupts=0,faults=0;
    for(form=0;form<5;++form){
        if((form==2||form==3)&&PROFILE_RV32)continue;
        if(form==4&&sizeof(long)==8)continue;
        ++forms;
        for(test_case=0;test_case<16;++test_case)if(has_case(test_case)){++cases;interrupts+=interruption_count();faults+=test_case==9||test_case==10;}
        pid_t child=fork();CHECK(child>=0,161);
        if(child==0){for(test_case=0;test_case<16;++test_case)if(has_case(test_case))run_case();_exit(0);}
        int status=0;CHECK(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0,162);
    }
    printf("SLEEP_SIGNAL_PASS arch=%s forms=%d cases=%d interrupts=%d efault=%d guards=1 parent=1\n",PROBE_ARCH,forms,cases,interrupts,faults);
    return 0;
}
