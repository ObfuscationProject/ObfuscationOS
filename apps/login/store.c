#include "store.h"

#include <errno.h>
#include <fcntl.h>
#include <ok/storage.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int same_principal(const struct ok_account *left, const struct ok_account *right)
{
    return !memcmp(left->name, right->name, sizeof(left->name));
}

static int same_identity(const struct ok_account *left, const struct ok_account *right)
{
    return same_principal(left, right) &&
           !memcmp(left->salt, right->salt, sizeof(left->salt)) &&
           !memcmp(left->verifier, right->verifier, sizeof(left->verifier));
}

static int same_account(const struct ok_account *left, const struct ok_account *right)
{
    return left->state == right->state && same_identity(left, right);
}

static int successor(const struct ok_account *current, const struct ok_account *next)
{
    return (current->state == OK_ACCOUNT_UNCONFIGURED && next->state == OK_ACCOUNT_PENDING) ||
           (current->state == OK_ACCOUNT_PENDING && next->state == OK_ACCOUNT_ACTIVE &&
            same_identity(current, next));
}

static int rotation_successor(const struct ok_account *current, const struct ok_account *next)
{
    return current->state == OK_ACCOUNT_ACTIVE && next->state == OK_ACCOUNT_ACTIVE &&
           same_principal(current, next);
}

static int protected_directory(int descriptor, int home)
{
    struct stat info;
    if (fstat(descriptor, &info) < 0) return -1;
    if (!S_ISDIR(info.st_mode) || info.st_uid || info.st_gid ||
        (info.st_mode & 07022) || (home && (info.st_mode & 07777) != 0700)) {
        errno = EACCES;
        return -1;
    }
    return ok_sync_persistent(descriptor);
}

static int protected_file(const struct stat *info)
{
    if (!S_ISREG(info->st_mode) || (info->st_mode & 07777) != 0600 ||
        info->st_uid || info->st_gid || info->st_nlink != 1) {
        errno = EACCES;
        return -1;
    }
    return 0;
}

static int same_node(const struct stat *left, const struct stat *right)
{
    return left->st_ino == right->st_ino && left->st_mode == right->st_mode &&
           left->st_uid == right->st_uid && left->st_gid == right->st_gid &&
           left->st_nlink == right->st_nlink && left->st_size == right->st_size;
}

/* Every component before name is an already checked root-owned dirfd. Opening
 * with NONBLOCK prevents an unexpected FIFO from blocking before fstat. */
