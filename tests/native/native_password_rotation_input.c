/* Qualification-only observation after the real hidden-input flush/prompt. */
#include "native_password_rotation_authority.h"
#include "input.h"
#include "password.h"

int __real_ok_login_read_line(uint32_t, const char *, unsigned char *, size_t, size_t *);
ssize_t __real_read(int, void *, size_t);
static int selected, armed, completed;
static uint32_t current_epoch;

ssize_t __wrap_read(int descriptor, void *buffer, size_t capacity)
{
    if (descriptor != STDIN_FILENO || !armed) return __real_read(descriptor, buffer, capacity);
    armed = 0;
    struct first_owner owner = {0};
    struct stat info;
    int fd = open(FIRST_PATH, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) { errno = EIO; return -1; }
    if (fstat(fd, &info) < 0 || !S_ISREG(info.st_mode) || (info.st_mode & 07777) != 0600 ||
        info.st_uid || info.st_gid || info.st_nlink != 1 || info.st_size != (off_t)sizeof(owner)) {
        (void)close(fd); errno = EIO; return -1;
    }
    ssize_t count = __real_read(fd, &owner, sizeof(owner));
    int closed = close(fd);
    if (closed || count != (ssize_t)sizeof(owner) || !owner.epoch || owner.epoch > OK_CONSOLE_EPOCH_MAX ||
        current_epoch <= owner.epoch || current_epoch > OK_CONSOLE_EPOCH_MAX || owner.leader <= 1 ||
        owner.leader == getpid() || getppid() != 1 || rotation_wait(0)) { errno = EIO; return -1; }
    for (unsigned role = 0; role != 3; ++role) {
        if (owner.children[role] <= 1 || owner.children[role] == owner.leader ||
            owner.children[role] == getpid()) { errno = EIO; return -1; }
        for (unsigned previous = 0; previous != role; ++previous)
            if (owner.children[previous] == owner.children[role]) { errno = EIO; return -1; }
    }
    struct pollfd input = {STDIN_FILENO, POLLIN, 0};
    if (poll(&input, 1, 30000) != 1 || input.revents != POLLIN ||
        rotation_record("BUFFERED", current_epoch) || put(ACTIVE_PATH, &current_epoch, sizeof(current_epoch)) ||
        mark(WINDOW_PATH) || rotation_wait(2)) { errno = EIO; return -1; }
    input.revents = 0;
    if (poll(&input, 1, 0) != 1 || input.revents != POLLIN ||
        rotation_record("WINDOW_PASS", current_epoch)) { errno = EIO; return -1; }
    completed = 1;
    return __real_read(descriptor, buffer, capacity);
}

int __wrap_ok_login_read_line(uint32_t epoch, const char *prompt, unsigned char *buffer,
                             size_t capacity, size_t *length)
{
    int watch = selected && !completed && !strcmp(prompt, "Password: ");
    if (watch) { current_epoch = epoch; armed = 1; }
    int result = __real_ok_login_read_line(epoch, prompt, buffer, capacity, length);
    armed = 0;
    if (watch) {
        if (!completed || result != OK_LOGIN_INPUT_OK || rotation_record("INPUT_FORWARDED", epoch) ||
            mark(DONE_PATH) || rotation_wait(1)) {
            ok_password_clear(buffer, capacity);
            *length = 0;
            errno = EIO;
            return OK_LOGIN_INPUT_ERROR;
        }
        selected = 0;
        current_epoch = 0;
    } else if (!selected && !completed && result == OK_LOGIN_INPUT_OK && !strcmp(prompt, "Login: ") &&
               *length == sizeof(":passwd") - 1 && !memcmp(buffer, ":passwd", *length)) {
        selected = 1;
        if (rotation_record("SELECTED", epoch)) {
            ok_password_clear(buffer, capacity); *length = 0;
            return OK_LOGIN_INPUT_ERROR;
        }
    }
    return result;
}
