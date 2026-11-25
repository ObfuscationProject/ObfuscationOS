#include "input.h"
#include "password.h"

#include <errno.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>

#define LOGIN_EPOCH_LIMIT 0x3fffffffU
#define LOGIN_ENVIRONMENT_MAX 16U
#define LOGIN_ENVIRONMENT_STRING_MAX 255U
#define LOGIN_DRAIN_LIMIT 4096U

int ok_login_epoch(char *const environment[], uint32_t *epoch)
{
    static const char prefix[] = "OK_CONSOLE_EPOCH=";
    uint32_t value = 0;
    int found = 0;
    size_t index;
    if (!environment || !epoch) return -1;
    for (index = 0; index <= LOGIN_ENVIRONMENT_MAX; ++index) {
        const char *entry = environment[index];
        size_t length = 0;
        if (!entry) break;
        if (index == LOGIN_ENVIRONMENT_MAX) return -1;
        while (length <= LOGIN_ENVIRONMENT_STRING_MAX && entry[length]) ++length;
        if (length > LOGIN_ENVIRONMENT_STRING_MAX) return -1;
        if (length < sizeof(prefix) - 1 || memcmp(entry, prefix, sizeof(prefix) - 1)) continue;
        const char *digits = entry + sizeof(prefix) - 1;
        if (found || *digits < '1' || *digits > '9') return -1;
        for (; *digits; ++digits) {
            unsigned digit;
            if (*digits < '0' || *digits > '9') return -1;
            digit = (unsigned)(*digits - '0');
            if (value > (LOGIN_EPOCH_LIMIT - digit) / 10U) return -1;
            value = value * 10U + digit;
        }
        found = 1;
    }
    if (!found) return -1;
    *epoch = value;
    return 0;
}

int ok_login_write(int descriptor, const char *text)
{
    size_t remaining;
    if (!text) { errno = EINVAL; return -1; }
    remaining = strlen(text);
    while (remaining) {
        ssize_t count = write(descriptor, text, remaining);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) return -1;
        if (!count || (size_t)count > remaining) { errno = EIO; return -1; }
        text += count;
        remaining -= (size_t)count;
    }
    return 0;
}

/* login runs on its pts: the line discipline echoes and edits the line, and
 * TCIFLUSH drops input typed before the prompt. A line read without echo ends
 * with login's own newline. */
static int login_read(const char *prompt, unsigned char *buffer, size_t capacity,
                      size_t *length, int echoed)
{
    size_t used = 0, discarded = 0;
    int invalid = 0;
    if (tcflush(STDIN_FILENO, TCIFLUSH) < 0 || ok_login_write(STDOUT_FILENO, prompt) < 0) goto fail;
    for (;;) {
        unsigned char byte;
        ssize_t count = read(STDIN_FILENO, &byte, 1);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) goto fail;
        if (count != 1) { errno = EIO; goto fail; }
        if (byte == '\n' || byte == '\r') {
            if (!echoed && ok_login_write(STDOUT_FILENO, "\n") < 0) goto fail;
            if (invalid) {
                ok_password_clear(buffer, capacity);
                return OK_LOGIN_INPUT_INVALID;
            }
            buffer[used] = 0;
            *length = used;
            return OK_LOGIN_INPUT_OK;
        }
        if (!byte || used + 1 >= capacity) invalid = 1;
        if (!invalid) buffer[used++] = byte;
        else if (++discarded == LOGIN_DRAIN_LIMIT) {
            /* Bound the drain without ever admitting the stored prefix. The
             * next prompt flushes again before accepting a new complete line. */
            if (tcflush(STDIN_FILENO, TCIFLUSH) < 0 || ok_login_write(STDOUT_FILENO, "\n") < 0) goto fail;
            ok_password_clear(buffer, capacity);
            return OK_LOGIN_INPUT_INVALID;
        }
    }
fail:
    ok_password_clear(buffer, capacity);
    return OK_LOGIN_INPUT_ERROR;
}

static int login_arguments(uint32_t epoch, const char *prompt, unsigned char *buffer,
                           size_t capacity, size_t *length)
{
    if (length) *length = 0;
    if (buffer && capacity) ok_password_clear(buffer, capacity);
    if (!buffer || !capacity || !length || !prompt || !epoch || epoch > LOGIN_EPOCH_LIMIT) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

int ok_login_read_line(uint32_t epoch, const char *prompt, unsigned char *buffer,
                       size_t capacity, size_t *length)
{
    if (login_arguments(epoch, prompt, buffer, capacity, length) < 0) return OK_LOGIN_INPUT_ERROR;
    return login_read(prompt, buffer, capacity, length, 1);
}

int ok_login_read_secret(uint32_t epoch, const char *prompt, unsigned char *buffer,
                         size_t capacity, size_t *length)
{
    struct termios saved, quiet;
    int status, error;
    if (login_arguments(epoch, prompt, buffer, capacity, length) < 0) return OK_LOGIN_INPUT_ERROR;
    if (tcgetattr(STDIN_FILENO, &saved) < 0) return OK_LOGIN_INPUT_ERROR;
    quiet = saved;
    quiet.c_lflag &= ~(tcflag_t)(ECHO | ECHONL);
    if (tcsetattr(STDIN_FILENO, TCSANOW, &quiet) < 0) {
        error = errno;
        (void)tcsetattr(STDIN_FILENO, TCSANOW, &saved);
        errno = error;
        return OK_LOGIN_INPUT_ERROR;
    }
    status = login_read(prompt, buffer, capacity, length, 0);
    error = errno;
    /* Echo comes back on every path; a secret read without it is not kept. */
    if (tcsetattr(STDIN_FILENO, TCSANOW, &saved) < 0) {
        ok_password_clear(buffer, capacity);
        *length = 0;
        return OK_LOGIN_INPUT_ERROR;
    }
    errno = error;
    return status;
}
