#include "commands.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

extern pid_t hosted_shell_pid;

static int echo(int argc, char **argv)
{
    for (int i = 1; i < argc; ++i) {
        if (i > 1) putchar(' ');
        fputs(argv[i], stdout);
    }
    return putchar('\n') == EOF;
}
static int help(int argc, char **argv)
{
    (void)argc; (void)argv;
    if (getenv("OKSH_CHECK_BUILTIN_FDS") && getpid() != hosted_shell_pid)
        for (int fd = 3; fd < 64; ++fd)
            if (fcntl(fd, F_GETFD) >= 0) return 125;
    return fputs("hosted echo/help fixture\n", stdout) < 0;
}
const struct command_entry *find_command(const char *name)
{
    static const struct command_entry commands[] = {{"echo", echo, ""}, {"help", help, ""}};
    return &commands[strcmp(name, "echo") != 0];
}
