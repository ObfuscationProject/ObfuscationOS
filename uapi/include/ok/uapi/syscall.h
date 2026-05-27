#ifndef OK_UAPI_SYSCALL_H
#define OK_UAPI_SYSCALL_H

#define OK_UAPI_VERSION 0x00010000u

#define OK_SYS_EXIT 1
#define OK_SYS_READ 2
#define OK_SYS_WRITE 3
#define OK_SYS_OPEN 4
#define OK_SYS_CLOSE 5
#define OK_SYS_STAT 6
#define OK_SYS_FSTAT 7
#define OK_SYS_LSEEK 8
#define OK_SYS_MKDIR 9
#define OK_SYS_UNLINK 10
#define OK_SYS_GETDENTS 11
#define OK_SYS_WRITEV 12

#define OK_SYS_FORK 32
#define OK_SYS_EXECVE 33
#define OK_SYS_WAITPID 34
#define OK_SYS_PIPE 35
#define OK_SYS_SELECT 36
#define OK_SYS_POLL 37

#define OK_O_RDONLY 0x0000
#define OK_O_WRONLY 0x0001
#define OK_O_RDWR 0x0002
#define OK_O_CREAT 0x0040
#define OK_O_EXCL 0x0080
#define OK_O_TRUNC 0x0200
#define OK_O_APPEND 0x0400
#define OK_O_DIRECTORY 0x10000

#define OK_SEEK_SET 0
#define OK_SEEK_CUR 1
#define OK_SEEK_END 2

#endif
