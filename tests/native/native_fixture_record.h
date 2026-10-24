#ifndef OK_NATIVE_FIXTURE_RECORD_H
#define OK_NATIVE_FIXTURE_RECORD_H

#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

/* okcrt printf writes characters separately. Keep each causal marker in one
 * write syscall so concurrent native services cannot split its identity. */
struct native_fixture_record {
    char bytes[256];
    size_t size;
    int failed;
};

static inline void nf_text(struct native_fixture_record *record, const char *value)
{
    size_t length = strlen(value);
    if (length > sizeof(record->bytes) - record->size) { record->failed = 1; return; }
    memcpy(record->bytes + record->size, value, length);
    record->size += length;
}

static inline void nf_number(struct native_fixture_record *record, uint64_t value)
{
    char digits[21];
    unsigned count = 0;
    do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value);
    if (count > sizeof(record->bytes) - record->size) { record->failed = 1; return; }
    while (count) record->bytes[record->size++] = digits[--count];
}

static inline int nf_emit(struct native_fixture_record *record)
{
    if (record->failed) return -1;
    ssize_t count;
    do { count = write(STDOUT_FILENO, record->bytes, record->size); } while (count < 0 && errno == EINTR);
    return count == (ssize_t)record->size ? 0 : -1;
}

static inline int nf_marker(const char *message)
{
    struct native_fixture_record record = {0};
    nf_text(&record, message);
    return nf_emit(&record);
}

#endif
