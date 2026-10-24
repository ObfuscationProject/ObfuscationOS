#ifndef _SIGNAL_H
#define _SIGNAL_H

#include <ok/uapi/signal.h>
#include <sys/types.h>

#define SIGKILL OK_SIGKILL
#define SIGTERM OK_SIGTERM

int kill(pid_t pid, int signal);

#endif
