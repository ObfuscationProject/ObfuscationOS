#ifndef OK_TIME_H
#define OK_TIME_H

#include <stdint.h>
#include <sys/types.h>

typedef int clockid_t;
#define CLOCK_REALTIME 0
#define CLOCK_MONOTONIC 1
#define TIMER_ABSTIME 1

/* Native time64 layout on every profile; this is not the Linux timespec ABI. */
struct timespec {
    time_t tv_sec;
    int64_t tv_nsec;
};

int clock_settime(clockid_t clock, const struct timespec *value);
int clock_gettime(clockid_t clock, struct timespec *value);
int clock_getres(clockid_t clock, struct timespec *value);
int nanosleep(const struct timespec *request, struct timespec *remaining);
int clock_nanosleep(clockid_t clock, int flags, const struct timespec *request, struct timespec *remaining);

#endif
