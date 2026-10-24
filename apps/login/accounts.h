#ifndef OK_LOGIN_ACCOUNTS_H
#define OK_LOGIN_ACCOUNTS_H

#include "password.h"

#define OK_ACCOUNT_FILE_MAX 512U
#define OK_ACCOUNT_NAME_MAX 31U

enum ok_account_state {
    OK_ACCOUNT_UNCONFIGURED,
    OK_ACCOUNT_PENDING,
    OK_ACCOUNT_ACTIVE
};

/* Version 1 supports the user-selected first administrator, with UID/GID 0
 * and /root. Adding ordinary users requires a different policy version. */
struct ok_account {
    enum ok_account_state state;
    char name[OK_ACCOUNT_NAME_MAX + 1];
    unsigned char salt[OK_PASSWORD_SALT_BYTES];
    unsigned char verifier[OK_PASSWORD_VERIFIER_BYTES];
};

int ok_account_name_valid(const char *name, size_t size);
int ok_account_parse(const void *data, size_t size, struct ok_account *result);
/* Returns the byte length, or -1; failed admission leaves output untouched. */
int ok_account_encode(const struct ok_account *account, void *output, size_t capacity);

#endif
