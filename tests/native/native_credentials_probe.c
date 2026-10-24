#include "native_fixture_record.h"
#include <fcntl.h>
#include <ok/syscall.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>

#define PRIVATE_PATH "/run/native-credentials-private"
/* Qualification pin: the exported SDK's native descriptor table has 32 slots.
 * Query the native resource contract as well, so a changed bound fails closed. */
#define LOGIN_FD_CAPACITY 32
#define LOGIN_NOFILE_RESOURCE 7
static int failure(unsigned code)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "NATIVE_CREDENTIALS_FAIL code="); nf_number(&record, code); nf_text(&record, "\n");
    (void)nf_emit(&record); return (int)code;
}
static int ids(uid_t real, uid_t effective, uid_t saved, gid_t group)
{
    uid_t users[3] = {0}; gid_t groups[3] = {0};
    return getresuid(users, users + 1, users + 2) || getresgid(groups, groups + 1, groups + 2) ||
        users[0] != real || users[1] != effective || users[2] != saved ||
        groups[0] != group || groups[1] != group || groups[2] != group ||
        getuid() != real || geteuid() != effective || getgid() != group || getegid() != group;
}
static int cannot_regain(void)
{
    errno = 0;
    if (setuid(0) != -1 || errno != EPERM) return -1;
    errno = 0;
    if (setgid(0) != -1 || errno != EPERM) return -1;
    errno = 0;
    if (setresuid(1000, 0, 1000) != -1 || errno != EPERM) return -1;
    errno = 0;
    if (setresgid(1000, 0, 1000) != -1 || errno != EPERM) return -1;
    return ids(1000, 1000, 1000, 1000);
}
static int private_denied(void)
{
    errno = 0;
    int fd = open(PRIVATE_PATH, O_RDONLY);
    if (fd >= 0) { (void)close(fd); return -1; }
    return errno == EACCES ? 0 : -1;
}
static int wait_child(pid_t child)
{
    for (unsigned i = 0; i < 500; ++i) {
        int status = 0; pid_t result = waitpid(child, &status, WNOHANG);
        if (result == child) return WIFEXITED(status) && !WEXITSTATUS(status) ? 0 : -1;
        if (result < 0 && errno != EINTR) return -1;
        const struct timespec delay = {0, 10000000}; (void)nanosleep(&delay, 0);
    }
    (void)kill(child, SIGKILL); (void)waitpid(child, 0, 0); return -1;
}
static int exec_child(int reversible)
{
    pid_t child = fork();
    if (child < 0) return -1;
    if (!child) {
        if (ids(0, 0, 0, 0) || setresgid(1000, 1000, 1000) ||
            setresuid(1000, 1000, reversible ? 0 : 1000) ||
            ids(1000, 1000, reversible ? 0 : 1000, 1000) || private_denied()) _Exit(failure(11));
        /* A failed exec must preserve the full tuple, including saved root. */
        char *missing[] = {"/bin/credentials-does-not-exist", 0};
        char *environment[] = {"PATH=/bin", "HOME=/", 0};
        errno = 0;
        if (execve(missing[0], missing, environment) != -1 || errno != ENOENT ||
            ids(1000, 1000, reversible ? 0 : 1000, 1000)) _Exit(failure(12));
        char *arguments[] = {"/bin/native-credentials-probe", reversible ? "saved-exec" : "permanent-exec", 0};
        execve(arguments[0], arguments, environment); _Exit(failure(13));
    }
    return wait_child(child);
}
static const char *service(char **environment)
{
    static const char prefix[] = "OK_SERVICE_NAME=";
    for (; *environment; ++environment)
        if (!strncmp(*environment, prefix, sizeof(prefix) - 1)) return *environment + sizeof(prefix) - 1;
    return 0;
}
static int registry_denied(const char *path)
{
    errno = 0;
    int descriptor = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (descriptor >= 0) { (void)close(descriptor); return -1; }
    return errno == EACCES ? 0 : -1;
}
static int login_descriptors(void)
{
    struct ok_rlimit limit = {0};
    if (ok_syscall_ret(ok_syscall6(OK_SYS_GETRLIMIT, LOGIN_NOFILE_RESOURCE,
            (long)&limit, 0, 0, 0, 0)) != 0 ||
        limit.current != LOGIN_FD_CAPACITY || limit.maximum != LOGIN_FD_CAPACITY) return -1;
    for (int descriptor = 0; descriptor < 3; ++descriptor) {
        struct stat info;
        int expected = descriptor ? O_WRONLY : O_RDONLY;
        if (fcntl(descriptor, F_GETFD) != 0 || fcntl(descriptor, F_GETFL) != expected ||
            fstat(descriptor, &info) < 0 ||
            (info.st_mode & S_IFMT) != OK_MODE_CHARACTER_DEVICE ||
            (info.st_mode & 07777) != 0600 || info.st_uid || info.st_gid ||
            info.st_size || info.st_nlink != 1) return -1;
    }
    for (int descriptor = 3; descriptor < LOGIN_FD_CAPACITY; ++descriptor) {
        errno = 0;
        if (fcntl(descriptor, F_GETFD) != -1 || errno != EBADF) return -1;
    }
    return 0;
}
static unsigned login_checks(void)
{
    if (ids(1000, 1000, 1000, 1000)) return 20;
    if (cannot_regain()) return 21;
    if (login_descriptors()) return 22;
    if (registry_denied("/etc/accounts.db")) return 23;
    if (registry_denied("/etc/users.db")) return 24;
    return 0;
}
static int login_marker(const char *phase)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_LOGIN_SESSION phase="); nf_text(&record, phase);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " ppid="); nf_number(&record, (unsigned)getppid());
    nf_text(&record, " ruid=1000 euid=1000 suid=1000 rgid=1000 egid=1000 sgid=1000");
    nf_text(&record, " regain=denied accounts=denied users=denied private_fds=none fd_limit=32\n");
    return nf_emit(&record);
}
static int login_session(char **environment, int descendant)
{
    unsigned code = login_checks();
    if (code) return failure(code);
    if (descendant) return login_marker("exec") ? failure(25) : 0;
    pid_t child = fork();
    if (child < 0) return failure(26);
    if (!child) {
        code = login_checks();
        if (code) _Exit(failure(code));
        if (login_marker("fork")) _Exit(failure(27));
        char *arguments[] = {"/bin/native-credentials-probe", "login-session", "exec", 0};
        execve(arguments[0], arguments, environment);
        _Exit(failure(28));
    }
    if (wait_child(child)) return failure(29);
    code = login_checks();
    if (code) return failure(code);
    if (login_marker("parent")) return failure(30);
    return nf_marker("\nNATIVE_LOGIN_SESSION_PASS native=1 uid=1000 gid=1000 all_six_ids=pass regain=denied registries=denied private_fds=none fork=pass exec=pass\n")
        ? failure(31) : 0;
}
int main(int argc, char **argv, char **environment)
{
    const char *name = service(environment);
    if (name && !strcmp(name, "identity")) {
        if (argc != 1 || getppid() != 1 || cannot_regain()) return failure(1);
        struct native_fixture_record record = {0};
        nf_text(&record, "\nNATIVE_SERVICE_IDENTITY service=identity pid="); nf_number(&record, (unsigned)getpid());
        nf_text(&record, " uid=1000 gid=1000 saved=1000 regain=denied\n");
        return nf_emit(&record) ? failure(2) : 0;
    }
    if (argc == 2 && !strcmp(argv[1], "login-session")) return login_session(environment, 0);
    if (argc == 3 && !strcmp(argv[1], "login-session") && !strcmp(argv[2], "exec"))
        return login_session(environment, 1);
    if (argc == 2 && (!strcmp(argv[1], "saved-exec") || !strcmp(argv[1], "permanent-exec"))) {
        if (cannot_regain() || private_denied()) return failure(3);
        if (nf_marker(!strcmp(argv[1], "saved-exec")
            ? "\nNATIVE_CREDENTIALS_EXEC kind=saved reset=pass regain=denied\n"
            : "\nNATIVE_CREDENTIALS_EXEC kind=permanent inherited=pass regain=denied\n")) return failure(4);
        return 0;
    }
    if (argc != 1 || ids(0, 0, 0, 0)) return failure(5);
    /* Exercise temporary restoration and unsigned IDs without losing root. */
    if (setresgid(4294967293U, 4294967293U, 4294967293U) ||
        setresuid(4294967294U, 4294967294U, 0) ||
        ids(4294967294U, 4294967294U, 0, 4294967293U) || setuid(0) ||
        ids(4294967294U, 0, 0, 4294967293U) || setresuid(0, 0, 0) || setgid(0) || ids(0, 0, 0, 0))
        return failure(6);
    if (setreuid((uid_t)-1, 1000) || ids(0, 1000, 1000, 0) ||
        setreuid((uid_t)-1, 0) || ids(0, 0, 1000, 0) || setresuid(0, 0, 0) ||
        setregid((gid_t)-1, 1000) || setregid((gid_t)-1, 0) || setresgid(0, 0, 0) ||
        ids(0, 0, 0, 0)) return failure(7);
    errno = 0;
    if (setuid((uid_t)-1) != -1 || errno != EINVAL || ids(0, 0, 0, 0)) return failure(8);
    errno = 0;
    if (setgid((gid_t)-1) != -1 || errno != EINVAL || ids(0, 0, 0, 0)) return failure(9);
    int fd = open(PRIVATE_PATH, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0 || write(fd, "root-only", 9) != 9 || close(fd)) return failure(10);
    if (exec_child(0) || exec_child(1) || ids(0, 0, 0, 0) || unlink(PRIVATE_PATH)) return failure(14);
    return nf_marker("\nNATIVE_CREDENTIALS_PASS native=1 reversible=pass high_ids=pass pair=pass permanent=pass fork_exec=pass failed_exec=pass file_permissions=pass failure_atomic=pass\n")
        ? failure(15) : 0;
}
