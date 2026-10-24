#include <ok/storage.h>
#include <ok/syscall.h>
#include <errno.h>

_Static_assert(OK_NATIVE_PERSISTENT_SYNC_VERSION == 1, "native persistent sync contract");
_Static_assert(OK_NATIVE_MOUNT_INFO_VERSION == 1 && sizeof(struct ok_mount_info) == 288,
               "native mount inventory contract");

int ok_sync_persistent(int descriptor)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_SYNC_PERSISTENT, descriptor, 0, 0, 0, 0, 0));
}

int ok_mount_info(uint32_t slot, struct ok_mount_info *output)
{
    long result = ok_syscall_ret(ok_syscall6(OK_SYS_MOUNT_INFO, (long)slot, (long)output,
                                           (long)sizeof(*output), 0, 0, 0));
    if (result < 0) return -1;
    if (result) { errno = EIO; return -1; }
    return 0;
}
