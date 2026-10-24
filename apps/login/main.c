#include "accounts.h"
#include "input.h"
#include "store.h"
#include "home.h"
#include "users_store.h"

#include <errno.h>
#include <fcntl.h>
#include <ok/console.h>
#include <ok/syscall.h>
#include <string.h>
#include <sys/random.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static int login_identity_as(uint32_t uid, uint32_t gid)
{
    uid_t real_uid, effective_uid, saved_uid;
    gid_t real_gid, effective_gid, saved_gid;
    if (getpid() <= 1 || getppid() != 1 ||
        getresuid(&real_uid, &effective_uid, &saved_uid) < 0 ||
        getresgid(&real_gid, &effective_gid, &saved_gid) < 0) return -1;
    if (real_uid != uid || effective_uid != uid || saved_uid != uid ||
        real_gid != gid || effective_gid != gid || saved_gid != gid) {
        errno = EPERM;
        return -1;
    }
    for (int descriptor = 0; descriptor < 3; ++descriptor) {
        struct stat info;
        int expected = descriptor ? O_WRONLY : O_RDONLY;
        if (fcntl(descriptor, F_GETFD) != 0 || fcntl(descriptor, F_GETFL) != expected ||
            fstat(descriptor, &info) < 0) return -1;
        if ((info.st_mode & S_IFMT) != OK_MODE_CHARACTER_DEVICE ||
            (info.st_mode & 07777) != 0600 || info.st_uid || info.st_gid ||
            info.st_size || info.st_nlink != 1) {
            errno = EPERM;
            return -1;
        }
    }
    return 0;
}

static int login_identity(void)
{
    return login_identity_as(0, 0);
}

static int login_session_identity(void)
{
    pid_t pid = getpid();
    if (pid <= 1 || getppid() != 1 || getsid(0) != pid || getsid(pid) != pid ||
        getpgrp() != pid || getpgid(0) != pid || getpgid(pid) != pid) {
        errno = EPERM;
        return -1;
    }
    return 0;
}

static int login_session_begin(void)
{
    pid_t pid = getpid();
    if (login_identity() < 0) return -1;
    pid_t sid = setsid();
    if (sid < 0) return -1;
    if (sid != pid) { errno = EIO; return -1; }
    return login_session_identity();
}

static int login_console_identity(void)
{
    if (tcgetsid(STDIN_FILENO) != getpid() || tcgetpgrp(STDIN_FILENO) != getpgrp()) {
        errno = EPERM;
        return -1;
    }
    return 0;
}

static int login_delay(void)
{
    struct timespec deadline;
    int result;
    if (clock_gettime(CLOCK_MONOTONIC, &deadline) < 0) return -1;
    if (deadline.tv_sec < 0 || deadline.tv_sec == INT64_MAX ||
        deadline.tv_nsec < 0 || deadline.tv_nsec >= 1000000000) { errno = EIO; return -1; }
    ++deadline.tv_sec;
    do { result = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &deadline, 0); }
    while (result == EINTR);
    if (result) { errno = result; return -1; }
    return 0;
}

static int login_salt(unsigned char salt[OK_PASSWORD_SALT_BYTES])
{
    size_t used = 0;
    while (used < OK_PASSWORD_SALT_BYTES) {
        ssize_t count = getrandom(salt + used, OK_PASSWORD_SALT_BYTES - used, 0);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) return -1;
        if (!count || (size_t)count > OK_PASSWORD_SALT_BYTES - used) { errno = EIO; return -1; }
        used += (size_t)count;
    }
    return 0;
}

