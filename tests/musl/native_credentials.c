#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#if defined(__x86_64__)
#define ARCH "x86_64"
#elif defined(__i386__)
#define ARCH "i386"
#elif defined(__aarch64__)
#define ARCH "aarch64"
#elif defined(__arm__)
#define ARCH "arm32"
#elif defined(__riscv) && __riscv_xlen == 64
#define ARCH "rv64"
#elif defined(__riscv) && __riscv_xlen == 32
#define ARCH "rv32"
#elif defined(__loongarch64)
#define ARCH "loongarch64"
#elif defined(__mips__) && _MIPS_SIM == 3
#define ARCH "mips64"
#elif defined(__mips__)
#define ARCH "mips"
#elif defined(__powerpc__)
#define ARCH "ppc"
#else
#error "Unsupported native credential probe profile"
#endif

_Static_assert(sizeof(uid_t)==4 && sizeof(gid_t)==4,"Linux native identity width");
static const char private_path[]="/tmp/saved-ids-private";
static unsigned checks;
static int peer_ready, peer_stop;

static void fail(unsigned code)
{
    dprintf(1,"CREDENTIALS_FAIL " ARCH " code=%u checks=%u errno=%d\n",code,checks,errno);
    _exit(1);
}
#define CHECK(test,code) do { ++checks; if(!(test))fail(code); } while(0)

static void ids(uid_t r,uid_t e,uid_t s,gid_t gr,gid_t ge,gid_t gs)
{
    uid_t actual[3]={0};gid_t groups[3]={0};
    CHECK(getresuid(actual,actual+1,actual+2)==0 && actual[0]==r && actual[1]==e && actual[2]==s,101);
    CHECK(getresgid(groups,groups+1,groups+2)==0 && groups[0]==gr && groups[1]==ge && groups[2]==gs,102);
    CHECK(getuid()==r && geteuid()==e && getgid()==gr && getegid()==ge,103);
}

static void denied_file(void)
{
    errno=0;int fd=open(private_path,O_RDONLY);
    CHECK(fd==-1 && errno==EACCES,104);
}

static void wait_clean(pid_t child)
{
    int status=0;
    CHECK(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,105);
}

static void *peer(void *unused)
{
    (void)unused;__atomic_store_n(&peer_ready,1,__ATOMIC_RELEASE);
    while(!__atomic_load_n(&peer_stop,__ATOMIC_ACQUIRE))sched_yield();
    return (void *)(uintptr_t)37;
}

