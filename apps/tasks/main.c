#include <ok/syscall.h>
#include <stdio.h>
#include <unistd.h>

int main(void)
{
    struct ok_sysinfo info;
    if (ok_syscall_ret(ok_syscall1(OK_SYS_SYSINFO, (long)&info)) < 0)
    {
        perror("sysinfo");
        return 1;
    }
    puts("System activity");
    printf("Processes: %u\n", (unsigned)info.process_count);
    printf("This process: %d\n", (int)getpid());
    printf("User: %u\n", (unsigned)geteuid());
    printf("Uptime: %ld seconds\n", (long)info.uptime);
    return 0;
}
