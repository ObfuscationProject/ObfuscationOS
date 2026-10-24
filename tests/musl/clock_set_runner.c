#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/mman.h>
#include <ok/syscall.h>

#define CHECK(x) do { if (!(x)) { printf("CLOCK_SET_NATIVE_FAIL line=%d errno=%d\n",__LINE__,errno);return 1; } } while(0)
int main(int argc,char **argv)
{
    if(argc==2 && !strcmp(argv[1],"negative")){
        CHECK(ok_syscall2(OK_SYS_CLOCK_SETTIME,CLOCK_REALTIME,1)==-ENOSYS);
        CHECK(ok_syscall2(OK_SYS_CLOCK_SETTIME,CLOCK_MONOTONIC,1)==-ENOSYS);
        puts("CLOCK_SET_NATIVE_NEGATIVE_PASS expected=SDK18 errno=ENOSYS");
        char *args[]={"musl-clock-set","negative",0};char *env[]={"PATH=/bin",0};
        execve("/bin/musl-clock-set",args,env);return 127;
    }
    CHECK(argc==1);
    const int denied=geteuid()!=0;
    struct timespec value={1700000000,246813579},wall={0,0},mono={0,0};
    CHECK(clock_gettime(CLOCK_MONOTONIC,&mono)==0);
    CHECK(ok_syscall2(OK_SYS_CLOCK_SETTIME,CLOCK_MONOTONIC,1)==-EINVAL);
    CHECK(ok_syscall2(OK_SYS_CLOCK_SETTIME,CLOCK_REALTIME,1)==-EFAULT);
    unsigned char *pages=mmap(0,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(pages!=MAP_FAILED && mprotect(pages+4096,4096,PROT_NONE)==0);
    memcpy(pages+4096-sizeof value,&value,sizeof value);
    CHECK(ok_syscall2(OK_SYS_CLOCK_SETTIME,CLOCK_REALTIME,(long)(pages+4097-sizeof value))==-EFAULT);
    CHECK(!memcmp(pages+4096-sizeof value,&value,sizeof value));
    CHECK(mprotect(pages,4096,PROT_READ)==0);
    int edge=clock_settime(CLOCK_REALTIME,(const struct timespec *)(pages+4096-sizeof value));
    CHECK(denied?(edge==-1 && errno==EPERM):edge==0);
    CHECK(munmap(pages,8192)==0);
    if(denied){
        CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EPERM);
        value.tv_nsec=1000000000;CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EINVAL);
        puts("CLOCK_SET_NATIVE_DENIED_PASS authority=real-process errno=EPERM");
        char *args[]={"musl-clock-set","deny",0};char *env[]={"PATH=/bin",0};
        execve("/bin/musl-clock-set",args,env);return 127;
    }
    CHECK(clock_settime(CLOCK_REALTIME,&value)==0);
    CHECK(clock_gettime(CLOCK_REALTIME,&wall)==0 && wall.tv_sec>=value.tv_sec && wall.tv_sec<=value.tv_sec+3);
    value.tv_nsec=(int64_t)1<<32;CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EINVAL);
    value.tv_sec=8277292036LL;value.tv_nsec=0;CHECK(clock_settime(CLOCK_REALTIME,&value)==-1 && errno==EINVAL);
    pid_t child=fork();CHECK(child>=0);
    if(!child){
        char *args[]={"musl-clock-set",0};char *env[]={"PATH=/bin",0};
        execve("/bin/musl-clock-set",args,env);printf("CLOCK_SET_NATIVE_EXEC_ERROR errno=%d\n",errno);_Exit(127);
    }
    int status=0;pid_t waited=waitpid(child,&status,0);printf("CLOCK_SET_NATIVE_WAIT pid=%d status=%d\n",(int)waited,status);CHECK(waited==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
    CHECK(clock_gettime(CLOCK_REALTIME,&wall)==0 && wall.tv_sec>=2214176523LL && wall.tv_sec<=2214176526LL);
    struct timespec later;CHECK(clock_gettime(CLOCK_MONOTONIC,&later)==0 && later.tv_sec>=mono.tv_sec);
    puts("CLOCK_SET_NATIVE_PASS setter=pass global-musl-child=pass monotonic=pass");return 0;
}
