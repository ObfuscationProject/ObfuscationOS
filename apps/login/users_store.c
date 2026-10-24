#include "users_store.h"

#include <errno.h>
#include <fcntl.h>
#include <ok/storage.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int same_user(const struct ok_user *left, const struct ok_user *right)
{
    return !memcmp(left, right, sizeof(*left));
}

static int same_principal(const struct ok_user *left, const struct ok_user *right)
{
    return left->uid == right->uid && left->gid == right->gid &&
        !memcmp(left->name, right->name, sizeof(left->name));
}

static int same_users(const struct ok_users *left, const struct ok_users *right)
{
    return !memcmp(left, right, sizeof(*left));
}

/* Both registries are canonical before comparison. Exactly one record changes;
 * identical staging, deletion and unrelated credential edits are not recovery. */
static enum ok_users_change successor(const struct ok_users *current, const struct ok_users *next,
                                      uint32_t *index)
{
    uint32_t changed = 0;
    if (next->count == current->count + 1U && next->count <= OK_USERS_MAX) {
        uint32_t old = 0;
        for (uint32_t i = 0; i < next->count; ++i) {
            if (old < current->count && same_user(&current->entries[old], &next->entries[i])) ++old;
            else { *index = i; ++changed; }
        }
        if (old == current->count && changed == 1U) return OK_USERS_ADD;
    } else if (next->count == current->count) {
        for (uint32_t i = 0; i < next->count; ++i) {
            if (!same_principal(&current->entries[i], &next->entries[i])) return OK_USERS_NO_CHANGE;
            if (!same_user(&current->entries[i], &next->entries[i])) { *index = i; ++changed; }
        }
        if (changed == 1U) return OK_USERS_ROTATE;
    }
    return OK_USERS_NO_CHANGE;
}

static int protected_directory(int descriptor)
{
    struct stat info;
    if (fstat(descriptor, &info) < 0) return -1;
    if (!S_ISDIR(info.st_mode) || info.st_uid || info.st_gid || (info.st_mode & 07022)) {
        errno = EACCES; return -1;
    }
    return ok_sync_persistent(descriptor);
}

static int protected_file(const struct stat *info)
{
    if (!S_ISREG(info->st_mode) || (info->st_mode & 07777) != 0600 ||
        info->st_uid || info->st_gid || info->st_nlink != 1) { errno = EACCES; return -1; }
    return 0;
}

static int same_node(const struct stat *left, const struct stat *right)
{
    return left->st_ino == right->st_ino && left->st_mode == right->st_mode &&
        left->st_uid == right->st_uid && left->st_gid == right->st_gid &&
        left->st_nlink == right->st_nlink && left->st_size == right->st_size;
}

/* Every parent is an admitted root-owned dirfd. NONBLOCK rejects an unexpected
 * FIFO without waiting. Explicit store scratch avoids a second 4K stack frame. */
