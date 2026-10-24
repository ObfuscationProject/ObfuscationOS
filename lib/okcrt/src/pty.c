#include <ok/pty.h>
#include <ok/syscall.h>

_Static_assert(sizeof(int) == 4, "native PTY descriptor width");
_Static_assert(OK_NATIVE_PTY_PAIR_VERSION == 1, "native PTY pair contract");
_Static_assert(OK_PTY_NONBLOCK == OK_NATIVE_PTY_NONBLOCK, "native PTY nonblock flag");
_Static_assert(OK_PTY_CLOEXEC == OK_NATIVE_PTY_CLOEXEC, "native PTY cloexec flag");

int ok_pty_pair(int descriptors[2], uint32_t flags)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_PTY_PAIR, (long)descriptors,
                                         (long)flags, 0, 0, 0, 0));
}