static int load_named(int directory, const char *name, struct ok_account *account, int optional)
{
    unsigned char bytes[OK_ACCOUNT_FILE_MAX + 1];
    struct ok_account candidate;
    struct stat opened, after, named;
    size_t used = 0;
    int result = -1;
    int descriptor = openat(directory, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (descriptor < 0) return optional && errno == ENOENT ? 1 : -1;
    if (fstat(descriptor, &opened) < 0 || protected_file(&opened) < 0) goto done;
    if (opened.st_size <= 0 || opened.st_size > OK_ACCOUNT_FILE_MAX) { errno = EIO; goto done; }
    if (ok_sync_persistent(descriptor) < 0) goto done;
    while (used < sizeof(bytes)) {
        ssize_t count = read(descriptor, bytes + used, sizeof(bytes) - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) goto done;
        if (!count) break;
        used += (size_t)count;
    }
    if (used != (size_t)opened.st_size || ok_account_parse(bytes, used, &candidate)) {
        errno = EIO;
        goto done;
    }
    if (fstat(descriptor, &after) < 0 ||
        fstatat(directory, name, &named, AT_SYMLINK_NOFOLLOW) < 0) goto done;
    if (!same_node(&opened, &after) || !same_node(&opened, &named)) { errno = EIO; goto done; }
    result = 0;
done:
    {
        int saved = errno;
        if (close(descriptor) < 0) result = -1;
        else errno = saved;
    }
    if (!result) *account = candidate;
    ok_password_clear(&candidate, sizeof(candidate));
    ok_password_clear(bytes, sizeof(bytes));
    return result;
}

int ok_account_store_close(struct ok_account_store *store)
{
    int descriptor, result = 0;
    if (!store) { errno = EINVAL; return -1; }
    descriptor = store->directory;
    ok_password_clear(store, sizeof(*store));
    store->directory = -1;
    if (descriptor >= 0) result = close(descriptor);
    return result;
}

int ok_account_store_open(struct ok_account_store *store)
{
    struct ok_account_store candidate = {.directory = -1};
    int root = -1, home = -1, staged, saved;
    if (!store) { errno = EINVAL; return -1; }
    *store = (struct ok_account_store){.directory = -1};
    root = open("/", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (root < 0 || protected_directory(root, 0) < 0) goto fail;
    candidate.directory = openat(root, "etc", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (candidate.directory < 0 || protected_directory(candidate.directory, 0) < 0) goto fail;
    home = openat(root, "root", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (home < 0 || protected_directory(home, 1) < 0) goto fail;
    if (close(home) < 0) { home = -1; goto fail; }
    home = -1;
    if (close(root) < 0) { root = -1; goto fail; }
    root = -1;
    if (load_named(candidate.directory, OK_ACCOUNT_DATABASE, &candidate.observed, 0) < 0) goto fail;
    staged = load_named(candidate.directory, OK_ACCOUNT_STAGING, &candidate.account, 1);
    if (staged < 0) goto fail;
    if (staged == 1) candidate.account = candidate.observed;
    else {
        if (!successor(&candidate.observed, &candidate.account) &&
            !rotation_successor(&candidate.observed, &candidate.account) &&
            !(candidate.account.state != OK_ACCOUNT_UNCONFIGURED &&
              same_account(&candidate.observed, &candidate.account))) { errno = EIO; goto fail; }
        candidate.recovering = 1;
    }
    candidate.ready = 1;
    *store = candidate;
    ok_password_clear(&candidate, sizeof(candidate));
    return 0;
fail:
    saved = errno;
    if (home >= 0) close(home);
    if (root >= 0) close(root);
    ok_account_store_close(&candidate);
    errno = saved;
    return -1;
}

static int current_matches(struct ok_account_store *store)
{
    struct ok_account current;
    int result = load_named(store->directory, OK_ACCOUNT_DATABASE, &current, 0);
    if (!result && !same_account(&current, &store->observed)) { errno = EIO; result = -1; }
    ok_password_clear(&current, sizeof(current));
    return result;
}

static int publish(struct ok_account_store *store, const struct ok_account *next)
{
    struct ok_account staged;
    int status = load_named(store->directory, OK_ACCOUNT_STAGING, &staged, 0);
    if (!status && !same_account(&staged, next)) { errno = EIO; status = -1; }
    ok_password_clear(&staged, sizeof(staged));
    if (status < 0 || current_matches(store) < 0) goto uncertain;
    if (renameat(store->directory, OK_ACCOUNT_STAGING, store->directory, OK_ACCOUNT_DATABASE) < 0 ||
        ok_sync_persistent(store->directory) < 0) goto uncertain;
    status = load_named(store->directory, OK_ACCOUNT_DATABASE, &staged, 0);
    if (!status && !same_account(&staged, next)) { errno = EIO; status = -1; }
    ok_password_clear(&staged, sizeof(staged));
    if (status < 0) goto uncertain;
    store->observed = store->account = *next;
    store->recovering = 0;
    return 0;
uncertain:
    store->ready = 0;
    return OK_ACCOUNT_STORE_UNCERTAIN;
}

int ok_account_store_recover(struct ok_account_store *store)
{
    if (!store || !store->ready || !store->recovering) { errno = EINVAL; return -1; }
    if (protected_directory(store->directory, 0) < 0 || current_matches(store) < 0) {
        store->ready = 0;
        return -1;
    }
    return publish(store, &store->account);
}

static int write_transaction(struct ok_account_store *store, const struct ok_account *next)
{
    unsigned char bytes[OK_ACCOUNT_FILE_MAX];
    struct stat info;
    int descriptor = -1, size, result = -1, saved;
    size_t used = 0;
    size = ok_account_encode(next, bytes, sizeof(bytes));
    if (size < 0) { errno = EINVAL; goto done; }
    if (protected_directory(store->directory, 0) < 0 || current_matches(store) < 0) goto done;
    descriptor = openat(store->directory, OK_ACCOUNT_STAGING,
        O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0600);
    if (descriptor < 0) goto done;
    result = OK_ACCOUNT_STORE_UNCERTAIN;
    if (fstat(descriptor, &info) < 0 || protected_file(&info) < 0) goto done;
    while (used < (size_t)size) {
        ssize_t count = write(descriptor, bytes + used, (size_t)size - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) goto done;
        if (!count) { errno = EIO; goto done; }
        used += (size_t)count;
    }
    if (ok_sync_persistent(descriptor) < 0) goto done;
    if (close(descriptor) < 0) { descriptor = -1; goto done; }
    descriptor = -1;
    result = publish(store, next);
done:
    saved = errno;
    if (descriptor >= 0 && close(descriptor) < 0) saved = errno;
    if (result < 0) store->ready = 0;
    ok_password_clear(bytes, sizeof(bytes));
    errno = saved;
    return result;
}

int ok_account_store_commit(struct ok_account_store *store, const struct ok_account *next)
{
    if (!store || !store->ready || store->recovering || !next ||
        !successor(&store->observed, next)) { errno = EINVAL; return -1; }
    return write_transaction(store, next);
}

int ok_account_store_rotate(struct ok_account_store *store, const struct ok_account *next)
{
    if (!store || !store->ready || store->recovering || !next ||
        !same_account(&store->observed, &store->account) ||
        !rotation_successor(&store->observed, next)) { errno = EINVAL; return -1; }
    return write_transaction(store, next);
}
