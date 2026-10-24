#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

static struct timespec clock_value;
static int fake_clock_gettime(clockid_t id, struct timespec *result)
{
    (void)id;
    *result = clock_value;
    return 0;
}

static ssize_t fake_write(int descriptor, const void *data, size_t length)
{
    (void)descriptor;
    (void)data;
    return (ssize_t)length;
}

#define main pid1_unused_main
#define clock_gettime fake_clock_gettime
#define write fake_write
#include "../apps/init/pid1.c"
#undef main
#undef clock_gettime
#undef write

int main(void)
{
    uint64_t result = 0;
    const uint64_t last_second = UINT64_MAX / 1000;
    const uint64_t last_fraction = UINT64_MAX - last_second * 1000;
    clock_value.tv_sec = (time_t)last_second;
    clock_value.tv_nsec = (long)(last_fraction * 1000000);
    assert(monotonic_ms(&result) == 0 && result == UINT64_MAX);
    clock_value.tv_nsec += 1000000;
    assert(monotonic_ms(&result) < 0);
    clock_value.tv_sec++;
    clock_value.tv_nsec = 0;
    assert(monotonic_ms(&result) < 0);
    clock_value.tv_sec = -1;
    assert(monotonic_ms(&result) < 0);
    clock_value.tv_sec = 0;
    clock_value.tv_nsec = 1000000000L;
    assert(monotonic_ms(&result) < 0);
    puts("PID1_CLOCK_BOUNDS_PASS max=UINT64_MAX overflow=rejected");
    return 0;
}
