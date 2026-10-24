#define _GNU_SOURCE 1
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Hosted syscall fault models only; native service lifecycle is a separate gate. */
static int model_open(const char *, int, ...);
static int model_fstat(int, struct stat *);
static ssize_t model_read(int, void *, size_t);
static ssize_t model_write(int, const void *, size_t);
static int model_close(int);
#define open model_open
#define fstat model_fstat
#define read model_read
#define write model_write
#define close model_close
#include "musl/service_generation.h"
#undef open
#undef fstat
#undef read
#undef write
#undef close

static struct stat metadata[2];
static int open_error, stat_error[2], transfer_error, close_error;
static unsigned opens, stats, transfers, closes, interruptions;
static unsigned cases;
static ssize_t transfer_size;
static char input, stored;
static int expect_writing;

static void reset(int writing)
{
    memset(metadata, 0, sizeof(metadata));
    metadata[0].st_mode = S_IFREG | 0600;
    metadata[0].st_size = 1;
    metadata[0].st_nlink = 1;
    metadata[0].st_ino = 12;
    metadata[0].st_dev = 1;
    metadata[1] = metadata[0];
    open_error = stat_error[0] = stat_error[1] = transfer_error = close_error = 0;
    opens = stats = transfers = closes = interruptions = 0;
    transfer_size = 1; input = '1'; stored = '?'; expect_writing = writing;
    errno = EDOM;
}

static int model_open(const char *path, int flags, ...)
{
    ++opens;
    assert(!strcmp(path, "/service-generation"));
    assert(flags == ((expect_writing ? O_WRONLY : O_RDONLY) |
        O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
    if (open_error) { errno = open_error; return -1; }
    return 19;
}

static int model_fstat(int fd, struct stat *value)
{
    assert(fd == 19 && stats < 2);
    unsigned index = stats++;
    if (stat_error[index]) { errno = stat_error[index]; return -1; }
    *value = metadata[index];
    errno = ERANGE;
    return 0;
}

static ssize_t transfer(void)
{
    ++transfers;
    if (interruptions) { --interruptions; errno = EINTR; return -1; }
    if (transfer_error) { errno = transfer_error; return -1; }
    errno = EDOM;
    return transfer_size;
}

static ssize_t model_read(int fd, void *value, size_t size)
{
    assert(fd == 19 && !expect_writing && size == 2);
    ssize_t result = transfer();
    if (result > 0) { ((char *)value)[0] = input; if (result == 2) ((char *)value)[1] = '2'; }
    return result;
}

static ssize_t model_write(int fd, const void *value, size_t size)
{
    assert(fd == 19 && expect_writing && size == 1);
    ssize_t result = transfer();
    if (result == 1) stored = *(const char *)value;
    return result;
}

static int model_close(int fd)
{
    assert(fd == 19 && closes == 0);
    ++closes;
    errno = close_error ? close_error : EBADF;
    return close_error ? -1 : 0;
}

static int call(void)
{
    if (expect_writing) return generation_write('2');
    char value = '?';
    int result = generation_read(&value);
    assert(value == (result ? '?' : input));
    return result;
}

static void failure(int error, unsigned expected_stats, unsigned expected_transfers)
{
    assert(call() == -1 && errno == error);
    assert(opens == 1 && stats == expected_stats && transfers == expected_transfers && closes == 1);
    ++cases;
}

static void alter(struct stat *value, unsigned field)
{
    switch (field) {
    case 0: value->st_mode = S_IFDIR | 0600; break;
    case 1: value->st_mode = S_IFLNK | 0600; break;
    case 2: value->st_mode = S_IFIFO | 0600; break;
    case 3: value->st_mode |= 0004; break;
    case 4: value->st_mode |= S_ISUID; break;
    case 5: value->st_uid = 1; break;
    case 6: value->st_gid = 1; break;
    case 7: value->st_size = 0; break;
    case 8: value->st_size = 2; break;
    case 9: value->st_nlink = 0; break;
    case 10: value->st_nlink = 2; break;
    case 11: value->st_ino = 0; break;
    case 12: value->st_dev = 0; break;
    case 13: ++value->st_ino; break;
    case 14: ++value->st_dev; break;
    default: assert(0);
    }
}

int main(void)
{
    reset(0);
    assert(generation_read(0) == -1 && errno == EINVAL && !opens);
    ++cases;
    reset(1);
    assert(generation_write('3') == -1 && errno == EINVAL && !opens);
    ++cases;
    for (int writing = 0; writing <= 1; ++writing) {
        for (char value = '0'; value <= '2'; ++value) {
            reset(writing); input = value;
            int result;
            if (writing) result = generation_write(value);
            else { char got = '?'; result = generation_read(&got); assert(got == value); }
            assert(result == 0 && opens == 1 && stats == 2 && transfers == 1 && closes == 1);
            if (writing) assert(stored == value);
            ++cases;
        }
        reset(writing); open_error = ELOOP;
        assert(call() == -1 && errno == ELOOP && opens == 1 && !stats && !transfers && !closes);
        ++cases;
        reset(writing); stat_error[0] = EACCES; close_error = EIO;
        failure(EACCES, 1, 0);
        for (unsigned field = 0; field < 13; ++field) {
            reset(writing); alter(&metadata[0], field); close_error = EINTR;
            failure(EPERM, 1, 0);
        }
        for (ssize_t size = 0; size <= 2; size += 2) {
            reset(writing); transfer_size = size; close_error = EINTR;
            failure(EIO, 1, 1);
        }
        for (unsigned retries = 1; retries < 8; ++retries) {
            reset(writing); interruptions = retries;
            assert(call() == 0 && transfers == retries + 1 && stats == 2 && closes == 1);
            ++cases;
        }
        reset(writing); interruptions = 9; close_error = EIO;
        failure(EINTR, 1, 8);
        reset(writing); transfer_error = EAGAIN; close_error = EIO;
        failure(EAGAIN, 1, 1);
        reset(writing); stat_error[1] = ENXIO; close_error = EINTR;
        failure(ENXIO, 2, 1);
        for (unsigned field = 0; field < 15; ++field) {
            reset(writing); alter(&metadata[1], field); close_error = EINTR;
            failure(EIO, 2, 1);
        }
        reset(writing); metadata[1].st_atim.tv_sec = 8; metadata[1].st_mtim.tv_nsec = 123;
        metadata[1].st_ctim.tv_sec = 9;
        assert(call() == 0 && stats == 2 && closes == 1);
        ++cases;
        for (unsigned i = 0; i < 2; ++i) {
            reset(writing); close_error = i ? EINTR : EIO;
            failure(close_error, 2, 1);
        }
    }
    reset(0); input = 'X'; close_error = EINTR;
    failure(EIO, 1, 1);
    assert(generation_progress('0', '1') == 0); ++cases;
    assert(generation_progress('1', '1') == 1); ++cases;
    assert(generation_progress('1', '2') == 0); ++cases;
    assert(generation_progress('2', '2') == 1); ++cases;
    assert(generation_progress('2', '1') == -1 && errno == EPROTO); ++cases;
    assert(generation_progress('0', '2') == -1 && errno == EPROTO); ++cases;
    assert(generation_progress('X', '2') == -1 && errno == EPROTO); ++cases;
    assert(generation_progress('0', '0') == -1 && errno == EINVAL); ++cases;
    printf("SERVICE GENERATION HOSTED MODELS PASS cases=%u\n", cases);
    return 0;
}
