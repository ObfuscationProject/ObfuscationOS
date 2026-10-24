#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <sys/mman.h>
#include <ok/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

static void native_number(int64_t value)
{
    char bytes[24]; unsigned count=0; uint64_t magnitude=(uint64_t)value;
    if(value<0){(void)write(1,"-",1);magnitude=0-magnitude;}
    do {bytes[count++]=(char)('0'+magnitude%10);magnitude/=10;} while(magnitude);
    for(unsigned i=0;i<count/2;++i){char c=bytes[i];bytes[i]=bytes[count-i-1];bytes[count-i-1]=c;}
    (void)write(1,bytes,count);
}

static void native_sample(const char *role, const struct timespec *wall, const struct timespec *mono)
{
    printf("OK_NATIVE_REALTIME_SAMPLE role=%s seconds=",role);native_number(wall->tv_sec);
    printf(" nanoseconds=");native_number(wall->tv_nsec);
    printf(" monotonic_seconds=");native_number(mono->tv_sec);
    printf(" monotonic_nanoseconds=");native_number(mono->tv_nsec);puts("");
}

#define RTC_CHECK(condition) do {if(!(condition)){printf("MUSL_CHECK failed: native realtime line=%d errno=%d\n",__LINE__,errno);return 41;}} while(0)

static int native_realtime(const char *role)
{
    struct timespec wall={71,92}, mono={0,0}, resolution={71,92}, later;
    RTC_CHECK(clock_getres(CLOCK_REALTIME,0)==0 && clock_getres(CLOCK_MONOTONIC,0)==0);
    RTC_CHECK(clock_getres(-1,0)==-1 && errno==EINVAL);
    RTC_CHECK(clock_gettime(CLOCK_MONOTONIC,&mono)==0 && mono.tv_sec>=0);
    errno=0;int available=clock_gettime(CLOCK_REALTIME,&wall)==0;
    struct ok_timeval tv={71,92};int64_t output=123;
    RTC_CHECK(ok_syscall2(OK_SYS_GETTIMEOFDAY,0,1)==0);
    if(!available){
        RTC_CHECK(errno==EIO && wall.tv_sec==71 && wall.tv_nsec==92);
        RTC_CHECK(clock_getres(CLOCK_REALTIME,&resolution)==-1 && errno==EIO && resolution.tv_sec==71 && resolution.tv_nsec==92);
        RTC_CHECK(ok_syscall1(OK_SYS_TIME,(long)&output)==-EIO && output==123);
        RTC_CHECK(ok_syscall2(OK_SYS_GETTIMEOFDAY,(long)&tv,0)==-EIO && tv.seconds==71 && tv.microseconds==92);
        RTC_CHECK(ok_syscall2(OK_SYS_CLOCK_GETTIME,0,1)==-EIO);
        printf("OK_NATIVE_REALTIME role=%s capability=unavailable errors=pass copies=unchanged monotonic=pass\n",role);
        return 0;
    }
    RTC_CHECK(wall.tv_sec>=0 && wall.tv_nsec>=0 && wall.tv_nsec<1000000000);
    RTC_CHECK(clock_getres(CLOCK_REALTIME,&resolution)==0 && resolution.tv_sec==0 && resolution.tv_nsec>0 && resolution.tv_nsec<1000000000);
    RTC_CHECK(ok_syscall2(OK_SYS_CLOCK_GETTIME,0,1)==-EFAULT);
    RTC_CHECK(ok_syscall2(OK_SYS_GETTIMEOFDAY,1,0)==-EFAULT);
    long legacy=ok_syscall1(OK_SYS_TIME,(long)&output);
    if(sizeof(long)==4 && wall.tv_sec>2147483647LL){
        RTC_CHECK(legacy==-EOVERFLOW && output==123 && ok_syscall1(OK_SYS_TIME,1)==-EOVERFLOW);
    }else{
        RTC_CHECK(legacy>=wall.tv_sec && legacy<=wall.tv_sec+1 && output==legacy);
        RTC_CHECK(ok_syscall1(OK_SYS_TIME,1)==-EFAULT);
    }
    RTC_CHECK(ok_syscall2(OK_SYS_GETTIMEOFDAY,(long)&tv,0)==0 && tv.seconds>=wall.tv_sec && tv.seconds<=wall.tv_sec+1 && tv.microseconds>=0 && tv.microseconds<1000000);
    unsigned char *pages=mmap(0,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    RTC_CHECK(pages!=MAP_FAILED && mprotect(pages+4096,4096,PROT_NONE)==0);
    memset(pages+4096-16,0xa5,16);
    RTC_CHECK(ok_syscall2(OK_SYS_CLOCK_GETTIME,0,(long)(pages+4096-15))==-EFAULT);
    for(unsigned i=0;i<16;++i)RTC_CHECK(pages[4096-16+i]==0xa5);
    RTC_CHECK(ok_syscall2(OK_SYS_CLOCK_GETTIME,0,(long)(pages+4096-16))==0);
    RTC_CHECK(munmap(pages,8192)==0);
    native_sample(role,&wall,&mono);
    struct timespec delay={0,20000000};
    RTC_CHECK(nanosleep(&delay,0)==0 && clock_gettime(CLOCK_REALTIME,&later)==0);
    RTC_CHECK(later.tv_sec>wall.tv_sec || (later.tv_sec==wall.tv_sec && later.tv_nsec>wall.tv_nsec));
    printf("OK_NATIVE_REALTIME role=%s capability=available legacy=%s copies=pass sleep=pass\n",role,
           sizeof(long)==4 && wall.tv_sec>2147483647LL ? "overflow" : "pass");
    return 0;
}

/* Native parent checks Linux-personality exec and its real exit status. */
int main(int argc, char **argv)
{
    if(argc==2 && !strcmp(argv[1],"realtime-native-exec"))return native_realtime("exec");
    if(argc!=1 || native_realtime("parent"))return 40;
    pid_t native_child=fork();
    RTC_CHECK(native_child>=0);
    if(!native_child){
        if(native_realtime("fork"))_Exit(42);
        char *args[]={"musl-test-runner","realtime-native-exec",0};
        char *env[]={"PATH=/bin",0};
        execve("/bin/musl-test-runner",args,env);_Exit(43);
    }
    int native_status=0;
    RTC_CHECK(waitpid(native_child,&native_status,0)==native_child && WIFEXITED(native_status) && WEXITSTATUS(native_status)==0);
    for (int attempt = 0; attempt < 2; ++attempt) {
        pid_t child = fork();
        if (child < 0)
            return 1;
        if (child == 0) {
            char *arguments[] = {"musl-bootstrap", 0};
            char *environment[] = {"PATH=/bin", 0};
            execve("/bin/musl-bootstrap", arguments, environment);
            _Exit(127);
        }
        int status = 0;
        if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
            printf("MUSL_CHECK failed: child status=%d\n", status);
            return 2;
        }
    }
    puts("OK_MUSL_PARENT scope=hardware native=pass exec=pass wait=pass exit=pass repeat=pass");
    return 0;
}
