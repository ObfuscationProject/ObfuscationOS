#ifndef OK_SERVICE_MANIFEST_H
#define OK_SERVICE_MANIFEST_H

#include "service_graph.h"
#include <string.h>

enum { SM_BYTE_LIMIT = 4096, SM_NAME_LIMIT = 31, SM_EXEC_LIMIT = 95 };
struct sm_record {
    char name[SM_NAME_LIMIT + 1];
    char executable[SM_EXEC_LIMIT + 1];
    uint32_t uid, gid;
    uint8_t dependencies;
    enum sg_mode mode;
};
struct service_manifest { unsigned count; struct sm_record records[SG_CAPACITY]; };

static inline int sm_name(const char *value, size_t size)
{
    if (!size || size > SM_NAME_LIMIT || (size == 1 && value[0] == '-')) return 0;
    for (size_t i = 0; i < size; ++i) {
        unsigned char c = (unsigned char)value[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '-' || c == '_')) return 0;
    }
    return 1;
}

static inline int sm_word(const char *value, size_t size, const char *expected)
{ return strlen(expected) == size && !memcmp(value, expected, size); }

static inline int sm_terminated(const char *value, size_t capacity)
{
    for (size_t i = 0; i < capacity; ++i) if (!value[i]) return 1;
    return 0;
}

/* UINT32_MAX is the credential setter's unchanged sentinel, never an identity. */
static inline int sm_identity(const char *value, size_t size, uint32_t *identity)
{
    if (!size || size > 10 || (size > 1 && value[0] == '0')) return -1;
    uint32_t result = 0;
    for (size_t i = 0; i < size; ++i) {
        unsigned char c = (unsigned char)value[i];
        if (c < '0' || c > '9' || result > (UINT32_MAX - 1 - (c - '0')) / 10) return -1;
        result = result * 10 + (c - '0');
    }
    *identity = result;
    return 0;
}

/* Graph pointers always refer to the caller's committed manifest storage. */
static inline int sm_bind(const struct service_manifest *manifest, struct service_graph *graph)
{
    if (!manifest || !graph || !manifest->count || manifest->count > SG_CAPACITY) return -1;
    struct sg_spec specs[SG_CAPACITY];
    for (unsigned i = 0; i < manifest->count; ++i) {
        const struct sm_record *record = &manifest->records[i];
        if (!sm_terminated(record->name, sizeof(record->name)) ||
            !sm_terminated(record->executable, sizeof(record->executable)) ||
            !sm_name(record->name, strlen(record->name)) ||
            record->uid == UINT32_MAX || record->gid == UINT32_MAX) return -1;
        specs[i] = (struct sg_spec){record->name, record->executable, record->dependencies, record->mode};
    }
    return sg_init(graph, specs, manifest->count);
}

/* All bytes, names and edges are validated before publishing owned strings. */
static inline int sm_parse(struct service_manifest *manifest, const char *bytes, size_t size)
{
    static const char header[] = "OK_SERVICE_MANIFEST ";
    enum { header_size = sizeof(header) - 1 + 2 };
    if (!manifest || !bytes || size < header_size || size > SM_BYTE_LIMIT ||
        bytes[size - 1] != '\n' || memcmp(bytes, header, sizeof(header) - 1) ||
        (bytes[sizeof(header) - 1] != '1' && bytes[sizeof(header) - 1] != '2') ||
        bytes[header_size - 1] != '\n') return -1;
    const unsigned fields = bytes[sizeof(header) - 1] == '1' ? 5 : 7;
    for (size_t i = 0; i < size; ++i) {
        unsigned char c = (unsigned char)bytes[i];
        if (c != '\n' && (c < 32 || c > 126)) return -1;
    }
    struct service_manifest prepared = {0};
    size_t dependency_start[SG_CAPACITY], dependency_size[SG_CAPACITY];
    for (size_t offset = header_size; offset < size;) {
        size_t end = offset;
        while (end < size && bytes[end] != '\n') ++end;
        size_t line = end - offset;
        if (!line || bytes[offset] == '#') { offset = end + 1; continue; }
        if (prepared.count == SG_CAPACITY) return -1;
        size_t start[7], length[7], cursor = offset;
        for (unsigned field = 0; field < fields; ++field) {
            start[field] = cursor;
            while (cursor < end && bytes[cursor] != ' ') ++cursor;
            length[field] = cursor - start[field];
            if (!length[field] || (field + 1 < fields && cursor == end) ||
                (field + 1 == fields && cursor != end)) return -1;
            if (field + 1 < fields) ++cursor;
        }
        if (!sm_word(bytes + start[0], length[0], "service") ||
            !sm_name(bytes + start[1], length[1]) || !length[3] ||
            length[3] > SM_EXEC_LIMIT || bytes[start[3]] != '/') return -1;
        struct sm_record *record = &prepared.records[prepared.count];
        if (fields == 7 && (sm_identity(bytes + start[5], length[5], &record->uid) ||
                           sm_identity(bytes + start[6], length[6], &record->gid))) return -1;
        if (sm_word(bytes + start[2], length[2], "simple")) record->mode = SG_SIMPLE;
        else if (sm_word(bytes + start[2], length[2], "notify")) record->mode = SG_NOTIFY;
        else if (sm_word(bytes + start[2], length[2], "oneshot")) record->mode = SG_ONESHOT;
        else return -1;
        memcpy(record->name, bytes + start[1], length[1]);
        memcpy(record->executable, bytes + start[3], length[3]);
        for (unsigned i = 0; i < prepared.count; ++i)
            if (sg_equal(record->name, prepared.records[i].name)) return -1;
        dependency_start[prepared.count] = start[4];
        dependency_size[prepared.count] = length[4];
        ++prepared.count;
        offset = end + 1;
    }
    for (unsigned i = 0; i < prepared.count; ++i) {
        const size_t end = dependency_start[i] + dependency_size[i];
        if (dependency_size[i] == 1 && bytes[dependency_start[i]] == '-') continue;
        for (size_t cursor = dependency_start[i]; cursor < end;) {
            size_t next = cursor;
            while (next < end && bytes[next] != ',') ++next;
            if (!sm_name(bytes + cursor, next - cursor)) return -1;
            unsigned found = prepared.count;
            for (unsigned j = 0; j < prepared.count; ++j)
                if (sm_word(bytes + cursor, next - cursor, prepared.records[j].name)) { found = j; break; }
            if (found == prepared.count || found == i ||
                (prepared.records[i].dependencies & (1u << found))) return -1;
            prepared.records[i].dependencies |= (uint8_t)(1u << found);
            if (next < end && next + 1 == end) return -1;
            cursor = next + 1;
        }
    }
    struct service_graph checked;
    if (sm_bind(&prepared, &checked)) return -1;
    *manifest = prepared;
    return 0;
}

#endif
