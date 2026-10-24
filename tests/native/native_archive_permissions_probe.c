#include "native_fixture_record.h"
#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>

static int failure(unsigned code)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_ARCHIVE_PERMISSIONS_FAIL code="); nf_number(&record, code);
    nf_text(&record, "\n"); (void)nf_emit(&record); return (int)code;
}
static int metadata(const char *path, unsigned mode, unsigned uid, unsigned gid)
{
    struct stat st;
    return stat(path, &st) || st.st_mode != mode || st.st_uid != uid || st.st_gid != gid;
}
static int create(const char *path, unsigned uid, unsigned gid)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0) return -1;
    int failed = write(fd, "owned", 5) != 5;
    if (close(fd)) failed = 1;
    return failed || metadata(path, S_IFREG | 0600, uid, gid);
}
static int drop(unsigned id)
{
    uid_t users[3]; gid_t groups[3];
    if (setresgid(id, id, id) || setresuid(id, id, id) ||
        getresuid(users, users + 1, users + 2) || getresgid(groups, groups + 1, groups + 2)) return -1;
    for (unsigned i = 0; i != 3; ++i) if (users[i] != id || groups[i] != id) return -1;
    return 0;
}
static int denied(const char *path)
{
    errno = 0;
    return unlink(path) != -1 || errno != EPERM;
}
static int child(unsigned id)
{
    if (drop(id)) return failure(10);
    if (id == 1000) {
        if (create("/archive-sticky/victim", id, id) || create("/tmp/archive-victim", id, id)) return failure(11);
        if (create("/archive-sgid/created", id, 0) || mkdir("/archive-sgid/created-dir", 0700) ||
            metadata("/archive-sgid/created-dir", S_IFDIR | 02700, id, 0)) return failure(12);
        return nf_marker("\nNATIVE_ARCHIVE_CREATOR uid=1000 gid=1000 sticky_file_gid=1000 sgid_file_gid=0 sgid_directory_mode=02700\n")
            ? failure(13) : 0;
    }
    if (id != 1001 || denied("/archive-sticky/victim") || denied("/tmp/archive-victim") ||
        metadata("/archive-sticky/victim", S_IFREG | 0600, 1000, 1000) ||
        metadata("/tmp/archive-victim", S_IFREG | 0600, 1000, 1000)) return failure(14);
    if (create("/archive-sticky/own", id, id) || unlink("/archive-sticky/own")) return failure(15);
    return nf_marker("\nNATIVE_ARCHIVE_ATTACKER uid=1001 gid=1001 foreign_unlink=EPERM tmp_unlink=EPERM own_unlink=pass\n")
        ? failure(16) : 0;
}
static int run_child(unsigned id)
{
    pid_t pid = fork();
    if (pid < 0) return -1;
    if (!pid) _Exit(child(id));
    for (unsigned i = 0; i != 500; ++i) {
        int status = 0; pid_t result = waitpid(pid, &status, WNOHANG);
        if (result == pid) {
            if (!WIFEXITED(status) || WEXITSTATUS(status)) return -1;
            struct native_fixture_record record = {0};
            nf_text(&record, "\nNATIVE_ARCHIVE_REAP child="); nf_number(&record, (unsigned)pid);
            nf_text(&record, " uid="); nf_number(&record, id); nf_text(&record, " raw_status=0\n");
            return nf_emit(&record);
        }
        if (result < 0 && errno != EINTR) return -1;
        const struct timespec pause = {0, 10000000}; (void)nanosleep(&pause, 0);
    }
    (void)kill(pid, SIGKILL); (void)waitpid(pid, 0, 0); return -1;
}
int main(void)
{
    if (getuid() || geteuid() || getgid() || getegid() || getppid() != 1) return failure(1);
    if (metadata("/tmp", S_IFDIR | 01777, 0, 0) ||
        metadata("/archive-sticky", S_IFDIR | 01777, 0, 0) ||
        metadata("/archive-sgid", S_IFDIR | 02777, 0, 0) ||
        metadata("/archive-sgid/imported", S_IFDIR | 0755, 0, 0) ||
        metadata("/archive-sgid/imported-file", S_IFREG | 0444, 0, 0)) return failure(2);
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_ARCHIVE_METADATA pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " parent=1 tmp=01777 sticky=01777 sgid=02777 imported=0755 regular=0444 uid=0 gid=0\n");
    if (nf_emit(&record)) return failure(3);
    if (run_child(1000) || run_child(1001)) return failure(4);
    if (metadata("/archive-sticky/victim", S_IFREG | 0600, 1000, 1000) ||
        metadata("/tmp/archive-victim", S_IFREG | 0600, 1000, 1000) ||
        metadata("/archive-sgid/created", S_IFREG | 0600, 1000, 0) ||
        metadata("/archive-sgid/created-dir", S_IFDIR | 02700, 1000, 0)) return failure(5);
    if (unlink("/archive-sticky/victim") || unlink("/tmp/archive-victim") ||
        unlink("/archive-sgid/created") || rmdir("/archive-sgid/created-dir")) return failure(6);
    return nf_marker("\nNATIVE_ARCHIVE_PERMISSIONS_PASS archive=1 exact_modes=pass root_ownership=pass sticky=pass sgid_create=pass imported_no_inherit=pass actual_child_reap=pass\n")
        ? failure(7) : 0;
}
