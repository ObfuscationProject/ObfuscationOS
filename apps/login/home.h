#ifndef OK_LOGIN_HOME_H
#define OK_LOGIN_HOME_H

#include "users.h"

/* All three operations require the serialized root console-login leader.
 * Fresh ADD checks absence before staging; prepare can resume only the exact
 * staged principal after administrator authentication. */
int ok_login_home_available(const struct ok_user *user);
int ok_login_home_prepare(const struct ok_user *user);
/* Retain the checked home, drop all GIDs then UIDs, verify, enter and close.
 * A failed drop is terminal for this login leader; callers must never retry. */
int ok_login_home_enter(const char *name, uint32_t uid, uint32_t gid);
/* Skip both configured numeric service identities and existing users. */
int ok_login_user_next_uid(const struct ok_users *users, uint32_t *uid);

#endif
