#ifndef OK_PTY_H
#define OK_PTY_H

#include <stdint.h>

#define OK_PTY_NONBLOCK 0x0800U
#define OK_PTY_CLOEXEC 0x080000U

#ifdef __cplusplus
extern "C" {
#endif

/* Native raw pair: master, then slave. The slave runs N_TTY under raw
 * termios (cfmakeraw of the standard settings); the pair never appears in
 * /dev/pts, so TIOCGPTN and TIOCSPTLCK give ENOTTY. Use posix_openpt for a
 * /dev/pts pair. Both kinds share the kernel's eight PTY slots. */
int ok_pty_pair(int descriptors[2], uint32_t flags);

#ifdef __cplusplus
}
#endif

#endif
