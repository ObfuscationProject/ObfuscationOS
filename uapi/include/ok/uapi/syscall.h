#ifndef OK_UAPI_SYSCALL_H
#define OK_UAPI_SYSCALL_H

#include <stdint.h>

#define OK_UAPI_VERSION_MAJOR 0
#define OK_UAPI_VERSION_MINOR 1
#define OK_UAPI_VERSION_PATCH 0

#define OK_UAPI_X86_64_SYSCALL 1
#define OK_UAPI_SYSCALL_ARG_COUNT 6

#define OK_SYS_READ 0ULL
#define OK_SYS_WRITE 1ULL
#define OK_SYS_OPEN 2ULL
#define OK_SYS_CLOSE 3ULL
#define OK_SYS_STAT 4ULL
#define OK_SYS_FSTAT 5ULL
#define OK_SYS_LSTAT 6ULL
#define OK_SYS_POLL 7ULL
#define OK_SYS_LSEEK 8ULL
#define OK_SYS_MMAP 9ULL
#define OK_SYS_MPROTECT 10ULL
#define OK_SYS_MUNMAP 11ULL
#define OK_SYS_BRK 12ULL
#define OK_SYS_RT_SIGACTION 13ULL
#define OK_SYS_RT_SIGPROCMASK 14ULL
#define OK_SYS_IOCTL 16ULL
#define OK_SYS_PREAD64 17ULL
#define OK_SYS_PWRITE64 18ULL
#define OK_SYS_READV 19ULL
#define OK_SYS_WRITEV 20ULL
#define OK_SYS_ACCESS 21ULL
#define OK_SYS_PIPE 22ULL
#define OK_SYS_SELECT 23ULL
#define OK_SYS_SCHED_YIELD 24ULL
#define OK_SYS_DUP 32ULL
#define OK_SYS_DUP2 33ULL
#define OK_SYS_NANOSLEEP 35ULL
#define OK_SYS_GETPID 39ULL
#define OK_SYS_CLONE 56ULL
#define OK_SYS_FORK 57ULL
#define OK_SYS_EXECVE 59ULL
#define OK_SYS_EXIT 60ULL
#define OK_SYS_WAIT4 61ULL
#define OK_SYS_KILL 62ULL
#define OK_SYS_UNAME 63ULL
#define OK_SYS_FCNTL 72ULL
#define OK_SYS_GETDENTS 78ULL
#define OK_SYS_GETCWD 79ULL
#define OK_SYS_CHDIR 80ULL
#define OK_SYS_FCHDIR 81ULL
#define OK_SYS_MKDIR 83ULL
#define OK_SYS_RMDIR 84ULL
#define OK_SYS_CREAT 85ULL
#define OK_SYS_UNLINK 87ULL
#define OK_SYS_UMASK 95ULL
#define OK_SYS_GETTIMEOFDAY 96ULL
#define OK_SYS_GETRLIMIT 97ULL
#define OK_SYS_SYSINFO 99ULL
#define OK_SYS_GETUID 102ULL
#define OK_SYS_GETGID 104ULL
#define OK_SYS_GETEUID 107ULL
#define OK_SYS_GETEGID 108ULL
#define OK_SYS_GETPPID 110ULL
#define OK_SYS_ARCH_PRCTL 158ULL
#define OK_SYS_GETTID 186ULL
#define OK_SYS_TIME 201ULL
#define OK_SYS_FUTEX 202ULL
#define OK_SYS_GETDENTS64 217ULL
#define OK_SYS_SET_TID_ADDRESS 218ULL
#define OK_SYS_CLOCK_GETTIME 228ULL
#define OK_SYS_CLOCK_GETRES 229ULL
#define OK_SYS_CLOCK_NANOSLEEP 230ULL
#define OK_SYS_EXIT_GROUP 231ULL
#define OK_SYS_OPENAT 257ULL
#define OK_SYS_MKDIRAT 258ULL
#define OK_SYS_NEWFSTATAT 262ULL
#define OK_SYS_UNLINKAT 263ULL
#define OK_SYS_FACCESSAT 269ULL
#define OK_SYS_SET_ROBUST_LIST 273ULL
#define OK_SYS_DUP3 292ULL
#define OK_SYS_PRLIMIT64 302ULL
#define OK_SYS_GETRANDOM 318ULL
#define OK_SYS_RSEQ 334ULL
#define OK_SYS_CLOSE_RANGE 436ULL
#define OK_SYS_FACCESSAT2 439ULL
#define OK_SYS_OK_DEBUG 1024ULL

