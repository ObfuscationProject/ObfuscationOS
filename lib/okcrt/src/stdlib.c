#include <stdlib.h>
#include <unistd.h>

void exit(int status)
{
    _Exit(status);
}

void abort(void)
{
    _Exit(127);
}

int atoi(const char *s)
{
    return (int)strtol(s, 0, 10);
}

long strtol(const char *s, char **endptr, int base)
{
    const char *p = s;
    long sign = 1;
    long value = 0;

    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') {
        ++p;
    }
    if (*p == '-') {
        sign = -1;
        ++p;
    } else if (*p == '+') {
        ++p;
    }
    if (base == 0) {
        base = 10;
        if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X')) {
            base = 16;
            p += 2;
        }
    }

    for (;;) {
        int digit;
        if (*p >= '0' && *p <= '9') {
            digit = *p - '0';
        } else if (*p >= 'a' && *p <= 'z') {
            digit = *p - 'a' + 10;
        } else if (*p >= 'A' && *p <= 'Z') {
            digit = *p - 'A' + 10;
        } else {
            break;
        }
        if (digit >= base) {
            break;
        }
        value = value * base + digit;
        ++p;
    }

    if (endptr) {
        *endptr = (char *)p;
    }
    return value * sign;
}
