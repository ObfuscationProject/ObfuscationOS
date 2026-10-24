#include <ok/console.h>
#include <ok/syscall.h>

_Static_assert(OK_NATIVE_CONSOLE_LEASE_VERSION == 1, "native console lease contract");
_Static_assert(OK_CONSOLE_EPOCH_MAX == 0x3fffffffU, "native console epoch width");

int ok_console_claim(pid_t leader)
{
    /* The lease UAPI admits only one argument and requires all reserved words
     * to be zero. Short syscall stubs leave unused argument registers intact. */
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_CONSOLE_CLAIM, leader, 0, 0, 0, 0, 0));
}

int ok_console_revoke(uint32_t epoch)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_CONSOLE_REVOKE, (long)epoch, 0, 0, 0, 0, 0));
}

int ok_console_flush(uint32_t epoch)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_CONSOLE_FLUSH, (long)epoch, 0, 0, 0, 0, 0));
}
