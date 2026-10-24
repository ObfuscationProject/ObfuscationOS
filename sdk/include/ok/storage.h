#ifndef OK_STORAGE_H
#define OK_STORAGE_H

#include <stdint.h>
#include <ok/uapi/syscall.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Refuses providers without the native persistent storage contract. Ordinary
 * fsync success on a RAM filesystem does not satisfy this operation. */
int ok_sync_persistent(int descriptor);

/* Public, native-only observation of one boot-local VFS slot. It grants no
 * mount authority, ownership reference, drain or shutdown admission. */
int ok_mount_info(uint32_t slot, struct ok_mount_info *output);

#ifdef __cplusplus
}
#endif

#endif
