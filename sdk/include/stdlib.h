#ifndef _STDLIB_H
#define _STDLIB_H

#include <stddef.h>

void exit(int status) __attribute__((noreturn));
void abort(void) __attribute__((noreturn));
int atoi(const char *s);
long strtol(const char *s, char **endptr, int base);

/* devpts pairs over /dev/ptmx; the slave is /dev/pts/<TIOCGPTN>. */
int posix_openpt(int flags);
int grantpt(int fd);
int unlockpt(int fd);
char *ptsname(int fd);
int ptsname_r(int fd, char *buffer, size_t size);

#endif
