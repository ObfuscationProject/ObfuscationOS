#include <errno.h>
#include <fcntl.h>
#include <ok/dirent.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Separate native disk acceptance; these are not POSIX ownership assertions. */
#define CHECK(c) do { if (!(c)) { printf("FAT_CHECK failed: " #c " errno=%d\n", errno); return 1; } } while (0)
static const char directory[] = "/media/Guest Folder";
static const char filename[] = "/media/Guest Folder/Long File Name.txt";

static unsigned char pattern(size_t offset)
{
    return (unsigned char)((offset * 37u + 11u) % 251u);
}

static int sync_directory(const char *path)
{
    int fd = open(path, O_RDONLY | O_DIRECTORY);
    if (fd < 0) return -1;
    int result = fsync(fd);
    if (close(fd)) return -1;
    return result;
}

int check_fat_media(const char *phase)
{
    unsigned char buffer[1024];
    struct stat st;
    if (!strcmp(phase, "--fat-write")) {
        CHECK(mkdir(directory, 0755) == 0);
        int fd = open(filename, O_CREAT | O_EXCL | O_RDWR, 0644);
        CHECK(fd >= 0);
        for (size_t position = 0; position < 12288; position += sizeof(buffer)) {
            for (size_t i = 0; i < sizeof(buffer); ++i) buffer[i] = pattern(position + i);
            CHECK(write(fd, buffer, sizeof(buffer)) == (ssize_t)sizeof(buffer));
        }
        CHECK(pwrite(fd, "PATCH", 5, 509) == 5);
        CHECK(ftruncate(fd, 8197) == 0);
        CHECK(ftruncate(fd, 10001) == 0);
        CHECK(pwrite(fd, "END", 3, 9998) == 3);
        CHECK(fsync(fd) == 0 && close(fd) == 0);
        fd = open("/media/delete-me", O_CREAT | O_EXCL | O_WRONLY, 0644);
        CHECK(fd >= 0 && write(fd, "temporary", 9) == 9 && close(fd) == 0);
        CHECK(unlink("/media/delete-me") == 0);
        CHECK(stat("/media/delete-me", &st) == -1 && errno == ENOENT);
        CHECK(mkdir("/media/empty-dir", 0755) == 0 && rmdir("/media/empty-dir") == 0);
        CHECK(sync_directory(directory) == 0 && sync_directory("/media") == 0);
    } else if (!strcmp(phase, "--fat-delete")) {
        CHECK(unlink(filename) == 0);
        CHECK(rmdir(directory) == 0);
        CHECK(stat(filename, &st) == -1 && errno == ENOENT);
        CHECK(sync_directory("/media") == 0);
        puts("OK_FAT_NATIVE scope=hardware phase=delete remove=pass flush=pass");
        return 0;
    }
    int fd = open("/media/guest folder/long file name.TXT", O_RDONLY);
    CHECK(fd >= 0 && fstat(fd, &st) == 0 && st.st_size == 10001);
    size_t position = 0;
    for (;;) {
        ssize_t count = read(fd, buffer, sizeof(buffer));
        CHECK(count >= 0);
        if (!count) break;
        for (ssize_t i = 0; i < count; ++i) {
            size_t offset = position + (size_t)i;
            unsigned char expected = offset < 8197 ? pattern(offset) : 0;
            if (offset >= 509 && offset < 514) expected = (unsigned char)"PATCH"[offset - 509];
            if (offset >= 9998 && offset < 10001) expected = (unsigned char)"END"[offset - 9998];
            CHECK(buffer[i] == expected);
        }
        position += (size_t)count;
    }
    CHECK(position == 10001 && close(fd) == 0);
    fd = open(directory, O_RDONLY | O_DIRECTORY);
    CHECK(fd >= 0);
    _Alignas(8) unsigned char entries[512];
    int found = 0;
    for (;;) {
        ssize_t bytes = getdents64(fd, entries, sizeof(entries));
        CHECK(bytes >= 0);
        if (!bytes) break;
        for (size_t i = 0; i < (size_t)bytes;) {
            struct dirent *entry = (struct dirent *)(entries + i);
            CHECK(entry->d_reclen >= 24 && entry->d_reclen <= (size_t)bytes - i);
            if (!strcmp(entry->d_name, "Long File Name.txt")) found = 1;
            i += entry->d_reclen;
        }
    }
    CHECK(found && close(fd) == 0);
    puts(!strcmp(phase, "--fat-write") ?
         "OK_FAT_NATIVE scope=hardware phase=write create=pass read=pass write=pass truncate=pass zero=pass list=pass remove=pass flush=pass" :
         "OK_FAT_NATIVE scope=hardware phase=read restart=pass content=pass casefold=pass list=pass");
    return 0;
}