static int login_enroll(struct ok_account_store *store, uint32_t epoch)
{
    struct ok_account next = {.state = OK_ACCOUNT_PENDING};
    unsigned char password[OK_PASSWORD_MAX + 1], repeated[OK_PASSWORD_MAX + 1];
    size_t name_size, password_size = 0, repeated_size = 0;
    int result = -1, status;
    if (store->account.state != OK_ACCOUNT_UNCONFIGURED || store->recovering) goto done;
    if (ok_login_write(STDOUT_FILENO, "Create the first administrator (UID 0). Input is not echoed.\n") < 0) goto done;
    for (;;) {
        status = ok_login_read_line(epoch, "Account name: ", (unsigned char *)next.name,
                                     sizeof(next.name), &name_size);
        if (status == OK_LOGIN_INPUT_ERROR) goto done;
        if (status == OK_LOGIN_INPUT_OK && ok_account_name_valid(next.name, name_size)) break;
        if (ok_login_write(STDOUT_FILENO, "Invalid account name.\n") < 0) goto done;
    }
    for (;;) {
        status = ok_login_read_line(epoch, "Password: ", password, sizeof(password), &password_size);
        if (status == OK_LOGIN_INPUT_ERROR) goto done;
        if (status != OK_LOGIN_INPUT_OK || !password_size) {
            ok_password_clear(password, sizeof(password));
            if (ok_login_write(STDOUT_FILENO, "Use a nonempty password of at most 128 bytes.\n") < 0) goto done;
            continue;
        }
        status = ok_login_read_line(epoch, "Repeat password: ", repeated, sizeof(repeated), &repeated_size);
        if (status == OK_LOGIN_INPUT_ERROR) goto done;
        if (status == OK_LOGIN_INPUT_OK && password_size == repeated_size &&
            !memcmp(password, repeated, password_size)) break;
        ok_password_clear(password, sizeof(password));
        ok_password_clear(repeated, sizeof(repeated));
        if (ok_login_write(STDOUT_FILENO, "Passwords did not match.\n") < 0) goto done;
    }
    if (login_salt(next.salt) < 0 ||
        ok_password_derive(password, password_size, next.salt, next.verifier) < 0) goto done;
    ok_password_clear(password, sizeof(password));
    ok_password_clear(repeated, sizeof(repeated));
    if (ok_account_store_commit(store, &next) < 0) goto done;
    next.state = OK_ACCOUNT_ACTIVE;
    if (ok_account_store_commit(store, &next) < 0) goto done;
    result = 0;
done:
    ok_password_clear(password, sizeof(password));
    ok_password_clear(repeated, sizeof(repeated));
    ok_password_clear(&next, sizeof(next));
    return result;
}

static int login_rotate(struct ok_account_store *store, uint32_t epoch)
{
    struct ok_account next = store->account;
    unsigned char password[OK_PASSWORD_MAX + 1], repeated[OK_PASSWORD_MAX + 1];
    size_t password_size = 0, repeated_size = 0;
    int result = -1, status;
    if (!store->ready || store->recovering || next.state != OK_ACCOUNT_ACTIVE) goto done;
    if (ok_login_write(STDOUT_FILENO,
        "If saving is interrupted, the next sign-in may require the new password.\n") < 0) goto done;
    for (;;) {
        status = ok_login_read_line(epoch, "New password: ", password, sizeof(password), &password_size);
        if (status == OK_LOGIN_INPUT_ERROR) goto done;
        if (status != OK_LOGIN_INPUT_OK || !password_size) {
            ok_password_clear(password, sizeof(password));
            ok_password_clear(repeated, sizeof(repeated));
            if (ok_login_write(STDOUT_FILENO, "Use a nonempty password of at most 128 bytes.\n") < 0) goto done;
            continue;
        }
        status = ok_login_read_line(epoch, "Repeat new password: ", repeated, sizeof(repeated), &repeated_size);
        if (status == OK_LOGIN_INPUT_ERROR) goto done;
        if (status == OK_LOGIN_INPUT_OK && password_size == repeated_size &&
            !memcmp(password, repeated, password_size)) break;
        ok_password_clear(password, sizeof(password));
        ok_password_clear(repeated, sizeof(repeated));
        if (ok_login_write(STDOUT_FILENO, "Passwords did not match.\n") < 0) goto done;
    }
    if (login_salt(next.salt) < 0 ||
        ok_password_derive(password, password_size, next.salt, next.verifier) < 0) goto done;
    ok_password_clear(password, sizeof(password));
    ok_password_clear(repeated, sizeof(repeated));
    if (ok_account_store_rotate(store, &next) < 0) goto done;
    result = 0;
done:
    ok_password_clear(password, sizeof(password));
    ok_password_clear(repeated, sizeof(repeated));
    ok_password_clear(&next, sizeof(next));
    return result;
}

struct login_selection {
    uint32_t uid, gid;
    int ordinary;
    char name[OK_ACCOUNT_NAME_MAX + 1];
    char home[OK_USER_HOME_MAX];
};

static int login_select(struct login_selection *selection, const struct ok_account *administrator,
                        const struct ok_user *user)
{
    memset(selection, 0, sizeof(*selection));
    if (user) {
        selection->ordinary = 1;
        selection->uid = user->uid;
        selection->gid = user->gid;
        memcpy(selection->name, user->name, sizeof(selection->name));
        return ok_user_home(user, selection->home);
    }
    memcpy(selection->name, administrator->name, sizeof(selection->name));
    strcpy(selection->home, "/root");
    return 0;
}

