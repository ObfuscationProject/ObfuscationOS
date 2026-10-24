/* Qualification-only link wrapper: stop after real durable staging, before
 * publication. The canonical login and store sources remain byte-identical. */
#include "accounts.h"
#include "store.h"
#include <errno.h>
#include <fcntl.h>
#include <ok/storage.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

int __real_renameat(int, const char *, int, const char *);
static const char cut_name[] = ".login-cut";
static const char cut_bytes[] = "NATIVE_LOGIN_CUT 1\n";

static int cut_failure(void)
{
    fputs("NATIVE_LOGIN_FIXTURE_FAIL component=cut\n", stderr);
    errno = EIO;
    return -1;
}

static int cut_existing(int directory)
{
    char bytes[sizeof(cut_bytes)] = {0};
    struct stat info;
    int result = -1;
    int descriptor = openat(directory, cut_name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (descriptor < 0) return errno == ENOENT ? 0 : -1;
    if (fstat(descriptor, &info) < 0 || !S_ISREG(info.st_mode) ||
        (info.st_mode & 07777) != 0600 || info.st_uid || info.st_gid || info.st_nlink != 1 ||
        info.st_size != (off_t)(sizeof(cut_bytes) - 1)) goto done;
    size_t used = 0;
    while (used < sizeof(bytes)) {
        ssize_t count = read(descriptor, bytes + used, sizeof(bytes) - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) goto done;
        if (!count) break;
        used += (size_t)count;
    }
    if (used == sizeof(cut_bytes) - 1 && !memcmp(bytes, cut_bytes, used)) result = 1;
done:
    if (close(descriptor) < 0) result = -1;
    return result;
}

static int cut_stage(int directory, struct ok_account *account)
{
    unsigned char bytes[OK_ACCOUNT_FILE_MAX + 1];
    struct stat info;
    size_t used = 0;
    int result = -1;
    int descriptor = openat(directory, OK_ACCOUNT_STAGING, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (descriptor < 0) return -1;
    if (fstat(descriptor, &info) < 0 || !S_ISREG(info.st_mode) ||
        (info.st_mode & 07777) != 0600 || info.st_uid || info.st_gid || info.st_nlink != 1 ||
        info.st_size <= 0 || info.st_size > OK_ACCOUNT_FILE_MAX || ok_sync_persistent(descriptor) < 0) goto done;
    while (used < sizeof(bytes)) {
        ssize_t count = read(descriptor, bytes + used, sizeof(bytes) - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) goto done;
        if (!count) break;
        used += (size_t)count;
    }
    if (used == (size_t)info.st_size && !ok_account_parse(bytes, used, account)) result = 0;
done:
    if (close(descriptor) < 0) result = -1;
    ok_password_clear(bytes, sizeof(bytes));
    return result;
}

static int cut_mark(int directory)
{
    struct stat info;
    size_t used = 0;
    int result = -1;
    int descriptor = openat(directory, cut_name,
        O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0600);
    if (descriptor < 0) return -1;
    if (fstat(descriptor, &info) < 0 || !S_ISREG(info.st_mode) ||
        (info.st_mode & 07777) != 0600 || info.st_uid || info.st_gid || info.st_nlink != 1) goto done;
    while (used < sizeof(cut_bytes) - 1) {
        ssize_t count = write(descriptor, cut_bytes + used, sizeof(cut_bytes) - 1 - used);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) goto done;
        used += (size_t)count;
    }
    result = ok_sync_persistent(descriptor);
done:
    if (close(descriptor) < 0) result = -1;
    if (!result) result = ok_sync_persistent(directory);
    return result;
}

int __wrap_renameat(int old_directory, const char *old_name, int new_directory, const char *new_name)
{
    struct ok_account staged;
    if (old_directory != new_directory || strcmp(old_name, OK_ACCOUNT_STAGING) ||
        strcmp(new_name, OK_ACCOUNT_DATABASE)) return cut_failure();
    int existing = cut_existing(old_directory);
    if (existing < 0 || cut_stage(old_directory, &staged) < 0) return cut_failure();
    if (!existing) {
        if (staged.state != OK_ACCOUNT_PENDING || cut_mark(old_directory) < 0) {
            ok_password_clear(&staged, sizeof(staged));
            return cut_failure();
        }
        ok_password_clear(&staged, sizeof(staged));
        puts("NATIVE_LOGIN_CUT state=pending publication=not-attempted staging=persistent");
        for (;;) {
            struct timespec delay = {.tv_sec = 1};
            if (nanosleep(&delay, 0) < 0 && errno != EINTR) return cut_failure();
        }
    }
    if (staged.state != OK_ACCOUNT_PENDING && staged.state != OK_ACCOUNT_ACTIVE) {
        ok_password_clear(&staged, sizeof(staged));
        return cut_failure();
    }
    int result = __real_renameat(old_directory, old_name, new_directory, new_name);
    if (!result) printf("NATIVE_LOGIN_PUBLICATION state=%s\n",
        staged.state == OK_ACCOUNT_PENDING ? "pending" : "active");
    ok_password_clear(&staged, sizeof(staged));
    return result;
}
