#ifndef _STDIO_H
#define _STDIO_H

#include <stdarg.h>
#include <stddef.h>

typedef struct FILE FILE;

extern FILE *stdin;
extern FILE *stdout;
extern FILE *stderr;

int putchar(int c);
int puts(const char *s);
int fputc(int c, FILE *stream);
int fputs(const char *s, FILE *stream);
int printf(const char *fmt, ...);
int fprintf(FILE *stream, const char *fmt, ...);
int vprintf(const char *fmt, va_list ap);
int vfprintf(FILE *stream, const char *fmt, va_list ap);
void perror(const char *prefix);

#endif
