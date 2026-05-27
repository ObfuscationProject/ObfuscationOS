#include <errno.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

struct FILE {
    int fd;
};

static FILE stdin_file = {0};
static FILE stdout_file = {1};
static FILE stderr_file = {2};

FILE *stdin = &stdin_file;
FILE *stdout = &stdout_file;
FILE *stderr = &stderr_file;

static int write_all(int fd, const char *buf, size_t len)
{
    size_t written = 0;
    while (written < len) {
        ssize_t n = write(fd, buf + written, len - written);
        if (n < 0) {
            return -1;
        }
        written += (size_t)n;
    }
    return (int)written;
}

static int emit_char(FILE *stream, char c)
{
    return write_all(stream->fd, &c, 1) < 0 ? -1 : 1;
}

static int emit_string(FILE *stream, const char *s)
{
    if (!s) {
        s = "(null)";
    }
    return write_all(stream->fd, s, strlen(s));
}

static int emit_unsigned(FILE *stream, unsigned long value, unsigned base, int uppercase)
{
    char digits[] = "0123456789abcdef";
    char digits_upper[] = "0123456789ABCDEF";
    char buf[32];
    int pos = 0;
    const char *table = uppercase ? digits_upper : digits;

    if (value == 0) {
        return emit_char(stream, '0');
    }
    while (value != 0) {
        buf[pos++] = table[value % base];
        value /= base;
    }

    int total = 0;
    while (pos > 0) {
        int n = emit_char(stream, buf[--pos]);
        if (n < 0) {
            return -1;
        }
        total += n;
    }
    return total;
}

static int emit_signed(FILE *stream, long value)
{
    if (value < 0) {
        if (emit_char(stream, '-') < 0) {
            return -1;
        }
        int n = emit_unsigned(stream, (unsigned long)(-value), 10, 0);
        return n < 0 ? -1 : n + 1;
    }
    return emit_unsigned(stream, (unsigned long)value, 10, 0);
}

int fputc(int c, FILE *stream)
{
    return emit_char(stream, (char)c) < 0 ? -1 : c;
}

int putchar(int c)
{
    return fputc(c, stdout);
}

int fputs(const char *s, FILE *stream)
{
    return emit_string(stream, s);
}

int puts(const char *s)
{
    int a = fputs(s, stdout);
    int b = fputc('\n', stdout);
    return a < 0 || b < 0 ? -1 : a + 1;
}

int vfprintf(FILE *stream, const char *fmt, va_list ap)
{
    int total = 0;
    for (const char *p = fmt; *p; ++p) {
        int n = 0;
        if (*p != '%') {
            n = emit_char(stream, *p);
        } else {
            ++p;
            int long_count = 0;
            if (*p == 'l' && p[1] == 'l') {
                long_count = 2;
                p += 2;
            } else if (*p == 'l') {
                long_count = 1;
                ++p;
            }
            switch (*p) {
            case '%':
                n = emit_char(stream, '%');
                break;
            case 'c':
                n = emit_char(stream, (char)va_arg(ap, int));
                break;
            case 's':
                n = emit_string(stream, va_arg(ap, const char *));
                break;
            case 'd':
            case 'i':
                n = long_count ? emit_signed(stream, va_arg(ap, long)) : emit_signed(stream, va_arg(ap, int));
                break;
            case 'u':
                n = long_count ? emit_unsigned(stream, va_arg(ap, unsigned long), 10, 0)
                               : emit_unsigned(stream, va_arg(ap, unsigned int), 10, 0);
                break;
            case 'x':
                n = long_count ? emit_unsigned(stream, va_arg(ap, unsigned long), 16, 0)
                               : emit_unsigned(stream, va_arg(ap, unsigned int), 16, 0);
                break;
            case 'X':
                n = long_count ? emit_unsigned(stream, va_arg(ap, unsigned long), 16, 1)
                               : emit_unsigned(stream, va_arg(ap, unsigned int), 16, 1);
                break;
            case 'p':
                n = emit_string(stream, "0x");
                if (n >= 0) {
                    int m = emit_unsigned(stream, (uintptr_t)va_arg(ap, void *), 16, 0);
                    n = m < 0 ? -1 : n + m;
                }
                break;
            default:
                n = emit_char(stream, *p);
                break;
            }
        }
        if (n < 0) {
            return -1;
        }
        total += n;
    }
    return total;
}

int fprintf(FILE *stream, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = vfprintf(stream, fmt, ap);
    va_end(ap);
    return n;
}

int vprintf(const char *fmt, va_list ap)
{
    return vfprintf(stdout, fmt, ap);
}

int printf(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = vfprintf(stdout, fmt, ap);
    va_end(ap);
    return n;
}

void perror(const char *prefix)
{
    if (prefix && *prefix) {
        fputs(prefix, stderr);
        fputs(": ", stderr);
    }
    fputs(strerror(errno), stderr);
    fputc('\n', stderr);
}