#define OK_EPERM 1
#define OK_ENOENT 2
#define OK_EIO 5
#define OK_EAGAIN 11
#define OK_ENOMEM 12
#define OK_EACCES 13
#define OK_EFAULT 14
#define OK_EEXIST 17
#define OK_EINVAL 22
#define OK_ENOSYS 38
#define OK_EOVERFLOW 75

#define OK_O_RDONLY 0x0000U
#define OK_O_WRONLY 0x0001U
#define OK_O_RDWR 0x0002U
#define OK_O_APPEND 0x0008U
#define OK_O_CREAT 0x0040U
#define OK_O_TRUNC 0x0200U
#define OK_O_CLOEXEC 0x080000U
#define OK_O_DIRECTORY 0x0200000U

#define OK_AT_FDCWD (-100)
#define OK_AT_EMPTY_PATH 0x1000U

#define OK_R_OK 4U
#define OK_W_OK 2U
#define OK_X_OK 1U
#define OK_F_OK 0U

#define OK_PROT_NONE 0x0U
#define OK_PROT_READ 0x1U
#define OK_PROT_WRITE 0x2U

#define OK_MAP_PRIVATE 0x02U
#define OK_MAP_ANONYMOUS 0x20U

#define OK_F_DUPFD 0U
#define OK_F_GETFD 1U
#define OK_F_SETFD 2U
#define OK_F_GETFL 3U
#define OK_F_SETFL 4U
#define OK_FD_CLOEXEC 1U

#define OK_SEEK_SET 0U
#define OK_SEEK_CUR 1U
#define OK_SEEK_END 2U

#define OK_ARCH_SET_GS 0x1001U
#define OK_ARCH_SET_FS 0x1002U
#define OK_ARCH_GET_FS 0x1003U
#define OK_ARCH_GET_GS 0x1004U

#define OK_FUTEX_WAIT 0U
#define OK_FUTEX_WAKE 1U

#define OK_NODE_DIRECTORY 0U
#define OK_NODE_REGULAR 1U
#define OK_NODE_DEVICE 2U
#define OK_NODE_SYMLINK 3U

#define OK_MODE_TYPE_MASK 0170000U
#define OK_MODE_SYMLINK 0120000U
#define OK_MODE_REGULAR 0100000U
#define OK_MODE_BLOCK_DEVICE 0060000U
#define OK_MODE_DIRECTORY 0040000U
#define OK_MODE_CHARACTER_DEVICE 0020000U
#define OK_MODE_FIFO 0010000U
#define OK_MODE_PERMISSION_MASK 07777U

struct ok_timespec
{
    int64_t seconds;
    int64_t nanoseconds;
};

struct ok_timeval
{
    int64_t seconds;
    int64_t microseconds;
};

struct ok_iovec
{
    uintptr_t base;
    uintptr_t length;
};

struct ok_stat
{
    uint8_t type;
    uintptr_t size;
    uint32_t mode;
    uint32_t uid;
    uint32_t gid;
    uint32_t link_count;
    uint32_t block_size;
    uint64_t blocks;
};

struct ok_rlimit
{
    uint64_t current;
    uint64_t maximum;
};

struct ok_sysinfo
{
    int64_t uptime;
    uint64_t total_ram;
    uint64_t free_ram;
    uint16_t process_count;
};

#endif
