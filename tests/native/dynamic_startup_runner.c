#include <errno.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

static int report(int code, int normal)
{
    if (normal && code == 0)
    {
        static const char record[] = "OK_DYNAMIC_RUNNER child_exit=0 normal=1\n";
        return write(1, record, sizeof record - 1) == sizeof record - 1;
    }
    if (normal && code == 127)
    {
        static const char record[] = "OK_DYNAMIC_RUNNER child_exit=127 normal=1\n";
        return write(1, record, sizeof record - 1) == sizeof record - 1;
    }
    if (normal && code == 124)
    {
        static const char record[] = "OK_DYNAMIC_RUNNER child_exit=124 normal=1\n";
        return write(1, record, sizeof record - 1) == sizeof record - 1;
    }
    static const char failure[] = "OK_DYNAMIC_RUNNER child_exit=unexpected normal=0\n";
    return write(1, failure, sizeof failure - 1) == sizeof failure - 1;
}

int main(void)
{
    pid_t child = fork();
    if (child < 0)
        return 80;
    if (child == 0)
    {
        char *argv[] = {"dynamic-startup", 0};
        char *envp[] = {"PATH=/bin", 0};
        execve("/bin/dynamic-startup", argv, envp);
        const int saved_errno = errno;
        if (saved_errno != ENOENT)
        {
            if (saved_errno != EAGAIN)
                _Exit(126);
            static const char record[] = "OK_DYNAMIC_NO_ENTROPY errno=11 continued=1\n";
            if (write(1, record, sizeof record - 1) != sizeof record - 1)
                _Exit(125);
            _Exit(124);
        }
        static const char record[] = "OK_DYNAMIC_ROLLBACK errno=2 continued=1\n";
        if (write(1, record, sizeof record - 1) != sizeof record - 1)
            _Exit(125);
        _Exit(127);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child)
        return 81;
    if (!report(WIFEXITED(status) ? WEXITSTATUS(status) : -1, WIFEXITED(status) ? 1 : 0))
        return 83;
    return WIFEXITED(status) &&
        (WEXITSTATUS(status) == 0 || WEXITSTATUS(status) == 124 || WEXITSTATUS(status) == 127) ? 0 : 82;
}
