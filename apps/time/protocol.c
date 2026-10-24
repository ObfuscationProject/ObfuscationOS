#include "time_service.h"
#include <errno.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

int ts_unsigned(const char *bytes, size_t size, uint64_t limit, uint64_t *value)
{
    if (!bytes || !value || !size || size > 20 || (size > 1 && bytes[0] == '0')) return -1;
    uint64_t result = 0;
    for (size_t i = 0; i < size; ++i) {
        unsigned digit = (unsigned char)bytes[i] - (unsigned)'0';
        if (digit > 9 || digit > limit || result > (limit - digit) / 10) return -1;
        result = result * 10 + digit;
    }
    *value = result;
    return 0;
}

static void text(struct ts_buffer *out, const char *value)
{
    size_t size = strlen(value);
    if (size > sizeof(out->bytes) - out->size) { out->failed = 1; return; }
    memcpy(out->bytes + out->size, value, size);
    out->size += size;
}

static void number(struct ts_buffer *out, uint64_t value)
{
    char digits[21]; size_t at = sizeof(digits) - 1; digits[at] = 0;
    do { digits[--at] = (char)('0' + value % 10); value /= 10; } while (value);
    text(out, digits + at);
}

static void signed_number(struct ts_buffer *out, int64_t value)
{
    if (value < 0) { text(out, "-"); number(out, (uint64_t)(-(value + 1)) + 1); }
    else number(out, (uint64_t)value);
}

struct cursor { const char *bytes; size_t size, at; };
static int take(struct cursor *in, const char *value)
{
    size_t size = strlen(value);
    if (size > in->size - in->at || memcmp(in->bytes + in->at, value, size)) return -1;
    in->at += size;
    return 0;
}

static int unsigned_value(struct cursor *in, uint64_t limit, uint64_t *value)
{
    size_t start = in->at;
    while (in->at < in->size && in->bytes[in->at] >= '0' && in->bytes[in->at] <= '9') ++in->at;
    return ts_unsigned(in->bytes + start, in->at - start, limit, value);
}

static int signed_value(struct cursor *in, int64_t *value)
{
    int negative = in->at < in->size && in->bytes[in->at] == '-';
    if (negative) ++in->at;
    uint64_t magnitude;
    if (unsigned_value(in, (uint64_t)INT64_MAX + (unsigned)negative, &magnitude) ||
        (negative && !magnitude)) return -1;
    *value = negative ? -(int64_t)(magnitude - 1) - 1 : (int64_t)magnitude;
    return 0;
}

int ts_request_parse(const char *bytes, size_t size, struct ts_request *request)
{
    if (!bytes || !request || size > TS_REQUEST_BYTES) return -1;
    int complete = 0;
    for (size_t i = 0; i < size; ++i) {
        unsigned char byte = (unsigned char)bytes[i];
        if (byte == '\n') { if (i + 1 != size) return -1; complete = 1; }
        else if (byte < 32 || byte > 126) return -1;
    }
    if (!complete) return size == TS_REQUEST_BYTES ? -1 : 0;
    struct cursor in = {bytes, size, 0};
    struct ts_request prepared = {0};
    if (!take(&in, "OKT1 STATUS\n") && in.at == size) prepared.operation = TS_STATUS;
    else {
        in.at = 0;
        uint64_t seconds, nanoseconds;
        if (take(&in, "OKT1 SET ") || unsigned_value(&in, TS_MAX_SECONDS - 1, &seconds) ||
            take(&in, " ") || unsigned_value(&in, 999999999, &nanoseconds) ||
            take(&in, "\n") || in.at != size) return -1;
        prepared = (struct ts_request){TS_SET, (int64_t)seconds, (uint32_t)nanoseconds};
    }
    *request = prepared;
    return 1;
}

int ts_request_encode(const struct ts_request *request, struct ts_buffer *out)
{
    *out = (struct ts_buffer){0};
    if (request->operation == TS_STATUS) text(out, "OKT1 STATUS\n");
    else if (request->operation == TS_SET && request->seconds >= 0 &&
             (uint64_t)request->seconds < TS_MAX_SECONDS && request->nanoseconds < 1000000000) {
        text(out, "OKT1 SET "); number(out, (uint64_t)request->seconds);
        text(out, " "); number(out, request->nanoseconds); text(out, "\n");
    } else return -1;
    return out->failed || out->size > TS_REQUEST_BYTES ? -1 : 0;
}

