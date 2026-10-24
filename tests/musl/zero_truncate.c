#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Native first and restart roles use the same convention as Notes/Files.
   Explicit role/path arguments permit a separate host reference run. */
static unsigned checks;
static const char rewritten[] = "Rewritten English document.\n";
static const char final_text[] = "Final English document.\n";
enum { final_offset = 137, independent_offset = 693 };

static void check(int truth, unsigned line)
{
    ++checks;
    if (truth) return;
    dprintf(STDOUT_FILENO, "OK_ZERO_TRUNCATE result=FAIL line=%u errno=%d checks=%u\n",
            line, errno, checks);
    _Exit(1);
}
#define CHECK(value) check(!!(value), __LINE__)

static void exact_write(int fd, const void *bytes, size_t size)
{
    size_t done = 0;
    for (unsigned attempts = 0; done < size && attempts < 64; ++attempts) {
        ssize_t got = write(fd, (const unsigned char *)bytes + done, size - done);
        if (got < 0 && errno == EINTR) continue;
        CHECK(got > 0 && (size_t)got <= size - done);
        done += (size_t)got;
    }
    CHECK(done == size);
}

static struct stat metadata(int fd)
{
    struct stat value;
    CHECK(fstat(fd, &value) == 0);
    CHECK(S_ISREG(value.st_mode) && value.st_nlink == 1 &&
          value.st_uid == 1000 && value.st_gid == 1000 &&
          (value.st_mode & 07777) == 0600 && value.st_size >= 0);
    return value;
}

static void identity(const struct stat *before, const struct stat *after)
{
    CHECK(before->st_dev == after->st_dev && before->st_ino == after->st_ino &&
          before->st_mode == after->st_mode && before->st_nlink == after->st_nlink &&
          before->st_uid == after->st_uid && before->st_gid == after->st_gid);
}

static void exact_content(int fd, size_t offset, const char *payload)
{
    unsigned char bytes[1024];
    size_t size = offset + strlen(payload);
    CHECK(size < sizeof bytes);
    off_t old = lseek(fd, 0, SEEK_CUR); CHECK(old >= 0);
    size_t done = 0;
    for (unsigned attempts = 0; done < size && attempts < 64; ++attempts) {
        ssize_t got = pread(fd, bytes + done, size - done, (off_t)done);
        if (got < 0 && errno == EINTR) continue;
        CHECK(got > 0 && (size_t)got <= size - done);
        done += (size_t)got;
    }
    CHECK(done == size);
    for (size_t i = 0; i < offset; ++i) CHECK(bytes[i] == 0);
    CHECK(!memcmp(bytes + offset, payload, strlen(payload)));
    CHECK(pread(fd, bytes, 1, (off_t)size) == 0 && lseek(fd, 0, SEEK_CUR) == old);
    struct stat value = metadata(fd); CHECK(value.st_size == (off_t)size);
}

static void empty_description(int fd, const struct stat *original, off_t offset)
{
    struct stat value = metadata(fd); identity(original, &value);
    CHECK(value.st_size == 0 && value.st_blocks == 0 && lseek(fd, 0, SEEK_CUR) == offset);
    unsigned char byte = 0xa5;
    CHECK(read(fd, &byte, 1) == 0 && byte == 0xa5 && lseek(fd, 0, SEEK_CUR) == offset);
}

