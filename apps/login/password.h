#ifndef OK_LOGIN_PASSWORD_H
#define OK_LOGIN_PASSWORD_H

#include <stddef.h>
#include <stdint.h>

#define OK_PASSWORD_MAX 128U
#define OK_PASSWORD_SALT_BYTES 16U
#define OK_PASSWORD_VERIFIER_BYTES 32U
#define OK_PASSWORD_ROUNDS 600000U

/* Internal distribution primitives; none acquire entropy or store passwords. */
int ok_pbkdf2_sha256(const void *password, size_t password_size,
                     const void *salt, size_t salt_size, uint32_t rounds,
                     unsigned char result[OK_PASSWORD_VERIFIER_BYTES]);
int ok_password_derive(const void *password, size_t password_size,
                       const unsigned char salt[OK_PASSWORD_SALT_BYTES],
                       unsigned char result[OK_PASSWORD_VERIFIER_BYTES]);
int ok_password_verify(const void *password, size_t password_size,
                       const unsigned char salt[OK_PASSWORD_SALT_BYTES],
                       const unsigned char expected[OK_PASSWORD_VERIFIER_BYTES]);
void ok_password_clear(void *memory, size_t size);

#endif
