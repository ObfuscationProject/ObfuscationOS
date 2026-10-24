#ifndef _SYS_MMAN_H
#define _SYS_MMAN_H

#include <ok/uapi/syscall.h>
#include <stddef.h>
#include <sys/types.h>

#define PROT_NONE OK_PROT_NONE
#define PROT_READ OK_PROT_READ
#define PROT_WRITE OK_PROT_WRITE
#define PROT_EXEC 0x4U
#define MAP_SHARED OK_MAP_SHARED
#define MAP_PRIVATE OK_MAP_PRIVATE
#define MAP_FIXED OK_MAP_FIXED
#define MAP_ANONYMOUS OK_MAP_ANONYMOUS
#define MAP_FAILED ((void *)-1)
#define MFD_CLOEXEC OK_MFD_CLOEXEC
#define MFD_ALLOW_SEALING OK_MFD_ALLOW_SEALING

int memfd_create(const char *name, unsigned int flags);
void *mmap(void *address, size_t length, int protection, int flags, int fd, off_t offset);
int mprotect(void *address, size_t length, int protection);
int munmap(void *address, size_t length);

#endif
