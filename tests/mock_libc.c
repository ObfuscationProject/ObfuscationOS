#include <errno.h>
#include <fcntl.h>
#include <ok/dirent.h>
#include <ok/uapi/syscall.h>
#include <stddef.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static long last_number;

long ok_syscall0(long number)
{
    last_number = number;
    return -OK_ENOSYS;
}

long ok_syscall1(long number, long arg0)
{
    (void)arg0;
    last_number = number;
    if (number == OK_SYS_CLOSE) {
        return 0;
    }
    if (number == OK_SYS_UNLINK) {
        return -OK_ENOENT;
    }
    return -OK_ENOSYS;
}

long ok_syscall2(long number, long arg0, long arg1)
{
    last_number = number;
    if (number == OK_SYS_STAT || number == OK_SYS_FSTAT) {
        struct ok_stat *st = (struct ok_stat *)arg1;
        memset(st, 0, sizeof(*st));
        st->type = OK_NODE_REGULAR;
        st->mode = OK_MODE_REGULAR | 0400;
        st->size = 123;
        st->link_count = 1;
        st->block_size = 512;
        return 0;
    }
    if (number == OK_SYS_MKDIR) {
        return arg0 ? 0 : -OK_EFAULT;
    }
    return -OK_ENOSYS;
}

long ok_syscall3(long number, long arg0, long arg1, long arg2)
{
    (void)arg0;
    (void)arg1;
    last_number = number;
    if (number == OK_SYS_READ) {
        return -OK_EINTR;
    }
    if (number == OK_SYS_WRITE) {
        return arg2;
    }
    if (number == OK_SYS_OPEN) {
        return 42;
    }
    if (number == OK_SYS_GETDENTS64) {
        return 0;
    }
    if (number == OK_SYS_LSEEK) {
        return 99;
    }
    return -OK_ENOSYS;
}

long ok_syscall4(long number, long arg0, long arg1, long arg2, long arg3)
{
    (void)arg0;
    (void)arg1;
    (void)arg2;
    (void)arg3;
    last_number = number;
    return -OK_ENOSYS;
}

long ok_syscall5(long number, long arg0, long arg1, long arg2, long arg3, long arg4)
{
    (void)arg0;
    (void)arg1;
    (void)arg2;
    (void)arg3;
    (void)arg4;
    last_number = number;
    return -OK_ENOSYS;
}

long ok_syscall6(long number, long arg0, long arg1, long arg2, long arg3, long arg4, long arg5)
{
    (void)arg0;
    (void)arg1;
    (void)arg2;
    (void)arg3;
    (void)arg4;
    (void)arg5;
    last_number = number;
    return -OK_ENOSYS;
}

int main(void)
{
    char buf[4];
    if (read(3, buf, sizeof(buf)) != -1 || errno != EINTR || last_number != OK_SYS_READ) {
        return 1;
    }
    if (write(1, "ok", 2) != 2 || last_number != OK_SYS_WRITE) {
        return 2;
    }
    if (open("/hello", O_RDONLY) != 42 || last_number != OK_SYS_OPEN) {
        return 3;
    }
    if (close(42) != 0 || last_number != OK_SYS_CLOSE) {
        return 4;
    }
    if (unlink("/missing") != -1 || errno != ENOENT || last_number != OK_SYS_UNLINK) {
        return 5;
    }
    if (lseek(4, 0, SEEK_SET) != 99 || last_number != OK_SYS_LSEEK) {
        return 6;
    }
    struct stat st;
    if (stat("/file", &st) != 0 || st.st_size != 123 || st.st_mode != (OK_MODE_REGULAR | 0400)) {
        return 7;
    }
    if (!S_ISREG(st.st_mode) || st.st_nlink != 1 || st.st_blksize != 512) {
        return 8;
    }
    memset(&st, 0, sizeof(st));
    if (fstat(42, &st) != 0 || st.st_size != 123 || last_number != OK_SYS_FSTAT) {
        return 9;
    }
    if (mkdir("/tmp", 0700) != 0 || last_number != OK_SYS_MKDIR) {
        return 10;
    }
    if (mkdir(NULL, 0700) != -1 || errno != EFAULT || last_number != OK_SYS_MKDIR) {
        return 11;
    }
    char dent_buffer[sizeof(struct dirent)];
    if (getdents64(42, dent_buffer, sizeof(dent_buffer)) != 0 || last_number != OK_SYS_GETDENTS64) {
        return 12;
    }
    if (strlen("abc") != 3 || strcmp("abc", "abc") != 0 || strncmp("abc", "abd", 2) != 0) {
        return 13;
    }
    if (memcmp("a", "b", 1) >= 0) {
        return 14;
    }
    return 0;
}
