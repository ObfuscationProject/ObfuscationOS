#ifndef OK_LOGIN_STORE_H
#define OK_LOGIN_STORE_H

#include "accounts.h"

#define OK_ACCOUNT_DATABASE "accounts.db"
#define OK_ACCOUNT_STAGING ".accounts.next"

enum ok_account_store_status {
    OK_ACCOUNT_STORE_ERROR = -1,
    /* A mutation was attempted. Reopen and inspect; do not repeat enrollment. */
    OK_ACCOUNT_STORE_UNCERTAIN = -2
};

struct ok_account_store {
    int directory;
    int ready;
    int recovering;
    struct ok_account observed;
    struct ok_account account;
};

/* Callers serialize every write. The PID1 console login does not fork or
 * overlap a restart with its predecessor; other root writers are outside this
 * single-writer API. Open accepts only a fresh or already closed store.
 * Opens only protected root paths and requires persistent sync. Missing,
 * malformed or unsupported state never becomes unconfigured. */
int ok_account_store_open(struct ok_account_store *store);
/* The caller authenticates account before recovering a staged transaction.
 * Unconfigured state has no recovery transaction. */
int ok_account_store_recover(struct ok_account_store *store);
/* Only unconfigured -> pending and same-identity pending -> active are legal. */
int ok_account_store_commit(struct ok_account_store *store, const struct ok_account *next);
/* The caller authenticates the current account before selecting new credentials.
 * Only active -> active for the exact same canonical principal is legal. */
int ok_account_store_rotate(struct ok_account_store *store, const struct ok_account *next);
int ok_account_store_close(struct ok_account_store *store);

#endif
