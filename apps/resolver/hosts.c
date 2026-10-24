#include "resolver.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

int rs_unsigned(const char *bytes, size_t size, uint64_t limit, uint64_t *value)
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

int rs_ipv4(const char *bytes, size_t size, uint8_t address[4])
{
    if (!bytes || !address || !size || size > 15) return -1;
    uint8_t prepared[4]; size_t at = 0;
    for (unsigned part = 0; part < 4; ++part) {
        size_t start = at; uint64_t value;
        while (at < size && bytes[at] >= '0' && bytes[at] <= '9') ++at;
        if (rs_unsigned(bytes + start, at - start, 255, &value)) return -1;
        prepared[part] = (uint8_t)value;
        if (part != 3 && (at == size || bytes[at++] != '.')) return -1;
    }
    if (at != size) return -1;
    memcpy(address, prepared, sizeof(prepared));
    return 0;
}

static int alnum(unsigned char c)
{ return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9'); }

int rs_name_normalize(const char *bytes, size_t size, char name[RS_NAME_BYTES + 1])
{
    if (!bytes || !name || !size || size > RS_NAME_BYTES) return -1;
    if (bytes[size - 1] == '.') --size;
    if (!size) return -1;
    size_t label = 0;
    for (size_t i = 0; i < size; ++i) {
        unsigned char c = (unsigned char)bytes[i];
        if (c == '.') {
            if (!label || !alnum((unsigned char)bytes[i - 1])) return -1;
            label = 0;
        } else {
            if ((!alnum(c) && c != '-') || (!label && !alnum(c)) || ++label > 63) return -1;
        }
    }
    if (!label || !alnum((unsigned char)bytes[size - 1])) return -1;
    for (size_t i = 0; i < size; ++i) {
        unsigned char c = (unsigned char)bytes[i];
        name[i] = (char)(c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c);
    }
    name[size] = 0;
    return 0;
}

static int digit_dot(const char *bytes, size_t size)
{
    for (size_t i = 0; i < size; ++i)
        if ((bytes[i] < '0' || bytes[i] > '9') && bytes[i] != '.') return 0;
    return 1;
}

int rs_query_normalize(const char *bytes, size_t size, char name[RS_NAME_BYTES + 1])
{
    uint8_t address[4];
    if (!bytes || !name || !size || size > RS_NAME_BYTES) return -1;
    if (!rs_ipv4(bytes, size, address)) { memcpy(name, bytes, size); name[size] = 0; return 0; }
    if (digit_dot(bytes, size)) return -1;
    return rs_name_normalize(bytes, size, name);
}

static int whitespace(char c) { return c == ' ' || c == '\t'; }
static int reject(int error) { errno = error; return -1; }

int rs_hosts_parse(const char *bytes, size_t size, struct rs_hosts *hosts, struct rs_hosts *scratch)
{
    if (!bytes || !hosts || !scratch || hosts == scratch) return reject(EINVAL);
    if (size > RS_HOSTS_BYTES) return reject(EFBIG);
    if (size && bytes[size - 1] != '\n') return reject(EINVAL);
    for (size_t i = 0; i < size; ++i) {
        unsigned char c = (unsigned char)bytes[i];
        if (c != '\n' && c != '\t' && (c < 32 || c > 126)) return reject(EINVAL);
    }
    memset(scratch, 0, sizeof(*scratch));
    for (size_t line = 0; line < size;) {
        size_t end = line; while (bytes[end] != '\n') ++end;
        size_t at = line; line = end + 1;
        while (at < end && whitespace(bytes[at])) ++at;
        if (at == end || bytes[at] == '#') continue;
        size_t start = at;
        while (at < end && !whitespace(bytes[at]) && bytes[at] != '#') ++at;
        uint8_t address[4];
        if (rs_ipv4(bytes + start, at - start, address)) return reject(EINVAL);
        unsigned aliases = 0;
        for (;;) {
            while (at < end && whitespace(bytes[at])) ++at;
            if (at == end || bytes[at] == '#') break;
            start = at;
            while (at < end && !whitespace(bytes[at]) && bytes[at] != '#') ++at;
            char name[RS_NAME_BYTES + 1];
            if (digit_dot(bytes + start, at - start) ||
                rs_name_normalize(bytes + start, at - start, name)) return reject(EINVAL);
            ++aliases;
            unsigned found = scratch->count;
            for (unsigned i = 0; i < scratch->count; ++i)
                if (!strcmp(name, scratch->aliases[i].name)) { found = i; break; }
            if (found != scratch->count) {
                if (memcmp(address, scratch->aliases[found].address, 4)) return reject(EINVAL);
            } else {
                if (scratch->count == RS_ALIAS_CAPACITY) return reject(EFBIG);
                memcpy(scratch->aliases[found].name, name, strlen(name) + 1);
                memcpy(scratch->aliases[found].address, address, 4);
                ++scratch->count;
            }
        }
        if (!aliases) return reject(EINVAL);
    }
    scratch->bytes = (uint32_t)size;
    *hosts = *scratch;
    return 0;
}

static int protected_directory(int fd)
{
    struct stat s;
    if (fstat(fd, &s) < 0) return -1;
    if (!S_ISDIR(s.st_mode) || s.st_uid || s.st_gid || (s.st_mode & 07022)) return reject(EACCES);
    return 0;
}

static int same_file(const struct stat *a, const struct stat *b)
{
    /* Native stat has no device identity or meaningful modification timestamps.
     * This is a validated startup byte snapshot, not root-edit atomicity. */
    return a->st_ino == b->st_ino && a->st_mode == b->st_mode && a->st_uid == b->st_uid &&
        a->st_gid == b->st_gid && a->st_nlink == b->st_nlink && a->st_size == b->st_size;
}

int rs_hosts_load(struct rs_hosts *hosts, struct rs_workspace *workspace)
{
    if (!hosts || !workspace || hosts == &workspace->table) return reject(EINVAL);
    int root = -1, etc = -1, file = -1, result = -1, error;
    struct stat before, after, named; size_t size = 0; unsigned interrupted = 0;
    root = open("/", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (root < 0 || protected_directory(root) < 0) goto done;
    etc = openat(root, "etc", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (etc < 0 || protected_directory(etc) < 0) goto done;
    file = openat(etc, "hosts", O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (file < 0 || fstat(file, &before) < 0) goto done;
    if (!S_ISREG(before.st_mode) || before.st_uid || before.st_gid || before.st_nlink != 1 ||
        (before.st_mode & 07022)) { errno = EACCES; goto done; }
    if (before.st_size < 0 || (uint64_t)before.st_size > RS_HOSTS_BYTES) { errno = EFBIG; goto done; }
    for (;;) {
        ssize_t count = read(file, workspace->bytes + size, sizeof(workspace->bytes) - size);
        if (count < 0) {
            if (errno == EINTR && ++interrupted < 16) continue;
            goto done;
        }
        if (!count) break;
        interrupted = 0;
        if ((size_t)count > sizeof(workspace->bytes) - size) { errno = EIO; goto done; }
        size += (size_t)count;
        if (size > RS_HOSTS_BYTES) { errno = EFBIG; goto done; }
    }
    if (fstat(file, &after) < 0) goto done;
    if (!same_file(&before, &after) || size != (size_t)before.st_size) { errno = EIO; goto done; }
    if (fstatat(etc, "hosts", &named, AT_SYMLINK_NOFOLLOW) < 0) goto done;
    if (!same_file(&before, &named)) { errno = EIO; goto done; }
    /* No table is exposed if either close fails. */
    if (close(file) < 0) { file = -1; goto done; } file = -1;
    if (close(etc) < 0) { etc = -1; goto done; } etc = -1;
    if (close(root) < 0) { root = -1; goto done; } root = -1;
    result = rs_hosts_parse(workspace->bytes, size, hosts, &workspace->table);
done:
    error = errno;
    if (file >= 0 && close(file) < 0) { error = errno; result = -1; }
    if (etc >= 0 && close(etc) < 0) { error = errno; result = -1; }
    if (root >= 0 && close(root) < 0) { error = errno; result = -1; }
    errno = error;
    return result;
}
