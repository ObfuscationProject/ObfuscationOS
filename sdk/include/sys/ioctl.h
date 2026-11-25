#ifndef _SYS_IOCTL_H
#define _SYS_IOCTL_H

#include <ok/uapi/syscall.h>

/* Native request numbers are the asm-generic ones on all ten profiles. */
#define TCGETS OK_TCGETS
#define TCSETS OK_TCSETS
#define TCSETSW OK_TCSETSW
#define TCSETSF OK_TCSETSF
#define TCSBRK OK_TCSBRK
#define TCFLSH OK_TCFLSH
#define TIOCSCTTY OK_TIOCSCTTY
#define TIOCGPGRP OK_TIOCGPGRP
#define TIOCSPGRP OK_TIOCSPGRP
#define TIOCGWINSZ OK_TIOCGWINSZ
#define TIOCSWINSZ OK_TIOCSWINSZ
#define FIONREAD OK_FIONREAD
#define TIOCNOTTY OK_TIOCNOTTY
#define TIOCGSID OK_TIOCGSID
#define TIOCGPTN OK_TIOCGPTN
#define TIOCSPTLCK OK_TIOCSPTLCK

/* Same layout as struct ok_winsize (lib/okcrt checks it). */
struct winsize {
    unsigned short ws_row;
    unsigned short ws_col;
    unsigned short ws_xpixel;
    unsigned short ws_ypixel;
};

int ioctl(int fd, unsigned long request, ...);

#endif
