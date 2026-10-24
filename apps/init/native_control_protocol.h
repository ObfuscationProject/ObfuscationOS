#ifndef OK_NATIVE_CONTROL_PROTOCOL_H
#define OK_NATIVE_CONTROL_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define NC_PATH "/run/init.sock"
#define NC_PREFIX "OK_INIT_CONTROL 1 "
enum { NC_CLIENTS = 2, NC_REQUEST_BYTES = 96, NC_REPLY_BYTES = 2048, NC_DEADLINE_MS = 1000 };
enum nc_operation { NC_INVALID, NC_STATUS, NC_RESTART, NC_STATE, NC_QUIESCE, NC_HALT, NC_REBOOT, NC_POWEROFF };
struct nc_request { enum nc_operation operation; char service[32]; };

static inline int nc_name(const char *name, size_t size)
{
    if (!size || size > 31) return 0;
    for (size_t i = 0; i < size; ++i)
        if (!((name[i] >= 'a' && name[i] <= 'z') || (name[i] >= 'A' && name[i] <= 'Z') ||
              (name[i] >= '0' && name[i] <= '9') || name[i] == '-' || name[i] == '_')) return 0;
    return 1;
}

/* Admit one complete buffered versioned line, without CR, NUL or buffered suffix.
 * Dispatch consumes its LF frame; later bytes cannot revoke that request. */
static inline struct nc_request nc_parse(const char *bytes, size_t size)
{
    struct nc_request result = {0};
    const size_t prefix = sizeof(NC_PREFIX) - 1;
    if (size <= prefix || size >= NC_REQUEST_BYTES || memcmp(bytes, NC_PREFIX, prefix) || bytes[size - 1] != '\n')
        return result;
    for (size_t i = 0; i + 1 < size; ++i)
        if ((unsigned char)bytes[i] < 32 || (unsigned char)bytes[i] > 126) return result;
    const char *command = bytes + prefix;
    size_t remaining = size - prefix - 1, offset;
    if (remaining == 6 && !memcmp(command, "STATUS", 6)) { result.operation = NC_STATUS; return result; }
    if (remaining == 5 && !memcmp(command, "STATE", 5)) { result.operation = NC_STATE; return result; }
    if (remaining == 7 && !memcmp(command, "QUIESCE", 7)) { result.operation = NC_QUIESCE; return result; }
    if (remaining == 4 && !memcmp(command, "HALT", 4)) { result.operation = NC_HALT; return result; }
    if (remaining == 6 && !memcmp(command, "REBOOT", 6)) { result.operation = NC_REBOOT; return result; }
    if (remaining == 8 && !memcmp(command, "POWEROFF", 8)) { result.operation = NC_POWEROFF; return result; }
    if (remaining > 7 && !memcmp(command, "STATUS ", 7)) { result.operation = NC_STATUS; offset = 7; }
    else if (remaining > 8 && !memcmp(command, "RESTART ", 8)) { result.operation = NC_RESTART; offset = 8; }
    else return result;
    if (!nc_name(command + offset, remaining - offset)) return (struct nc_request){0};
    memcpy(result.service, command + offset, remaining - offset);
    return result;
}

struct nc_buffer { char bytes[NC_REPLY_BYTES]; size_t size; int failed; };
static inline void nc_text(struct nc_buffer *out, const char *text)
{
    size_t size = strlen(text);
    if (size > sizeof(out->bytes) - out->size) { out->failed = 1; return; }
    memcpy(out->bytes + out->size, text, size); out->size += size;
}
static inline void nc_number(struct nc_buffer *out, uint64_t number)
{
    char digits[21]; size_t size = 0;
    do { digits[size++] = (char)('0' + number % 10); number /= 10; } while (number);
    while (size) { char text[2] = {digits[--size], 0}; nc_text(out, text); }
}

