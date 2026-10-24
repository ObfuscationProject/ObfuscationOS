#include "password.h"

#include <string.h>

/* SHA-256 (FIPS 180-4) and PBKDF2-HMAC-SHA-256 (RFC 8018). State and byte
 * encoding are explicit so the result does not depend on guest endianness. */
struct sha256 {
    uint32_t words[8];
    uint64_t bytes;
    size_t used;
    unsigned char block[64];
};

static const uint32_t constants[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
    0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
    0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
    0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
    0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
    0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
    0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
    0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
    0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
    0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
    0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U
};

void ok_password_clear(void *memory, size_t size)
{
    volatile unsigned char *bytes = memory;
    while (size--) *bytes++ = 0;
}

static uint32_t rotate(uint32_t value, unsigned count)
{
    return (value >> count) | (value << (32U - count));
}

static void transform(struct sha256 *state)
{
    uint32_t schedule[64];
    uint32_t a, b, c, d, e, f, g, h;
    unsigned i;
    for (i = 0; i < 16; ++i) {
        const unsigned char *p = state->block + i * 4;
        schedule[i] = (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 |
                      (uint32_t)p[2] << 8 | (uint32_t)p[3];
    }
    for (; i < 64; ++i) {
        uint32_t x = schedule[i - 15], y = schedule[i - 2];
        schedule[i] = schedule[i - 16] + (rotate(x, 7) ^ rotate(x, 18) ^ (x >> 3)) +
                      schedule[i - 7] + (rotate(y, 17) ^ rotate(y, 19) ^ (y >> 10));
    }
    a = state->words[0]; b = state->words[1]; c = state->words[2]; d = state->words[3];
    e = state->words[4]; f = state->words[5]; g = state->words[6]; h = state->words[7];
    for (i = 0; i < 64; ++i) {
        uint32_t first = h + (rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25)) +
                         ((e & f) ^ (~e & g)) + constants[i] + schedule[i];
        uint32_t second = (rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22)) +
                          ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + first;
        d = c; c = b; b = a; a = first + second;
    }
    state->words[0] += a; state->words[1] += b;
    state->words[2] += c; state->words[3] += d;
    state->words[4] += e; state->words[5] += f;
    state->words[6] += g; state->words[7] += h;
    ok_password_clear(schedule, sizeof(schedule));
}

static void sha_init(struct sha256 *state)
{
    static const uint32_t initial[8] = {
        0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
        0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U
    };
    memset(state, 0, sizeof(*state));
    memcpy(state->words, initial, sizeof(initial));
}

static void sha_update(struct sha256 *state, const void *data, size_t size)
{
    const unsigned char *bytes = data;
    state->bytes += size;
    while (size) {
        size_t take = sizeof(state->block) - state->used;
        if (take > size) take = size;
        memcpy(state->block + state->used, bytes, take);
        state->used += take; bytes += take; size -= take;
        if (state->used == sizeof(state->block)) {
            transform(state);
            state->used = 0;
        }
    }
}

static void sha_final(struct sha256 *state, unsigned char result[32])
{
    uint64_t bits = state->bytes * 8;
    unsigned i;
    state->block[state->used++] = 0x80;
    if (state->used > 56) {
        memset(state->block + state->used, 0, 64 - state->used);
        transform(state);
        state->used = 0;
    }
    memset(state->block + state->used, 0, 56 - state->used);
    for (i = 0; i < 8; ++i) state->block[63 - i] = (unsigned char)(bits >> (i * 8));
    transform(state);
    for (i = 0; i < 32; ++i) result[i] = (unsigned char)(state->words[i / 4] >> (24 - (i % 4) * 8));
    ok_password_clear(state, sizeof(*state));
}

struct hmac256 { struct sha256 inner, outer; };

static void hmac_init(struct hmac256 *state, const void *key, size_t size)
{
    unsigned char pad[64] = {0};
    unsigned i;
    if (size > sizeof(pad)) {
        struct sha256 hash;
        sha_init(&hash); sha_update(&hash, key, size); sha_final(&hash, pad);
    } else if (size) memcpy(pad, key, size);
    for (i = 0; i < sizeof(pad); ++i) pad[i] ^= 0x36;
    sha_init(&state->inner); sha_update(&state->inner, pad, sizeof(pad));
    for (i = 0; i < sizeof(pad); ++i) pad[i] ^= 0x36 ^ 0x5c;
    sha_init(&state->outer); sha_update(&state->outer, pad, sizeof(pad));
    ok_password_clear(pad, sizeof(pad));
}

static void hmac_digest(const struct hmac256 *base, const void *data, size_t size,
                        const void *suffix, size_t suffix_size, unsigned char result[32])
{
    struct hmac256 state = *base;
    unsigned char inner[32];
    sha_update(&state.inner, data, size);
    sha_update(&state.inner, suffix, suffix_size);
    sha_final(&state.inner, inner);
    sha_update(&state.outer, inner, sizeof(inner));
    sha_final(&state.outer, result);
    ok_password_clear(inner, sizeof(inner));
    ok_password_clear(&state, sizeof(state));
}

int ok_pbkdf2_sha256(const void *password, size_t password_size,
                     const void *salt, size_t salt_size, uint32_t rounds,
                     unsigned char result[32])
{
    struct hmac256 base;
    unsigned char u[32], derived[32];
    static const unsigned char block_number[4] = {0, 0, 0, 1};
    uint32_t round;
    unsigned i;
    if ((!password && password_size) || password_size > OK_PASSWORD_MAX ||
        (!salt && salt_size) || salt_size > 64 || !rounds || rounds > 1000000U || !result)
        return -1;
    hmac_init(&base, password, password_size);
    hmac_digest(&base, salt, salt_size, block_number, sizeof(block_number), u);
    memcpy(derived, u, sizeof(derived));
    for (round = 1; round < rounds; ++round) {
        hmac_digest(&base, u, sizeof(u), NULL, 0, u);
        for (i = 0; i < sizeof(u); ++i) derived[i] ^= u[i];
    }
    memcpy(result, derived, sizeof(derived));
    ok_password_clear(&base, sizeof(base));
    ok_password_clear(u, sizeof(u));
    ok_password_clear(derived, sizeof(derived));
    return 0;
}

int ok_password_derive(const void *password, size_t password_size,
                       const unsigned char salt[16], unsigned char result[32])
{
    if (!password_size || !salt) return -1;
    return ok_pbkdf2_sha256(password, password_size, salt, 16, OK_PASSWORD_ROUNDS, result);
}

int ok_password_verify(const void *password, size_t password_size,
                       const unsigned char salt[16], const unsigned char expected[32])
{
    unsigned char candidate[32];
    volatile unsigned difference = 0;
    unsigned i;
    if (!expected || ok_password_derive(password, password_size, salt, candidate)) return -1;
    for (i = 0; i < sizeof(candidate); ++i) difference |= candidate[i] ^ expected[i];
    ok_password_clear(candidate, sizeof(candidate));
    return difference == 0;
}
