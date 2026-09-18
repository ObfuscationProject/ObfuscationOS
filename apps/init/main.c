#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>

static int launch(const char *path, char *const argv[])
{
    pid_t pid = fork();
    if (pid < 0)
        return -1;
    if (pid == 0)
    {
        char *env[] = {"PATH=/bin", 0};
        execve(path, argv, env);
        perror(path);
        _Exit(127);
    }
    int status = 0;
    if (waitpid(pid, &status, 0) != pid)
        return -1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128;
}

int main(void)
{
#ifdef OK_USERLAND_SELFTEST
    puts("ObfuscationOS: /init entered user mode");
    char *check[] = {"posix-check", 0};
    if (launch("/bin/posix-check", check) != 0)
    {
        puts("OK_USERLAND scope=hardware acceptance=FAIL");
        return 1;
    }
    char *script[] = {"oksh", "-c", "hello | cat", 0};
    if (launch("/bin/oksh", script) != 0)
    {
        puts("OK_USERLAND scope=hardware shell_pipeline=FAIL");
        return 1;
    }
    puts("OK_USERLAND scope=hardware acceptance=pass shell_pipeline=pass");
#else
    puts("ObfuscationOS");
#endif
    char *shell[] = {"oksh", 0};
    return launch("/bin/oksh", shell);
}
