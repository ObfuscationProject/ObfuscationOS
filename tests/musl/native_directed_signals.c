#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>
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
#error "PPC probe requires native big-endian PPC32 scalar soft-float"
#endif
#else
#error "Unsupported private native architecture"
#endif

#ifdef SYS_setresuid32
#define SETRESUID SYS_setresuid32
#define GETRESUID SYS_getresuid32
#else
#define SETRESUID SYS_setresuid
#define GETRESUID SYS_getresuid
#endif
#if defined(__mips__)
#define MAX_SIGNAL 128
#else
#define MAX_SIGNAL 64
#endif
#if (defined(__powerpc__) || defined(__PPC__)) && defined(__clang__)
#define load(p) __c11_atomic_load((p), __ATOMIC_SEQ_CST)
#define increment(p) __c11_atomic_fetch_add((p), 1, __ATOMIC_SEQ_CST)
#else
#define load(p) __atomic_load_n((p), __ATOMIC_SEQ_CST)
#define increment(p) __atomic_fetch_add((p), 1, __ATOMIC_SEQ_CST)
#endif
_Static_assert(sizeof(uid_t)==4 && sizeof(pid_t)==4,"native Linux ID widths");
struct ids { uid_t real, effective, saved; };
struct scenario {
    struct ids sender, receiver;
    int permitted, tkill, masked, ignored;
};
// Each sender runs in a separate child so dropping IDs never affects the driver.
static const struct scenario scenarios[] = {
    {{1101,1201,1301},{2101,2201,1101},1,0,1,0}, // real -> saved; coalescing and queued identity
    {{1102,1202,1302},{1202,2202,2302},1,1,0,0}, // effective -> real; global tkill
    {{1103,1203,1303},{2103,1103,2303},0,0,0,0}, // target effective UID is insufficient
    {{1104,1204,1304},{1304,2204,2304},0,1,0,0}, // sender saved UID is insufficient
    {{1105,1205,1305},{1105,2205,2305},1,1,0,0}, // real -> real
    {{1106,1206,1306},{2106,2206,1206},1,0,0,0}, // effective -> saved
    {{1107,0,1307},{2107,2207,2307},1,0,0,0},    // reduced effective-root privilege
    {{0,1208,1308},{2108,2208,2308},0,0,0,0},    // real UID zero alone is insufficient
    {{1109,1209,1309},{1109,2209,2309},1,0,0,1}, // target ignores; caller catches
};
static int case_number, role;
static pid_t expected_sender, receiver_identity;
static uid_t expected_uid;
static _Atomic unsigned received;
static volatile uint32_t private_canary = 0x71a2b3c4;

static __attribute__((noreturn)) void fail(int code)
{
    char text[]="DIRECTED_SIGNALS_FAIL code=000 case=00 role=0\n";
    unsigned at=sizeof("DIRECTED_SIGNALS_FAIL code=")-1;
    text[at]='0'+code/100%10; text[at+1]='0'+code/10%10; text[at+2]='0'+code%10;
    at=sizeof("DIRECTED_SIGNALS_FAIL code=000 case=")-1;
    text[at]='0'+case_number/10; text[at+1]='0'+case_number%10;
    text[sizeof("DIRECTED_SIGNALS_FAIL code=000 case=00 role=")-1]='0'+role;
    syscall(SYS_write,1,text,sizeof(text)-1);
    syscall(SYS_exit_group,1);
    for (;;) {}
}
#define CHECK(c,n) do { if(!(c))fail(n); } while(0)

