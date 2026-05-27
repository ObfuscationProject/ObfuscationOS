#include "commands.h"

#include <errno.h>
#include <fcntl.h>
#include <ok/dirent.h>
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
    struct ok_dirent entries[8];
    int fd = open(path, O_RDONLY | O_DIRECTORY);
    if (fd < 0) {
        perror(path);
        return 1;
    }

    for (;;) {
        ssize_t n = getdents(fd, entries, sizeof(entries));
        if (n == 0) {
            break;
        }
        if (n < 0) {
            perror(path);
            close(fd);
            return 1;
        }
        size_t count = (size_t)n / sizeof(entries[0]);
        for (size_t i = 0; i < count; ++i) {
            printf("%s\n", entries[i].d_name);
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
        printf("%s: type=%s size=%ld mode=%x ino=%lu\n",
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

int cmd_rm(int argc, char **argv)
{
    if (argc < 2) {
        fputs("usage: rm PATH...\n", stderr);
        return 2;
    }

    int rc = 0;
    for (int i = 1; i < argc; ++i) {
        if (unlink(argv[i]) < 0) {
            perror(argv[i]);
            rc = 1;
        }
    }
    return rc;
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

static const struct command_entry COMMANDS[] = {
    {"help", cmd_help, "list builtins"},
    {"hello", cmd_hello, "print a greeting"},
    {"echo", cmd_echo, "print arguments"},
    {"cat", cmd_cat, "print files"},
    {"ls", cmd_ls, "list a directory"},
    {"stat", cmd_stat, "show file metadata"},
    {"mkdir", cmd_mkdir, "create directories"},
    {"rm", cmd_rm, "remove files"},
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
