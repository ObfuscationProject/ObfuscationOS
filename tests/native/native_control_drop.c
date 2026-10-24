#include "native_fixture_record.h"

/* Native-only control helper; all six IDs are checked before native exec. */
int main(void)
{
    uid_t users[3] = {0}; gid_t groups[3] = {0};
    if (getuid() || geteuid() || setresgid(1000, 1000, 1000) || setresuid(1000, 1000, 1000) ||
        getresuid(users, users + 1, users + 2) || getresgid(groups, groups + 1, groups + 2) ||
        users[0] != 1000 || users[1] != 1000 || users[2] != 1000 ||
        groups[0] != 1000 || groups[1] != 1000 || groups[2] != 1000) goto failed;
    errno = 0;
    if (setuid(0) != -1 || errno != EPERM) goto failed;
    errno = 0;
    if (setgid(0) != -1 || errno != EPERM) goto failed;
    if (nf_marker("\nNATIVE_CONTROL_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 saved=1000\n") ||
        nf_marker("NATIVE_CONTROL_NATIVE_CREDENTIALS permanent=pass regain=denied\n")) goto failed;
    char *arguments[] = {"/bin/native-init-control-probe", "denied", 0};
    char *environment[] = {"PATH=/bin", "HOME=/", 0};
    execve(arguments[0], arguments, environment);
failed:
    (void)nf_marker("NATIVE_CONTROL_FAIL code=native-credential-drop\n"); return 1;
}
