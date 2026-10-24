#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

int oksh_main(int argc, char **argv);
pid_t __real_fork(void);
int __real_pipe(int fds[2]);
int __real_dup2(int from, int to);
pid_t __real_waitpid(pid_t pid, int *status, int flags);
int __real_setpgid(pid_t pid, pid_t group);
static pid_t terminal_sid, terminal_group, shell_group;
static int console_enabled;
pid_t hosted_shell_pid;

static void terminal_event(const char *format, ...)
{
    const char *path = getenv("OKSH_CONSOLE_EVENTS");
    if (!path) return;
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (fd < 0) _Exit(125);
    va_list arguments;
    va_start(arguments, format);
    vdprintf(fd, format, arguments);
    va_end(arguments);
    close(fd);
}
static int fail_at(const char *name, unsigned *calls)
{
    const char *value = getenv(name);
    ++*calls;
    return value && (unsigned)atoi(value) == *calls;
}
pid_t __wrap_fork(void)
{
    static unsigned calls;
    if (fail_at("OKSH_FAIL_FORK", &calls)) { errno = EAGAIN; return -1; }
    return __real_fork();
}
int __wrap_pipe(int fds[2])
{
    static unsigned calls;
    if (fail_at("OKSH_FAIL_PIPE", &calls)) { errno = EMFILE; return -1; }
    return __real_pipe(fds);
}
int __wrap_dup2(int from, int to)
{
    static unsigned calls;
    if (fail_at("OKSH_FAIL_DUP2", &calls)) { errno = EBADF; return -1; }
    return __real_dup2(from, to);
}
pid_t __wrap_waitpid(pid_t pid, int *status, int flags)
{
    static unsigned calls, permanent;
    if (fail_at("OKSH_INTERRUPT_WAIT", &calls)) { errno = EINTR; return -1; }
    if (fail_at("OKSH_FAIL_WAIT", &permanent)) { errno = EIO; return -1; }
    return __real_waitpid(pid, status, flags);
}
pid_t __wrap_tcgetsid(int fd)
{
    terminal_event("SID %d\n", fd);
    const char *mask = getenv("OKSH_CONSOLE_MASK");
    if (!console_enabled || (fd < 3 && !(atoi(mask) & (1 << fd)))) {
        errno = ENOTTY; return -1;
    }
    if (getenv("OKSH_WRONG_CONSOLE_SID")) return terminal_sid + 1;
    return terminal_sid;
}
pid_t __wrap_tcgetpgrp(int fd)
{
    terminal_event("GET %d %ld\n", fd, (long)terminal_group);
    return terminal_group;
}
int __wrap_tcsetpgrp(int fd, pid_t group)
{
    static unsigned calls;
    if (fd < 3 || fcntl(fd, F_GETFD) != FD_CLOEXEC) _Exit(125);
    if (fail_at("OKSH_FAIL_FOREGROUND", &calls)) {
        terminal_event("SET_FAIL %d %ld\n", fd, (long)group);
        errno = EPERM; return -1;
    }
    if (getenv("OKSH_FAIL_RESTORE") && group == shell_group) {
        terminal_event("RESTORE_FAIL %d %ld\n", fd, (long)group);
        errno = EIO; return -1;
    }
    terminal_group = group;
    terminal_event("SET %d %ld\n", fd, (long)group);
    return 0;
}
int __wrap_setpgid(pid_t pid, pid_t group)
{
    static unsigned calls;
    if (fail_at("OKSH_FAIL_SETPGID", &calls)) {
        terminal_event("GROUP_FAIL %ld %ld\n", (long)pid, (long)group);
        errno = EPERM; return -1;
    }
    int result = __real_setpgid(pid, group);
    terminal_event("GROUP %ld %ld %ld\n", (long)pid, (long)group, (long)getpgid(pid));
    return result;
}
int main(int argc, char **argv)
{
    const char *mask = getenv("OKSH_CONSOLE_MASK");
    console_enabled = mask && atoi(mask);
    hosted_shell_pid = getpid();
    terminal_sid = getsid(0);
    terminal_group = shell_group = getpgrp();
    terminal_event("SHELL %ld %ld %ld\n", (long)getpid(), (long)terminal_sid, (long)shell_group);
    if (getenv("OKSH_CLOSE_STDIN")) close(0);
    if (getenv("OKSH_CLOSE_STDOUT")) close(1);
    int before[64];
    for (int fd = 3; fd < 64; ++fd) before[fd] = fcntl(fd, F_GETFD);
    int result = oksh_main(argc, argv);
    for (int fd = 3; fd < 64; ++fd)
        if (before[fd] < 0 && fcntl(fd, F_GETFD) >= 0) return 125;
    int status;
    if (__real_waitpid(-1, &status, WNOHANG) != -1 || errno != ECHILD) return 125;
    return result;
}
