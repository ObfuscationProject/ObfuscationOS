#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static const char note[] = "/home/notes.txt", saved[] = "/home/saved-note.txt";
static const char discarded[] = "/home/discard.txt";
static const char first[] = "First English document.\n";
static const char updated[] = "Updated English document.\n";
static const char disposable[] = "Disposable English document.\n";

static void require(int truth, const char *operation)
{
    if (truth) return;
    dprintf(1, "OK_NOTES_FILES_WORKFLOW result=FAIL operation=%s errno=%d\n", operation, errno);
    _Exit(1);
}

static void launch(const char *path, char *const arguments[], int expected)
{
    pid_t child = fork(); require(child >= 0, "fork");
    if (!child) {
        char *environment[] = {"PATH=/bin", 0};
        execve(path, arguments, environment);
        _Exit(127);
    }
    int status;
    require(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == expected,
            "default-app-exit");
}

static void display(char *const arguments[], const char *expected)
{
    int output[2]; require(pipe2(output, O_CLOEXEC) == 0, "display-pipe");
    pid_t child = fork(); require(child >= 0, "display-fork");
    if (!child) {
        require(close(output[0]) == 0 && dup2(output[1], STDOUT_FILENO) == STDOUT_FILENO &&
                close(output[1]) == 0, "display-stdout");
        char *environment[] = {"PATH=/bin", 0};
        execve("/bin/notes", arguments, environment);
        _Exit(127);
    }
    require(close(output[1]) == 0, "display-parent-write-close");
    char bytes[128]; size_t count = 0;
    for (;;) {
        require(count < sizeof bytes, "display-output-bound");
        ssize_t size = read(output[0], bytes + count, sizeof bytes - count);
        if (size < 0 && errno == EINTR) continue;
        require(size >= 0, "display-read");
        if (!size) break;
        count += (size_t)size;
    }
    int status;
    require(close(output[0]) == 0 && waitpid(child, &status, 0) == child &&
            WIFEXITED(status) && WEXITSTATUS(status) == 0 && count == strlen(expected) &&
            !memcmp(bytes, expected, count), "default-notes-exact-display");
}

static int absent(const char *path)
{
    struct stat value; errno = 0;
    return stat(path, &value) < 0 && errno == ENOENT;
}

static struct stat descriptor(int fd, const char *text, nlink_t links)
{
    struct stat value;
    require(fstat(fd, &value) == 0 && S_ISREG(value.st_mode) && value.st_nlink == links &&
            value.st_uid == 1000 && value.st_gid == 1000 && (value.st_mode & 07777) == 0600 &&
            value.st_size == (off_t)strlen(text), "file-metadata");
    char bytes[128];
    require(pread(fd, bytes, sizeof bytes, 0) == (ssize_t)strlen(text) &&
            !memcmp(bytes, text, strlen(text)) && pread(fd, bytes, 1, strlen(text)) == 0,
            "file-exact-bytes");
    return value;
}

static struct stat reopen(const char *path, const char *text)
{
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC); require(fd >= 0, "reopen");
    struct stat value = descriptor(fd, text, 1);
    require(close(fd) == 0, "reopen-close"); return value;
}

int main(int argc, char **argv)
{
    require(argc == 1 && argv && argv[0], "explicit-first-or-restart-role");
    if (geteuid() != 1000 || getegid() != 1000)
        require(setgid(1000) == 0 && setuid(1000) == 0, "desktop-credentials");
    require(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000,
            "ordinary-desktop-user");
    struct stat parent;
    require(stat("/home", &parent) == 0 && S_ISDIR(parent.st_mode) && parent.st_uid == 1000 &&
            parent.st_gid == 1000 && (parent.st_mode & 07777) == 0700, "private-desktop-home");
    int first_boot = !strcmp(argv[0], "/init");
    require(first_boot || !strcmp(argv[0], "/./init"), "explicit-role-selector");
    if (first_boot) {
        require(absent(note) && absent(saved) && absent(discarded), "fresh-note-namespace");
        char *create[] = {"notes", (char *)note, "First English document.", 0};
        launch("/bin/notes", create, 0);
        int old = open(note, O_RDONLY | O_CLOEXEC); require(old >= 0, "retain-first-save");
        struct stat original = descriptor(old, first, 1);
        char *show_default[] = {"notes", 0}; display(show_default, first);
        char *replace[] = {"notes", (char *)note, "Updated English document.", 0};
        launch("/bin/notes", replace, 0);
        struct stat current = reopen(note, updated), retained = descriptor(old, first, 0);
        require(original.st_ino == retained.st_ino && original.st_ino != current.st_ino,
                "atomic-replacement-retained-old-description");
        require(close(old) == 0, "last-old-description-reclaim");
        char *move[] = {"mv", (char *)note, (char *)saved, 0}; launch("/bin/mv", move, 0);
        struct stat moved = reopen(saved, updated);
        require(moved.st_ino == current.st_ino && absent(note), "durable-rename-identity");
        char *extra[] = {"notes", (char *)discarded, "Disposable English document.", 0};
        launch("/bin/notes", extra, 0);
        int removed = open(discarded, O_RDONLY | O_CLOEXEC); require(removed >= 0, "retain-removal");
        struct stat before = descriptor(removed, disposable, 1);
        char *remove[] = {"rm", (char *)discarded, 0}; launch("/bin/rm", remove, 0);
        require(absent(discarded), "durable-remove-namespace");
        struct stat after = descriptor(removed, disposable, 0);
        require(before.st_ino == after.st_ino && close(removed) == 0, "last-removed-description-reclaim");
    } else {
        require(absent(note) && absent(discarded), "restart-namespace");
    }
    (void)reopen(saved, updated);
    char *show[] = {"notes", (char *)saved, 0}; display(show, updated);
    char *information[] = {"stat", (char *)saved, 0}; launch("/bin/stat", information, 0);
    char *missing[] = {"notes", (char *)note, 0}; launch("/bin/notes", missing, 1);
    /* No fixture-side fsync compensates for missing sync in the applications.
       The separately composed provider must drain, seal and attest its root. */
    const char *marker = first_boot ?
        "OK_NOTES_FILES_WORKFLOW result=pass stage=first save=pass replacement=pass old_descriptor=pass rename=pass removal=pass reopen=pass namespace=pass\n" :
        "OK_NOTES_FILES_WORKFLOW result=pass stage=restart content=pass reopen=pass namespace=pass user_mutation=none\n";
    require(write(1, marker, strlen(marker)) == (ssize_t)strlen(marker), "completion-marker");
    return 0;
}
