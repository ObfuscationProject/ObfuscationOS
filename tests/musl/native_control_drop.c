#define _GNU_SOURCE
#include <unistd.h>

/* Test-only Linux-personality bridge retained for the separate Linux credential
 * inheritance lane. Native credential mutation uses a different native helper. */
int main(void)
{
    uid_t users[3] = {0}; gid_t groups[3] = {0};
    if (getuid() || geteuid() || setresgid(1000, 1000, 1000) || setresuid(1000, 1000, 1000) ||
        getresuid(users, users + 1, users + 2) || getresgid(groups, groups + 1, groups + 2) ||
        users[0] != 1000 || users[1] != 1000 || users[2] != 1000 ||
        groups[0] != 1000 || groups[1] != 1000 || groups[2] != 1000) goto failed;
    static const char record[] = "\nNATIVE_CONTROL_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 saved=1000\n";
    if (write(1, record, sizeof(record) - 1) != sizeof(record) - 1) goto failed;
    char *arguments[] = {"/bin/native-init-control-probe", "denied", 0};
    char *environment[] = {"PATH=/bin", "HOME=/", 0};
    execve(arguments[0], arguments, environment);
failed:;
    static const char failure[] = "NATIVE_CONTROL_FAIL code=credential-drop\n";
    (void)write(1, failure, sizeof(failure) - 1); return 1;
}