static int login_user_secret(struct ok_user *user, uint32_t epoch)
{
    unsigned char password[OK_PASSWORD_MAX + 1], repeated[OK_PASSWORD_MAX + 1];
    size_t password_size = 0, repeated_size = 0;
    int result = -1, status;
    for (;;) {
        status = ok_login_read_line(epoch, "New password: ", password, sizeof(password), &password_size);
        if (status == OK_LOGIN_INPUT_ERROR) goto done;
        if (status != OK_LOGIN_INPUT_OK || !password_size) {
            ok_password_clear(password, sizeof(password));
            if (ok_login_write(STDOUT_FILENO, "Use a nonempty password of at most 128 bytes.\n") < 0) goto done;
            continue;
        }
        status = ok_login_read_line(epoch, "Repeat new password: ", repeated, sizeof(repeated), &repeated_size);
        if (status == OK_LOGIN_INPUT_ERROR) goto done;
        if (status == OK_LOGIN_INPUT_OK && password_size == repeated_size &&
            !memcmp(password, repeated, password_size)) break;
        ok_password_clear(password, sizeof(password));
        ok_password_clear(repeated, sizeof(repeated));
        if (ok_login_write(STDOUT_FILENO, "Passwords did not match.\n") < 0) goto done;
    }
    if (login_salt(user->salt) < 0 ||
        ok_password_derive(password, password_size, user->salt, user->verifier) < 0) goto done;
    result = 0;
done:
    ok_password_clear(password, sizeof(password));
    ok_password_clear(repeated, sizeof(repeated));
    return result;
}

static int login_add_user(struct ok_users_store *users, uint32_t epoch)
{
    struct ok_user prepared = {0};
    size_t size = 0;
    int result = -1;
    if (!users->ready || users->recovering || users->users.count == OK_USERS_MAX) goto done;
    for (;;) {
        int status = ok_login_read_line(epoch, "New account name: ", (unsigned char *)prepared.name,
                                        sizeof(prepared.name), &size);
        if (status == OK_LOGIN_INPUT_ERROR) goto done;
        if (status == OK_LOGIN_INPUT_OK && ok_account_name_valid(prepared.name, size) &&
            strcmp(prepared.name, users->administrator) &&
            ok_users_find(&users->users, prepared.name, size) < 0) break;
        if (ok_login_write(STDOUT_FILENO, "Invalid or existing account name.\n") < 0) goto done;
    }
    if (ok_login_user_next_uid(&users->users, &prepared.uid) < 0) goto done;
    prepared.gid = prepared.uid;
    if (login_user_secret(&prepared, epoch) < 0 || ok_login_home_available(&prepared) < 0 ||
        ok_users_store_stage_add(users, &prepared) < 0) goto done;
    /* A complete protected ADD is durable before the first home mutation. */
    if (!users->ready || !users->recovering || users->recovery_kind != OK_USERS_ADD ||
        users->change_index >= users->users.count ||
        ok_login_home_prepare(&users->users.entries[users->change_index]) < 0 ||
        ok_users_store_recover(users) < 0) goto done;
    result = 0;
done:
    ok_password_clear(&prepared, sizeof(prepared));
    return result;
}

