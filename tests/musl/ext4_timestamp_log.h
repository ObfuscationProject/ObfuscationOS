#ifndef EXT4_TIMESTAMP_LOG_H
#define EXT4_TIMESTAMP_LOG_H

#include <stdint.h>
#include <time.h>
#include <unistd.h>

static struct timespec timestamp_before;
static int timestamp_begin(void)
{
    return clock_gettime(CLOCK_REALTIME, &timestamp_before);
}
static void timestamp_text(char **out, const char *text)
{
    while (*text) *(*out)++ = *text++;
}
static void timestamp_number(char **out, uint64_t value)
{
    char digits[24]; unsigned count = 0;
    do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (count) *(*out)++ = digits[--count];
}
static int timestamp_failure(const char *api, unsigned line, unsigned error)
{
    char buffer[128], *out = buffer;
    timestamp_text(&out, "EXT4_TIME_"); timestamp_text(&out, api);
    timestamp_text(&out, "_FAIL line="); timestamp_number(&out, line);
    timestamp_text(&out, " errno="); timestamp_number(&out, error);
    *out++ = '\n';
    (void)write(2, buffer, (size_t)(out - buffer));
    return 1;
}
static int timestamp_record(const char *api, const char *event, const char *path, unsigned mask)
{
    struct timespec after;
    if (clock_gettime(CLOCK_REALTIME, &after) || timestamp_before.tv_sec < 0 || after.tv_sec < 0)
        return -1;
    char buffer[512], *out = buffer;
    timestamp_text(&out, "EXT4_TIME_USER_EVENT api="); timestamp_text(&out, api);
    timestamp_text(&out, " event="); timestamp_text(&out, event);
    timestamp_text(&out, " path="); timestamp_text(&out, path);
    const char *names[] = {" mask=", " before_s=", " before_n=", " after_s=", " after_n="};
    const uint64_t values[] = {mask, (uint64_t)timestamp_before.tv_sec,
        (uint64_t)timestamp_before.tv_nsec, (uint64_t)after.tv_sec, (uint64_t)after.tv_nsec};
    for (unsigned i = 0; i < 5; ++i) { timestamp_text(&out, names[i]); timestamp_number(&out, values[i]); }
    *out++ = '\n';
    return write(1, buffer, (size_t)(out - buffer)) == out - buffer ? 0 : -1;
}
#endif
