#include <errno.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

int main(void)
{
    pid_t child = fork();
    if (child < 0) return 80;
    if (child == 0)
    {
        char *argv[] = {"entropy-static", 0};
        char *envp[] = {"PATH=/bin", 0};
        execve("/bin/entropy-static", argv, envp);
        if (errno != EAGAIN) _Exit(126);
        static const char rollback[] = "OK_STATIC_ENTROPY_ROLLBACK errno=11 continued=1\n";
        if (write(1, rollback, sizeof rollback - 1) != sizeof rollback - 1) _Exit(125);
        _Exit(124);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status)) return 81;
    if (WEXITSTATUS(status) == 0)
    {
        static const char record[] = "OK_STATIC_ENTROPY_RUNNER child_exit=0 normal=1\n";
        return write(1, record, sizeof record - 1) == sizeof record - 1 ? 0 : 83;
    }
    if (WEXITSTATUS(status) == 124)
    {
        static const char record[] = "OK_STATIC_ENTROPY_RUNNER child_exit=124 normal=1\n";
        return write(1, record, sizeof record - 1) == sizeof record - 1 ? 0 : 83;
    }
    static const char failure[] = "OK_STATIC_ENTROPY_RUNNER child_exit=unexpected normal=0\n";
    (void)write(1, failure, sizeof failure - 1);
    return 82;
}
