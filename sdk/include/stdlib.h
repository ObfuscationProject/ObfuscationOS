#ifndef _STDLIB_H
#define _STDLIB_H

#include <stddef.h>

void exit(int status) __attribute__((noreturn));
void abort(void) __attribute__((noreturn));
int atoi(const char *s);
long strtol(const char *s, char **endptr, int base);

#endif
