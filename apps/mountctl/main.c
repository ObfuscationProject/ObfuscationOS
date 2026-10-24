#include <ok/storage.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#define MOUNTCTL_ATTEMPTS 8u

_Static_assert(OK_NATIVE_MOUNT_INFO_VERSION == 1 && OK_MOUNT_INFO_CAPACITY == 9 &&
               OK_MOUNT_INFO_PATH_CAPACITY == 256 && sizeof(struct ok_mount_info) == 288,
               "mountctl requires the bounded native mount inventory");

static int canonical_path(const struct ok_mount_info *row)
{
    if (!row->path_length || row->path[0] != '/' ||
        (row->path_length > 1 && row->path[row->path_length - 1] == '/')) return 0;
    uint32_t start = 1;
    for (uint32_t i = 1; i <= row->path_length; ++i) {
        if (i != row->path_length && row->path[i] != '/') continue;
        uint32_t size = i - start;
        if ((size == 0 && row->path_length != 1) ||
            (size == 1 && row->path[start] == '.') ||
            (size == 2 && row->path[start] == '.' && row->path[start + 1] == '.')) return 0;
        start = i + 1;
    }
    return 1;
}

static int valid_row(const struct ok_mount_info *row, uint32_t slot)
{
    if (row->version != OK_NATIVE_MOUNT_INFO_VERSION || row->size != sizeof(*row) ||
        !row->generation || row->generation > 2 * (OK_MOUNT_INFO_CAPACITY - 1) + 1 ||
        row->slot != slot || row->capacity != OK_MOUNT_INFO_CAPACITY ||
        row->state > OK_MOUNT_STATE_DETACHED || row->parent_id >= OK_MOUNT_INFO_CAPACITY ||
        row->path_length >= OK_MOUNT_INFO_PATH_CAPACITY) return 0;
    for (uint32_t i = 0; i < OK_MOUNT_INFO_PATH_CAPACITY; ++i)
        if ((i < row->path_length && !row->path[i]) ||
            (i >= row->path_length && row->path[i])) return 0;
    if (!slot)
        return row->state == OK_MOUNT_STATE_UNDERLYING_RAM && !row->parent_id &&
               row->path_length == 1 && row->path[0] == '/';
    if (row->state == OK_MOUNT_STATE_UNDERLYING_RAM || row->parent_id == slot) return 0;
    if (row->state == OK_MOUNT_STATE_UNUSED) return !row->parent_id && !row->path_length;
    return canonical_path(row);
}

static int attached(const struct ok_mount_info *row)
{
    return row->state >= OK_MOUNT_STATE_BORROWED && row->state <= OK_MOUNT_STATE_OWNED_RAM;
}

static int valid_inventory(const struct ok_mount_info *rows)
{
    uint32_t generation = 1;
    for (uint32_t slot = 1; slot < OK_MOUNT_INFO_CAPACITY; ++slot) {
        const struct ok_mount_info *row = &rows[slot];
        if (row->state != OK_MOUNT_STATE_UNUSED) ++generation;
        if (row->state == OK_MOUNT_STATE_DETACHED) ++generation;
        if (row->state != OK_MOUNT_STATE_UNUSED) {
            uint32_t parent = row->parent_id;
            for (uint32_t depth = 0; parent; ++depth) {
                if (depth >= OK_MOUNT_INFO_CAPACITY || rows[parent].state == OK_MOUNT_STATE_UNUSED)
                    return 0;
                parent = rows[parent].parent_id;
            }
        }
        if (!attached(row)) continue;
        if (row->parent_id && !attached(&rows[row->parent_id])) return 0;
        for (uint32_t prior = 1; prior < slot; ++prior)
            if (attached(&rows[prior]) && !strcmp(rows[prior].path, row->path)) return 0;
    }
    return generation == rows[0].generation;
}

static int collect(struct ok_mount_info *rows)
{
    for (unsigned attempt = 0; attempt < MOUNTCTL_ATTEMPTS; ++attempt) {
        int retry = 0;
        for (uint32_t slot = 0; slot < OK_MOUNT_INFO_CAPACITY; ++slot) {
            if (ok_mount_info(slot, &rows[slot]) < 0) {
                if (errno != EBUSY) return -1;
                retry = 1; break;
            }
            if (!valid_row(&rows[slot], slot)) { errno = EIO; return -1; }
            if (slot && rows[slot].generation != rows[0].generation) { retry = 1; break; }
        }
        if (retry) continue;
        struct ok_mount_info final;
        if (ok_mount_info(0, &final) < 0) {
            if (errno != EBUSY) return -1;
            continue;
        }
        if (!valid_row(&final, 0)) { errno = EIO; return -1; }
        if (memcmp(&rows[0], &final, sizeof(final))) continue;
        if (!valid_inventory(rows)) { errno = EIO; return -1; }
        return 0;
    }
    errno = EBUSY;
    return -1;
}

static int print_path(const struct ok_mount_info *row)
{
    static const char hex[] = "0123456789abcdef";
    if (fputc('"', stdout) < 0) return -1;
    for (uint32_t i = 0; i < row->path_length; ++i) {
        unsigned char byte = (unsigned char)row->path[i];
        if (byte == '\\' || byte == '"') {
            if (fputc('\\', stdout) < 0 || fputc(byte, stdout) < 0) return -1;
        } else if (byte < 0x20 || byte >= 0x7f) {
            if (fputs("\\x", stdout) < 0 || fputc(hex[byte >> 4], stdout) < 0 ||
                fputc(hex[byte & 15], stdout) < 0) return -1;
        } else if (fputc(byte, stdout) < 0) return -1;
    }
    return fputc('"', stdout) < 0 ? -1 : 0;
}

int main(int argc, char **argv)
{
    if (argc != 2 || strcmp(argv[1], "status")) {
        fputs("usage: mountctl status\n", stderr); return 2;
    }
    struct ok_mount_info rows[OK_MOUNT_INFO_CAPACITY];
    if (collect(rows) < 0) { perror("mountctl"); return 1; }
    int covered = 0;
    for (uint32_t slot = 1; slot < OK_MOUNT_INFO_CAPACITY; ++slot)
        if (attached(&rows[slot]) && rows[slot].path_length == 1) covered = 1;
    if (printf("MOUNTS version=1 generation=%u capacity=%u\n", rows[0].generation,
               rows[0].capacity) < 0) return 1;
    static const char *const states[] = {
        "unused", "underlying-ram-namespace", "borrowed-provider", "owned-provider", "owned-ram", "detached-history"
    };
    for (uint32_t slot = 0; slot < OK_MOUNT_INFO_CAPACITY; ++slot) {
        if (printf("slot=%u state=%s parent=%u path=", slot, states[rows[slot].state],
                   rows[slot].parent_id) < 0 || print_path(&rows[slot]) < 0) return 1;
        if (!slot && printf(" covered=%u", (unsigned)covered) < 0) return 1;
        if (fputc('\n', stdout) < 0) return 1;
    }
    return 0;
}
