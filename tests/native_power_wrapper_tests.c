/* Actual okcrt power/errno marshalling with a hosted syscall6 capture seam. */
#include <ok/power.h>
#include <ok/syscall.h>
#include <errno.h>

static long selected, argument, response, reserved_nonzero;
static unsigned calls;
long ok_syscall6(long number, long value, long a1, long a2, long a3, long a4, long a5)
{
    ++calls; selected = number; argument = value;
    reserved_nonzero |= a1 | a2 | a3 | a4 | a5;
    return response;
}
#define CHECK(value) do { if (!(value)) return __LINE__; } while (0)
int main(void)
{
    const uint32_t valid[] = {1, OK_POWER_TOKEN_MAX};
    const uint32_t actions[] = {OK_POWER_HALT, OK_POWER_REBOOT};
    for (unsigned action = 0; action < sizeof(actions) / sizeof(actions[0]); ++action) {
        for (unsigned i = 0; i < sizeof(valid) / sizeof(valid[0]); ++i) {
            response = valid[i]; errno = 73;
            CHECK(ok_power_prepare(actions[action]) == (int)valid[i]);
            CHECK(selected == 1032 && argument == actions[action] && errno == 73);
            response = 0; errno = 73;
            CHECK(ok_power_commit(valid[i]) == 0);
            CHECK(selected == 1033 && argument == valid[i] && errno == 73);
        }
    }
    const int errors[] = {EPERM, EIO, EBUSY, EINVAL, ENOSYS, EOVERFLOW, EOPNOTSUPP};
    for (unsigned i = 0; i < sizeof(errors) / sizeof(errors[0]); ++i) {
        response = -errors[i]; errno = 0;
        CHECK(ok_power_prepare(OK_POWER_REBOOT) == -1 && errno == errors[i]);
        CHECK(selected == 1032 && argument == OK_POWER_REBOOT);
        errno = 0;
        CHECK(ok_power_commit(1) == -1 && errno == errors[i]);
        CHECK(selected == 1033 && argument == 1);
    }
    const uint32_t malformed[] = {0, 4, OK_POWER_TOKEN_MAX + 1U, UINT32_MAX};
    for (unsigned i = 0; i < sizeof(malformed) / sizeof(malformed[0]); ++i) {
        response = -EINVAL; errno = 0;
        unsigned before = calls;
        CHECK(ok_power_prepare(malformed[i]) == -1 && errno == EINVAL);
        CHECK(calls == before + 1 && selected == 1032 && argument == (long)malformed[i]);
        CHECK(ok_power_commit(malformed[i]) == -1 && errno == EINVAL);
        CHECK(calls == before + 2 && selected == 1033 && argument == (long)malformed[i]);
    }
    response = 0; errno = 0;
    CHECK(ok_power_prepare(OK_POWER_HALT) == -1 && errno == EIO);
    response = OK_POWER_TOKEN_MAX + 1L; errno = 0;
    CHECK(ok_power_prepare(OK_POWER_HALT) == -1 && errno == EIO);
    response = 1; errno = 0;
    CHECK(ok_power_commit(1) == -1 && errno == EIO);
    CHECK(!reserved_nonzero);
    return 0;
}
