#include <errno.h>
#include <stddef.h>
#include <string.h>

void *memcpy(void *dst, const void *src, size_t n)
{
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    for (size_t i = 0; i < n; ++i) {
        d[i] = s[i];
    }
    return dst;
}

void *memmove(void *dst, const void *src, size_t n)
{
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    if (d == s || n == 0) {
        return dst;
    }
    if (d < s) {
        for (size_t i = 0; i < n; ++i) {
            d[i] = s[i];
        }
    } else {
        for (size_t i = n; i > 0; --i) {
            d[i - 1] = s[i - 1];
        }
    }
    return dst;
}

void *memset(void *dst, int value, size_t n)
{
    unsigned char *d = (unsigned char *)dst;
    for (size_t i = 0; i < n; ++i) {
        d[i] = (unsigned char)value;
    }
    return dst;
}

int memcmp(const void *lhs, const void *rhs, size_t n)
{
    const unsigned char *l = (const unsigned char *)lhs;
    const unsigned char *r = (const unsigned char *)rhs;
    for (size_t i = 0; i < n; ++i) {
        if (l[i] != r[i]) {
            return (int)l[i] - (int)r[i];
        }
    }
    return 0;
}

size_t strlen(const char *s)
{
    size_t n = 0;
    while (s[n] != '\0') {
        ++n;
    }
    return n;
}

int strcmp(const char *lhs, const char *rhs)
{
    while (*lhs && *lhs == *rhs) {
        ++lhs;
        ++rhs;
    }
    return (unsigned char)*lhs - (unsigned char)*rhs;
}

int strncmp(const char *lhs, const char *rhs, size_t n)
{
    for (size_t i = 0; i < n; ++i) {
        unsigned char l = (unsigned char)lhs[i];
        unsigned char r = (unsigned char)rhs[i];
        if (l != r || l == '\0') {
            return (int)l - (int)r;
        }
    }
    return 0;
}

char *strcpy(char *dst, const char *src)
{
    char *out = dst;
    while ((*dst++ = *src++) != '\0') {
    }
    return out;
}

char *strncpy(char *dst, const char *src, size_t n)
{
    size_t i = 0;
    for (; i < n && src[i] != '\0'; ++i) {
        dst[i] = src[i];
    }
    for (; i < n; ++i) {
        dst[i] = '\0';
    }
    return dst;
}

char *strchr(const char *s, int c)
{
    char needle = (char)c;
    while (*s) {
        if (*s == needle) {
            return (char *)s;
        }
        ++s;
    }
    return needle == '\0' ? (char *)s : NULL;
}

char *strrchr(const char *s, int c)
{
    char needle = (char)c;
    const char *last = NULL;
    do {
        if (*s == needle) {
            last = s;
        }
    } while (*s++ != '\0');
    return (char *)last;
}

char *strerror(int errnum)
{
    switch (errnum) {
    case EPERM:
        return "Operation not permitted";
    case ENOENT:
        return "No such file or directory";
    case EIO:
        return "I/O error";
    case EBADF:
        return "Bad file descriptor";
    case EAGAIN:
        return "Try again";
    case ENOMEM:
        return "Out of memory";
    case EACCES:
        return "Permission denied";
    case EFAULT:
        return "Bad address";
    case EEXIST:
        return "File exists";
    case ENOTDIR:
        return "Not a directory";
    case EISDIR:
        return "Is a directory";
    case EINVAL:
        return "Invalid argument";
    case ENOSPC:
        return "No space left on device";
    case ENOSYS:
        return "Function not implemented";
    case ENOTEMPTY:
        return "Directory not empty";
    case ENAMETOOLONG:
        return "File name too long";
    default:
        return "Unknown error";
    }
}