static int load_named(struct ok_users_store *store, const char *name, struct ok_users *users, int optional)
{
    struct stat opened, after, named;
    size_t used = 0;
    int result = -1;
    int descriptor = openat(store->directory, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (descriptor < 0) return optional && errno == ENOENT ? 1 : -1;
    if (fstat(descriptor, &opened) < 0 || protected_file(&opened) < 0) goto done;
    if (opened.st_size <= 0 || opened.st_size > OK_USERS_FILE_MAX) { errno = EIO; goto done; }
    if (ok_sync_persistent(descriptor) < 0) goto done;
    while (used < sizeof(store->bytes)) {
        ssize_t count = read(descriptor, store->bytes + used, sizeof(store->bytes) - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) goto done;
        if (!count) break;
        used += (size_t)count;
    }
    if (used != (size_t)opened.st_size || ok_users_parse(store->bytes, used, users) ||
        ok_users_validate(users, store->administrator)) { errno = EIO; goto done; }
    if (fstat(descriptor, &after) < 0 ||
        fstatat(store->directory, name, &named, AT_SYMLINK_NOFOLLOW) < 0) goto done;
    if (!same_node(&opened, &after) || !same_node(&opened, &named)) { errno = EIO; goto done; }
    result = 0;
done:
    {
        int saved = errno;
        if (close(descriptor) < 0) result = -1;
        else errno = saved;
    }
    ok_password_clear(store->bytes, sizeof(store->bytes));
    if (result) ok_password_clear(users, sizeof(*users));
    return result;
}

int ok_users_store_close(struct ok_users_store *store)
{
    int descriptor, result = 0;
    if (!store) { errno = EINVAL; return -1; }
    descriptor = store->directory;
    ok_password_clear(store, sizeof(*store));
    store->directory = -1;
    if (descriptor >= 0) result = close(descriptor);
    return result;
}

int ok_users_store_open(struct ok_users_store *store, const char *administrator)
{
    int root = -1, observed, staged, saved;
    size_t size = 0;
    if (!store || !administrator) { errno = EINVAL; return -1; }
    while (size <= OK_ACCOUNT_NAME_MAX && administrator[size]) ++size;
    if (!ok_account_name_valid(administrator, size)) { errno = EINVAL; return -1; }
    /* As with the legacy account store, only fresh or already closed objects
     * may be opened. The caller supplies a separate trusted administrator. */
    memset(store, 0, sizeof(*store)); store->directory = -1;
    memcpy(store->administrator, administrator, size);
    root = open("/", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (root < 0 || protected_directory(root) < 0) goto fail;
    store->directory = openat(root, "etc", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (store->directory < 0 || protected_directory(store->directory) < 0) goto fail;
    if (close(root) < 0) { root = -1; goto fail; }
    root = -1;
    observed = load_named(store, OK_USERS_DATABASE, &store->observed, 1);
    if (observed < 0) goto fail;
    store->observed_present = observed == 0;
    staged = load_named(store, OK_USERS_STAGING, &store->users, 1);
    if (staged < 0) goto fail;
    if (staged == 1) store->users = store->observed;
    else {
        store->recovery_kind = successor(&store->observed, &store->users, &store->change_index);
        if (store->recovery_kind == OK_USERS_NO_CHANGE) { errno = EIO; goto fail; }
        store->recovering = 1;
    }
    store->ready = 1;
    return 0;
fail:
    saved = errno;
    if (root >= 0) close(root);
    ok_users_store_close(store);
    errno = saved;
    return -1;
}

static int current_matches(struct ok_users_store *store)
{
    int result = load_named(store, OK_USERS_DATABASE, &store->work, 1);
    if (result < 0) return -1;
    if ((result == 0) != store->observed_present ||
        (!result && !same_users(&store->work, &store->observed))) { errno = EIO; result = -1; }
    else result = 0;
    ok_password_clear(&store->work, sizeof(store->work));
    return result;
}

static int publish(struct ok_users_store *store)
{
    int result = load_named(store, OK_USERS_STAGING, &store->work, 0);
    if (!result && !same_users(&store->work, &store->users)) { errno = EIO; result = -1; }
    ok_password_clear(&store->work, sizeof(store->work));
    if (result < 0 || current_matches(store) < 0) goto uncertain;
    if (renameat(store->directory, OK_USERS_STAGING, store->directory, OK_USERS_DATABASE) < 0 ||
        ok_sync_persistent(store->directory) < 0) goto uncertain;
    result = load_named(store, OK_USERS_DATABASE, &store->work, 0);
    if (!result && !same_users(&store->work, &store->users)) { errno = EIO; result = -1; }
    ok_password_clear(&store->work, sizeof(store->work));
    if (result < 0) goto uncertain;
    store->observed = store->users;
    store->observed_present = 1;
    store->recovering = 0;
    store->recovery_kind = OK_USERS_NO_CHANGE;
    store->change_index = 0;
    return 0;
uncertain:
    store->ready = 0;
    return OK_USERS_STORE_UNCERTAIN;
}

int ok_users_store_recover(struct ok_users_store *store)
{
    if (!store || !store->ready || !store->recovering) { errno = EINVAL; return -1; }
    if (protected_directory(store->directory) < 0 || current_matches(store) < 0) {
        store->ready = 0; return -1;
    }
    return publish(store);
}

static int write_transaction(struct ok_users_store *store, int publish_now)
{
    struct stat info;
    int descriptor = -1, size, result = -1, saved;
    size_t used = 0;
    if (protected_directory(store->directory) < 0 || current_matches(store) < 0) goto done;
    /* current_matches uses and erases byte scratch. Encode only after
     * observing the unchanged predecessor and before creating staging. */
    size = ok_users_encode(&store->users, store->bytes, OK_USERS_FILE_MAX);
    if (size < 0) { errno = EINVAL; goto done; }
    descriptor = openat(store->directory, OK_USERS_STAGING,
        O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0600);
    if (descriptor < 0) goto done;
    result = OK_USERS_STORE_UNCERTAIN;
    if (fstat(descriptor, &info) < 0 || protected_file(&info) < 0) goto done;
    while (used < (size_t)size) {
        ssize_t count = write(descriptor, store->bytes + used, (size_t)size - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) goto done;
        if (!count) { errno = EIO; goto done; }
        used += (size_t)count;
    }
    if (ok_sync_persistent(descriptor) < 0) goto done;
    if (close(descriptor) < 0) { descriptor = -1; goto done; }
    descriptor = -1;
    /* Preserve the complete staging directory entry before publication. A
     * later reopen still requires authentication before recover can rename. */
    if (ok_sync_persistent(store->directory) < 0) goto done;
    store->recovery_kind = successor(&store->observed, &store->users, &store->change_index);
    if (store->recovery_kind == OK_USERS_NO_CHANGE) { errno = EIO; goto done; }
    store->recovering = 1;
    result = publish_now ? publish(store) : 0;
done:
    saved = errno;
    if (descriptor >= 0 && close(descriptor) < 0) saved = errno;
    ok_password_clear(store->bytes, sizeof(store->bytes));
    if (result < 0) store->ready = 0;
    errno = saved;
    return result;
}

static int mutation_ready(struct ok_users_store *store)
{
    if (!store || !store->ready || store->recovering ||
        ok_users_validate(&store->observed, store->administrator) ||
        !same_users(&store->observed, &store->users)) { errno = EINVAL; return 0; }
    return 1;
}

static int add_user(struct ok_users_store *store, const struct ok_user *user, int publish_now)
{
    uint32_t insertion = 0, index = 0;
    if (!mutation_ready(store) || !user) { errno = EINVAL; return -1; }
    if (store->observed.count == OK_USERS_MAX) { errno = ENOSPC; return -1; }
    store->work = store->observed;
    while (insertion < store->work.count && store->work.entries[insertion].uid < user->uid) ++insertion;
    for (uint32_t i = store->work.count; i > insertion; --i) store->work.entries[i] = store->work.entries[i - 1];
    store->work.entries[insertion] = *user;
    ++store->work.count;
    if (ok_users_validate(&store->work, store->administrator) ||
        successor(&store->observed, &store->work, &index) != OK_USERS_ADD) {
        ok_password_clear(&store->work, sizeof(store->work)); errno = EINVAL; return -1;
    }
    store->users = store->work;
    ok_password_clear(&store->work, sizeof(store->work));
    return write_transaction(store, publish_now);
}

int ok_users_store_add(struct ok_users_store *store, const struct ok_user *user)
{
    return add_user(store, user, 1);
}

int ok_users_store_stage_add(struct ok_users_store *store, const struct ok_user *user)
{
    return add_user(store, user, 0);
}

int ok_users_store_rotate(struct ok_users_store *store, const struct ok_user *user)
{
    int index;
    uint32_t changed = 0;
    size_t length = 0;
    if (!mutation_ready(store) || !user) { errno = EINVAL; return -1; }
    while (length < sizeof(user->name) && user->name[length]) ++length;
    index = ok_users_find(&store->observed, user->name, length);
    if (index < 0 || !same_principal(user, &store->observed.entries[index])) { errno = EINVAL; return -1; }
    store->work = store->observed;
    store->work.entries[index] = *user;
    if (ok_users_validate(&store->work, store->administrator) ||
        successor(&store->observed, &store->work, &changed) != OK_USERS_ROTATE) {
        ok_password_clear(&store->work, sizeof(store->work)); errno = EINVAL; return -1;
    }
    store->users = store->work;
    ok_password_clear(&store->work, sizeof(store->work));
    return write_transaction(store, 1);
}
