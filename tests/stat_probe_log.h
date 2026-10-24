#ifndef LINUX_STAT_PROBE_LOG_H
#define LINUX_STAT_PROBE_LOG_H

#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* No printf dependency: MIPS64's unrelated quad-float formatting is not needed. */
static inline void stat_probe_write(const char *text, size_t size)
{
    while (size) {
        ssize_t count = write(1, text, size);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) exit(2);
        text += count;
        size -= (size_t)count;
    }
}

static inline void stat_probe_text(const char *text)
{
    stat_probe_write(text, strlen(text));
}

static inline void stat_probe_unsigned(unsigned value)
{
    char data[16];
    unsigned end = sizeof data;
    do { data[--end] = (char)('0' + value % 10); value /= 10; } while (value);
    stat_probe_write(data + end, sizeof data - end);
}

static inline void stat_probe_snapshot(const char *label, const struct statx *value)
{
    static const char digits[] = "0123456789abcdef";
    const unsigned char *bytes = (const unsigned char *)value;
    char encoded[512];
    _Static_assert(sizeof(struct statx) == 256, "Linux statx snapshot wire size");
    for (unsigned i = 0; i < 256; ++i) {
        encoded[2 * i] = digits[bytes[i] >> 4];
        encoded[2 * i + 1] = digits[bytes[i] & 15];
    }
    stat_probe_text("LINUX_STAT_SNAPSHOT name=");
    stat_probe_text(label);
    stat_probe_text(" hex=");
    stat_probe_write(encoded, sizeof encoded);
    stat_probe_text("\n");
}

#endif
