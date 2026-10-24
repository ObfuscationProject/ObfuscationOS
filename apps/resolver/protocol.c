#include "resolver.h"
#include <errno.h>
#include <string.h>
#include <unistd.h>

static size_t name_size(const char name[RS_NAME_BYTES + 1])
{
    size_t size = 0;
    while (size <= RS_NAME_BYTES && name[size]) ++size;
    return size;
}

static void text(struct rs_buffer *out, const char *value)
{
    size_t size = strlen(value);
    if (size > sizeof(out->bytes) - out->size) { out->failed = 1; return; }
    memcpy(out->bytes + out->size, value, size); out->size += size;
}

static void number(struct rs_buffer *out, uint64_t value)
{
    char digits[21]; size_t at = sizeof(digits) - 1; digits[at] = 0;
    do { digits[--at] = (char)('0' + value % 10); value /= 10; } while (value);
    text(out, digits + at);
}

static void address_text(struct rs_buffer *out, const uint8_t address[4])
{
    for (unsigned i = 0; i < 4; ++i) {
        if (i) text(out, ".");
        number(out, address[i]);
    }
}

struct cursor { const char *bytes; size_t size, at; };
static int take(struct cursor *in, const char *value)
{
    size_t size = strlen(value);
    if (size > in->size - in->at || memcmp(in->bytes + in->at, value, size)) return -1;
    in->at += size; return 0;
}
static int unsigned_value(struct cursor *in, uint64_t limit, uint64_t *value)
{
    size_t start = in->at;
    while (in->at < in->size && in->bytes[in->at] >= '0' && in->bytes[in->at] <= '9') ++in->at;
    return rs_unsigned(in->bytes + start, in->at - start, limit, value);
}

int rs_request_parse(const char *bytes, size_t size, struct rs_request *request)
{
    if (!bytes || !request || size > RS_REQUEST_BYTES) return -1;
    int complete = 0;
    for (size_t i = 0; i < size; ++i) {
        unsigned char c = (unsigned char)bytes[i];
        if (c == '\n') { if (i + 1 != size) return -1; complete = 1; }
        else if (c < 32 || c > 126) return -1;
    }
    if (!complete) return size == RS_REQUEST_BYTES ? -1 : 0;
    struct cursor in = {bytes, size, 0}; struct rs_request prepared = {0};
    if (!take(&in, "OKR1 STATUS\n") && in.at == size) prepared.operation = RS_STATUS;
    else {
        in.at = 0;
        if (take(&in, "OKR1 LOOKUP ") ||
            rs_query_normalize(bytes + in.at, size - in.at - 1, prepared.name)) return -1;
        prepared.operation = RS_LOOKUP;
    }
    *request = prepared; return 1;
}

int rs_request_encode(const struct rs_request *request, struct rs_buffer *out)
{
    if (!request || !out) return -1;
    *out = (struct rs_buffer){0};
    if (request->operation == RS_STATUS) text(out, "OKR1 STATUS\n");
    else if (request->operation == RS_LOOKUP) {
        char name[RS_NAME_BYTES + 1];
        if (rs_query_normalize(request->name, name_size(request->name), name)) return -1;
        text(out, "OKR1 LOOKUP "); text(out, name); text(out, "\n");
    } else return -1;
    return out->failed || out->size > RS_REQUEST_BYTES ? -1 : 0;
}

static int valid_lookup(const struct rs_reply *reply)
{
    char name[RS_NAME_BYTES + 1]; uint8_t address[4];
    size_t size = name_size(reply->name);
    if (rs_query_normalize(reply->name, size, name) || strcmp(name, reply->name)) return 0;
    int numeric = !rs_ipv4(name, size, address);
    return numeric ? reply->source == RS_NUMERIC && !memcmp(address, reply->address, 4)
                   : reply->source == RS_HOSTS;
}

