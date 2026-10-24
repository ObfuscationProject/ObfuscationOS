#include "users.h"

#include <string.h>

_Static_assert(OK_PASSWORD_ROUNDS == 600000U, "version 1 users work factor");
_Static_assert(OK_USERS_FILE_MAX >= 2700U, "sixteen maximum-width user records");

static const char prefix[] = "OKUSERS 1\nkdf pbkdf2-hmac-sha256\nrounds 600000\ncount ";

static size_t name_size(const char name[OK_ACCOUNT_NAME_MAX + 1])
{
    size_t size = 0;
    while (size <= OK_ACCOUNT_NAME_MAX && name[size]) ++size;
    return size;
}

static int canonical_user(const struct ok_user *user)
{
    size_t size = name_size(user->name);
    if (!ok_account_name_valid(user->name, size) || user->uid < OK_USER_FIRST_UID ||
        user->uid == UINT32_MAX || user->uid != user->gid) return 0;
    for (size_t i = size + 1; i < sizeof(user->name); ++i)
        if (user->name[i]) return 0;
    return 1;
}

int ok_users_validate(const struct ok_users *users, const char *administrator)
{
    struct ok_user empty = {0};
    size_t admin_size = 0;
    if (!users || users->count > OK_USERS_MAX) return -1;
    if (administrator) {
        admin_size = name_size(administrator);
        if (!ok_account_name_valid(administrator, admin_size)) return -1;
    }
    for (uint32_t i = 0; i < users->count; ++i) {
        const struct ok_user *user = &users->entries[i];
        if (!canonical_user(user) || (i && users->entries[i - 1].uid >= user->uid)) return -1;
        if (administrator && name_size(user->name) == admin_size &&
            !memcmp(user->name, administrator, admin_size)) return -1;
        for (uint32_t j = 0; j < i; ++j)
            if (!memcmp(user->name, users->entries[j].name, sizeof(user->name))) return -1;
    }
    for (uint32_t i = users->count; i < OK_USERS_MAX; ++i)
        if (memcmp(&users->entries[i], &empty, sizeof(empty))) return -1;
    return 0;
}

static int consume(const unsigned char **cursor, size_t *remaining, const char *literal)
{
    size_t size = strlen(literal);
    if (*remaining < size || memcmp(*cursor, literal, size)) return -1;
    *cursor += size; *remaining -= size;
    return 0;
}

static int number(const unsigned char **cursor, size_t *remaining, unsigned char end, uint32_t *result)
{
    uint32_t value = 0;
    size_t size = 0;
    while (size < *remaining && (*cursor)[size] != end) {
        unsigned char byte = (*cursor)[size];
        if (byte < '0' || byte > '9' || (size && (*cursor)[0] == '0') ||
            value > (UINT32_MAX - (uint32_t)(byte - '0')) / 10U) return -1;
        value = value * 10U + (uint32_t)(byte - '0');
        ++size;
    }
    if (!size || size == *remaining) return -1;
    *cursor += size + 1; *remaining -= size + 1; *result = value;
    return 0;
}

static int hex(const unsigned char **cursor, size_t *remaining, unsigned char *output, size_t size)
{
    if (*remaining < size * 2) return -1;
    for (size_t i = 0; i < size * 2; ++i) {
        unsigned char c = (*cursor)[i];
        int value = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1;
        if (value < 0) return -1;
        if (!(i & 1U)) output[i / 2] = (unsigned char)(value << 4);
        else output[i / 2] |= (unsigned char)value;
    }
    *cursor += size * 2; *remaining -= size * 2;
    return 0;
}

static int parse_record(const unsigned char **cursor, size_t *remaining, struct ok_user *user)
{
    size_t size = 0;
    memset(user, 0, sizeof(*user));
    if (consume(cursor, remaining, "user ")) return -1;
    while (size < *remaining && (*cursor)[size] != ' ') ++size;
    if (size == *remaining || !ok_account_name_valid((const char *)*cursor, size)) return -1;
    memcpy(user->name, *cursor, size);
    *cursor += size + 1; *remaining -= size + 1;
    if (number(cursor, remaining, ' ', &user->uid) || number(cursor, remaining, ' ', &user->gid) ||
        hex(cursor, remaining, user->salt, sizeof(user->salt)) || consume(cursor, remaining, " ") ||
        hex(cursor, remaining, user->verifier, sizeof(user->verifier)) || consume(cursor, remaining, "\n") ||
        !canonical_user(user)) return -1;
    return 0;
}

static int overlaps(const void *left, size_t a, const void *right, size_t b)
{
    uintptr_t x = (uintptr_t)left, y = (uintptr_t)right;
    return x <= y ? y - x < a : x - y < b;
}