static void first(const char *path)
{
    /* Exclusive creation cannot silently overwrite an earlier fixture. Errors
       leave the file intact for diagnosis; no fixture-side rollback or repair. */
    umask(0077);
    int writer = open(path, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    CHECK(writer >= 0);
    unsigned char initial[700];
    for (size_t i = 0; i < sizeof initial; ++i) initial[i] = (unsigned char)(29 + 17 * i);
    exact_write(writer, initial, sizeof initial); CHECK(fsync(writer) == 0);
    struct stat original = metadata(writer); CHECK(original.st_size == sizeof initial);
    int shared = dup(writer); CHECK(shared >= 0);
    int reader = open(path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC); CHECK(reader >= 0);
    CHECK(lseek(writer, final_offset, SEEK_SET) == final_offset &&
          lseek(shared, 0, SEEK_CUR) == final_offset &&
          lseek(reader, independent_offset, SEEK_SET) == independent_offset);
    errno = 0;
    CHECK(ftruncate(reader, 0) == -1 && (errno == EBADF || errno == EINVAL));
    struct stat unchanged = metadata(writer); identity(&original, &unchanged);
    CHECK(unchanged.st_size == original.st_size);
    errno = 0; CHECK(ftruncate(writer, (off_t)-1) == -1 && errno == EINVAL);
    unchanged = metadata(writer); CHECK(unchanged.st_size == original.st_size);

    CHECK(ftruncate(writer, 0) == 0 && fsync(writer) == 0);
    empty_description(writer, &original, final_offset);
    empty_description(shared, &original, final_offset);
    empty_description(reader, &original, independent_offset);
    /* Positioned reallocation must zero the gap and preserve shared offsets. */
    CHECK(pwrite(writer, rewritten, sizeof rewritten - 1, 31) == sizeof rewritten - 1);
    CHECK(fsync(writer) == 0 && lseek(writer, 0, SEEK_CUR) == final_offset &&
          lseek(shared, 0, SEEK_CUR) == final_offset);
    exact_content(reader, 31, rewritten);
    struct stat allocated = metadata(writer); identity(&original, &allocated);
    CHECK(allocated.st_blocks > 0);

    int truncating = open(path, O_RDWR | O_TRUNC | O_NOFOLLOW | O_CLOEXEC);
    CHECK(truncating >= 0 && fsync(truncating) == 0);
    empty_description(truncating, &original, 0);
    empty_description(writer, &original, final_offset);
    empty_description(shared, &original, final_offset);
    empty_description(reader, &original, independent_offset);
    /* The admitted empty-to-empty operation retains the live inode. */
    CHECK(ftruncate(truncating, 0) == 0 && fsync(truncating) == 0);
    empty_description(truncating, &original, 0);
    exact_write(truncating, rewritten, sizeof rewritten - 1);
    CHECK(fsync(truncating) == 0); exact_content(reader, 0, rewritten);

    CHECK(truncate(path, 0) == 0 && fsync(writer) == 0);
    empty_description(writer, &original, final_offset);
    empty_description(shared, &original, final_offset);
    empty_description(reader, &original, independent_offset);
    /* A normal write through dup resumes at the retained shared position. */
    exact_write(shared, final_text, sizeof final_text - 1); CHECK(fsync(shared) == 0);
    CHECK(lseek(writer, 0, SEEK_CUR) == final_offset + sizeof final_text - 1 &&
          lseek(shared, 0, SEEK_CUR) == final_offset + sizeof final_text - 1 &&
          lseek(reader, 0, SEEK_CUR) == independent_offset);
    exact_content(reader, final_offset, final_text);
    struct stat saved = metadata(writer); identity(&original, &saved);
    CHECK(close(truncating) == 0 && close(shared) == 0 && close(writer) == 0 && close(reader) == 0);
    int reopened = open(path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC); CHECK(reopened >= 0);
    struct stat value = metadata(reopened); identity(&original, &value);
    exact_content(reopened, final_offset, final_text); CHECK(close(reopened) == 0);
}

int main(int argc, char **argv)
{
    CHECK(argv && argv[0]);
    int initial;
    const char *path;
    if (argc == 1) {
        CHECK(!strcmp(argv[0], "/init") || !strcmp(argv[0], "/./init"));
        initial = !strcmp(argv[0], "/init");
        path = "/home/zero-truncate.txt";
    } else {
        CHECK(argc == 3 && argv[1] && argv[2] &&
              (!strcmp(argv[1], "first") || !strcmp(argv[1], "restart")));
        initial = !strcmp(argv[1], "first"); path = argv[2];
        CHECK(path[0] == '/' && strlen(path) < 256);
    }
    if (geteuid() != 1000 || getegid() != 1000)
        CHECK(setgid(1000) == 0 && setuid(1000) == 0);
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    if (initial) first(path);
    else {
        int fd = open(path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC); CHECK(fd >= 0);
        exact_content(fd, final_offset, final_text); CHECK(close(fd) == 0);
    }
    int printed = dprintf(STDOUT_FILENO, "OK_ZERO_TRUNCATE result=pass stage=%s identity=%s eof=pass offsets=%s rewrite=pass gap=pass reopen=pass checks=%u\n",
            initial ? "first" : "restart", initial ? "pass" : "not-exercised",
            initial ? "pass" : "not-exercised", checks);
    CHECK(printed > 0);
    return 0;
}
