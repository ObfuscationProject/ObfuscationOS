/* Fixture-only /bin/oksh wrapper; validates production login's direct exec,
 * then preserves the same lease leader while executing the actual shell. */
#include <ok/console.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int fail(void)
{
    fputs("NATIVE_LOGIN_FIXTURE_FAIL component=session\n", stderr);
    return 1;
}

int main(int argc, char **argv, char **environment)
{
    static const char *fixed[] = {"HOME=/root", "PATH=/bin", "USER=qual_admin", "LOGNAME=qual_admin"};
    char cwd[16];
    uid_t real_uid, effective_uid, saved_uid;
    gid_t real_gid, effective_gid, saved_gid;
    uint32_t epoch = 0;
    if (argc != 1 || strcmp(argv[0], "/bin/oksh") || getpid() <= 1 || getppid() != 1 ||
        getresuid(&real_uid, &effective_uid, &saved_uid) < 0 ||
        getresgid(&real_gid, &effective_gid, &saved_gid) < 0 ||
        real_uid || effective_uid || saved_uid || real_gid || effective_gid || saved_gid ||
        !getcwd(cwd, sizeof(cwd)) || strcmp(cwd, "/root")) return fail();
    for (size_t i = 0; i < 4; ++i)
        if (!environment[i] || strcmp(environment[i], fixed[i])) return fail();
    if (!environment[4] || environment[5] || strncmp(environment[4], "OK_CONSOLE_EPOCH=", 17)) return fail();
    const char *digits = environment[4] + 17;
    if (*digits < '1' || *digits > '9') return fail();
    for (; *digits; ++digits) {
        if (*digits < '0' || *digits > '9' || epoch > (0x3fffffffU - (unsigned)(*digits - '0')) / 10U) return fail();
        epoch = epoch * 10U + (unsigned)(*digits - '0');
    }
    if (ok_console_flush(epoch) < 0) return fail();
    printf("NATIVE_LOGIN_SESSION pid=%d ppid=1 uid=0 gid=0 epoch=%u user=qual_admin home=/root\n", getpid(), epoch);
    char *shell[] = {"/bin/oksh-real", 0};
    execve(shell[0], shell, environment);
    return fail();
}
