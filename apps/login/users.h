#ifndef OK_LOGIN_USERS_H
#define OK_LOGIN_USERS_H

#include "accounts.h"

#define OK_USERS_MAX 16U
#define OK_USERS_FILE_MAX 4096U
#define OK_USER_HOME_MAX (sizeof("/home/") + OK_ACCOUNT_NAME_MAX)
#define OK_USER_FIRST_UID 1000U

struct ok_user {
    char name[OK_ACCOUNT_NAME_MAX + 1];
    uint32_t uid, gid;
    unsigned char salt[OK_PASSWORD_SALT_BYTES];
    unsigned char verifier[OK_PASSWORD_VERIFIER_BYTES];
};

/* Canonical records are ordered by increasing UID. Unused entries are zero.
 * Homes are derived from canonical names, never supplied by the database. */
struct ok_users {
    uint32_t count;
    struct ok_user entries[OK_USERS_MAX];
};

/* Failure preserves output. Input and output must not overlap. Parsing checks
 * format policy; operation validation also excludes the actual administrator. */
int ok_users_parse(const void *data, size_t size, struct ok_users *output);
int ok_users_encode(const struct ok_users *users, void *output, size_t capacity);
int ok_users_validate(const struct ok_users *users, const char *administrator);
int ok_users_find(const struct ok_users *users, const char *name, size_t size);
int ok_users_next_uid(const struct ok_users *users, uint32_t *uid);
int ok_user_home(const struct ok_user *user, char output[OK_USER_HOME_MAX]);

#endif
