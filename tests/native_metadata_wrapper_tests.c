/* Actual metadata wrappers and errno with a hosted syscall6 capture seam. */
#include <errno.h>
#include <fcntl.h>
#include <ok/syscall.h>
#include <sys/stat.h>
#include <unistd.h>

static long selected, arguments[6], response;
static unsigned calls;
long ok_syscall6(long number, long a0, long a1, long a2, long a3, long a4, long a5)
{
    ++calls; selected = number;
    arguments[0] = a0; arguments[1] = a1; arguments[2] = a2;
    arguments[3] = a3; arguments[4] = a4; arguments[5] = a5;
    return response;
}
#define CHECK(value) do { if (!(value)) return __LINE__; } while (0)
static int zeros(unsigned first)
{
    for (unsigned i = first; i < 6; ++i) if (arguments[i]) return 0;
    return 1;
}
int main(void)
{
    const char path[] = "target";
    const uint32_t modes[] = {0, 0600, 04750, UINT32_MAX};
    const uint32_t ids[] = {0, 1, 0x80000001U, UINT32_MAX};
    for (unsigned i = 0; i < sizeof(modes) / sizeof(modes[0]); ++i) {
        response = 0; errno = 73;
        CHECK(chmod(path, modes[i]) == 0 && errno == 73);
        CHECK(selected == 90 && arguments[0] == (long)path && arguments[1] == (long)modes[i] && zeros(2));
        CHECK(fchmod(-1, modes[i]) == 0 && selected == 91 && arguments[0] == -1);
        CHECK(arguments[1] == (long)modes[i] && zeros(2));
        CHECK(fchmodat(AT_FDCWD, path, modes[i], AT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW) == 0);
        CHECK(selected == 268 && arguments[0] == AT_FDCWD && arguments[1] == (long)path);
        CHECK(arguments[2] == (long)modes[i] && arguments[3] == 0x1100 && zeros(4));
    }
    for (unsigned i = 0; i < sizeof(ids) / sizeof(ids[0]); ++i) {
        for (unsigned j = 0; j < sizeof(ids) / sizeof(ids[0]); ++j) {
            CHECK(chown(path, ids[i], ids[j]) == 0 && selected == 92 && arguments[0] == (long)path);
            CHECK(arguments[1] == (long)ids[i] && arguments[2] == (long)ids[j] && zeros(3));
            CHECK(fchown(7, ids[i], ids[j]) == 0 && selected == 93 && arguments[0] == 7);
            CHECK(arguments[1] == (long)ids[i] && arguments[2] == (long)ids[j] && zeros(3));
            CHECK(fchownat(AT_FDCWD, path, ids[i], ids[j], AT_SYMLINK_NOFOLLOW) == 0);
            CHECK(selected == 260 && arguments[0] == AT_FDCWD && arguments[1] == (long)path);
            CHECK(arguments[2] == (long)ids[i] && arguments[3] == (long)ids[j]);
            CHECK(arguments[4] == AT_SYMLINK_NOFOLLOW && zeros(5));
        }
    }
    const int errors[] = {EPERM, EACCES, EBADF, EFAULT, EINVAL, ENOENT, ENAMETOOLONG, EROFS, EOPNOTSUPP, EIO};
    for (unsigned i = 0; i < sizeof(errors) / sizeof(errors[0]); ++i) {
        response = -errors[i]; errno = 0;
        CHECK(chmod(path, 0600) == -1 && errno == errors[i]);
        CHECK(fchmod(7, 0600) == -1 && errno == errors[i]);
        CHECK(fchmodat(AT_FDCWD, path, 0600, 0) == -1 && errno == errors[i]);
        CHECK(chown(path, 0, UINT32_MAX) == -1 && errno == errors[i]);
        CHECK(fchown(7, UINT32_MAX, 0) == -1 && errno == errors[i]);
        CHECK(fchownat(7, path, UINT32_MAX, UINT32_MAX, 0) == -1 && errno == errors[i]);
    }
    CHECK(calls == 120);
    return 0;
}