struct nc_cursor { const char *bytes; size_t size, at; };
struct nc_status {
    char service[32], phase[16], mode[8];
    uint64_t pid, generation, next_ms, launches;
};
struct nc_state {
    char phase[16], graph[16], children[8];
    uint64_t started_ms, deadline_ms;
};
static inline int nc_take(struct nc_cursor *in, const char *text)
{
    size_t size = strlen(text);
    if (size > in->size - in->at || memcmp(in->bytes + in->at, text, size)) return -1;
    in->at += size; return 0;
}
static inline int nc_value(struct nc_cursor *in, uint64_t *value)
{
    size_t start = in->at; *value = 0;
    while (in->at < in->size && in->bytes[in->at] >= '0' && in->bytes[in->at] <= '9') {
        unsigned digit = (unsigned)(in->bytes[in->at++] - '0');
        if (*value > (UINT64_MAX - digit) / 10) return -1;
        *value = *value * 10 + digit;
    }
    return in->at == start ? -1 : 0;
}
static inline int nc_word(struct nc_cursor *in, char *out, size_t capacity)
{
    size_t start = in->at;
    while (in->at < in->size && in->bytes[in->at] != ' ' && in->bytes[in->at] != '\n') ++in->at;
    size_t size = in->at - start;
    if (size >= capacity || !nc_name(in->bytes + start, size)) return -1;
    memcpy(out, in->bytes + start, size); out[size] = 0; return 0;
}
static inline int nc_status_line(struct nc_cursor *in, struct nc_status *out, int full)
{
    *out = (struct nc_status){0};
    if (nc_take(in, "service=") || nc_word(in, out->service, sizeof(out->service)) ||
        nc_take(in, " pid=") || nc_value(in, &out->pid) || out->pid > 2147483647u ||
        nc_take(in, " generation=") || nc_value(in, &out->generation)) return -1;
    if (full) {
        if (nc_take(in, " phase=") || nc_word(in, out->phase, sizeof(out->phase)) ||
            nc_take(in, " mode=") || nc_word(in, out->mode, sizeof(out->mode)) ||
            nc_take(in, " next_ms=") || nc_value(in, &out->next_ms) ||
            nc_take(in, " launches=") || nc_value(in, &out->launches)) return -1;
        if (strcmp(out->phase, "wait") && strcmp(out->phase, "reserved") && strcmp(out->phase, "starting") &&
            strcmp(out->phase, "ready") && strcmp(out->phase, "retiring") && strcmp(out->phase, "stopped") &&
            strcmp(out->phase, "failed")) return -1;
        if (strcmp(out->mode, "simple") && strcmp(out->mode, "notify") && strcmp(out->mode, "oneshot")) return -1;
    }
    return nc_take(in, "\n");
}
static inline int nc_quiesce_line(struct nc_cursor *in, uint64_t *started, uint64_t *deadline)
{
    return nc_take(in, "started_ms=") || nc_value(in, started) ||
        nc_take(in, " deadline_ms=") || nc_value(in, deadline) || *deadline <= *started || nc_take(in, "\n") ? -1 : 0;
}
static inline int nc_state_line(struct nc_cursor *in, struct nc_state *out)
{
    *out = (struct nc_state){0};
    if (nc_take(in, "phase=") || nc_word(in, out->phase, sizeof(out->phase)) ||
        nc_take(in, " graph=") || nc_word(in, out->graph, sizeof(out->graph)) ||
        nc_take(in, " children=") || nc_word(in, out->children, sizeof(out->children)) ||
        nc_take(in, " started_ms=") || nc_value(in, &out->started_ms) ||
        nc_take(in, " deadline_ms=") || nc_value(in, &out->deadline_ms) || nc_take(in, "\n")) return -1;
    if (strcmp(out->children, "unknown") && strcmp(out->children, "live") && strcmp(out->children, "empty")) return -1;
    if (!strcmp(out->phase, "running"))
        return strcmp(out->graph, "running") || out->started_ms || out->deadline_ms ? -1 : 0;
    if (out->deadline_ms <= out->started_ms) return -1;
    if (!strcmp(out->phase, "quiescing"))
        return strcmp(out->graph, "stopping") && strcmp(out->graph, "stopped") ? -1 : 0;
    if (!strcmp(out->phase, "quiesced"))
        return strcmp(out->graph, "stopped") || strcmp(out->children, "empty") ? -1 : 0;
    return -1;
}
/* Validate complete syntax and framing before printing or reporting success. */
static inline int nc_response(const char *bytes, size_t size)
{
    struct nc_cursor in = {bytes, size, 0};
    struct nc_status row;
    if (!size || size > NC_REPLY_BYTES || nc_take(&in, NC_PREFIX)) return -1;
    if (!nc_take(&in, "STATUS\n")) {
        char names[8][32]; unsigned count = 0;
        while (in.at < in.size && in.bytes[in.at] != 'E') {
            if (count == 8 || nc_take(&in, "SERVICE ") || nc_status_line(&in, &row, 1)) return -1;
            for (unsigned i = 0; i < count; ++i) if (!strcmp(names[i], row.service)) return -1;
            strcpy(names[count++], row.service);
        }
        if (!count) return -1;
    } else if (!nc_take(&in, "ACCEPTED ")) {
        if (nc_status_line(&in, &row, 0)) return -1;
    } else if (!nc_take(&in, "QUIESCE accepted=1 ")) {
        uint64_t started, deadline;
        if (nc_quiesce_line(&in, &started, &deadline)) return -1;
    } else if (!nc_take(&in, "HALT accepted=1 ")) {
        uint64_t started, deadline;
        if (nc_quiesce_line(&in, &started, &deadline)) return -1;
    } else if (!nc_take(&in, "REBOOT accepted=1 ")) {
        uint64_t started, deadline;
        if (nc_quiesce_line(&in, &started, &deadline)) return -1;
    } else if (!nc_take(&in, "POWEROFF accepted=1 ")) {
        uint64_t started, deadline;
        if (nc_quiesce_line(&in, &started, &deadline)) return -1;
    } else if (!nc_take(&in, "STATE ")) {
        struct nc_state state;
        if (nc_state_line(&in, &state)) return -1;
    } else {
        char code[32];
        if (nc_take(&in, "ERROR code=") || nc_word(&in, code, sizeof(code)) || nc_take(&in, "\nEND\n") || in.at != size)
            return -1;
        if (strcmp(code, "protocol") && strcmp(code, "denied") && strcmp(code, "unknown-service") &&
            strcmp(code, "busy") && strcmp(code, "capacity") && strcmp(code, "unsupported")) return -1;
        return 1;
    }
    return nc_take(&in, "END\n") || in.at != size ? -1 : 0;
}
static inline int nc_state_snapshot(const struct nc_buffer *reply, struct nc_state *out)
{
    struct nc_cursor in = {reply->bytes, reply->size, 0};
    return nc_response(reply->bytes, reply->size) || nc_take(&in, NC_PREFIX "STATE ") ||
        nc_state_line(&in, out) ? -1 : 0;
}
static inline int nc_snapshot(const struct nc_buffer *reply, const char *service, struct nc_status *out)
{
    struct nc_cursor in = {reply->bytes, reply->size, 0};
    if (nc_response(reply->bytes, reply->size) || nc_take(&in, NC_PREFIX "STATUS\n")) return -1;
    while (in.at < in.size && in.bytes[in.at] != 'E') {
        struct nc_status row;
        if (nc_take(&in, "SERVICE ") || nc_status_line(&in, &row, 1)) return -1;
        if (!strcmp(row.service, service)) { *out = row; return 0; }
    }
    return -1;
}
#endif
