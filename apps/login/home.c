#include "home.h"
#include "../init/native_manifest_load.h"

#include <errno.h>
#include <fcntl.h>
#include <ok/storage.h>
#include <ok/syscall.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

struct home_parent { int root, homes; };

int ok_login_user_next_uid(const struct ok_users *users, uint32_t *uid)
{
    static struct service_manifest manifest;
    if (!users || !uid || users->count >= OK_USERS_MAX) { errno = ENOSPC; return -1; }
    memset(&manifest, 0, sizeof(manifest));
    if (ns_manifest_load(&manifest) < 0) return -1;
    uint32_t candidate = OK_USER_FIRST_UID;
    for (;;) {
        int used = 0;
        for (uint32_t i = 0; i < users->count; ++i)
            if (users->entries[i].uid == candidate || users->entries[i].gid == candidate) used = 1;
        for (unsigned i = 0; i < manifest.count; ++i)
            if (manifest.records[i].uid == candidate || manifest.records[i].gid == candidate) used = 1;
        if (!used) { *uid = candidate; return 0; }
        if (candidate == UINT32_MAX - 1) { errno = ENOSPC; return -1; }
        ++candidate;
    }
}

static int principal(const char *name, uint32_t uid, uint32_t gid)
{
    size_t size = 0;
    if (name) while (size <= OK_ACCOUNT_NAME_MAX && name[size]) ++size;
    if (!name || !ok_account_name_valid(name, size) ||
        uid < OK_USER_FIRST_UID || uid == UINT32_MAX || gid != uid) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int close_parent(struct home_parent *parent, int result)
{
    int saved = errno;
    if (parent->homes >= 0 && close(parent->homes) < 0) { result = -1; saved = errno; }
    if (parent->root >= 0 && close(parent->root) < 0) { result = -1; saved = errno; }
    parent->homes = parent->root = -1;
    errno = saved;
    return result;
}

static int open_parent(struct home_parent *parent)
{
    struct stat info;
    *parent = (struct home_parent){-1, -1};
    parent->root = open("/", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent->root < 0 || fstat(parent->root, &info) < 0) goto fail;
    if (!S_ISDIR(info.st_mode) || info.st_uid || info.st_gid || (info.st_mode & 07022)) {
        errno = EACCES;
        goto fail;
    }
    parent->homes = openat(parent->root, "home", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent->homes < 0 || fstat(parent->homes, &info) < 0) goto fail;
    if (!S_ISDIR(info.st_mode) || info.st_uid || info.st_gid ||
        ((info.st_mode & 07777) != 0700 && (info.st_mode & 07777) != 0755)) {
        errno = EACCES;
        goto fail;
    }
    return 0;
fail:
    return close_parent(parent, -1);
}

static int same_directory(const struct stat *left, const struct stat *right)
{
    return left->st_ino == right->st_ino && left->st_mode == right->st_mode &&
        left->st_uid == right->st_uid && left->st_gid == right->st_gid &&
        left->st_nlink == right->st_nlink;
}

int ok_login_home_available(const struct ok_user *user)
{
    struct home_parent parent;
    struct stat info;
    if (!user) { errno = EINVAL; return -1; }
    if (principal(user->name, user->uid, user->gid) < 0 || open_parent(&parent) < 0) return -1;
    int result = fstatat(parent.homes, user->name, &info, AT_SYMLINK_NOFOLLOW);
    if (result >= 0) { errno = EEXIST; result = -1; }
    else if (errno == ENOENT) result = 0;
    return close_parent(&parent, result);
}

int ok_login_home_prepare(const struct ok_user *user)
{
    struct home_parent parent;
    struct stat before, after, named;
    int home = -1, result = -1, saved;
    if (!user) { errno = EINVAL; return -1; }
    if (principal(user->name, user->uid, user->gid) < 0 || open_parent(&parent) < 0) return -1;
    /* /home remains root-owned. Its children alone carry ordinary ownership. */
    if (fstat(parent.homes, &before) < 0) goto done;
    if ((before.st_mode & 07777) == 0700 && fchmod(parent.homes, 0755) < 0) goto done;
    if (fstat(parent.homes, &after) < 0) goto done;
    if (!S_ISDIR(after.st_mode) || after.st_uid || after.st_gid ||
        (after.st_mode & 07777) != 0755 || after.st_ino != before.st_ino) { errno = EACCES; goto done; }
    if (ok_syscall_ret(ok_syscall3(OK_SYS_MKDIRAT, parent.homes, (long)user->name, 0700)) < 0 &&
        errno != EEXIST) goto done;
    home = openat(parent.homes, user->name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (home < 0 || fstat(home, &before) < 0) goto done;
    if (!S_ISDIR(before.st_mode) || (before.st_mode & 07777) != 0700 ||
        !((before.st_uid == 0 && before.st_gid == 0) ||
          (before.st_uid == user->uid && before.st_gid == user->gid))) { errno = EACCES; goto done; }
    if (!before.st_uid && fchown(home, user->uid, user->gid) < 0) goto done;
    if (fstat(home, &after) < 0 || fstatat(parent.homes, user->name, &named, AT_SYMLINK_NOFOLLOW) < 0) goto done;
    if (!S_ISDIR(after.st_mode) || (after.st_mode & 07777) != 0700 ||
        after.st_uid != user->uid || after.st_gid != user->gid || after.st_ino != before.st_ino ||
        !same_directory(&after, &named)) { errno = EACCES; goto done; }
    if (ok_sync_persistent(home) < 0 || ok_sync_persistent(parent.homes) < 0) goto done;
    if (fstat(home, &named) < 0 || !same_directory(&after, &named)) { errno = EIO; goto done; }
    result = 0;
done:
    saved = errno;
    if (home >= 0 && close(home) < 0) { result = -1; saved = errno; }
    errno = saved;
    return close_parent(&parent, result);
}

int ok_login_home_enter(const char *name, uint32_t uid, uint32_t gid)
{
    struct home_parent parent;
    struct stat info, named;
    uid_t real_uid, effective_uid, saved_uid;
    gid_t real_gid, effective_gid, saved_gid;
    int home = -1, result = -1, saved;
    if (principal(name, uid, gid) < 0 || open_parent(&parent) < 0) return -1;
    home = openat(parent.homes, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (home < 0 || fstat(home, &info) < 0 ||
        fstatat(parent.homes, name, &named, AT_SYMLINK_NOFOLLOW) < 0) goto done;
    if (!S_ISDIR(info.st_mode) || (info.st_mode & 07777) != 0700 ||
        info.st_uid != uid || info.st_gid != gid || !same_directory(&info, &named)) { errno = EACCES; goto done; }
    if (close_parent(&parent, 0) < 0) goto done;
    if (setresgid(gid, gid, gid) < 0 || setresuid(uid, uid, uid) < 0 ||
        getresgid(&real_gid, &effective_gid, &saved_gid) < 0 ||
        getresuid(&real_uid, &effective_uid, &saved_uid) < 0) goto done;
    if (real_gid != gid || effective_gid != gid || saved_gid != gid ||
        real_uid != uid || effective_uid != uid || saved_uid != uid) { errno = EPERM; goto done; }
    if (ok_syscall_ret(ok_syscall1(OK_SYS_FCHDIR, home)) < 0 ||
        ok_syscall_ret(ok_syscall1(OK_SYS_UMASK, 0077)) < 0) goto done;
    result = 0;
done:
    saved = errno;
    if (home >= 0 && close(home) < 0) { result = -1; saved = errno; }
    errno = saved;
    return close_parent(&parent, result);
}
