#define _POSIX_C_SOURCE 200809L
#include "commands.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <signal.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#ifdef OKSH_HOSTED
#include <termios.h>
#endif

#define LINE_CAPACITY 1024
#define ARGUMENT_CAPACITY 32
#define PIPELINE_CAPACITY 16
#define LIST_CAPACITY 16
#define LINE_COMMAND_CAPACITY 16
#define REDIRECTION_CAPACITY 32

struct redirection {
    int target, source, flags;
    char *path;
};
struct command {
    char *argv[ARGUMENT_CAPACITY];
    int argc, first_redirection, redirections;
};
struct pipeline {
    int first_command, count, condition;
};
struct command_list {
    struct command commands[LINE_COMMAND_CAPACITY];
    struct pipeline pipelines[LIST_CAPACITY];
    struct redirection redirections[REDIRECTION_CAPACITY];
    char words[LINE_CAPACITY];
    int count, command_count, redirection_count;
};
struct lexer { const char *cursor; char *output; };
struct token { int kind, target, source, flags; char *word; };
enum { END, WORD, PIPE, REDIRECT, SEMICOLON, AND_IF, OR_IF, INVALID };

static struct { int fd, failed; pid_t sid, group; } shell_console = {.fd = -1};

static int console_finish(int status)
{
    if (shell_console.fd >= 0) {
        if (close(shell_console.fd) < 0) status = 1;
        shell_console.fd = -1;
    }
    return status;
}

static int console_prepare(void)
{
    shell_console.sid = getsid(0);
    shell_console.group = getpgrp();
    shell_console.failed = 0;
    for (int fd = 0; fd < 3; ++fd) {
        pid_t sid = tcgetsid(fd);
        if (sid < 0 && (errno == ENOTTY || errno == EBADF)) continue;
        if (sid < 0 || sid != shell_console.sid || tcgetpgrp(fd) != shell_console.group) {
            fputs("oksh: console input is not available.\n", stderr);
            return -1;
        }
        int control = fcntl(fd, F_DUPFD, 3);
        if (control < 0) { perror("oksh: console"); return -1; }
        if (fcntl(control, F_SETFD, FD_CLOEXEC) < 0) {
            int error = errno;
            close(control); errno = error;
            perror("oksh: console");
            return -1;
        }
        shell_console.fd = control;
        return 0;
    }
    return 0;
}

static int console_restore(void)
{
    if (shell_console.fd < 0) return 0;
    if (tcsetpgrp(shell_console.fd, shell_console.group) < 0 ||
        tcgetsid(shell_console.fd) != shell_console.sid ||
        tcgetpgrp(shell_console.fd) != shell_console.group) {
        shell_console.failed = 1;
        fputs("oksh: cannot restore console input.\n", stderr);
        return -1;
    }
    return 0;
}

/* Native stdio writes immediately; hosted verification uses buffered stdio. */
static void flush_streams(void)
{
#ifdef OKSH_HOSTED
    fflush(NULL);
#endif
}

