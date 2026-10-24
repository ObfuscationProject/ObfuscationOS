#ifndef _SYS_RANDOM_H
#define _SYS_RANDOM_H

#include <stddef.h>
#include <sys/types.h>

#define GRND_NONBLOCK 0x0001
#define GRND_RANDOM 0x0002

#ifdef __cplusplus
extern "C" {
#endif

ssize_t getrandom(void *buffer, size_t size, unsigned int flags);

#ifdef __cplusplus
}
#endif

#endif
