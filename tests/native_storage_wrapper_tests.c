/* Hosted native syscall marshalling; no filesystem is synchronized. */
#include <errno.h>
#include <ok/storage.h>
#include <ok/syscall.h>

static long selected, arguments[6], response;
int errno;
long ok_syscall6(long number, long value, long a1, long a2, long a3, long a4, long a5)
{
    selected = number;
    arguments[0] = value; arguments[1] = a1; arguments[2] = a2;
    arguments[3] = a3; arguments[4] = a4; arguments[5] = a5;
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
    response = 0; errno = 73;
    CHECK(!ok_sync_persistent(17) && selected == 1031 && arguments[0] == 17 && errno == 73);
    for (unsigned i = 1; i < 6; ++i) CHECK(!arguments[i]);
    response = -OK_EOPNOTSUPP; errno = 0;
    CHECK(ok_sync_persistent(18) == -1 && errno == EOPNOTSUPP);
    response = -OK_EBADF; errno = 0;
    CHECK(ok_sync_persistent(-1) == -1 && arguments[0] == -1 && errno == EBADF);
    response = -OK_EIO; errno = 0;
    CHECK(ok_sync_persistent(19) == -1 && errno == EIO);
    for (unsigned i = 1; i < 6; ++i) CHECK(!arguments[i]);
    struct ok_mount_info row;
    response = 0; errno = 73;
    CHECK(!ok_mount_info(UINT32_MAX, &row) && selected == 1034 && errno == 73);
    CHECK((uint32_t)arguments[0] == UINT32_MAX && arguments[1] == (long)&row && arguments[2] == 288);
    for (unsigned i = 3; i < 6; ++i) CHECK(!arguments[i]);
    response = -EFAULT; errno = 0;
    CHECK(ok_mount_info(1, 0) == -1 && errno == EFAULT && !arguments[1]);
    response = -EBUSY; errno = 0;
    CHECK(ok_mount_info(8, &row) == -1 && errno == EBUSY);
    response = -ENOSYS; errno = 0;
    CHECK(ok_mount_info(0, &row) == -1 && errno == ENOSYS);
    response = 1; errno = 0;
    CHECK(ok_mount_info(0, &row) == -1 && errno == EIO);
    return 0;
}
