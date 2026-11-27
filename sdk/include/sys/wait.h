#ifndef _SYS_WAIT_H
#define _SYS_WAIT_H
#include <ok/uapi/job_control.h>
#include <sys/types.h>
#define WNOHANG OK_WNOHANG
#define WUNTRACED OK_WUNTRACED
#define WCONTINUED OK_WCONTINUED
/* Kernel status words: exit (code<<8), termination by sig (sig), stopped
 * (sig<<8)|0x7f, continued 0xffff. */
#define WIFEXITED(status) (((status) & 0x7f) == 0)
#define WIFSIGNALED(status) (((status) & 0x7f) != 0 && ((status) & 0x7f) != 0x7f)
#define WTERMSIG(status) ((status) & 0x7f)
#define WEXITSTATUS(status) (((status) >> 8) & 0xff)
#define WIFSTOPPED(status) (((status) & 0xff) == 0x7f)
#define WSTOPSIG(status) (((status) >> 8) & 0xff)
#define WIFCONTINUED(status) ((status) == 0xffff)
pid_t waitpid(pid_t pid, int *status, int options);
#endif
