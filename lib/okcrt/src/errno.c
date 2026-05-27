#include <errno.h>

int errno;

long ok_syscall_ret(long result)
{
    if (result < 0 && result >= -4095) {
        errno = (int)-result;
        return -1;
    }
    return result;
}
