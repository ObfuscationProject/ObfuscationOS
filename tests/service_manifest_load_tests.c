#define _GNU_SOURCE 1
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *input;
static size_t input_size, input_offset, read_piece;
static int directory_error, leaf_error, stat_error_call, stat_calls, read_error, read_eintr;
static int close_error_fd, closed_directory, closed_leaf, mutation;
static struct stat directory_metadata, file_metadata;
static int fake_open(const char *path, int flags, ...);
static int fake_openat(int directory, const char *path, int flags, ...);
static int fake_fstat(int descriptor, struct stat *metadata);
static ssize_t fake_read(int descriptor, void *bytes, size_t size);
static int fake_close(int descriptor);
#define open fake_open
#define openat fake_openat
#define fstat fake_fstat
#define read fake_read
#define close fake_close
#include "../apps/init/service_manifest_load.h"
#undef open
#undef openat
#undef fstat
#undef read
#undef close

static int fake_open(const char *path, int flags, ...)
{
    assert(!strcmp(path, "/etc") && flags == (O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
    if (directory_error) { errno = directory_error; return -1; } return 40;
}
static int fake_openat(int directory, const char *path, int flags, ...)
{
    assert(directory == 40 && !strcmp(path, "services.conf") && flags == (O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
    if (leaf_error) { errno = leaf_error; return -1; } return 41;
}
static int fake_fstat(int descriptor, struct stat *metadata)
{
    ++stat_calls;
    if (stat_error_call == stat_calls) { errno = EIO; return -1; }
    if (descriptor == 40) *metadata = directory_metadata;
    else {
        assert(descriptor == 41); *metadata = file_metadata;
        if (stat_calls == 3) {
            if (mutation == 1) metadata->st_ino++;
            if (mutation == 2) metadata->st_mode ^= 0001;
            if (mutation == 3) metadata->st_uid++;
            if (mutation == 4) metadata->st_gid++;
            if (mutation == 5) metadata->st_size++;
            if (mutation == 6) metadata->st_mtim.tv_nsec++;
            if (mutation == 7) metadata->st_ctim.tv_nsec++;
            if (mutation == 8) metadata->st_dev++;
            if (mutation == 9) metadata->st_atim.tv_nsec++; /* Reading may change atime. */
        }
    }
    return 0;
}
static ssize_t fake_read(int descriptor, void *bytes, size_t size)
{
    assert(descriptor == 41 && size);
    if (read_eintr) { --read_eintr; errno = EINTR; return -1; }
    if (read_error) { errno = read_error; return -1; }
    size_t available = input_size - input_offset;
    if (size > available) size = available;
    if (size > read_piece) size = read_piece;
    memcpy(bytes, input + input_offset, size); input_offset += size; return (ssize_t)size;
}
static int fake_close(int descriptor)
{
    if (descriptor == 40) ++closed_directory; else { assert(descriptor == 41); ++closed_leaf; }
    if (descriptor == close_error_fd) { errno = EIO; return -1; } return 0;
}
static void reset(void)
{
    input = "OK_SERVICE_MANIFEST 1\nservice first simple /first -\n";
    input_size = strlen(input); input_offset = 0; read_piece = 3;
    directory_error = leaf_error = stat_error_call = stat_calls = read_error = read_eintr = 0;
    close_error_fd = closed_directory = closed_leaf = mutation = 0;
    memset(&directory_metadata, 0, sizeof(directory_metadata)); directory_metadata.st_mode = S_IFDIR | 0755;
    memset(&file_metadata, 0, sizeof(file_metadata)); file_metadata.st_mode = S_IFREG | 0644;
    file_metadata.st_size = (off_t)input_size;
}
static void refused(void)
{
    struct service_manifest output, before;
    memset(&output, 0x5a, sizeof(output)); before = output;
    assert(sm_load(&output) == -1 && !memcmp(&before, &output, sizeof(output)));
    assert(closed_directory == (directory_error ? 0 : 1));
    assert(closed_leaf == ((!directory_error && !leaf_error && stat_error_call != 1 &&
        S_ISDIR(directory_metadata.st_mode) && !directory_metadata.st_uid && !(directory_metadata.st_mode & 0022)) ? 1 : 0));
}
int main(void)
{
    struct service_manifest output;
    reset(); read_eintr = 2; mutation = 9;
    assert(sm_load(&output) == SM_CONFIG_PRESENT && output.count == 1 && closed_directory == 1 && closed_leaf == 1);
    reset(); input = "OK_SERVICE_MANIFEST 2\nservice worker simple /worker - 1001 2002\n";
    input_size = strlen(input); file_metadata.st_size = (off_t)input_size; refused(); assert(errno == EINVAL);
    reset(); input = "OK_SERVICE_MANIFEST 2\nservice root simple /root - 0 0\n";
    input_size = strlen(input); file_metadata.st_size = (off_t)input_size; refused(); assert(errno == EINVAL);
    reset(); leaf_error = ENOENT; memset(&output, 0x5a, sizeof(output));
    struct service_manifest before = output;
    assert(sm_load(&output) == SM_CONFIG_MISSING && !memcmp(&output, &before, sizeof(output)) && closed_directory == 1 && !closed_leaf);
    for (int error = 1; error <= 3; ++error) { reset(); directory_error = error == 1 ? ENOENT : error == 2 ? ELOOP : EACCES; refused(); }
    for (int error = 1; error <= 3; ++error) { reset(); leaf_error = error == 1 ? ELOOP : error == 2 ? EACCES : EIO; refused(); }
    for (int index = 1; index <= 3; ++index) { reset(); stat_error_call = index; refused(); }
    reset(); directory_metadata.st_uid = 1; refused();
    reset(); directory_metadata.st_mode |= 0002; refused();
    reset(); directory_metadata.st_mode = S_IFREG | 0755; refused();
    reset(); file_metadata.st_uid = 1; refused();
    reset(); file_metadata.st_mode |= 0020; refused();
    reset(); file_metadata.st_mode = S_IFIFO | 0644; refused();
    reset(); file_metadata.st_size = -1; refused();
    reset(); file_metadata.st_size = SM_BYTE_LIMIT + 1; refused();
    reset(); file_metadata.st_size--; refused();
    reset(); read_error = EIO; refused();
    reset(); close_error_fd = 40; refused();
    reset(); close_error_fd = 41; refused();
    reset(); leaf_error = ENOENT; close_error_fd = 40; refused();
    for (int index = 1; index <= 8; ++index) { reset(); mutation = index; refused(); }
    reset(); input = "bad\n"; input_size = 4; file_metadata.st_size = 4; refused();
    char boundary[SM_BYTE_LIMIT + 1];
    reset(); size_t prefix = input_size; memcpy(boundary, input, prefix); boundary[prefix++] = '#';
    memset(boundary + prefix, 'x', SM_BYTE_LIMIT - prefix - 1); boundary[SM_BYTE_LIMIT - 1] = '\n';
    input = boundary; input_size = SM_BYTE_LIMIT; file_metadata.st_size = SM_BYTE_LIMIT;
    assert(sm_load(&output) == SM_CONFIG_PRESENT && input_offset == SM_BYTE_LIMIT);
    reset(); input = boundary; input_size = SM_BYTE_LIMIT + 1; boundary[SM_BYTE_LIMIT] = '\n'; file_metadata.st_size = SM_BYTE_LIMIT;
    refused();
    puts("SERVICE_MANIFEST_LOADER_HOSTED_PASS");
    return 0;
}
