#define _POSIX_C_SOURCE 200809L
#include "commands.h"

#include <errno.h>
#include <fcntl.h>
#include <ok/dirent.h>
#include <ok/syscall.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int copy_fd(int fd)
{
    char buf[512];
    for (;;) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n == 0) {
            return 0;
        }
        if (n < 0) {
            perror("read");
            return 1;
        }
        ssize_t off = 0;
        while (off < n) {
            ssize_t w = write(STDOUT_FILENO, buf + off, (size_t)(n - off));
            if (w < 0) {
                perror("write");
                return 1;
            }
            off += w;
        }
    }
}

int cmd_hello(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    puts("hello from ObfuscationOS userland");
    return 0;
}

int cmd_cat(int argc, char **argv)
{
    if (argc == 1) {
        return copy_fd(STDIN_FILENO);
    }

    int rc = 0;
    for (int i = 1; i < argc; ++i) {
        int fd = open(argv[i], O_RDONLY);
        if (fd < 0) {
            perror(argv[i]);
            rc = 1;
            continue;
        }
        if (copy_fd(fd) != 0) {
            rc = 1;
        }
        close(fd);
    }
    return rc;
}

static int list_dir(const char *path)
{
    _Alignas(8) unsigned char buffer[512];
    int fd = open(path, O_RDONLY | O_DIRECTORY);
    if (fd < 0) {
        perror(path);
        return 1;
    }

    for (;;) {
        ssize_t n = getdents64(fd, buffer, sizeof(buffer));
        if (n == 0) {
            break;
        }
        if (n < 0) {
            perror(path);
            close(fd);
            return 1;
        }
        size_t offset = 0;
        while (offset < (size_t)n) {
            struct dirent *entry = (struct dirent *)(buffer + offset);
            if (entry->d_reclen == 0) {
                break;
            }
            printf("%s\n", entry->d_name);
            offset += entry->d_reclen;
        }
    }

    close(fd);
    return 0;
}

int cmd_ls(int argc, char **argv)
{
    if (argc == 1) {
        return list_dir(".");
    }

    int rc = 0;
    for (int i = 1; i < argc; ++i) {
        if (argc > 2) {
            printf("%s:\n", argv[i]);
        }
        if (list_dir(argv[i]) != 0) {
            rc = 1;
        }
    }
    return rc;
}

static const char *file_type(mode_t mode)
{
    if (S_ISDIR(mode)) {
        return "directory";
    }
    if (S_ISREG(mode)) {
        return "file";
    }
    return "unknown";
}

int cmd_stat(int argc, char **argv)
{
    if (argc < 2) {
        fputs("usage: stat PATH...\n", stderr);
        return 2;
    }

    int rc = 0;
    for (int i = 1; i < argc; ++i) {
        struct stat st;
        if (stat(argv[i], &st) < 0) {
            perror(argv[i]);
            rc = 1;
            continue;
        }
        printf("%s: type=%s size=%ld mode=%lx ino=%lu\n",
               argv[i],
               file_type(st.st_mode),
               (long)st.st_size,
               (unsigned long)st.st_mode,
               (unsigned long)st.st_ino);
    }
    return rc;
}

int cmd_mkdir(int argc, char **argv)
{
    if (argc < 2) {
        fputs("usage: mkdir PATH...\n", stderr);
        return 2;
    }

    int rc = 0;
    for (int i = 1; i < argc; ++i) {
        if (mkdir(argv[i], S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH) < 0) {
            perror(argv[i]);
            rc = 1;
        }
    }
    return rc;
}

struct command_parent_path {
    char parent[256];
    const char *leaf;
};

/* Keep namespace operations attached to the directories that were opened.
   The trailing slash is retained on the leaf so directory-only semantics do
   not become a rename/removal of a regular file. */
