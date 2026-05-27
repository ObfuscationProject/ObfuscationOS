#ifndef _ERRNO_H
#define _ERRNO_H

#include <ok/uapi/syscall.h>

#ifndef OK_ESRCH
#define OK_ESRCH 3
#endif
#ifndef OK_EINTR
#define OK_EINTR 4
#endif
#ifndef OK_ENXIO
#define OK_ENXIO 6
#endif
#ifndef OK_E2BIG
#define OK_E2BIG 7
#endif
#ifndef OK_ENOEXEC
#define OK_ENOEXEC 8
#endif
#ifndef OK_EBADF
#define OK_EBADF 9
#endif
#ifndef OK_ECHILD
#define OK_ECHILD 10
#endif
#ifndef OK_EBUSY
#define OK_EBUSY 16
#endif
#ifndef OK_EXDEV
#define OK_EXDEV 18
#endif
#ifndef OK_ENODEV
#define OK_ENODEV 19
#endif
#ifndef OK_ENOTDIR
#define OK_ENOTDIR 20
#endif
#ifndef OK_EISDIR
#define OK_EISDIR 21
#endif
#ifndef OK_ENFILE
#define OK_ENFILE 23
#endif
#ifndef OK_EMFILE
#define OK_EMFILE 24
#endif
#ifndef OK_ENOTTY
#define OK_ENOTTY 25
#endif
#ifndef OK_EFBIG
#define OK_EFBIG 27
#endif
#ifndef OK_ENOSPC
#define OK_ENOSPC 28
#endif
#ifndef OK_ESPIPE
#define OK_ESPIPE 29
#endif
#ifndef OK_EROFS
#define OK_EROFS 30
#endif
#ifndef OK_EMLINK
#define OK_EMLINK 31
#endif
#ifndef OK_EPIPE
#define OK_EPIPE 32
#endif
#ifndef OK_ERANGE
#define OK_ERANGE 34
#endif
#ifndef OK_ENAMETOOLONG
#define OK_ENAMETOOLONG 36
#endif
#ifndef OK_ENOTEMPTY
#define OK_ENOTEMPTY 39
#endif

extern int errno;

#define EPERM OK_EPERM
#define ENOENT OK_ENOENT
#define ESRCH OK_ESRCH
#define EINTR OK_EINTR
#define EIO OK_EIO
#define ENXIO OK_ENXIO
#define E2BIG OK_E2BIG
#define ENOEXEC OK_ENOEXEC
#define EBADF OK_EBADF
#define ECHILD OK_ECHILD
#define EAGAIN OK_EAGAIN
#define ENOMEM OK_ENOMEM
#define EACCES OK_EACCES
#define EFAULT OK_EFAULT
#define EBUSY OK_EBUSY
#define EEXIST OK_EEXIST
#define EXDEV OK_EXDEV
#define ENODEV OK_ENODEV
#define ENOTDIR OK_ENOTDIR
#define EISDIR OK_EISDIR
#define EINVAL OK_EINVAL
#define ENFILE OK_ENFILE
#define EMFILE OK_EMFILE
#define ENOTTY OK_ENOTTY
#define EFBIG OK_EFBIG
#define ENOSPC OK_ENOSPC
#define ESPIPE OK_ESPIPE
#define EROFS OK_EROFS
#define EMLINK OK_EMLINK
#define EPIPE OK_EPIPE
#define ERANGE OK_ERANGE
#define ENAMETOOLONG OK_ENAMETOOLONG
#define ENOSYS OK_ENOSYS
#define ENOTEMPTY OK_ENOTEMPTY

#endif
