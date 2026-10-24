/* Hosted native syscall marshalling; no console ownership is acquired. */
#include <errno.h>
#include <ok/console.h>
#include <ok/syscall.h>

static long selected, argument, response, reserved_nonzero;
int errno;
long ok_syscall6(long number, long value, long a1, long a2, long a3, long a4, long a5)
{
    selected = number; argument = value;
    reserved_nonzero |= a1 | a2 | a3 | a4 | a5;
    return response;
}
long ok_syscall_ret(long result)
{
    if (result < 0 && result >= -4095) { errno = (int)-result; return -1; }
    return result;
}
#define CHECK(value) do { if (!(value)) return __LINE__; } while (0)
int main(void)
{
    response = OK_CONSOLE_EPOCH_MAX; errno = 73;
    CHECK(ok_console_claim(17) == OK_CONSOLE_EPOCH_MAX && selected == OK_SYS_CONSOLE_CLAIM && argument == 17 && errno == 73);
    response = 0;
    CHECK(!ok_console_revoke(OK_CONSOLE_EPOCH_MAX) && selected == OK_SYS_CONSOLE_REVOKE && argument == OK_CONSOLE_EPOCH_MAX);
    CHECK(!ok_console_flush(29) && selected == OK_SYS_CONSOLE_FLUSH && argument == 29);
    response = -OK_EACCES; errno = 0;
    CHECK(ok_console_claim(18) == -1 && errno == EACCES);
    response = -OK_EBUSY; errno = 0;
    CHECK(ok_console_revoke(28) == -1 && errno == EBUSY);
    response = -OK_EOVERFLOW; errno = 0;
    CHECK(ok_console_flush(0) == -1 && errno == EOVERFLOW);
    CHECK(!reserved_nonzero);
    return 0;
}
