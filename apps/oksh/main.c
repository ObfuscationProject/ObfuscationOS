#include "commands.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define LINE_MAX 256
#define ARGV_MAX 16

static int read_line(char *line, size_t cap)
{
    size_t pos = 0;
    while (pos + 1 < cap) {
        char c;
        ssize_t n = read(STDIN_FILENO, &c, 1);
        if (n == 0) {
            if (pos == 0) {
                return 0;
            }
            break;
        }
        if (n < 0) {
            return -1;
        }
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            break;
        }
        line[pos++] = c;
    }
    line[pos] = '\0';
    return 1;
}

static int split_line(char *line, char **argv, int max_args)
{
    int argc = 0;
    char *p = line;
    while (*p && argc < max_args - 1) {
        while (*p == ' ' || *p == '\t') {
            *p++ = '\0';
        }
        if (*p == '\0') {
            break;
        }
        argv[argc++] = p;
        while (*p && *p != ' ' && *p != '\t') {
            ++p;
        }
    }
    argv[argc] = 0;
    return argc;
}

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    puts("oksh: builtins only until fork/execve are implemented");
    char line[LINE_MAX];
    char *args[ARGV_MAX];

    for (;;) {
        fputs("oksh> ", stdout);
        int status = read_line(line, sizeof(line));
        if (status == 0) {
            putchar('\n');
            return 0;
        }
        if (status < 0) {
            perror("read");
            return 1;
        }
        int nargs = split_line(line, args, ARGV_MAX);
        if (nargs == 0) {
            continue;
        }
        if (strcmp(args[0], "exit") == 0) {
            return 0;
        }
        const struct command_entry *cmd = find_command(args[0]);
        if (!cmd) {
            fprintf(stderr, "%s: command not found\n", args[0]);
            continue;
        }
        cmd->run(nargs, args);
    }
}