int main(int argc,char **argv)
{
    if(argc==2 && !strcmp(argv[1],"--exec-child"))
    {
        ids(1000,1000,1000,1000,1000,1000);
        errno=0;CHECK(setuid(0)==-1 && errno==EPERM,106);
        errno=0;CHECK(setgid(0)==-1 && errno==EPERM,107);
        denied_file();
        puts("CREDENTIALS_EXEC_CHILD_PASS " ARCH " saved_reset=1 permanent=1");
        return 0;
    }
    CHECK(argc==1 && argv[0][0]=='/',108);
    ids(0,0,0,0,0,0);
    int fd=open(private_path,O_CREAT|O_TRUNC|O_WRONLY,0600);
    CHECK(fd>=0 && write(fd,"private",7)==7 && close(fd)==0,109);

    pthread_t thread;CHECK(pthread_create(&thread,0,peer,0)==0,110);
    while(!__atomic_load_n(&peer_ready,__ATOMIC_ACQUIRE))sched_yield();
    errno=0;CHECK(syscall(SYS_setresuid,(uid_t)-1,(uid_t)-1,(uid_t)-1)==-1 && errno==EOPNOTSUPP,111);
    errno=0;CHECK(syscall(SYS_setresgid,(gid_t)-1,(gid_t)-1,(gid_t)-1)==-1 && errno==EOPNOTSUPP,112);
    ids(0,0,0,0,0,0);
    __atomic_store_n(&peer_stop,1,__ATOMIC_RELEASE);
    void *answer=0;CHECK(pthread_join(thread,&answer)==0 && answer==(void *)(uintptr_t)37,113);

    CHECK(setresgid(1000,1000,0)==0 && setresuid(1000,1000,0)==0,114);
    ids(1000,1000,0,1000,1000,0);denied_file();
    errno=0;CHECK(setresuid(1000,1000,77)==-1 && errno==EPERM,115);
    errno=0;CHECK(setregid(1000,77)==-1 && errno==EPERM,116);
    ids(1000,1000,0,1000,1000,0);
    CHECK(setgid(0)==0,117);
    errno=0;CHECK(setuid(77)==-1 && errno==EPERM,118);
    ids(1000,1000,0,1000,0,0);
    CHECK(setuid(0)==0,119);
    ids(1000,0,0,1000,0,0);
    CHECK(setresgid(0,0,0)==0 && setresuid(0,0,0)==0,120);
    ids(0,0,0,0,0,0);
    errno=0;CHECK(setuid((uid_t)-1)==-1 && errno==EINVAL,121);
    errno=0;CHECK(setgid((gid_t)-1)==-1 && errno==EINVAL,122);
    CHECK(setreuid((uid_t)-1,(uid_t)-1)==0 && setregid((gid_t)-1,(gid_t)-1)==0,123);
    ids(0,0,0,0,0,0);

    /* libc scalar getters return unsigned IDs without syscall() errno decoding. */
    const uid_t high_ids[]={0x80000000U,0xfffff000U,0xfffff001U,0xfffffffeU};
    for(unsigned i=0;i<sizeof high_ids/sizeof *high_ids;++i)
    {
        uid_t high=high_ids[i];
        CHECK(setresgid(high,high,high)==0 && setresuid(high,high,0)==0,133);
        ids(high,high,0,high,high,high);
        CHECK(setuid(0)==0,134);
        CHECK(setresgid(0,0,0)==0 && setresuid(0,0,0)==0,135);
        ids(0,0,0,0,0,0);
    }

    pid_t permanent=fork();CHECK(permanent>=0,124);
    if(!permanent)
    {
        ids(0,0,0,0,0,0);
        CHECK(setgid(1000)==0 && setuid(1000)==0,125);
        ids(1000,1000,1000,1000,1000,1000);
        errno=0;CHECK(setuid(0)==-1 && errno==EPERM,126);
        errno=0;CHECK(setgid(0)==-1 && errno==EPERM,127);
        denied_file();_exit(0);
    }
    wait_clean(permanent);ids(0,0,0,0,0,0);
    pid_t executable=fork();CHECK(executable>=0,128);
    if(!executable)
    {
        CHECK(setresgid(1000,1000,0)==0 && setresuid(1000,1000,0)==0,129);
        ids(1000,1000,0,1000,1000,0);
        char *missing[]={"/bin/saved-ids-does-not-exist",0};
        errno=0;CHECK(execv(missing[0],missing)==-1 && errno==ENOENT,130);
        ids(1000,1000,0,1000,1000,0);
        char *child[]={argv[0],"--exec-child",0};
        execv(child[0],child);fail(131);
    }
    wait_clean(executable);ids(0,0,0,0,0,0);
    // Linux unlink is a separate adapter gate. Keep the private fixture on the
    // disposable test disk and prove restored root can still open/read it.
    char contents[7];fd=open(private_path,O_RDONLY);
    CHECK(fd>=0 && read(fd,contents,sizeof contents)==sizeof contents &&
          !memcmp(contents,"private",sizeof contents) && close(fd)==0,132);
    puts("CREDENTIALS_PASS " ARCH " reversible=1 permanent_child=1 fork=1 failed_exec=1 saved_exec=1 file_permissions=1 failure_atomic=1 thread_gate=2 high_uid=4");
    return 0;
}