static int command_parent(const char *path, struct command_parent_path *value)
{
    if (!path || !*path) {
        errno = EINVAL;
        return -1;
    }
    size_t length = strlen(path);
    if (length >= sizeof value->parent) {
        errno = ENAMETOOLONG;
        return -1;
    }
    size_t end = length;
    while (end && path[end - 1] == '/')
        --end;
    if (!end) {
        errno = EINVAL;
        return -1;
    }
    size_t separator = end;
    while (separator && path[separator - 1] != '/')
        --separator;
    size_t leaf_length = end - separator;
    if ((leaf_length == 1 && path[separator] == '.') ||
        (leaf_length == 2 && path[separator] == '.' && path[separator + 1] == '.')) {
        errno = EINVAL;
        return -1;
    }
    value->leaf = path + separator;
    if (!separator) {
        memcpy(value->parent, ".", 2);
    } else {
        size_t parent_length = separator == 1 ? 1 : separator - 1;
        memcpy(value->parent, path, parent_length);
        value->parent[parent_length] = 0;
    }
    return 0;
}

static void completion_error(int result, int *error)
{
    if (result < 0 && !*error)
        *error = errno;
}

/* -1: no namespace commit; 1: committed but sync/close failed; 0: complete.
   Failed close consumes the descriptor and is never retried. */