static int login_authenticate(struct ok_account_store *store, struct ok_users_store *users,
                              uint32_t epoch, struct login_selection *selection)
{
    unsigned char name[OK_ACCOUNT_NAME_MAX + 1], password[OK_PASSWORD_MAX + 1];
    static const unsigned char invalid_password = 0;
    size_t name_size, password_size;
    int result = -1, command = 0, selected = -1;
    if (store->account.state != OK_ACCOUNT_PENDING && store->account.state != OK_ACCOUNT_ACTIVE) goto done;
    if (store->account.state == OK_ACCOUNT_ACTIVE && !store->recovering) {
        if (ok_login_write(STDOUT_FILENO, "Enter :passwd at Login to change an account password.\n") < 0 ||
            ok_login_write(STDOUT_FILENO, "Enter :useradd to create an ordinary account as administrator.\n") < 0) goto done;
    }
    for (;;) {
        int name_status = ok_login_read_line(epoch, "Login: ", name, sizeof(name), &name_size);
        if (name_status == OK_LOGIN_INPUT_ERROR) goto done;
        int requested = name_status == OK_LOGIN_INPUT_OK && name_size == sizeof(":passwd") - 1 &&
                        !memcmp(name, ":passwd", name_size) ? 1 :
                        name_status == OK_LOGIN_INPUT_OK && name_size == sizeof(":useradd") - 1 &&
                        !memcmp(name, ":useradd", name_size) ? 2 : 0;
        if (requested) {
            ok_password_clear(name, sizeof(name));
            if (store->account.state == OK_ACCOUNT_ACTIVE && !store->recovering) {
                command = requested;
                const char *message = requested == 2 ? "Authenticate the administrator before creating an account.\n" :
                                                      "Authenticate the current account password.\n";
                if (ok_login_write(STDOUT_FILENO, message) < 0) goto done;
            } else if (ok_login_write(STDOUT_FILENO,
                "Complete account activation or recovery before changing the password.\n") < 0) goto done;
            continue;
        }
        int password_status = ok_login_read_line(epoch, "Password: ", password, sizeof(password), &password_size);
        if (password_status == OK_LOGIN_INPUT_ERROR) goto done;
        int usable = password_status == OK_LOGIN_INPUT_OK && password_size;
        selected = name_status == OK_LOGIN_INPUT_OK ? ok_users_find(&users->users, (const char *)name, name_size) : -1;
        const unsigned char *salt = selected < 0 ? store->account.salt : users->users.entries[selected].salt;
        const unsigned char *verifier = selected < 0 ? store->account.verifier : users->users.entries[selected].verifier;
        int verified = ok_password_verify(usable ? password : &invalid_password,
            usable ? password_size : 1, salt, verifier);
        int administrator = name_status == OK_LOGIN_INPUT_OK && name_size == strlen(store->account.name) &&
                            !memcmp(name, store->account.name, name_size);
        int matched = name_status == OK_LOGIN_INPUT_OK && usable && verified == 1 && (administrator || selected >= 0);
        if (selected >= 0 && (command == 2 || store->recovering || store->account.state != OK_ACCOUNT_ACTIVE ||
            (users->recovering && users->recovery_kind == OK_USERS_ADD))) matched = 0;
        ok_password_clear(password, sizeof(password));
        ok_password_clear(name, sizeof(name));
        if (verified < 0) goto done;
        if (matched) break;
        if (ok_login_write(STDOUT_FILENO, "Login incorrect.\n") < 0 || login_delay() < 0) goto done;
    }
    if (selected < 0) {
        /* Legacy staged administrator credentials retain their authenticated
         * publication and activation order. */
        if (store->recovering && ok_account_store_recover(store) < 0) goto done;
        if (store->account.state == OK_ACCOUNT_PENDING) {
            struct ok_account active = store->account;
            active.state = OK_ACCOUNT_ACTIVE;
            int committed = ok_account_store_commit(store, &active);
            ok_password_clear(&active, sizeof(active));
            if (committed < 0) goto done;
        }
        if (users->recovering && users->recovery_kind == OK_USERS_ADD) {
            if (users->change_index >= users->users.count ||
                ok_login_home_prepare(&users->users.entries[users->change_index]) < 0 ||
                ok_users_store_recover(users) < 0) goto done;
        }
        if (command == 1 && login_rotate(store, epoch) < 0) goto done;
        if (command == 2 && login_add_user(users, epoch) < 0) goto done;
        if (login_select(selection, &store->account, 0) < 0) goto done;
    } else {
        if (users->recovering && users->recovery_kind == OK_USERS_ROTATE &&
            users->change_index == (uint32_t)selected && ok_users_store_recover(users) < 0) goto done;
        if (command == 1) {
            struct ok_user next = users->users.entries[selected];
            int changed = -1;
            if (!users->recovering && ok_login_write(STDOUT_FILENO,
                "If saving is interrupted, the next sign-in may require the new password.\n") == 0 &&
                login_user_secret(&next, epoch) == 0) changed = ok_users_store_rotate(users, &next);
            ok_password_clear(&next, sizeof(next));
            if (changed < 0) goto done;
        }
        if (login_select(selection, &store->account, &users->users.entries[selected]) < 0) goto done;
    }
    result = command;
done:
    ok_password_clear(password, sizeof(password));
    ok_password_clear(name, sizeof(name));
    return result;
}

