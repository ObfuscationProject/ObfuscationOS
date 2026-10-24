#include <elf.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/auxv.h>
#include <sys/random.h>
#include <unistd.h>

int main(void)
{
    const unsigned char *initial = (const unsigned char *)(uintptr_t)getauxval(AT_RANDOM);
    unsigned char later[16];
    if (!initial || getrandom(later, sizeof later, 0) != sizeof later ||
        memcmp(initial, later, sizeof later) == 0)
        _Exit(91);
    struct { unsigned char before[16], bytes[600], after[16]; } guarded;
    memset(&guarded, 0xa5, sizeof guarded);
    if (getrandom(guarded.bytes, sizeof guarded.bytes, GRND_NONBLOCK) != sizeof guarded.bytes)
        _Exit(93);
    for (size_t i = 0; i < sizeof guarded.before; ++i)
        if (guarded.before[i] != 0xa5 || guarded.after[i] != 0xa5)
            _Exit(94);
    memset(later, 0xa5, sizeof later);
    errno = 0;
    if (getrandom(later, sizeof later, 0x80000000u) != -1 || errno != EINVAL ||
        getrandom(later, 0, 0) != 0)
        _Exit(95);
    for (size_t i = 0; i < sizeof later; ++i)
        if (later[i] != 0xa5)
            _Exit(96);
    static const char record[] = "OK_STATIC_ENTROPY auxv=pass getrandom=pass\n";
    if (write(1, record, sizeof record - 1) != sizeof record - 1)
        _Exit(92);
    return 0;
}
