/* Qualification-only shell boundary; forks old readers after authentication. */
#include "native_password_rotation_authority.h"

int main(int argc, char **argv, char **environment)
{
    const char *fixed[] = {"HOME=/root", "PATH=/bin", "USER=qual_admin", "LOGNAME=qual_admin"};
    char cwd[16];
    uid_t ru, eu, su;
    gid_t rg, eg, sg;
    uint32_t epoch = 0;
    if (argc != 1 || strcmp(argv[0], "/bin/oksh") || getpid() <= 1 || getppid() != 1 ||
        getresuid(&ru, &eu, &su) < 0 || getresgid(&rg, &eg, &sg) < 0 || ru || eu || su || rg || eg || sg ||
        !getcwd(cwd, sizeof(cwd)) || strcmp(cwd, "/root")) return failure(61);
    for (unsigned i = 0; i != 4; ++i)
        if (!environment[i] || strcmp(environment[i], fixed[i])) return failure(62);
    if (!environment[4] || environment[5] || strncmp(environment[4], "OK_CONSOLE_EPOCH=", 17)) return failure(63);
    const char *digits = environment[4] + 17;
    if (*digits < '1' || *digits > '9') return failure(64);
    for (; *digits; ++digits) {
        if (*digits < '0' || *digits > '9' || epoch > (OK_CONSOLE_EPOCH_MAX - (unsigned)(*digits - '0')) / 10U)
            return failure(65);
        epoch = epoch * 10U + (unsigned)(*digits - '0');
    }
    if (ok_console_flush(epoch) < 0 || rotation_record("SESSION", epoch)) return failure(66);
    int first = exists(FIRST_PATH);
    if (first < 0) return failure(67);
    if (!first) return first_console(epoch);
    uint32_t active = 0;
    if (exists(DONE_PATH) != 1 || active_epoch(&active) || active != epoch || rotation_wait(1)) return failure(68);
    char *shell[] = {"/bin/oksh-real", 0};
    execve(shell[0], shell, environment);
    return failure(69);
}
