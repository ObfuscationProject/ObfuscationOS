#ifndef OK_POWER_H
#define OK_POWER_H

#include <stdint.h>
#include <ok/uapi/syscall.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Original native PID1 only. PREPARE is non-consuming and returns a positive
 * selector <= OK_POWER_TOKEN_MAX. COMMIT success means queued, not clean. */
int ok_power_prepare(uint32_t action);
int ok_power_commit(uint32_t token);

#ifdef __cplusplus
}
#endif

#endif
