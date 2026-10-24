#ifndef OK_CONSOLE_H
#define OK_CONSOLE_H

#include <stdint.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

/* A successful claim returns a positive epoch. Only boot PID1 can claim/revoke. */
int ok_console_claim(pid_t leader);
int ok_console_revoke(uint32_t epoch);
int ok_console_flush(uint32_t epoch);

#ifdef __cplusplus
}
#endif

#endif
