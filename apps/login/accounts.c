#include "accounts.h"

#include <string.h>

_Static_assert(OK_PASSWORD_ROUNDS == 600000U, "version 1 account work factor");
_Static_assert(OK_ACCOUNT_FILE_MAX >= 320U, "bounded version 1 encoding capacity");

static const char unconfigured[] = "OKACCOUNTS 1\nstate unconfigured\n";
static const char policy[] = "\nuid 0\ngid 0\nhome /root\nkdf pbkdf2-hmac-sha256\nrounds 600000\nsalt ";

int ok_account_name_valid(const char *name, size_t size)
{
    size_t i;
    if (!name || !size || size > OK_ACCOUNT_NAME_MAX ||
        !((name[0] >= 'a' && name[0] <= 'z') || name[0] == '_')) return 0;
    for (i = 1; i < size; ++i) {
        unsigned char c = (unsigned char)name[i];
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-')) return 0;
    }
    return 1;
}

static int consume(const unsigned char **cursor, size_t *remaining, const char *literal)
{
    size_t size = strlen(literal);
    if (*remaining < size || memcmp(*cursor, literal, size)) return -1;
    *cursor += size; *remaining -= size;
    return 0;
}

static int hex_value(unsigned char value)
{
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    return -1;
}

static int decode_hex(const unsigned char **cursor, size_t *remaining,
                      unsigned char *output, size_t bytes)
{
    size_t i;
    if (*remaining < bytes * 2) return -1;
    for (i = 0; i < bytes; ++i) {
        int high = hex_value((*cursor)[i * 2]), low = hex_value((*cursor)[i * 2 + 1]);
        if (high < 0 || low < 0) return -1;
        output[i] = (unsigned char)(high * 16 + low);
    }
    *cursor += bytes * 2; *remaining -= bytes * 2;
    return 0;
}

int ok_account_parse(const void *data, size_t size, struct ok_account *result)
{
    const unsigned char *cursor = data;
    struct ok_account candidate;
    size_t remaining = size, name_size = 0;
    int status = -1;
    if (!data || !result || !size || size > OK_ACCOUNT_FILE_MAX) return -1;
    memset(&candidate, 0, sizeof(candidate));
    if (size == sizeof(unconfigured) - 1 && !memcmp(data, unconfigured, size)) {
        candidate.state = OK_ACCOUNT_UNCONFIGURED;
    } else {
        if (consume(&cursor, &remaining, "OKACCOUNTS 1\nstate ")) goto done;
        if (remaining >= 8 && !memcmp(cursor, "pending\n", 8)) {
            candidate.state = OK_ACCOUNT_PENDING;
            cursor += 8; remaining -= 8;
        } else if (remaining >= 7 && !memcmp(cursor, "active\n", 7)) {
            candidate.state = OK_ACCOUNT_ACTIVE;
            cursor += 7; remaining -= 7;
        } else goto done;
        if (consume(&cursor, &remaining, "name ")) goto done;
        while (name_size < remaining && cursor[name_size] != '\n') ++name_size;
        if (!ok_account_name_valid((const char *)cursor, name_size)) goto done;
        memcpy(candidate.name, cursor, name_size);
        cursor += name_size; remaining -= name_size;
        if (consume(&cursor, &remaining, policy) ||
            decode_hex(&cursor, &remaining, candidate.salt, sizeof(candidate.salt)) ||
            consume(&cursor, &remaining, "\nverifier ") ||
            decode_hex(&cursor, &remaining, candidate.verifier, sizeof(candidate.verifier)) ||
            consume(&cursor, &remaining, "\n") || remaining) goto done;
    }
    *result = candidate;
    status = 0;
done:
    ok_password_clear(&candidate, sizeof(candidate));
    return status;
}

static void append(char *buffer, size_t *used, const void *data, size_t size)
{
    memcpy(buffer + *used, data, size);
    *used += size;
}

static void encode_hex(char *buffer, size_t *used, const unsigned char *data, size_t size)
{
    static const char digits[] = "0123456789abcdef";
    size_t i;
    for (i = 0; i < size; ++i) {
        buffer[(*used)++] = digits[data[i] >> 4];
        buffer[(*used)++] = digits[data[i] & 15];
    }
}

int ok_account_encode(const struct ok_account *account, void *output, size_t capacity)
{
    char buffer[OK_ACCOUNT_FILE_MAX];
    size_t used = 0, name_size = 0;
    int status = -1;
    if (!account || !output) return -1;
    if (account->state == OK_ACCOUNT_UNCONFIGURED) {
        /* Do not silently discard a configured identity when reseeding. */
        unsigned char fields[sizeof(account->name) + sizeof(account->salt) + sizeof(account->verifier)] = {0};
        if (memcmp(account->name, fields, sizeof(account->name)) ||
            memcmp(account->salt, fields, sizeof(account->salt)) ||
            memcmp(account->verifier, fields, sizeof(account->verifier))) goto done;
        append(buffer, &used, unconfigured, sizeof(unconfigured) - 1);
    } else if (account->state == OK_ACCOUNT_PENDING || account->state == OK_ACCOUNT_ACTIVE) {
        const char *prefix = account->state == OK_ACCOUNT_PENDING ?
            "OKACCOUNTS 1\nstate pending\nname " : "OKACCOUNTS 1\nstate active\nname ";
        while (name_size < sizeof(account->name) && account->name[name_size]) ++name_size;
        if (!ok_account_name_valid(account->name, name_size)) goto done;
        /* The parsed form is zero-padded. Do not publish an identity whose
         * ignored name tail would disagree with its later canonical readback. */
        for (size_t i = name_size + 1; i < sizeof(account->name); ++i)
            if (account->name[i]) goto done;
        append(buffer, &used, prefix, strlen(prefix));
        append(buffer, &used, account->name, name_size);
        append(buffer, &used, policy, sizeof(policy) - 1);
        encode_hex(buffer, &used, account->salt, sizeof(account->salt));
        append(buffer, &used, "\nverifier ", 10);
        encode_hex(buffer, &used, account->verifier, sizeof(account->verifier));
        append(buffer, &used, "\n", 1);
    } else goto done;
    if (capacity < used) goto done;
    memcpy(output, buffer, used);
    status = (int)used;
done:
    ok_password_clear(buffer, sizeof(buffer));
    return status;
}
