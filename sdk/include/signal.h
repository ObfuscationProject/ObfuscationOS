#ifndef _SIGNAL_H
#define _SIGNAL_H

#include <ok/uapi/job_control.h>
#include <ok/uapi/signal.h>
#include <stdint.h>
#include <sys/types.h>

#define SIGHUP OK_SIGHUP
#define SIGINT OK_SIGINT
#define SIGQUIT OK_SIGQUIT
#define SIGKILL OK_SIGKILL
#define SIGTERM OK_SIGTERM
#define SIGCHLD OK_SIGCHLD
#define SIGCONT OK_SIGCONT
#define SIGSTOP OK_SIGSTOP
#define SIGTSTP OK_SIGTSTP
#define SIGTTIN OK_SIGTTIN
#define SIGTTOU OK_SIGTTOU
#define SIGWINCH OK_SIGWINCH

/* Native processes have SIG_DFL and SIG_IGN only (no handlers, flags or
 * masks); any other handler is refused with EINVAL. */
typedef void (*sighandler_t)(int);
typedef uint64_t sigset_t;
#define SIG_DFL ((sighandler_t)OK_SIG_DFL)
#define SIG_IGN ((sighandler_t)OK_SIG_IGN)
#define SIG_ERR ((sighandler_t)-1)

struct sigaction
{
    sighandler_t sa_handler;
    sigset_t sa_mask;
    int sa_flags;
};

int kill(pid_t pid, int signal);
sighandler_t signal(int signal, sighandler_t handler);
int sigaction(int signal, const struct sigaction *action, struct sigaction *old);
int sigemptyset(sigset_t *set);

#endif
