#ifndef _TERMIOS_H
#define _TERMIOS_H

#include <ok/uapi/termios.h>
#include <stdint.h>
#include <sys/types.h>

/* Native terminal attributes: the layout of struct ok_termios (36 bytes, the
 * asm-generic values on all ten profiles). Speeds live only in the CBAUD bits
 * of c_cflag; the input speed is the output speed. */
typedef uint32_t tcflag_t;
typedef uint8_t cc_t;
typedef uint32_t speed_t;

#define NCCS OK_NCCS

struct termios {
    tcflag_t c_iflag;
    tcflag_t c_oflag;
    tcflag_t c_cflag;
    tcflag_t c_lflag;
    cc_t c_line;
    cc_t c_cc[NCCS];
};

#define VINTR OK_VINTR
#define VQUIT OK_VQUIT
#define VERASE OK_VERASE
#define VKILL OK_VKILL
#define VEOF OK_VEOF
#define VTIME OK_VTIME
#define VMIN OK_VMIN
#define VSWTC OK_VSWTC
#define VSTART OK_VSTART
#define VSTOP OK_VSTOP
#define VSUSP OK_VSUSP
#define VEOL OK_VEOL
#define VREPRINT OK_VREPRINT
#define VDISCARD OK_VDISCARD
#define VWERASE OK_VWERASE
#define VLNEXT OK_VLNEXT
#define VEOL2 OK_VEOL2

#define IGNBRK OK_IGNBRK
#define BRKINT OK_BRKINT
#define IGNPAR OK_IGNPAR
#define PARMRK OK_PARMRK
#define INPCK OK_INPCK
#define ISTRIP OK_ISTRIP
#define INLCR OK_INLCR
#define IGNCR OK_IGNCR
#define ICRNL OK_ICRNL
#define IUCLC OK_IUCLC
#define IXON OK_IXON
#define IXANY OK_IXANY
#define IXOFF OK_IXOFF
#define IMAXBEL OK_IMAXBEL
#define IUTF8 OK_IUTF8

#define OPOST OK_OPOST
#define OLCUC OK_OLCUC
#define ONLCR OK_ONLCR
#define OCRNL OK_OCRNL
#define ONOCR OK_ONOCR
#define ONLRET OK_ONLRET
#define OFILL OK_OFILL
#define OFDEL OK_OFDEL
#define NLDLY OK_NLDLY
#define NL0 OK_NL0
#define NL1 OK_NL1
#define CRDLY OK_CRDLY
#define CR0 OK_CR0
#define CR1 OK_CR1
#define CR2 OK_CR2
#define CR3 OK_CR3
#define TABDLY OK_TABDLY
#define TAB0 OK_TAB0
#define TAB1 OK_TAB1
#define TAB2 OK_TAB2
#define TAB3 OK_TAB3
#define XTABS OK_XTABS
#define BSDLY OK_BSDLY
#define BS0 OK_BS0
#define BS1 OK_BS1
#define VTDLY OK_VTDLY
#define VT0 OK_VT0
#define VT1 OK_VT1
#define FFDLY OK_FFDLY
#define FF0 OK_FF0
#define FF1 OK_FF1

#define CBAUD OK_CBAUD
#define CBAUDEX OK_CBAUDEX
#define B0 OK_B0
#define B50 OK_B50
#define B75 OK_B75
#define B110 OK_B110
#define B134 OK_B134
#define B150 OK_B150
#define B200 OK_B200
#define B300 OK_B300
#define B600 OK_B600
#define B1200 OK_B1200
#define B1800 OK_B1800
#define B2400 OK_B2400
#define B4800 OK_B4800
#define B9600 OK_B9600
#define B19200 OK_B19200
#define B38400 OK_B38400
#define B57600 OK_B57600
#define B115200 OK_B115200
#define B230400 OK_B230400
#define B460800 OK_B460800
#define B500000 OK_B500000
#define B576000 OK_B576000
#define B921600 OK_B921600
#define B1000000 OK_B1000000
#define B1152000 OK_B1152000
#define B1500000 OK_B1500000
#define B2000000 OK_B2000000
#define B2500000 OK_B2500000
#define B3000000 OK_B3000000
#define B3500000 OK_B3500000
#define B4000000 OK_B4000000
#define CSIZE OK_CSIZE
#define CS5 OK_CS5
#define CS6 OK_CS6
#define CS7 OK_CS7
#define CS8 OK_CS8
#define CSTOPB OK_CSTOPB
#define CREAD OK_CREAD
#define PARENB OK_PARENB
#define PARODD OK_PARODD
#define HUPCL OK_HUPCL
#define CLOCAL OK_CLOCAL
#define CIBAUD OK_CIBAUD
#define CMSPAR OK_CMSPAR
#define CRTSCTS OK_CRTSCTS

#define ISIG OK_ISIG
#define ICANON OK_ICANON
#define XCASE OK_XCASE
#define ECHO OK_ECHO
#define ECHOE OK_ECHOE
#define ECHOK OK_ECHOK
#define ECHONL OK_ECHONL
#define NOFLSH OK_NOFLSH
#define TOSTOP OK_TOSTOP
#define ECHOCTL OK_ECHOCTL
#define ECHOPRT OK_ECHOPRT
#define ECHOKE OK_ECHOKE
#define FLUSHO OK_FLUSHO
#define PENDIN OK_PENDIN
#define IEXTEN OK_IEXTEN
#define EXTPROC OK_EXTPROC

#define TCIFLUSH OK_TCIFLUSH
#define TCOFLUSH OK_TCOFLUSH
#define TCIOFLUSH OK_TCIOFLUSH

/* tcsetattr actions; libc selectors for TCSETS, TCSETSW and TCSETSF. */
#define TCSANOW 0
#define TCSADRAIN 1
#define TCSAFLUSH 2

int tcgetattr(int fd, struct termios *attributes);
int tcsetattr(int fd, int action, const struct termios *attributes);
int tcflush(int fd, int queue);
int tcdrain(int fd);
pid_t tcgetsid(int fd);
void cfmakeraw(struct termios *attributes);
speed_t cfgetispeed(const struct termios *attributes);
speed_t cfgetospeed(const struct termios *attributes);
int cfsetispeed(struct termios *attributes, speed_t speed);
int cfsetospeed(struct termios *attributes, speed_t speed);

#endif
