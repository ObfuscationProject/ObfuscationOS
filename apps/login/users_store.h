#ifndef OK_LOGIN_USERS_STORE_H
#define OK_LOGIN_USERS_STORE_H

#include "users.h"

#define OK_USERS_DATABASE "users.db"
#define OK_USERS_STAGING ".users.next"

enum ok_users_change { OK_USERS_NO_CHANGE, OK_USERS_ADD, OK_USERS_ROTATE };
enum ok_users_store_status { OK_USERS_STORE_ERROR = -1, OK_USERS_STORE_UNCERTAIN = -2 };

/* Keep this explicit workspace in static storage, not on a native user stack.
 * observed is the admitted database; users is the selected complete successor
 * during recovery. work/bytes are scratch and never contain plaintext secrets. */
struct ok_users_store {
    int directory, ready, recovering, observed_present;
    enum ok_users_change recovery_kind;
    uint32_t change_index;
    char administrator[OK_ACCOUNT_NAME_MAX + 1];
    struct ok_users observed, users, work;
    unsigned char bytes[OK_USERS_FILE_MAX + 1];
};

/* Only the serialized PID1 console-login leader writes. No overlapping opens,
 * other privileged writer or concurrent mutation is supported. The trusted
 * legacy administrator name is supplied after admitting accounts.db. Missing
 * database AND staging is empty; malformed/unsupported files fail closed. */
int ok_users_store_open(struct ok_users_store *store, const char *administrator);
/* Caller authenticates the administrator for ADD, or the selected staged user
 * at users.entries[change_index] for ROTATE, before recovery publication. */
int ok_users_store_recover(struct ok_users_store *store);
/* Caller authenticates the administrator before adding exactly one prepared
 * record whose home is already prepared and persisted, or the current selected
 * user before rotating that same principal.
 * Salt/verification use the existing password API and trusted caller entropy.
 * Neither operation erases, reorders or modifies unrelated identities. */
int ok_users_store_add(struct ok_users_store *store, const struct ok_user *user);
/* Durably select an ADD without publishing users.db. The authenticated caller
 * first checks home absence, stages, prepares/syncs that exact home, then calls
 * recover. A restarted ADD requires administrator authentication and the same
 * home completion before recover. */
int ok_users_store_stage_add(struct ok_users_store *store, const struct ok_user *user);
int ok_users_store_rotate(struct ok_users_store *store, const struct ok_user *user);
int ok_users_store_close(struct ok_users_store *store);

#endif
