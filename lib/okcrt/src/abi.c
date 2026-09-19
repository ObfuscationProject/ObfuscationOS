#include <stdint.h>
#include <stddef.h>

_Static_assert(sizeof(int64_t) == 8 && sizeof(uint64_t) == 8, "UAPI needs exact-width integers");
_Static_assert(sizeof(uintptr_t) == sizeof(void *), "UAPI pointers follow the native ABI");
