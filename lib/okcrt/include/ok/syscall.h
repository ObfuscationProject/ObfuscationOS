#ifndef OK_SYSCALL_H
#define OK_SYSCALL_H

#include <ok/uapi/syscall.h>

long ok_syscall0(long number);
long ok_syscall1(long number, long arg0);
long ok_syscall2(long number, long arg0, long arg1);
long ok_syscall3(long number, long arg0, long arg1, long arg2);
long ok_syscall4(long number, long arg0, long arg1, long arg2, long arg3);
long ok_syscall5(long number, long arg0, long arg1, long arg2, long arg3, long arg4);
long ok_syscall6(long number, long arg0, long arg1, long arg2, long arg3, long arg4, long arg5);

long ok_syscall_ret(long result);

#endif
