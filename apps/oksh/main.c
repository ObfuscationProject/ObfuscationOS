#include "commands.h"

#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
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

static void execute(char **args)
{
    if (strcmp(args[0], "echo") == 0 || strcmp(args[0], "help") == 0)
    {
        int argc = 0;
        while (args[argc])
            ++argc;
        _Exit(find_command(args[0])->run(argc, args));
    }
    char path[128];
    if (strchr(args[0], '/'))
    {
        if (strlen(args[0]) >= sizeof(path))
            _Exit(127);
        strcpy(path, args[0]);
    }
    else
    {
        if (strlen(args[0]) + 6 >= sizeof(path))
            _Exit(127);
        strcpy(path, "/bin/");
        strcpy(path + 5, args[0]);
    }
    char *env[] = {"PATH=/bin", 0};
    execve(path, args, env);
    perror(path);
    _Exit(127);
}

static int run_line(char *line)
{
    char *args[ARGV_MAX];
    int nargs = split_line(line, args, ARGV_MAX);
    if (!nargs)
        return 0;
    int split = -1;
    for (int i = 0; i < nargs; ++i)
    {
        if (strcmp(args[i], "|") == 0)
        {
            if (split >= 0 || i == 0 || i + 1 == nargs)
            {
                fputs("oksh: expected one command on each side of |\n", stderr);
                return 2;
            }
            split = i;
        }
    }
    if (split < 0 && strcmp(args[0], "cd") == 0)
        return chdir(nargs > 1 ? args[1] : "/");
    if (split < 0 && (strcmp(args[0], "help") == 0 || strcmp(args[0], "echo") == 0))
    {
        const struct command_entry *cmd = find_command(args[0]);
        return cmd->run(nargs, args);
    }
    int fds[2];
    if (split >= 0)
    {
        args[split] = 0;
        if (pipe(fds) != 0)
        {
            perror("pipe");
            return 1;
        }
    }
    pid_t left = fork();
    if (left < 0)
    {
        if (split >= 0)
        {
            close(fds[0]);
            close(fds[1]);
        }
        perror("fork");
        return 1;
    }
    if (left == 0)
    {
        if (split >= 0)
        {
            dup2(fds[1], 1);
            close(fds[0]);
            close(fds[1]);
        }
        execute(args);
    }
    pid_t right = -1;
    if (split >= 0)
    {
        right = fork();
        if (right == 0)
        {
            dup2(fds[0], 0);
            close(fds[0]);
            close(fds[1]);
            execute(args + split + 1);
        }
        close(fds[0]);
        close(fds[1]);
    }
    int status = 0;
    if (waitpid(left, &status, 0) < 0)
        return 1;
    if (split >= 0 && (right < 0 || waitpid(right, &status, 0) < 0))
        return 1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128;
}

int main(int argc, char **argv)
{
    char line[LINE_MAX];
    if (argc == 3 && strcmp(argv[1], "-c") == 0)
    {
        if (strlen(argv[2]) >= sizeof(line))
            return 2;
        strcpy(line, argv[2]);
        return run_line(line);
    }
    puts("oksh: commands run as user processes; use | to connect two programs");
    for (;;) {
        fputs("oksh> ", stdout);
        int status = read_line(line, sizeof(line));
        if (status == 0)
            return 0;
        if (status < 0)
        {
            perror("read");
            return 1;
        }
        if (strcmp(line, "exit") == 0)
            return 0;
        (void)run_line(line);
    }
}
