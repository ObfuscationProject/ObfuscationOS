#ifndef OBFUSCATION_PROBE_OUTPUT_H
#define OBFUSCATION_PROBE_OUTPUT_H
#include <stddef.h>
#include <stdint.h>
#include <unistd.h>
/* Integer-only probe logging avoids the unrelated MIPS64 quad-float formatter. */
static void probe_text(const char *text)
{
    size_t size = 0;
    while (text[size]) ++size;
    while (size) {
        ssize_t count = write(1, text, size);
        if (count <= 0) _exit(92);
        text += count; size -= (size_t)count;
    }
}
static void probe_number(uint64_t value)
{
    char digits[21]; size_t count = 0;
    do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (count) { char text[2] = {digits[--count], 0}; probe_text(text); }
}
static void probe_failure(const char *name, unsigned line, unsigned error)
{
    probe_text(name); probe_text(" line="); probe_number(line);
    probe_text(" errno="); probe_number(error); probe_text("\n");
    _exit(91);
}
#endif