int ts_reply_encode(const struct ts_reply *reply, struct ts_buffer *out)
{
    *out = (struct ts_buffer){0};
    if (reply->operation == TS_ERROR) {
        if (reply->error <= 0 || reply->error > 4095) return -1;
        text(out, "OKT1 ERROR errno="); number(out, (unsigned)reply->error);
    } else if (reply->operation == TS_SET || reply->operation == TS_STATUS) {
        if (!reply->pid || reply->pid > INT32_MAX || (reply->operation == TS_SET && !reply->manual_updates)) return -1;
        text(out, reply->operation == TS_SET ? "OKT1 SET pid=" : "OKT1 STATUS pid=");
        number(out, reply->pid); text(out, " manual_updates="); number(out, reply->manual_updates);
        if (reply->operation == TS_STATUS) {
            if (reply->realtime_error < 0 || reply->realtime_error > 4095 ||
                reply->realtime_nanoseconds >= 1000000000 || reply->monotonic_seconds < 0 ||
                reply->monotonic_nanoseconds >= 1000000000 ||
                (reply->realtime_error && (reply->realtime_seconds || reply->realtime_nanoseconds))) return -1;
            text(out, " realtime_error="); number(out, (unsigned)reply->realtime_error);
            text(out, " realtime_seconds="); signed_number(out, reply->realtime_seconds);
            text(out, " realtime_nanoseconds="); number(out, reply->realtime_nanoseconds);
            text(out, " monotonic_seconds="); number(out, (uint64_t)reply->monotonic_seconds);
            text(out, " monotonic_nanoseconds="); number(out, reply->monotonic_nanoseconds);
        }
    } else return -1;
    text(out, "\nEND\n");
    return out->failed ? -1 : 0;
}

int ts_reply_parse(const char *bytes, size_t size, struct ts_reply *reply)
{
    if (!bytes || !reply || !size || size > TS_REPLY_BYTES) return -1;
    struct cursor in = {bytes, size, 0};
    struct ts_reply prepared = {0}; uint64_t value;
    if (!take(&in, "OKT1 ERROR errno=")) {
        if (unsigned_value(&in, 4095, &value) || !value) return -1;
        prepared.operation = TS_ERROR; prepared.error = (int)value;
    } else {
        in.at = 0;
        if (!take(&in, "OKT1 STATUS pid=")) prepared.operation = TS_STATUS;
        else { in.at = 0; if (take(&in, "OKT1 SET pid=")) return -1; prepared.operation = TS_SET; }
        if (unsigned_value(&in, INT32_MAX, &value) || !value) return -1;
        prepared.pid = (uint32_t)value;
        if (take(&in, " manual_updates=") || unsigned_value(&in, UINT64_MAX, &prepared.manual_updates) ||
            (prepared.operation == TS_SET && !prepared.manual_updates)) return -1;
        if (prepared.operation == TS_STATUS) {
            if (take(&in, " realtime_error=") || unsigned_value(&in, 4095, &value)) return -1;
            prepared.realtime_error = (int)value;
            if (take(&in, " realtime_seconds=") || signed_value(&in, &prepared.realtime_seconds) ||
                take(&in, " realtime_nanoseconds=") || unsigned_value(&in, 999999999, &value)) return -1;
            prepared.realtime_nanoseconds = (uint32_t)value;
            if (take(&in, " monotonic_seconds=") || unsigned_value(&in, INT64_MAX, &value)) return -1;
            prepared.monotonic_seconds = (int64_t)value;
            if (take(&in, " monotonic_nanoseconds=") || unsigned_value(&in, 999999999, &value)) return -1;
            prepared.monotonic_nanoseconds = (uint32_t)value;
            if (prepared.realtime_error && (prepared.realtime_seconds || prepared.realtime_nanoseconds)) return -1;
        }
    }
    if (take(&in, "\nEND\n") || in.at != size) return -1;
    *reply = prepared;
    return 0;
}

static int clock_error(void) { return errno > 0 && errno <= 4095 ? errno : EIO; }
void ts_dispatch(const struct ts_request *request, const struct ok_ucred *peer,
                 uint64_t *manual_updates, struct ts_reply *reply)
{
    *reply = (struct ts_reply){.operation = TS_ERROR, .error = EINVAL};
    pid_t pid = getpid();
    if (pid <= 1) { reply->error = EIO; return; }
    if (request->operation == TS_SET) {
        if (peer->uid) { reply->error = EPERM; return; }
        if (*manual_updates == UINT64_MAX) { reply->error = EOVERFLOW; return; }
        const struct timespec value = {request->seconds, request->nanoseconds};
        if (clock_settime(CLOCK_REALTIME, &value) < 0) { reply->error = clock_error(); return; }
        /* A failed/lost response cannot revoke an already successful syscall. */
        ++*manual_updates;
    } else if (request->operation != TS_STATUS) return;
    *reply = (struct ts_reply){.operation = request->operation, .pid = (uint32_t)pid,
                               .manual_updates = *manual_updates};
    if (request->operation == TS_STATUS) {
        struct timespec realtime = {0}, monotonic;
        if (clock_gettime(CLOCK_REALTIME, &realtime) < 0) reply->realtime_error = clock_error();
        else if (realtime.tv_nsec < 0 || realtime.tv_nsec >= 1000000000) reply->realtime_error = EIO;
        else { reply->realtime_seconds = realtime.tv_sec; reply->realtime_nanoseconds = (uint32_t)realtime.tv_nsec; }
        if (clock_gettime(CLOCK_MONOTONIC, &monotonic) < 0) {
            *reply = (struct ts_reply){.operation = TS_ERROR, .error = clock_error()}; return;
        }
        if (monotonic.tv_sec < 0 || monotonic.tv_nsec < 0 || monotonic.tv_nsec >= 1000000000) {
            *reply = (struct ts_reply){.operation = TS_ERROR, .error = EIO}; return;
        }
        reply->monotonic_seconds = monotonic.tv_sec;
        reply->monotonic_nanoseconds = (uint32_t)monotonic.tv_nsec;
    }
}
