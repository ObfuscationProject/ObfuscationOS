#ifndef OK_LOGIN_INPUT_H
#define OK_LOGIN_INPUT_H

#include <stddef.h>
#include <stdint.h>

enum ok_login_input_status {
    OK_LOGIN_INPUT_ERROR = -1,
    OK_LOGIN_INPUT_OK = 0,
    OK_LOGIN_INPUT_INVALID = 1
};

/* Parses one canonical, positive console epoch from the explicit environment. */
int ok_login_epoch(char *const environment[], uint32_t *epoch);
int ok_login_write(int descriptor, const char *text);
/* Reads one line from the login terminal on fd 0 after flushing earlier
 * input. Capacity includes the trailing NUL. Invalid and failed reads erase
 * the entire buffer, and EOF never admits a partial line. read_line leaves the
 * terminal's echo as it is (names); read_secret clears ECHO for the read and
 * restores the attributes on every path (passwords). */
int ok_login_read_line(uint32_t epoch, const char *prompt, unsigned char *buffer,
                       size_t capacity, size_t *length);
int ok_login_read_secret(uint32_t epoch, const char *prompt, unsigned char *buffer,
                         size_t capacity, size_t *length);

#endif
