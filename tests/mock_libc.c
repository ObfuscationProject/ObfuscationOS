#include <errno.h>
#include <fcntl.h>
#include <ok/dirent.h>
#include <ok/uapi/syscall.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static long last_number;
static long last_arguments[5];
static uintptr_t metadata_size = 123;
static uint64_t metadata_blocks;

long ok_syscall0(long number)
{
    last_number = number;
    if (number == OK_SYS_GETUID || number == OK_SYS_GETEUID) {
        return 1000;
    }
    if (number == OK_SYS_GETGID || number == OK_SYS_GETEGID) {
        return 1000;
    }
    if (number == OK_SYS_GETPID) {
        return 7;
    }
    return -OK_ENOSYS;
}

long ok_syscall1(long number, long arg0)
{
    (void)arg0;
    last_number = number;
    if (number == OK_SYS_CLOSE) {
        return 0;
    }
    if (number == OK_SYS_CHDIR) {
        return arg0 ? 0 : -OK_EFAULT;
    }
    if (number == OK_SYS_UNLINK) {
        return -OK_ENOENT;
    }
    if (number == OK_SYS_RMDIR) {
        last_arguments[0] = arg0;
        return arg0 ? 0 : -OK_EFAULT;
    }
    return -OK_ENOSYS;
}

long ok_syscall2(long number, long arg0, long arg1)
{
    last_number = number;
    if (number == OK_SYS_RENAME || number == OK_SYS_LINK) {
        last_arguments[0] = arg0;
        last_arguments[1] = arg1;
        return arg0 && arg1 ? 0 : -OK_EFAULT;
    }
    if (number == OK_SYS_STAT || number == OK_SYS_FSTAT) {
        struct ok_stat *st = (struct ok_stat *)arg1;
        memset(st, 0, sizeof(*st));
        st->type = OK_NODE_REGULAR;
        st->mode = OK_MODE_REGULAR | 0400;
        st->size = metadata_size;
        st->blocks = metadata_blocks;
        st->link_count = 1;
        st->block_size = 512;
        return 0;
    }
    if (number == OK_SYS_MKDIR) {
        return arg0 ? 0 : -OK_EFAULT;
    }
    if (number == OK_SYS_GETCWD) {
        char *out = (char *)arg0;
        if (!out || arg1 < 5) {
            return -OK_EOVERFLOW;
        }
        strcpy(out, "/tmp");
        return 4;
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
    last_number = number;
    if (number == OK_SYS_RENAMEAT) {
        last_arguments[0] = arg0;
        last_arguments[1] = arg1;
        last_arguments[2] = arg2;
        last_arguments[3] = arg3;
        return arg1 && arg3 ? 0 : -OK_EFAULT;
    }
    return -OK_ENOSYS;
}

long ok_syscall5(long number, long arg0, long arg1, long arg2, long arg3, long arg4)
{
    last_number = number;
    if (number == OK_SYS_LINKAT) {
        last_arguments[0] = arg0;
        last_arguments[1] = arg1;
        last_arguments[2] = arg2;
        last_arguments[3] = arg3;
        last_arguments[4] = arg4;
        if (arg4) return -OK_EINVAL;
        return arg1 && arg3 ? 0 : -OK_EFAULT;
    }
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
    metadata_size = (uintptr_t)__LONG_MAX__ + 1u;
    if (stat("/too-large", &st) != -1 || errno != EOVERFLOW || st.st_size != 123)
        return 30;
    metadata_size = 123;
    metadata_blocks = (uint64_t)~0u + 1;
    if (fstat(42, &st) != -1 || errno != EOVERFLOW || st.st_size != 123)
        return 31;
    metadata_blocks = 0;
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
    uid_t uid = getuid();
    if (uid != 1000 || geteuid() != 1000 || getgid() != 1000 || getegid() != 1000) {
        return 13;
    }
    if (getpid() != 7 || last_number != OK_SYS_GETPID) {
        return 14;
    }
    char cwd[8];
    if (getcwd(cwd, sizeof(cwd)) != cwd || strcmp(cwd, "/tmp") != 0 || last_number != OK_SYS_GETCWD) {
        return 15;
    }
    char tiny_cwd[2];
    if (getcwd(tiny_cwd, sizeof(tiny_cwd)) != NULL || errno != EOVERFLOW) {
        return 16;
    }
    if (chdir("/tmp") != 0 || last_number != OK_SYS_CHDIR) {
        return 17;
    }
    if (chdir(NULL) != -1 || errno != EFAULT) {
        return 18;
    }
    if (strlen("abc") != 3 || strcmp("abc", "abc") != 0 || strncmp("abc", "abd", 2) != 0) {
        return 19;
    }
    if (memcmp("a", "b", 1) >= 0) {
        return 20;
    }
    const char oldpath[] = "old";
    const char newpath[] = "new";
    if (rename(oldpath, newpath) != 0 || last_number != OK_SYS_RENAME ||
        last_arguments[0] != (long)oldpath || last_arguments[1] != (long)newpath) {
        return 32;
    }
    if (link(oldpath, newpath) != 0 || last_number != OK_SYS_LINK ||
        last_arguments[0] != (long)oldpath || last_arguments[1] != (long)newpath) {
        return 33;
    }
    if (renameat(AT_FDCWD, oldpath, 9, newpath) != 0 || last_number != OK_SYS_RENAMEAT ||
        last_arguments[0] != AT_FDCWD || last_arguments[1] != (long)oldpath ||
        last_arguments[2] != 9 || last_arguments[3] != (long)newpath) {
        return 34;
    }
    if (linkat(8, oldpath, AT_FDCWD, newpath, 0) != 0 || last_number != OK_SYS_LINKAT ||
        last_arguments[0] != 8 || last_arguments[1] != (long)oldpath ||
        last_arguments[2] != AT_FDCWD || last_arguments[3] != (long)newpath || last_arguments[4] != 0) {
        return 35;
    }
    if (linkat(8, oldpath, 9, newpath, 1) != -1 || errno != EINVAL || last_arguments[4] != 1) {
        return 36;
    }
    if (rename(NULL, newpath) != -1 || errno != EFAULT ||
        link(oldpath, NULL) != -1 || errno != EFAULT ||
        renameat(8, NULL, 9, newpath) != -1 || errno != EFAULT ||
        linkat(8, oldpath, 9, NULL, 0) != -1 || errno != EFAULT) {
        return 37;
    }
    if (rmdir(oldpath) != 0 || last_number != OK_SYS_RMDIR || last_arguments[0] != (long)oldpath ||
        rmdir(NULL) != -1 || errno != EFAULT) {
        return 38;
    }
    return 0;
}