static int login_home(void)
{
    struct stat info;
    int root = -1, home = -1, result = -1, saved;
    root = open("/", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (root < 0 || fstat(root, &info) < 0) goto done;
    if (!S_ISDIR(info.st_mode) || info.st_uid || info.st_gid || (info.st_mode & 07022)) {
        errno = EACCES;
        goto done;
    }
    home = openat(root, "root", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (home < 0 || fstat(home, &info) < 0) goto done;
    if (!S_ISDIR(info.st_mode) || info.st_uid || info.st_gid || (info.st_mode & 07777) != 0700) {
        errno = EACCES;
        goto done;
    }
    /* Native fchdir is already part of the exported syscall ABI. Retaining the
     * checked dirfd avoids a second pathname lookup after admission. */
    result = (int)ok_syscall_ret(ok_syscall1(OK_SYS_FCHDIR, home));
done:
    saved = errno;
    if (home >= 0 && close(home) < 0) { result = -1; saved = errno; }
    if (root >= 0 && close(root) < 0) { result = -1; saved = errno; }
    errno = saved;
    return result;
}

static void login_environment(char *output, const char *prefix, const char *value)
{
    size_t offset = strlen(prefix);
    memcpy(output, prefix, offset);
    strcpy(output + offset, value);
}

static void login_epoch_environment(char output[32], uint32_t epoch)
{
    char digits[10];
    size_t used = 0, offset = sizeof("OK_CONSOLE_EPOCH=") - 1;
    strcpy(output, "OK_CONSOLE_EPOCH=");
    do { digits[used++] = (char)('0' + epoch % 10U); epoch /= 10U; } while (epoch);
    while (used) output[offset++] = digits[--used];
    output[offset] = 0;
}

int main(int argc, char **argv, char **environment)
{
    struct ok_account_store store = {.directory = -1};
    static struct ok_users_store users = {.directory = -1};
    struct login_selection selection = {0};
    uint32_t epoch;
    int rotated = 0;
    char user[sizeof("USER=") + OK_ACCOUNT_NAME_MAX];
    char logname[sizeof("LOGNAME=") + OK_ACCOUNT_NAME_MAX];
    char console[32];
    char home[sizeof("HOME=") + OK_USER_HOME_MAX];
    char *shell_arguments[] = {"/bin/oksh", 0};
    char *shell_environment[] = {home, "PATH=/bin", user, logname, console, 0};
    (void)argv;
    if (argc != 1 || ok_login_epoch(environment, &epoch) < 0 || login_identity() < 0 ||
        ok_account_store_open(&store) < 0) goto fail;
    if (ok_login_write(STDOUT_FILENO, "ObfuscationOS\n") < 0) goto fail;
    if (store.account.state == OK_ACCOUNT_UNCONFIGURED) {
        if (login_enroll(&store, epoch) < 0 ||
            ok_users_store_open(&users, store.account.name) < 0 || login_select(&selection, &store.account, 0) < 0) goto fail;
    } else {
        if (ok_users_store_open(&users, store.account.name) < 0) goto fail;
        rotated = login_authenticate(&store, &users, epoch, &selection);
        if (rotated < 0) goto fail;
    }
    if (!store.ready || store.recovering || store.account.state != OK_ACCOUNT_ACTIVE) goto fail;
    login_environment(user, "USER=", selection.name);
    login_environment(logname, "LOGNAME=", selection.name);
    login_environment(home, "HOME=", selection.home);
    login_epoch_environment(console, epoch);
    if (ok_users_store_close(&users) < 0 || ok_account_store_close(&store) < 0) goto fail;
    /* Account descriptors are closed before creating the authenticated session;
     * the native console lease and PID1 parent remain independently checked. */
    if (login_session_begin() < 0 || ioctl(STDIN_FILENO, TIOCSCTTY, 0) < 0 ||
        login_console_identity() < 0) goto fail;
    if (selection.ordinary) {
        if (login_identity() < 0 || ok_login_home_enter(selection.name, selection.uid, selection.gid) < 0 ||
            login_identity_as(selection.uid, selection.gid) < 0) goto fail;
    } else if (login_home() < 0 || login_identity() < 0) goto fail;
    if (login_session_identity() < 0 || login_console_identity() < 0 || ok_console_flush(epoch) < 0) goto fail;
    if (rotated == 1 && ok_login_write(STDOUT_FILENO, "Password changed.\n") < 0) goto fail;
    if (rotated == 2 && ok_login_write(STDOUT_FILENO, "Account created.\n") < 0) goto fail;
    execve(shell_arguments[0], shell_arguments, shell_environment);
fail:
    (void)ok_users_store_close(&users);
    (void)ok_account_store_close(&store);
    (void)ok_login_write(STDERR_FILENO, "login: unable to establish an authenticated console session.\n");
    return 1;
}
