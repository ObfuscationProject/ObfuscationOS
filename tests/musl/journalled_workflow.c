#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static const char *const original = "/home/workflow-first.txt";
static const char *const final = "/home/workflow.txt";
static const char expected[] = "Basic English journalled workflow\n";

static void failed(const char *operation)
{
    char buffer[160];
    int size = snprintf(buffer, sizeof buffer,
                        "OK_JOURNALLED_WORKFLOW result=FAIL operation=%s errno=%d\n",
                        operation, errno);
    if (size > 0 && (size_t)size < sizeof buffer)
        (void)write(1, buffer, (size_t)size);
    _Exit(1);
}

static void require(int truth, const char *operation)
{
    if (!truth) failed(operation);
}

static void launch(const char *path, char *const arguments[], const char *operation)
{
    pid_t child = fork();
    require(child >= 0, "fork");
    if (!child) {
        char *environment[] = {"PATH=/bin", 0};
        execve(path, arguments, environment);
        failed("exec");
    }
    int status;
    require(waitpid(child, &status, 0) == child && WIFEXITED(status) &&
            WEXITSTATUS(status) == 0, operation);
}

static int absent(const char *path)
{
    struct stat metadata;
    errno = 0;
    return stat(path, &metadata) == -1 && errno == ENOENT;
}

static struct stat verify_file(const char *path)
{
    struct stat metadata;
    require(stat(path, &metadata) == 0 && S_ISREG(metadata.st_mode) &&
            metadata.st_nlink == 1 && metadata.st_uid == geteuid() &&
            metadata.st_gid == getegid() && metadata.st_size == sizeof expected - 1,
            "file-metadata");
    char content[sizeof expected + 1] = {0};
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    require(fd >= 0, "reopen");
    size_t offset = 0;
    for (;;) {
        ssize_t size = read(fd, content + offset, sizeof content - offset);
        if (size < 0 && errno == EINTR) continue;
        require(size >= 0, "read");
        if (!size) break;
        offset += (size_t)size;
        require(offset < sizeof content, "file-length");
    }
    require(close(fd) == 0 && offset == sizeof expected - 1 &&
            memcmp(content, expected, offset) == 0, "file-content");
    return metadata;
}

int main(void)
{
    struct stat metadata;
    /* The selected disk profile gives /home to the ordinary desktop user.
       Exercise the native credential transition instead of relaxing Notes'
       same-owner save checks to make a privileged bootstrap pass. */
    require(setgid(1000) == 0 && setuid(1000) == 0 &&
            geteuid() == 1000 && getegid() == 1000, "desktop-credentials");
    errno = 0;
    int first = stat(final, &metadata) < 0;
    if (first) {
        require(errno == ENOENT && absent(original),
                "fresh-namespace");
        char *save[] = {"notes", (char *)original, "Basic", "English",
                        "journalled", "workflow", 0};
        launch("/bin/notes", save, "notes-save");
        struct stat before = verify_file(original);
        char *show[] = {"notes", (char *)original, 0};
        launch("/bin/notes", show, "notes-reopen");
        char *move[] = {"mv", (char *)original, (char *)final, 0};
        launch("/bin/mv", move, "file-rename");
        struct stat after = verify_file(final);
        require(before.st_ino == after.st_ino && absent(original), "rename-identity");
    } else {
        (void)verify_file(final);
        require(absent(original), "restart-namespace");
        char *show[] = {"notes", (char *)final, 0};
        launch("/bin/notes", show, "restart-notes-reopen");
    }
    char *information[] = {"stat", (char *)final, 0};
    launch("/bin/stat", information, "file-stat");
    struct stat retained = verify_file(final);
    errno = 0;
    require(unlink(final) == -1 && errno == ENOSYS, "unlink-refusal");
    struct stat still_present = verify_file(final);
    require(retained.st_ino == still_present.st_ino &&
            retained.st_mode == still_present.st_mode &&
            retained.st_size == still_present.st_size, "unlink-preserved-file");
    int directory = open("/home", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    require(directory >= 0 && fsync(directory) == 0 && close(directory) == 0,
            "directory-fsync");
    const char *record = first ?
        "OK_JOURNALLED_WORKFLOW result=pass stage=first notes_save=pass reopen=pass rename=pass inode=stable fsync=pass unlink=unsupported\n" :
        "OK_JOURNALLED_WORKFLOW result=pass stage=restart notes_reopen=pass content=pass namespace=pass fsync=pass unlink=unsupported\n";
    require(write(1, record, strlen(record)) == (ssize_t)strlen(record), "marker");
    /* The host preserves this flushed disk and stops QEMU after the marker.
       No clean unmount or shutdown syscall is claimed by this campaign. */
    for (;;) {
        struct timespec delay = {1, 0};
        (void)nanosleep(&delay, 0);
    }
}