/* Drain an oversized input line so its tail cannot execute as another command. */
static int read_line(char *line, size_t capacity)
{
    size_t used = 0;
    int overflow = 0;
    for (;;) {
        char c;
        ssize_t count = read(STDIN_FILENO, &c, 1);
        if (count < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (!count || c == '\n') {
            if (!count && !used && !overflow) return 0;
            line[used] = '\0';
            return overflow ? 2 : 1;
        }
        if (c == '\r') continue;
        if (used + 1 < capacity) line[used++] = c;
        else overflow = 1;
    }
}

static int special(char c)
{
    return c == '|' || c == '<' || c == '>' || c == '&' || c == ';' || c == '(' || c == ')';
}

static struct token next_token(struct lexer *lexer)
{
    struct token token = {END, -1, -1, 0, NULL};
    const char *p = lexer->cursor;
    while (*p == ' ' || *p == '\t') ++p;
    if (!*p) { lexer->cursor = p; return token; }
    if (*p == '|') {
        token.kind = p[1] == '|' ? OR_IF : PIPE;
        lexer->cursor = p + (token.kind == OR_IF ? 2 : 1);
        return token;
    }
    if (*p == '&' && p[1] == '&') {
        token.kind = AND_IF;
        lexer->cursor = p + 2;
        return token;
    }
    if (*p == ';') {
        token.kind = SEMICOLON;
        lexer->cursor = p + 1;
        return token;
    }
    const char *digits = p;
    while (*digits >= '0' && *digits <= '9') ++digits;
    if (*p == '<' || *p == '>' || (digits != p && (*digits == '<' || *digits == '>'))) {
        token.kind = REDIRECT;
        if (digits != p) {
            if (digits != p + 1 || *p > '2') { token.kind = INVALID; return token; }
            token.target = *p - '0';
            p = digits;
        } else token.target = *p == '<' ? 0 : 1;
        const char direction = *p++;
        token.flags = direction == '<' ? O_RDONLY : O_WRONLY | O_CREAT | O_TRUNC;
        if (direction == '>' && *p == '>') { ++p; token.flags = O_WRONLY | O_CREAT | O_APPEND; }
        if (*p == '&') {
            ++p;
            if ((*p < '0' || *p > '2') && *p != '-') { token.kind = INVALID; return token; }
            token.source = *p == '-' ? -2 : *p - '0';
            ++p;
            if (*p && *p != ' ' && *p != '\t' && !special(*p)) { token.kind = INVALID; return token; }
        }
        lexer->cursor = p;
        return token;
    }
    if (special(*p)) { token.kind = INVALID; return token; }
    token.kind = WORD;
    token.word = lexer->output;
    while (*p && *p != ' ' && *p != '\t' && !special(*p)) {
        if (*p == '\'' || *p == '"') {
            const char quote = *p++;
            while (*p && *p != quote) {
                if (quote == '"' && *p == '\\' && (p[1] == '\\' || p[1] == '"' || p[1] == '$' || p[1] == '`')) ++p;
                *lexer->output++ = *p++;
            }
            if (*p != quote) { token.kind = INVALID; return token; }
            ++p;
        } else {
            if (*p == '\\') {
                if (!p[1]) { token.kind = INVALID; return token; }
                ++p;
            }
            *lexer->output++ = *p++;
        }
    }
    *lexer->output++ = '\0';
    lexer->cursor = p;
    return token;
}

static int parse_line(const char *line, struct command_list *list)
{
    struct lexer lexer = {line, list->words};
    memset(list, 0, sizeof(*list));
    list->count = list->command_count = 1;
    struct pipeline *pipeline = &list->pipelines[0];
    pipeline->count = 1;
    pipeline->condition = SEMICOLON;
    struct command *command = &list->commands[0];
    int pending = END;
    for (;;) {
        struct token token = next_token(&lexer);
        if (token.kind == INVALID) return -1;
        if (pending != END) {
            /* A final semicolon is allowed, but never an empty list element. */
            if (token.kind == END && pending == SEMICOLON) return 0;
            if (token.kind != WORD && token.kind != REDIRECT) return -1;
            if (list->count == LIST_CAPACITY || list->command_count == LINE_COMMAND_CAPACITY) return -1;
            pipeline = &list->pipelines[list->count++];
            pipeline->first_command = list->command_count;
            pipeline->count = 1;
            pipeline->condition = pending;
            command = &list->commands[list->command_count++];
            command->first_redirection = list->redirection_count;
            pending = END;
        }
        if (token.kind == END || token.kind == SEMICOLON || token.kind == AND_IF || token.kind == OR_IF) {
            if (!command->argc && (pipeline->count > 1 || !command->redirections)) {
                if (token.kind == END && list->count == 1 && list->command_count == 1) {
                    list->count = 0;
                    return 0;
                }
                return -1;
            }
            if (token.kind == END) return 0;
            pending = token.kind;
            continue;
        }
        if (token.kind == PIPE) {
            if (!command->argc || pipeline->count == PIPELINE_CAPACITY ||
                list->command_count == LINE_COMMAND_CAPACITY) return -1;
            ++pipeline->count;
            command = &list->commands[list->command_count++];
            command->first_redirection = list->redirection_count;
        } else if (token.kind == WORD) {
            if (command->argc == ARGUMENT_CAPACITY - 1) return -1;
            command->argv[command->argc++] = token.word;
        } else {
            if (list->redirection_count == REDIRECTION_CAPACITY) return -1;
            struct redirection *redirection = &list->redirections[list->redirection_count++];
            *redirection = (struct redirection){token.target, token.source, token.flags, NULL};
            if (token.source == -1) {
                token = next_token(&lexer);
                if (token.kind != WORD) return -1;
                redirection->path = token.word;
            }
            ++command->redirections;
        }
    }
}

static int apply_redirections(const struct command_list *list, const struct command *command)
{
    for (int i = 0; i < command->redirections; ++i) {
        const struct redirection *r = &list->redirections[command->first_redirection + i];
        if (r->source == -2) {
            if (close(r->target) != 0 && errno != EBADF) { perror("oksh: close"); return 1; }
            continue;
        }
        int fd = r->source;
        if (r->path) {
            fd = open(r->path, r->flags, 0666);
            if (fd < 0) { perror(r->path); return 1; }
        }
        if (dup2(fd, r->target) < 0) {
            perror("oksh: dup2");
            if (r->path && fd != r->target) close(fd);
            return 1;
        }
        if (r->path && fd != r->target) close(fd);
    }
    return 0;
}

static int is_builtin(const struct command *command)
{
    return !command->argc || !strcmp(command->argv[0], "cd") || !strcmp(command->argv[0], "exit") ||
           !strcmp(command->argv[0], "echo") || !strcmp(command->argv[0], "help");
}

static int write_text(const char *text)
{
    size_t remaining = strlen(text);
    while (remaining) {
        ssize_t count = write(STDOUT_FILENO, text, remaining);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return 1;
        text += count;
        remaining -= (size_t)count;
    }
    return 0;
}

static int builtin(struct command *command, int previous_status, int *exit_requested)
{
    if (!command->argc) return 0;
    char **args = command->argv;
    if (!strcmp(args[0], "cd")) {
        if (command->argc > 2) { fputs("oksh: cd: too many arguments\n", stderr); return 2; }
        if (chdir(command->argc == 2 ? args[1] : "/") != 0) { perror("oksh: cd"); return 1; }
        return 0;
    }
    if (!strcmp(args[0], "exit")) {
        if (command->argc > 2) { fputs("oksh: exit: too many arguments\n", stderr); return 2; }
        *exit_requested = 1;
        if (command->argc == 1) return previous_status;
        const char *p = args[1];
        int negative = *p == '-';
        if (*p == '+' || *p == '-') ++p;
        unsigned value = 0;
        if (!*p) { fputs("oksh: exit: numeric argument required\n", stderr); return 2; }
        for (; *p; ++p) {
            if (*p < '0' || *p > '9') { fputs("oksh: exit: numeric argument required\n", stderr); return 2; }
            value = (value * 10 + (unsigned)(*p - '0')) & 255u;
        }
        return (int)(negative ? (0u - value) & 255u : value);
    }
    if (!strcmp(args[0], "echo")) {
        for (int i = 1; i < command->argc; ++i)
            if ((i > 1 && write_text(" ")) || write_text(args[i])) return 1;
        return write_text("\n");
    }
    return find_command(args[0])->run(command->argc, args);
}

static int parent_builtin(struct command_list *list, struct command *command, int previous_status, int *exit_requested)
{
    int saved[3] = {-1, -1, -1};
    int result = 1;
    /* Preserve each target once, before any ordered redirection takes effect. */
    for (int i = 0; i < command->redirections; ++i) {
        int target = list->redirections[command->first_redirection + i].target;
        if (saved[target] != -1) continue;
        saved[target] = fcntl(target, F_DUPFD, 3);
        if (saved[target] < 0) {
            if (errno == EBADF) saved[target] = -2;
            else { perror("oksh: save descriptor"); goto restore; }
        }
    }
    flush_streams();
    if (apply_redirections(list, command) == 0) result = builtin(command, previous_status, exit_requested);
    flush_streams();
restore:
    for (int fd = 0; fd < 3; ++fd) {
        if (saved[fd] >= 0) {
            if (dup2(saved[fd], fd) < 0) result = 1;
            close(saved[fd]);
        } else if (saved[fd] == -2) close(fd);
    }
    return result;
}

static void execute(struct command *command, int previous_status)
{
    if (is_builtin(command)) {
        int ignored = 0;
        int status = builtin(command, previous_status, &ignored);
        flush_streams();
        _Exit(status);
    }
    char path[LINE_CAPACITY];
    const char *name = command->argv[0];
    if (strlen(name) + (strchr(name, '/') ? 1u : 6u) > sizeof(path)) _Exit(126);
    if (strchr(name, '/')) strcpy(path, name);
    else { strcpy(path, "/bin/"); strcpy(path + 5, name); }
    char *env[] = {"PATH=/bin", NULL};
    execve(path, command->argv, env);
    int status = errno == ENOENT ? 127 : 126;
    perror(path);
    flush_streams();
    _Exit(status);
}

/* Keep internal pipe descriptors away from redirection targets, even if a
 * caller started the shell with one of its standard descriptors closed. */
static int internal_pipe(int fds[2])
{
    if (pipe(fds) != 0) return -1;
    for (int i = 0; i < 2; ++i) {
        if (fds[i] > 2) continue;
        int replacement = fcntl(fds[i], F_DUPFD, 3);
        if (replacement < 0) {
            int error = errno;
            close(fds[0]); close(fds[1]); errno = error;
            return -1;
        }
        close(fds[i]); fds[i] = replacement;
    }
    return 0;
}

static int wait_child(pid_t child, int *status)
{
    pid_t result;
    do { result = waitpid(child, status, 0); } while (result < 0 && errno == EINTR);
    return result == child ? 0 : -1;
}

static int finish_child(pid_t child, int *status)
{
    if (wait_child(child, status) == 0) return 0;
    if (errno != ECHILD) {
        (void)kill(child, SIGKILL);
        (void)wait_child(child, status);
    }
    return -1;
}

static int run_pipeline(struct command_list *list, const struct pipeline *pipeline, int previous_status)
{
    pid_t children[PIPELINE_CAPACITY];
    int launched = 0, previous = -1, gate[2];
    pid_t group = 0;
    if (internal_pipe(gate) < 0) { perror("oksh: pipe"); (void)console_restore(); return 1; }
    flush_streams();
    for (int stage = 0; stage < pipeline->count; ++stage) {
        int next[2] = {-1, -1};
        if (stage + 1 < pipeline->count && internal_pipe(next) < 0) { perror("oksh: pipe"); goto abort_launch; }
        pid_t child = fork();
        if (child < 0) {
            perror("oksh: fork");
            if (next[0] >= 0) { close(next[0]); close(next[1]); }
            goto abort_launch;
        }
        if (!child) {
            if (shell_console.fd >= 0) close(shell_console.fd);
            close(gate[1]);
            char abort_token;
            ssize_t result;
            do { result = read(gate[0], &abort_token, 1); } while (result < 0 && errno == EINTR);
            close(gate[0]);
            if (result != 0) _Exit(1);
            if ((previous >= 0 && dup2(previous, STDIN_FILENO) < 0) ||
                (next[1] >= 0 && dup2(next[1], STDOUT_FILENO) < 0)) {
                perror("oksh: pipe dup2"); flush_streams(); _Exit(1);
            }
            if (previous >= 0) close(previous);
            if (next[0] >= 0) { close(next[0]); close(next[1]); }
            struct command *command = &list->commands[pipeline->first_command + stage];
            if (apply_redirections(list, command)) { flush_streams(); _Exit(1); }
            execute(command, previous_status);
        }
        children[launched++] = child;
        if (shell_console.fd >= 0) {
            if (!group) group = child;
            if (setpgid(child, group) < 0) {
                perror("oksh: command");
                if (next[0] >= 0) { close(next[0]); close(next[1]); }
                goto abort_launch;
            }
        }
        if (previous >= 0) close(previous);
        if (next[1] >= 0) close(next[1]);
        previous = next[0];
    }
    if (shell_console.fd >= 0 && (tcsetpgrp(shell_console.fd, group) < 0 ||
        tcgetpgrp(shell_console.fd) != group)) {
        fputs("oksh: cannot give the command console input.\n", stderr);
        goto abort_launch;
    }
    /* EOF releases every child only after every stage exists. On a partial
     * launch, one abort byte per child prevents commands from running at all. */
    close(gate[0]); close(gate[1]);
    int result = 0, failed_wait = 0;
    for (int i = 0; i < launched; ++i) {
        int status;
        if (finish_child(children[i], &status) < 0) {
            failed_wait = 1;
            continue;
        }
        if (i + 1 == launched) result = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    }
    if (console_restore() < 0) return 1;
    return failed_wait ? 1 : result;
abort_launch:
    if (previous >= 0) close(previous);
    for (int i = 0; i < launched;) {
        ssize_t result = write(gate[1], "x", 1);
        if (result == 1) ++i;
        else if (result < 0 && errno == EINTR) continue;
        else break;
    }
    close(gate[0]); close(gate[1]);
    for (int i = 0; i < launched; ++i) { int status; (void)finish_child(children[i], &status); }
    (void)console_restore();
    return 1;
}

static int run_line(const char *line, int previous_status, int *exit_requested)
{
    struct command_list list;
    if (parse_line(line, &list) != 0) {
        fputs("oksh: invalid syntax or command limit exceeded\n", stderr);
        return 2;
    }
    int status = previous_status;
    for (int i = 0; i < list.count; ++i) {
        struct pipeline *pipeline = &list.pipelines[i];
        /* && and || share precedence and associate left to right. A skipped
         * pipeline preserves the last executed status for the next operator. */
        if ((pipeline->condition == AND_IF && status != 0) ||
            (pipeline->condition == OR_IF && status == 0)) continue;
        struct command *command = &list.commands[pipeline->first_command];
        if (pipeline->count == 1 && is_builtin(command))
            status = parent_builtin(&list, command, status, exit_requested);
        else status = run_pipeline(&list, pipeline, status);
        if (*exit_requested || shell_console.failed) break;
    }
    return status;
}

int main(int argc, char **argv)
{
    if (argc != 1) {
        if (argc != 3 || strcmp(argv[1], "-c") || strlen(argv[2]) >= LINE_CAPACITY) {
            fputs("usage: oksh [-c COMMAND]\n", stderr);
            return 2;
        }
        int ignored = 0;
        return run_line(argv[2], 0, &ignored);
    }
    if (console_prepare() < 0) return console_finish(1);
    char line[LINE_CAPACITY];
    int previous_status = 0, exit_requested = 0;
    puts("oksh: user processes, pipelines, lists, < > >> and descriptor redirections");
    while (!exit_requested) {
        fputs("oksh> ", stdout); flush_streams();
        int status = read_line(line, sizeof(line));
        if (!status) return console_finish(previous_status);
        if (status < 0) { perror("read"); return console_finish(1); }
        if (status == 2) { fputs("oksh: input line too long\n", stderr); previous_status = 2; continue; }
        previous_status = run_line(line, previous_status, &exit_requested);
        if (shell_console.failed) return console_finish(1);
    }
    return console_finish(previous_status);
}
