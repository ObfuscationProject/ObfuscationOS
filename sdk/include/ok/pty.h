#ifndef OK_PTY_H
#define OK_PTY_H

#include <stdint.h>

#define OK_PTY_NONBLOCK 0x0800U
#define OK_PTY_CLOEXEC 0x080000U

#ifdef __cplusplus
extern "C" {
#endif

/* Native raw transport only: master, then slave. No line discipline or devpts. */
int ok_pty_pair(int descriptors[2], uint32_t flags);

#ifdef __cplusplus
}
#endif

#endif
