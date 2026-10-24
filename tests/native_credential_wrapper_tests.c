/* Hosted syscall argument/result boundary; no host credentials are modified. */
#include <errno.h>
#include <ok/syscall.h>
#include <sys/random.h>
#include <unistd.h>

static long selected, words[3], response;
int errno;
long ok_syscall0(long number) { selected = number; return response; }
long ok_syscall1(long number, long a) { selected = number; words[0] = a; return response; }
long ok_syscall2(long number, long a, long b)
{ selected = number; words[0] = a; words[1] = b; return response; }
long ok_syscall3(long number, long a, long b, long c)
{ selected = number; words[0] = a; words[1] = b; words[2] = c; return response; }
long ok_syscall_ret(long result)
{
    if (result < 0 && result >= -4095) { errno = (int)-result; return -1; }
    return result;
}
#define CHECK(value) do { if (!(value)) return __LINE__; } while (0)
int main(void)
{
    /* Simulate the negative signed long representation of a high 32-bit ID. */
    response = -2; errno = 73;
    CHECK(getuid() == (uid_t)4294967294U && selected == OK_SYS_GETUID && errno == 73);
    CHECK(geteuid() == (uid_t)4294967294U && selected == OK_SYS_GETEUID && errno == 73);
    CHECK(getgid() == (gid_t)4294967294U && selected == OK_SYS_GETGID && errno == 73);
    CHECK(getegid() == (gid_t)4294967294U && selected == OK_SYS_GETEGID && errno == 73);
    response = 0;
    CHECK(!setuid(4294967294U) && selected == OK_SYS_SETUID && (uint32_t)words[0] == 4294967294U);
    CHECK(!setgid(4294967293U) && selected == OK_SYS_SETGID && (uint32_t)words[0] == 4294967293U);
    CHECK(!setreuid((uid_t)-1, 1000) && selected == OK_SYS_SETREUID &&
          (uint32_t)words[0] == UINT32_MAX && words[1] == 1000);
    CHECK(!setregid(1000, (gid_t)-1) && selected == OK_SYS_SETREGID &&
          words[0] == 1000 && (uint32_t)words[1] == UINT32_MAX);
    CHECK(!setresuid(17, 18, 19) && selected == OK_SYS_SETRESUID &&
          words[0] == 17 && words[1] == 18 && words[2] == 19);
    CHECK(!setresgid(27, 28, 29) && selected == OK_SYS_SETRESGID &&
          words[0] == 27 && words[1] == 28 && words[2] == 29);
    uid_t users[3]; gid_t groups[3];
    CHECK(!getresuid(users, users + 1, users + 2) && selected == OK_SYS_GETRESUID &&
          words[0] == (long)users && words[1] == (long)(users + 1) && words[2] == (long)(users + 2));
    CHECK(!getresgid(groups, groups + 1, groups + 2) && selected == OK_SYS_GETRESGID &&
          words[0] == (long)groups && words[1] == (long)(groups + 1) && words[2] == (long)(groups + 2));
    response = -OK_EPERM; errno = 0;
    CHECK(setresuid(0, 0, 0) == -1 && errno == EPERM);
    response = -OK_EOPNOTSUPP; errno = 0;
    CHECK(setresgid(0, 0, 0) == -1 && errno == EOPNOTSUPP);
    response = -OK_EFAULT; errno = 0;
    CHECK(getresuid(users, 0, users + 2) == -1 && errno == EFAULT);
    unsigned char salt[16];
    response = 7; errno = 73;
    CHECK(getrandom(salt, sizeof(salt), GRND_NONBLOCK) == 7 && errno == 73 &&
          selected == OK_SYS_GETRANDOM && words[0] == (long)salt &&
          words[1] == sizeof(salt) && words[2] == GRND_NONBLOCK);
    response = -OK_EAGAIN; errno = 0;
    CHECK(getrandom(salt, sizeof(salt), 0) == -1 && errno == EAGAIN);
    return 0;
}
