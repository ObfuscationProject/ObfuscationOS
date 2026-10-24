#include <ok/power.h>
#include <ok/syscall.h>
#include <errno.h>

_Static_assert(OK_UAPI_VERSION_MAJOR == 0 && OK_UAPI_VERSION_MINOR == 16 && OK_UAPI_VERSION_PATCH == 0,
               "native power requires the explicit UAPI0.16.0 SDK");
_Static_assert(OK_NATIVE_POWER_VERSION == 1 && OK_POWER_TOKEN_MAX == 0x3fffffffU,
               "native scalar power contract");

int ok_power_prepare(uint32_t action)
{
    /* Short stubs leave unused argument registers intact. Always clear all
     * five reserved words, even for a malformed action the Kernel will refuse. */
    long result = ok_syscall_ret(ok_syscall6(OK_SYS_POWER_PREPARE, (long)action, 0, 0, 0, 0, 0));
    if (result < 0) return -1;
    if (!result || result > OK_POWER_TOKEN_MAX) { errno = EIO; return -1; }
    return (int)result;
}

int ok_power_commit(uint32_t token)
{
    long result = ok_syscall_ret(ok_syscall6(OK_SYS_POWER_COMMIT, (long)token, 0, 0, 0, 0, 0));
    if (result < 0) return -1;
    if (result) { errno = EIO; return -1; }
    return 0;
}