static int64_t seconds(void)
{
    struct timespec now;
    CHECK(clock_gettime(CLOCK_MONOTONIC,&now)==0,101);
    return now.tv_sec;
}
static void timeout(int64_t start)
{
    CHECK(seconds()-start<15,102);
}
static void send_byte(int fd, unsigned char value)
{
    int64_t start=seconds();
    for (;;) {
        long n=syscall(SYS_write,fd,&value,1);
        if(n==1)return;
        CHECK(n==-1 && (errno==EAGAIN || errno==EINTR),103);
        timeout(start);
    }
}
static unsigned char receive_byte(int fd)
{
    int64_t start=seconds();
    for (;;) {
        unsigned char value=0;
        long n=syscall(SYS_read,fd,&value,1);
        if(n==1)return value;
        CHECK(n==-1 && (errno==EAGAIN || errno==EINTR),104);
        timeout(start);
    }
}
static void receive_eof(int fd)
{
    int64_t start=seconds();
    for (;;) {
        unsigned char value=0;
        long n=syscall(SYS_read,fd,&value,1);
        if(n==0)return;
        CHECK(n==-1 && (errno==EAGAIN || errno==EINTR),105);
        timeout(start);
    }
}
static void exchange(int command, int reply, unsigned char request, unsigned char response)
{
    send_byte(command,request);CHECK(receive_byte(reply)==response,106);
}
static void set_ids(struct ids ids)
{
    uid_t real=0,effective=0,saved=0;
    CHECK(syscall(SETRESUID,ids.real,ids.effective,ids.saved)==0,107);
    CHECK(syscall(GETRESUID,&real,&effective,&saved)==0 && real==ids.real &&
          effective==ids.effective && saved==ids.saved,108);
}
static void handle(int sig, siginfo_t *info, void *context)
{
    CHECK(role==2 && sig==SIGUSR1 && info && context,201);
    CHECK(info->si_signo==SIGUSR1 && info->si_errno==0 && info->si_code==SI_TKILL,202);
    CHECK(info->si_pid==expected_sender && info->si_uid==expected_uid,203);
    CHECK(getpid()==receiver_identity && syscall(SYS_gettid)==receiver_identity,204);
    CHECK(private_canary==0x29da461b,205);
    sigset_t mask;
    CHECK(sigprocmask(SIG_SETMASK,0,&mask)==0 && sigismember(&mask,SIGUSR1)==1,206);
    increment(&received);
}
static void install(int ignored)
{
    struct sigaction action={0};
    CHECK(sigemptyset(&action.sa_mask)==0,109);
    if(ignored)action.sa_handler=SIG_IGN;
    else { action.sa_sigaction=handle;action.sa_flags=SA_SIGINFO; }
    CHECK(sigaction(SIGUSR1,&action,0)==0,110);
}
static void inspect(unsigned calls, int pending, int masked, int ignored)
{
    sigset_t set;
    struct sigaction action={0};
    CHECK(load(&received)==calls && private_canary==0x29da461b,111);
    CHECK(sigpending(&set)==0 && sigismember(&set,SIGUSR1)==pending,112);
    CHECK(sigprocmask(SIG_SETMASK,0,&set)==0 && sigismember(&set,SIGUSR1)==masked,113);
    CHECK(sigaction(SIGUSR1,0,&action)==0,114);
    CHECK(ignored ? action.sa_handler==SIG_IGN : action.sa_sigaction==handle && (action.sa_flags&SA_SIGINFO),115);
}
static void receiver(const struct scenario *s, int command, int reply)
{
    role=2;private_canary=0x29da461b;receiver_identity=getpid();expected_sender=getppid();expected_uid=s->sender.real;
    CHECK(syscall(SYS_gettid)==receiver_identity,116);
    set_ids(s->receiver);install(s->ignored);
    sigset_t blocked;
    CHECK(sigemptyset(&blocked)==0,117);
    if(s->masked)CHECK(sigaddset(&blocked,SIGUSR1)==0,118);
    CHECK(sigprocmask(SIG_SETMASK,&blocked,0)==0,119);
    send_byte(reply,'R');
    unsigned expected=0;int masked=s->masked;
    for (;;) {
        unsigned char request=receive_byte(command);
        if(request=='Z') { inspect(0,0,masked,s->ignored);send_byte(reply,'z'); }
        else if(request=='P') { inspect(0,1,1,0);send_byte(reply,'p'); }
        else if(request=='U') {
            CHECK(sigemptyset(&blocked)==0 && sigprocmask(SIG_SETMASK,&blocked,0)==0,120);
            masked=0;expected=1;inspect(expected,0,masked,0);send_byte(reply,'u');
        } else if(request=='D') {
            int64_t start=seconds();
            while(load(&received)==0)timeout(start);
            expected=1;inspect(expected,0,masked,0);send_byte(reply,'d');
        } else if(request=='N') { inspect(0,0,masked,s->ignored);send_byte(reply,'n'); }
        else if(request=='X') {
            inspect(expected,0,masked,s->ignored);send_byte(reply,'x');
            // Only exit closes this writer. Its EOF is the unreaped-zombie barrier.
            syscall(SYS_exit_group,0);fail(121);
        } else fail(122);
    }
}
static long directed(const struct scenario *s, pid_t target, int sig)
{
    return s->tkill ? syscall(SYS_tkill,target,sig) : syscall(SYS_tgkill,target,target,sig);
}
static void denied(long value, int error, int code)
{
    CHECK(value==-1 && errno==error,code);
}
static void coordinator(const struct scenario *s)
{
    role=1;private_canary=0x58c1a729;
    int command[2],reply[2];
    CHECK(pipe2(command,O_NONBLOCK)==0 && pipe2(reply,O_NONBLOCK)==0,123);
    pid_t child=fork();CHECK(child>=0,124);
    if(!child) {
        CHECK(close(command[1])==0 && close(reply[0])==0,125);
        receiver(s,command[0],reply[1]);fail(126);
    }
    CHECK(close(command[0])==0 && close(reply[1])==0,127);
    CHECK(receive_byte(reply[0])=='R',128);
    // Opposite actions expose using the sender table for target ignored checks.
    install(!s->ignored);set_ids(s->sender);
    errno=0;denied(syscall(SYS_tkill,0,SIGUSR1),EINVAL,129);
    errno=0;denied(syscall(SYS_tgkill,0,child,SIGUSR1),EINVAL,130);
    errno=0;denied(syscall(SYS_tgkill,getpid(),child,0),ESRCH,131);
    errno=0;denied(syscall(SYS_tgkill,getpid(),child,-1),ESRCH,132);
    errno=0;denied(directed(s,child,-1),EINVAL,133);
    errno=0;denied(directed(s,child,MAX_SIGNAL+1),EINVAL,134);
    errno=0;
    long zero=directed(s,child,0);
    if(s->permitted)CHECK(zero==0,135);else denied(zero,EPERM,136);
    exchange(command[1],reply[0],'Z','z');
    errno=0;long sent=directed(s,child,SIGUSR1);
    if(!s->permitted) {
        denied(sent,EPERM,137);exchange(command[1],reply[0],'N','n');
    } else {
        CHECK(sent==0,138);
        if(s->masked) {
            CHECK(directed(s,child,SIGUSR1)==0,139);
            exchange(command[1],reply[0],'P','p');
            // Change the sender real UID while preserving permission through euid.
            set_ids((struct ids){s->sender.effective,s->sender.real,s->sender.saved});
            exchange(command[1],reply[0],'U','u');
        } else if(s->ignored)exchange(command[1],reply[0],'N','n');
        else exchange(command[1],reply[0],'D','d');
    }
    CHECK(load(&received)==0 && private_canary==0x58c1a729,140);
    exchange(command[1],reply[0],'X','x');receive_eof(reply[0]);
    // No wait operation reaps the receiver before these existence probes.
    errno=0;zero=directed(s,child,0);
    if(s->permitted)CHECK(zero==0,141);else denied(zero,EPERM,142);
    errno=0;sent=directed(s,child,SIGUSR1);
    if(s->permitted)CHECK(sent==0,143);else denied(sent,EPERM,144);
    errno=0;denied(directed(s,child,-1),EINVAL,145);
    int status=0;CHECK(waitpid(child,&status,WNOHANG)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,146);
    errno=0;denied(directed(s,child,0),ESRCH,147);
    errno=0;denied(directed(s,child,-1),ESRCH,148);
    CHECK(close(command[1])==0 && close(reply[0])==0,149);
    syscall(SYS_exit_group,0);fail(150);
}
int main(void)
{
    uid_t real=0,effective=0,saved=0;
    CHECK(__atomic_always_lock_free(sizeof(received),&received),151);
    CHECK(syscall(GETRESUID,&real,&effective,&saved)==0 && real==0 && effective==0 && saved==0,152);
    for(unsigned i=0;i<sizeof(scenarios)/sizeof(scenarios[0]);++i) {
        case_number=(int)i+1;
        pid_t child=fork();CHECK(child>=0,153);
        if(!child)coordinator(&scenarios[i]);
        int status=0;CHECK(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,154);
        CHECK(load(&received)==0 && private_canary==0x71a2b3c4,155);
    }
    CHECK(syscall(GETRESUID,&real,&effective,&saved)==0 && real==0 && effective==0 && saved==0,156);
    static const char marker[]="DIRECTED_SIGNALS_PASS " PROBE_ARCH " cases=9 cross=6 denied=3 handlers=5 masked=1 coalesced=1 sender_snapshot=1 zero=9 zombie=9 reaped=9 target_actions=2 isolation=1\n";
    CHECK(syscall(SYS_write,1,marker,sizeof(marker)-1)==(long)(sizeof(marker)-1),157);
    return 0;
}