int ok_users_parse(const void *data, size_t size, struct ok_users *output)
{
    const unsigned char *cursor = data, *start;
    const unsigned char *names[OK_USERS_MAX];
    size_t lengths[OK_USERS_MAX], remaining = size;
    struct ok_user record = {0};
    uint32_t count, previous = 0;
    int result = -1;
    if (!data || !output || !size || size > OK_USERS_FILE_MAX ||
        overlaps(data, size, output, sizeof(*output))) return -1;
    if (consume(&cursor, &remaining, prefix) || number(&cursor, &remaining, '\n', &count) || count > OK_USERS_MAX) goto done;
    start = cursor;
    /* Validate first using one record and non-secret name spans. No registry
     * copy is placed on a nested native login stack. */
    for (uint32_t i = 0; i < count; ++i) {
        if (remaining < 5) goto done;
        names[i] = cursor + 5;
        if (parse_record(&cursor, &remaining, &record) || record.uid <= previous) goto done;
        lengths[i] = name_size(record.name);
        for (uint32_t j = 0; j < i; ++j)
            if (lengths[i] == lengths[j] && !memcmp(names[i], names[j], lengths[i])) goto done;
        previous = record.uid;
    }
    if (remaining) goto done;
    memset(output, 0, sizeof(*output));
    output->count = count;
    cursor = start; remaining = size - (size_t)(start - (const unsigned char *)data);
    for (uint32_t i = 0; i < count; ++i) {
        (void)parse_record(&cursor, &remaining, &record);
        output->entries[i] = record;
    }
    result = 0;
done:
    ok_password_clear(&record, sizeof(record));
    return result;
}

static size_t decimal_size(uint32_t number)
{
    size_t size = 1;
    while (number >= 10U) { number /= 10U; ++size; }
    return size;
}

static void decimal(unsigned char **cursor, uint32_t number)
{
    size_t size = decimal_size(number);
    for (size_t i = size; i; --i) { (*cursor)[i - 1] = (unsigned char)('0' + number % 10U); number /= 10U; }
    *cursor += size;
}

static void encode_hex(unsigned char **cursor, const unsigned char *input, size_t size)
{
    static const char digits[] = "0123456789abcdef";
    for (size_t i = 0; i < size; ++i) {
        *(*cursor)++ = (unsigned char)digits[input[i] >> 4];
        *(*cursor)++ = (unsigned char)digits[input[i] & 15];
    }
}

int ok_users_encode(const struct ok_users *users, void *output, size_t capacity)
{
    unsigned char *cursor = output;
    size_t size = sizeof(prefix) - 1;
    if (!users || !output || ok_users_validate(users, 0)) return -1;
    size += decimal_size(users->count) + 1;
    for (uint32_t i = 0; i < users->count; ++i)
        size += 5 + name_size(users->entries[i].name) + 1 + decimal_size(users->entries[i].uid) + 1 +
            decimal_size(users->entries[i].gid) + 1 + OK_PASSWORD_SALT_BYTES * 2 + 1 + OK_PASSWORD_VERIFIER_BYTES * 2 + 1;
    if (size > OK_USERS_FILE_MAX || size > capacity || overlaps(output, size, users, sizeof(*users))) return -1;
    memcpy(cursor, prefix, sizeof(prefix) - 1); cursor += sizeof(prefix) - 1;
    decimal(&cursor, users->count); *cursor++ = '\n';
    for (uint32_t i = 0; i < users->count; ++i) {
        const struct ok_user *user = &users->entries[i];
        size_t length = name_size(user->name);
        memcpy(cursor, "user ", 5); cursor += 5;
        memcpy(cursor, user->name, length); cursor += length; *cursor++ = ' ';
        decimal(&cursor, user->uid); *cursor++ = ' ';
        decimal(&cursor, user->gid); *cursor++ = ' ';
        encode_hex(&cursor, user->salt, sizeof(user->salt)); *cursor++ = ' ';
        encode_hex(&cursor, user->verifier, sizeof(user->verifier)); *cursor++ = '\n';
    }
    return (int)size;
}

int ok_users_find(const struct ok_users *users, const char *name, size_t size)
{
    if (!users || !ok_account_name_valid(name, size) || ok_users_validate(users, 0)) return -1;
    for (uint32_t i = 0; i < users->count; ++i)
        if (name_size(users->entries[i].name) == size && !memcmp(users->entries[i].name, name, size)) return (int)i;
    return -1;
}

int ok_users_next_uid(const struct ok_users *users, uint32_t *uid)
{
    uint32_t candidate = OK_USER_FIRST_UID;
    if (!uid || ok_users_validate(users, 0) || users->count == OK_USERS_MAX) return -1;
    for (uint32_t i = 0; i < users->count && users->entries[i].uid == candidate; ++i) ++candidate;
    *uid = candidate;
    return 0;
}

int ok_user_home(const struct ok_user *user, char output[OK_USER_HOME_MAX])
{
    if (!user || !output || !canonical_user(user) || overlaps(output, OK_USER_HOME_MAX, user, sizeof(*user))) return -1;
    memcpy(output, "/home/", 6);
    memcpy(output + 6, user->name, name_size(user->name) + 1);
    return 0;
}
