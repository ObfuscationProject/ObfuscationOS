#ifndef _POLL_H
#define _POLL_H

#include <ok/uapi/syscall.h>

typedef unsigned long nfds_t;
struct pollfd
{
    int fd;
    short events;
    short revents;
};

#define POLLIN OK_POLLIN
#define POLLOUT OK_POLLOUT
#define POLLERR OK_POLLERR
#define POLLHUP OK_POLLHUP
#define POLLNVAL OK_POLLNVAL

int poll(struct pollfd *fds, nfds_t count, int timeout);

#endif
