#ifndef _SYS_IOCTL_H
#define _SYS_IOCTL_H

#include <ok/uapi/syscall.h>

#define TIOCSCTTY OK_TIOCSCTTY
#define TIOCGPGRP OK_TIOCGPGRP
#define TIOCSPGRP OK_TIOCSPGRP
#define TIOCGSID OK_TIOCGSID

int ioctl(int fd, unsigned long request, ...);

#endif