int rs_reply_encode(const struct rs_reply *reply, struct rs_buffer *out)
{
    if (!reply || !out) return -1;
    *out = (struct rs_buffer){0};
    if (reply->operation == RS_ERROR) {
        if (reply->error <= 0 || reply->error > 4095) return -1;
        text(out, "OKR1 ERROR errno="); number(out, (unsigned)reply->error);
    } else if (reply->operation == RS_STATUS || reply->operation == RS_LOOKUP) {
        if (reply->pid <= 1 || reply->pid > INT32_MAX) return -1;
        text(out, reply->operation == RS_STATUS ? "OKR1 STATUS pid=" : "OKR1 LOOKUP pid=");
        number(out, reply->pid);
        if (reply->operation == RS_STATUS) {
            if (reply->aliases > RS_ALIAS_CAPACITY || reply->bytes > RS_HOSTS_BYTES) return -1;
            text(out, " aliases="); number(out, reply->aliases);
            text(out, " bytes="); number(out, reply->bytes);
        } else {
            if (!valid_lookup(reply)) return -1;
            text(out, " name="); text(out, reply->name);
            text(out, " address="); address_text(out, reply->address);
            text(out, reply->source == RS_NUMERIC ? " source=numeric" : " source=hosts");
        }
    } else return -1;
    text(out, "\nEND\n"); return out->failed ? -1 : 0;
}

int rs_reply_parse(const char *bytes, size_t size, struct rs_reply *reply)
{
    if (!bytes || !reply || !size || size > RS_REPLY_BYTES) return -1;
    struct cursor in = {bytes, size, 0}; struct rs_reply prepared = {0}; uint64_t value;
    if (!take(&in, "OKR1 ERROR errno=")) {
        if (unsigned_value(&in, 4095, &value) || !value) return -1;
        prepared.operation = RS_ERROR; prepared.error = (int)value;
    } else {
        in.at = 0;
        if (!take(&in, "OKR1 STATUS pid=")) prepared.operation = RS_STATUS;
        else { in.at = 0; if (take(&in, "OKR1 LOOKUP pid=")) return -1; prepared.operation = RS_LOOKUP; }
        if (unsigned_value(&in, INT32_MAX, &value) || value <= 1) return -1;
        prepared.pid = (uint32_t)value;
        if (prepared.operation == RS_STATUS) {
            if (take(&in, " aliases=") || unsigned_value(&in, RS_ALIAS_CAPACITY, &value)) return -1;
            prepared.aliases = (uint32_t)value;
            if (take(&in, " bytes=") || unsigned_value(&in, RS_HOSTS_BYTES, &value)) return -1;
            prepared.bytes = (uint32_t)value;
        } else {
            if (take(&in, " name=")) return -1;
            size_t start = in.at;
            while (in.at < size && bytes[in.at] != ' ') ++in.at;
            size_t name_length = in.at - start;
            if (rs_query_normalize(bytes + start, name_length, prepared.name) ||
                strlen(prepared.name) != name_length || memcmp(prepared.name, bytes + start, name_length)) return -1;
            if (take(&in, " address=")) return -1;
            start = in.at; while (in.at < size && bytes[in.at] != ' ') ++in.at;
            if (rs_ipv4(bytes + start, in.at - start, prepared.address)) return -1;
            if (!take(&in, " source=numeric")) prepared.source = RS_NUMERIC;
            else { if (take(&in, " source=hosts")) return -1; prepared.source = RS_HOSTS; }
            if (!valid_lookup(&prepared)) return -1;
        }
    }
    if (take(&in, "\nEND\n") || in.at != size) return -1;
    *reply = prepared; return 0;
}

void rs_dispatch(const struct rs_request *request, const struct rs_hosts *hosts, struct rs_reply *reply)
{
    *reply = (struct rs_reply){.operation = RS_ERROR, .error = EINVAL};
    if (!request || !hosts || hosts->count > RS_ALIAS_CAPACITY || hosts->bytes > RS_HOSTS_BYTES) return;
    pid_t pid = getpid();
    if (pid <= 1) { reply->error = EIO; return; }
    if (request->operation == RS_STATUS) {
        *reply = (struct rs_reply){.operation = RS_STATUS, .pid = (uint32_t)pid,
                                  .aliases = hosts->count, .bytes = hosts->bytes}; return;
    }
    if (request->operation != RS_LOOKUP) return;
    char name[RS_NAME_BYTES + 1];
    if (rs_query_normalize(request->name, name_size(request->name), name)) return;
    uint8_t address[4]; enum rs_source source = RS_NUMERIC;
    if (rs_ipv4(name, strlen(name), address)) {
        source = RS_HOSTS; unsigned i;
        for (i = 0; i < hosts->count; ++i) if (!strcmp(name, hosts->aliases[i].name)) break;
        if (i == hosts->count) { reply->error = ENOENT; return; }
        memcpy(address, hosts->aliases[i].address, 4);
    }
    *reply = (struct rs_reply){.operation = RS_LOOKUP, .pid = (uint32_t)pid, .source = source};
    memcpy(reply->name, name, strlen(name) + 1); memcpy(reply->address, address, 4);
}
