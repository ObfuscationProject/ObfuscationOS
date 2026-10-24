#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

int main(void)
{
    pid_t child = fork();
    if (child < 0) return 80;
    if (child == 0)
    {
        char *argv[] = {"unix-socketpair-static", 0};
        char *envp[] = {"PATH=/bin", 0};
        execve("/bin/unix-socketpair-static", argv, envp);
        _Exit(126);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status) != 0)
        return 81;
    static const char record[] = "OK_STATIC_UNIX_SOCKETPAIR_RUNNER child_exit=0\n";
    return write(1, record, sizeof record - 1) == sizeof record - 1 ? 0 : 82;
}