static int durable_move(const char *source, const char *destination)
{
    struct command_parent_path from, to;
    if (command_parent(source, &from) < 0 || command_parent(destination, &to) < 0)
        return -1;
    int fromfd = open(from.parent, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fromfd < 0) {
        int error = errno;
        /* Search/write permission may permit rename without directory read
           permission. Preserve that operation, but never attest missing sync. */
        if (error == EACCES && rename(source, destination) == 0) {
            errno = error;
            return 1;
        }
        return -1;
    }
    int tofd = fromfd;
    if (strcmp(from.parent, to.parent)) {
        tofd = open(to.parent, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
        if (tofd < 0) {
            int error = errno;
            if (error == EACCES) {
                int result = renameat(fromfd, from.leaf, AT_FDCWD, destination);
                int operation_error = errno;
                if (result == 0)
                    (void)fsync(fromfd);
                (void)close(fromfd);
                errno = result < 0 ? operation_error : error;
                return result < 0 ? -1 : 1;
            }
            (void)close(fromfd);
            errno = error;
            return -1;
        }
    }
    if (renameat(fromfd, from.leaf, tofd, to.leaf) < 0) {
        int error = errno;
        if (tofd != fromfd)
            (void)close(tofd);
        (void)close(fromfd);
        errno = error;
        return -1;
    }
    int error = 0;
    completion_error(fsync(tofd), &error);
    if (tofd != fromfd) {
        completion_error(fsync(fromfd), &error);
        completion_error(close(tofd), &error);
    }
    completion_error(close(fromfd), &error);
    if (error) {
        errno = error;
        return 1;
    }
    return 0;
}

static int durable_remove(const char *path)
{
    struct command_parent_path value;
    if (command_parent(path, &value) < 0)
        return -1;
    int directory = open(value.parent, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (directory < 0) {
        int error = errno;
        if (error == EACCES && unlink(path) == 0) {
            errno = error;
            return 1;
        }
        return -1;
    }
    if (unlinkat(directory, value.leaf, 0) < 0) {
        int error = errno;
        (void)close(directory);
        errno = error;
        return -1;
    }
    int error = 0;
    completion_error(fsync(directory), &error);
    completion_error(close(directory), &error);
    if (error) {
        errno = error;
        return 1;
    }
    return 0;
}

int cmd_rm(int argc, char **argv)
{
    if (argc < 2) {
        fputs("usage: rm PATH...\n", stderr);
        return 2;
    }

    int rc = 0;
    for (int i = 1; i < argc; ++i) {
        int result = durable_remove(argv[i]);
        if (result) {
            int error = errno;
            if (result > 0)
                fputs("File removed; removal completion failed.\n", stderr);
            errno = error;
            perror(argv[i]);
            rc = 1;
        }
    }
    return rc;
}

int cmd_mv(int argc, char **argv)
{
    if (argc != 3) {
        fputs("usage: mv SOURCE DEST\n", stderr);
        return 2;
    }
    int result = durable_move(argv[1], argv[2]);
    if (result) {
        int error = errno;
        if (result > 0)
            fputs("File moved; move completion failed.\n", stderr);
        errno = error;
        perror("mv");
        return 1;
    }
    return 0;
}

int cmd_ln(int argc, char **argv)
{
    const int symbolic = argc == 4 && strcmp(argv[1], "-s") == 0;
    if (argc != 3 && !symbolic) {
        fputs("usage: ln [-s] SOURCE DEST\n", stderr);
        return 2;
    }
    if ((symbolic ? symlink(argv[2], argv[3]) : link(argv[1], argv[2])) < 0) {
        perror("ln");
        return 1;
    }
    return 0;
}

int cmd_echo(int argc, char **argv)
{
    for (int i = 1; i < argc; ++i) {
        if (i > 1) {
            putchar(' ');
        }
        fputs(argv[i], stdout);
    }
    putchar('\n');
    return 0;
}

int cmd_pwd(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    char cwd[256];
    if (!getcwd(cwd, sizeof(cwd))) {
        perror("pwd");
        return 1;
    }
    puts(cwd);
    return 0;
}

int cmd_cd(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "/";
    if (chdir(path) < 0) {
        perror(path);
        return 1;
    }
    return 0;
}

int cmd_whoami(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    uid_t uid = geteuid();
    if (uid == 0) {
        puts("root");
    } else {
        printf("uid%u\n", (unsigned)uid);
    }
    return 0;
}

int cmd_uname(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    puts("ObfuscationOS");
    return 0;
}

int cmd_uptime(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    long seconds = ok_syscall_ret(ok_syscall1(OK_SYS_TIME, 0));
    if (seconds < 0) {
        perror("uptime");
        return 1;
    }
    printf("up %ld seconds\n", seconds);
    return 0;
}

int cmd_touch(int argc, char **argv)
{
    if (argc < 2) {
        fputs("usage: touch PATH...\n", stderr);
        return 2;
    }

    int rc = 0;
    for (int i = 1; i < argc; ++i) {
        int fd = open(argv[i], O_CREAT | O_WRONLY, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
        if (fd < 0) {
            perror(argv[i]);
            rc = 1;
            continue;
        }
        close(fd);
    }
    return rc;
}

static const struct command_entry COMMANDS[] = {
    {"help", cmd_help, "list builtins"},
    {"hello", cmd_hello, "print a greeting"},
    {"echo", cmd_echo, "print arguments"},
    {"cat", cmd_cat, "print files"},
    {"ls", cmd_ls, "list a directory"},
    {"stat", cmd_stat, "show file metadata"},
    {"mkdir", cmd_mkdir, "create directories"},
    {"rm", cmd_rm, "remove files"},
    {"mv", cmd_mv, "rename a path"},
    {"ln", cmd_ln, "create a hard or symbolic link"},
    {"pwd", cmd_pwd, "print working directory"},
    {"cd", cmd_cd, "change directory"},
    {"whoami", cmd_whoami, "print effective user"},
    {"uname", cmd_uname, "print system name"},
    {"uptime", cmd_uptime, "print system uptime"},
    {"touch", cmd_touch, "create empty files"},
    {0, 0, 0},
};

int cmd_help(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    for (const struct command_entry *cmd = COMMANDS; cmd->name; ++cmd) {
        printf("%s\t%s\n", cmd->name, cmd->summary);
    }
    return 0;
}

const struct command_entry *commands_table(void)
{
    return COMMANDS;
}

const struct command_entry *find_command(const char *name)
{
    for (const struct command_entry *cmd = COMMANDS; cmd->name; ++cmd) {
        if (strcmp(cmd->name, name) == 0) {
            return cmd;
        }
    }
    return 0;
}
