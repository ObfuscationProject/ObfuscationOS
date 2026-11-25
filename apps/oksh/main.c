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
#define JOB_CAPACITY 8
#define JOB_TEXT_CAPACITY 64

struct redirection {
    int target, source, flags;
    char *path;
};
struct command {
    char *argv[ARGUMENT_CAPACITY];
    int argc, first_redirection, redirections;
};
struct pipeline {
    int first_command, count, condition, background, text_start, text_end;
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
enum { END, WORD, PIPE, REDIRECT, SEMICOLON, AND_IF, OR_IF, BACKGROUND, INVALID };

static struct { int fd, failed; pid_t sid, group; } shell_console = {.fd = -1};

/* Job control state. A job is one pipeline; its processes share a process
 * group only when the shell manages a terminal. Native processes get no
 * SIGCHLD, so the shell polls with WNOHANG before each prompt. */
enum { JOB_RUNNING, JOB_STOPPED, JOB_DONE };
struct job {
    pid_t pids[PIPELINE_CAPACITY];
    unsigned char states[PIPELINE_CAPACITY];
    int count, status, failed, stop_signal, reported;
    pid_t group;
    unsigned order;
    char text[JOB_TEXT_CAPACITY];
};
static struct {
    struct job table[JOB_CAPACITY];
    unsigned order;
    int interactive, subshell, exit_warned, exit_warning;
} shell_jobs;

/* An interactive shell ignores the job-control signals: SIGTTOU lets it take
 * the console back from the background, SIGTTIN and SIGTSTP keep it running,
 * and SIGINT and SIGQUIT at its prompt reach the foreground job instead.
 * Commands start with the defaults. */
static const int job_signals[] = {SIGINT, SIGQUIT, SIGTSTP, SIGTTIN, SIGTTOU};
static int job_signals_ignored;

static int job_signals_set(void (*handler)(int))
{
    for (size_t i = 0; i < sizeof(job_signals) / sizeof(job_signals[0]); ++i)
        if (signal(job_signals[i], handler) == SIG_ERR) return -1;
    return 0;
}

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

static const char *skip_blanks(const char *p)
{
    while (*p == ' ' || *p == '\t') ++p;
    return p;
}

static int special(char c)
{
    return c == '|' || c == '<' || c == '>' || c == '&' || c == ';' || c == '(' || c == ')';
}

static struct token next_token(struct lexer *lexer)
{
    struct token token = {END, -1, -1, 0, NULL};
    const char *p = skip_blanks(lexer->cursor);
    if (!*p) { lexer->cursor = p; return token; }
    if (*p == '|') {
        token.kind = p[1] == '|' ? OR_IF : PIPE;
        lexer->cursor = p + (token.kind == OR_IF ? 2 : 1);
        return token;
    }
    if (*p == '&') {
        token.kind = p[1] == '&' ? AND_IF : BACKGROUND;
        lexer->cursor = p + (token.kind == AND_IF ? 2 : 1);
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
    pipeline->text_start = (int)(skip_blanks(line) - line);
    struct command *command = &list->commands[0];
    int pending = END;
    for (;;) {
        const int at = (int)(skip_blanks(lexer.cursor) - line);
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
            pipeline->text_start = at;
            command = &list->commands[list->command_count++];
            command->first_redirection = list->redirection_count;
            pending = END;
        }
        if (token.kind == END || token.kind == SEMICOLON || token.kind == AND_IF || token.kind == OR_IF ||
            token.kind == BACKGROUND) {
            if (!command->argc && (pipeline->count > 1 || !command->redirections)) {
                if (token.kind == END && list->count == 1 && list->command_count == 1) {
                    list->count = 0;
                    return 0;
                }
                return -1;
            }
            pipeline->text_end = at;
            if (token.kind == BACKGROUND) {
                /* Only a lone pipeline at the end of the line runs in the
                 * background; an and-or list or a later command does not. */
                if (pipeline->condition != SEMICOLON) return -1;
                pipeline->background = 1;
                return next_token(&lexer).kind == END ? 0 : -1;
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
    static const char *const names[] = {"cd", "exit", "echo", "help", "jobs", "fg", "bg"};
    if (!command->argc) return 1;
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
        if (!strcmp(command->argv[0], names[i])) return 1;
    return 0;
}

static int write_bytes(int fd, const char *text, size_t remaining)
{
    while (remaining) {
        ssize_t count = write(fd, text, remaining);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return 1;
        text += count;
        remaining -= (size_t)count;
    }
    return 0;
}

static int write_text(const char *text)
{
    return write_bytes(STDOUT_FILENO, text, strlen(text));
}

/* Job reports are assembled first so each one reaches the terminal in a
 * single write; native stdio writes byte by byte. */
struct text_line { char data[128]; size_t used; };

static void line_add(struct text_line *line, const char *text)
{
    while (*text && line->used + 1 < sizeof(line->data)) line->data[line->used++] = *text++;
}

static void line_number(struct text_line *line, unsigned long value)
{
    char digits[24];
    int count = 0;
    do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (count && line->used + 1 < sizeof(line->data)) line->data[line->used++] = digits[--count];
}

static int line_write(int fd, struct text_line *line)
{
    line->data[line->used] = '\0';
    return write_bytes(fd, line->data, line->used);
}

static int job_used(const struct job *job) { return job->count != 0; }
static int job_number(const struct job *job) { return (int)(job - shell_jobs.table) + 1; }

static int job_in_table(const struct job *job)
{
    return job >= shell_jobs.table && job < shell_jobs.table + JOB_CAPACITY;
}

static struct job *job_free_slot(void)
{
    for (int i = 0; i < JOB_CAPACITY; ++i)
        if (!job_used(&shell_jobs.table[i])) return &shell_jobs.table[i];
    return NULL;
}

/* The current job (+) is the most recently started, stopped or resumed one;
 * the previous job (-) comes before it. */
static struct job *job_current(int previous)
{
    struct job *first = NULL, *second = NULL;
    for (int i = 0; i < JOB_CAPACITY; ++i) {
        struct job *job = &shell_jobs.table[i];
        if (!job_used(job)) continue;
        if (!first || job->order > first->order) { second = first; first = job; }
        else if (!second || job->order > second->order) second = job;
    }
    return previous ? second : first;
}

static void job_touch(struct job *job) { job->order = ++shell_jobs.order; }

static int job_state(const struct job *job)
{
    int state = JOB_DONE;
    for (int i = 0; i < job->count; ++i) {
        if (job->states[i] == JOB_RUNNING) return JOB_RUNNING;
        if (job->states[i] == JOB_STOPPED) state = JOB_STOPPED;
    }
    return state;
}

static int job_status(const struct job *job)
{
    if (job->failed) return 1;
    return WIFEXITED(job->status) ? WEXITSTATUS(job->status) : 128 + WTERMSIG(job->status);
}

static void job_set_text(struct job *job, const char *line, const struct pipeline *pipeline)
{
    int end = pipeline->text_end;
    while (end > pipeline->text_start && (line[end - 1] == ' ' || line[end - 1] == '\t')) --end;
    size_t length = (size_t)(end - pipeline->text_start);
    if (length < sizeof(job->text)) {
        memcpy(job->text, line + pipeline->text_start, length);
        job->text[length] = '\0';
    } else {
        length = sizeof(job->text) - 4;
        memcpy(job->text, line + pipeline->text_start, length);
        memcpy(job->text + length, "...", 4);
    }
}

/* `[n]+ Stopped text`, `[n]  Done text`, `[n]- Exit 3 text`, `[n]  Killed 15 text`. */
static int job_report(int fd, const struct job *job, int state)
{
    struct text_line line = {.used = 0};
    char mark[] = "]  ";
    mark[1] = job == job_current(0) ? '+' : job == job_current(1) ? '-' : ' ';
    line_add(&line, "[");
    line_number(&line, (unsigned long)job_number(job));
    line_add(&line, mark);
    if (state == JOB_RUNNING) line_add(&line, "Running");
    else if (state == JOB_STOPPED) line_add(&line, "Stopped");
    else if (!job->failed && WIFSIGNALED(job->status)) {
        line_add(&line, "Killed ");
        line_number(&line, (unsigned long)WTERMSIG(job->status));
    } else if (job_status(job)) {
        line_add(&line, "Exit ");
        line_number(&line, (unsigned long)job_status(job));
    } else line_add(&line, "Done");
    line_add(&line, " ");
    line_add(&line, job->text);
    line_add(&line, "\n");
    return line_write(fd, &line);
}

static void job_record(struct job *job, int index, int status)
{
    if (WIFCONTINUED(status)) job->states[index] = JOB_RUNNING;
    else if (WIFSTOPPED(status)) {
        job->states[index] = JOB_STOPPED;
        job->stop_signal = WSTOPSIG(status);
    } else {
        job->states[index] = JOB_DONE;
        if (index + 1 == job->count) job->status = status;
    }
}

/* A wait that fails for any reason but ECHILD loses track of the process,
 * so it is killed and reaped; either way the job's status becomes 1. */
static void job_wait_process(struct job *job, int index, int options)
{
    const pid_t pid = job->pids[index];
    int status;
    pid_t result;
    do { result = waitpid(pid, &status, options); } while (result < 0 && errno == EINTR);
    if (result == 0) return;
    if (result == pid) { job_record(job, index, status); return; }
    if (errno != ECHILD) {
        (void)kill(pid, SIGKILL);
        do { result = waitpid(pid, &status, 0); } while (result < 0 && errno == EINTR);
    }
    job->states[index] = JOB_DONE;
    job->failed = 1;
}

/* Wait until every process of a foreground job has exited or stopped. Only
 * the interactive shell treats a stop as the end of the wait; `oksh -c` has
 * no job control and waits until the command is continued and exits. */
static void job_wait(struct job *job)
{
    const int options = shell_jobs.interactive ? WUNTRACED : 0;
    for (int i = 0; i < job->count; ++i)
        if (job->states[i] == JOB_RUNNING) job_wait_process(job, i, options);
}

static void jobs_update(void)
{
    for (int i = 0; i < JOB_CAPACITY; ++i) {
        struct job *job = &shell_jobs.table[i];
        for (int process = 0; process < job->count; ++process)
            if (job->states[process] != JOB_DONE)
                job_wait_process(job, process, WNOHANG | WUNTRACED | WCONTINUED);
    }
}

static int job_signal(const struct job *job, int signal_number)
{
    if (job->group > 0) return kill(-job->group, signal_number);
    int result = 0;
    for (int i = 0; i < job->count; ++i)
        if (job->states[i] != JOB_DONE && kill(job->pids[i], signal_number) < 0) result = -1;
    return result;
}

static void job_continue(struct job *job)
{
    for (int i = 0; i < job->count; ++i)
        if (job->states[i] == JOB_STOPPED) job->states[i] = JOB_RUNNING;
    job->reported = JOB_RUNNING;
    if (job_signal(job, SIGCONT) < 0) perror("oksh: continue job");
}

/* Report finished and newly stopped jobs before a prompt, then forget the
 * finished ones. */
static void jobs_notify(void)
{
    jobs_update();
    for (int i = 0; i < JOB_CAPACITY; ++i) {
        struct job *job = &shell_jobs.table[i];
        if (!job_used(job)) continue;
        int state = job_state(job);
        if (state == JOB_DONE) {
            (void)job_report(STDERR_FILENO, job, state);
            memset(job, 0, sizeof(*job));
        } else if (state != job->reported) {
            if (state == JOB_STOPPED) {
                job_touch(job);
                (void)job_report(STDERR_FILENO, job, state);
            }
            job->reported = state;
        }
    }
}

/* Stopped jobs get the hangup a terminal would send to an orphaned stopped
 * group; running background jobs keep running after the shell exits. Only
 * the interactive shell tracks stops, so `oksh -c` leaves its jobs alone. */
static void jobs_hang_up(void)
{
    if (!shell_jobs.interactive || shell_jobs.subshell) return;
    jobs_update();
    for (int i = 0; i < JOB_CAPACITY; ++i) {
        struct job *job = &shell_jobs.table[i];
        if (!job_used(job) || job_state(job) != JOB_STOPPED) continue;
        (void)job_signal(job, SIGHUP);
        (void)job_signal(job, SIGCONT);
    }
}

static int shell_finish(int status)
{
    jobs_hang_up();
    return console_finish(status);
}

/* Like other shells, the first exit request with stopped jobs only warns. */
static int exit_allowed(void)
{
    if (!shell_jobs.interactive || shell_jobs.subshell || shell_jobs.exit_warned) return 1;
    for (int i = 0; i < JOB_CAPACITY; ++i) {
        if (job_used(&shell_jobs.table[i]) && job_state(&shell_jobs.table[i]) == JOB_STOPPED) {
            fputs("oksh: there are stopped jobs\n", stderr);
            shell_jobs.exit_warning = 1;
            return 0;
        }
    }
    return 1;
}

/* Wait for a job that owns the terminal, then take the terminal back. A job
 * that stops is kept in the table; when the table is full it is continued
 * in the foreground instead, because nothing could resume it later. */
static int job_foreground(struct job *job)
{
    struct job *slot = NULL;
    for (;;) {
        job_wait(job);
        if (job_state(job) != JOB_STOPPED) break;
        slot = job_in_table(job) ? job : job_free_slot();
        if (slot) break;
        fprintf(stderr, "oksh: job table full (%d jobs), continuing %s\n", JOB_CAPACITY, job->text);
        job_continue(job);
    }
    const int restored = console_restore();
    if (slot) {
        if (slot != job) *slot = *job;
        slot->reported = JOB_STOPPED;
        job_touch(slot);
        (void)job_report(STDERR_FILENO, slot, JOB_STOPPED);
        return restored < 0 ? 1 : 128 + slot->stop_signal;
    }
    const int status = job_status(job);
    if (job_in_table(job)) memset(job, 0, sizeof(*job));
    return restored < 0 ? 1 : status;
}

static struct job *job_find(const char *name, const char *spec)
{
    struct job *job = NULL;
    if (!spec || !strcmp(spec, "%%") || !strcmp(spec, "%+")) job = job_current(0);
    else if (!strcmp(spec, "%-")) job = job_current(1);
    else if (spec[0] == '%' && spec[1] >= '1' && spec[1] <= '9' && !spec[2] && spec[1] - '0' <= JOB_CAPACITY)
        job = &shell_jobs.table[spec[1] - '1'];
    if (job && job_used(job)) return job;
    if (spec) fprintf(stderr, "oksh: %s: %s: no such job\n", name, spec);
    else fprintf(stderr, "oksh: %s: no current job\n", name);
    return NULL;
}

static int builtin_jobs(const struct command *command)
{
    if (command->argc > 1) { fputs("oksh: jobs: too many arguments\n", stderr); return 2; }
    if (!shell_jobs.subshell) jobs_update();
    int result = 0;
    for (int i = 0; i < JOB_CAPACITY; ++i) {
        const struct job *job = &shell_jobs.table[i];
        if (job_used(job) && job_report(STDOUT_FILENO, job, job_state(job))) result = 1;
    }
    if (shell_jobs.subshell) return result;
    for (int i = 0; i < JOB_CAPACITY; ++i) {
        struct job *job = &shell_jobs.table[i];
        if (!job_used(job)) continue;
        if (job_state(job) == JOB_DONE) memset(job, 0, sizeof(*job));
        else job->reported = job_state(job);
    }
    return result;
}

/* fg gives the job the terminal before continuing it; bg only continues it. */
static int builtin_resume(const struct command *command)
{
    const char *name = command->argv[0];
    if (shell_jobs.subshell) { fprintf(stderr, "oksh: %s: not available in a pipeline\n", name); return 1; }
    if (command->argc > 2) { fprintf(stderr, "oksh: %s: too many arguments\n", name); return 2; }
    jobs_update();
    struct job *job = job_find(name, command->argc == 2 ? command->argv[1] : NULL);
    if (!job) return 1;
    if (job_state(job) == JOB_DONE) {
        fprintf(stderr, "oksh: %s: job %d has finished\n", name, job_number(job));
        return 1;
    }
    struct text_line line = {.used = 0};
    if (!strcmp(name, "bg")) {
        if (job_state(job) != JOB_STOPPED) {
            fprintf(stderr, "oksh: bg: job %d is already running\n", job_number(job));
            return 0;
        }
        job_touch(job);
        line_add(&line, "[");
        line_number(&line, (unsigned long)job_number(job));
        line_add(&line, "]+ ");
        line_add(&line, job->text);
        line_add(&line, " &\n");
        (void)line_write(STDOUT_FILENO, &line);
        job_continue(job);
        return 0;
    }
    line_add(&line, job->text);
    line_add(&line, "\n");
    (void)line_write(STDOUT_FILENO, &line);
    job_touch(job);
    if (shell_console.fd >= 0 && (tcsetpgrp(shell_console.fd, job->group) < 0 ||
        tcgetpgrp(shell_console.fd) != job->group)) {
        fputs("oksh: cannot give the job console input.\n", stderr);
        (void)console_restore();
        return 1;
    }
    job_continue(job);
    return job_foreground(job);
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
        if (!exit_allowed()) return 1;
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
    if (!strcmp(args[0], "jobs")) return builtin_jobs(command);
    if (!strcmp(args[0], "fg") || !strcmp(args[0], "bg")) return builtin_resume(command);
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

/* Without job control an asynchronous command ignores the interactive
 * interrupt signals and its first stage reads /dev/null instead of the
 * shell's input (POSIX). */
static void detach_background_child(int first_stage)
{
    if (signal(SIGINT, SIG_IGN) == SIG_ERR || signal(SIGQUIT, SIG_IGN) == SIG_ERR) {
        perror("oksh: signal"); flush_streams(); _Exit(1);
    }
    if (!first_stage) return;
    int input = open("/dev/null", O_RDONLY);
    if (input < 0 || (input != STDIN_FILENO && dup2(input, STDIN_FILENO) < 0)) {
        perror("oksh: /dev/null"); flush_streams(); _Exit(1);
    }
    if (input != STDIN_FILENO) close(input);
}

static int run_pipeline(struct command_list *list, const struct pipeline *pipeline, int previous_status,
                        const char *line)
{
    struct job job;
    memset(&job, 0, sizeof(job));
    pid_t *children = job.pids;
    int launched = 0, previous = -1, gate[2];
    pid_t group = 0;
    const int background = pipeline->background;
    if (background && !job_free_slot()) {
        fprintf(stderr, "oksh: job table full (%d jobs)\n", JOB_CAPACITY);
        return 1;
    }
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
            shell_jobs.subshell = 1;
            if (job_signals_ignored && job_signals_set(SIG_DFL) < 0) { perror("oksh: signal"); _Exit(1); }
            if (background && shell_console.fd < 0) detach_background_child(!stage);
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
    if (!background && shell_console.fd >= 0 && (tcsetpgrp(shell_console.fd, group) < 0 ||
        tcgetpgrp(shell_console.fd) != group)) {
        fputs("oksh: cannot give the command console input.\n", stderr);
        goto abort_launch;
    }
    /* EOF releases every child only after every stage exists. On a partial
     * launch, one abort byte per child prevents commands from running at all. */
    close(gate[0]); close(gate[1]);
    job.count = launched;
    job.group = group;
    job_set_text(&job, line, pipeline);
    if (!background) return job_foreground(&job);
    struct job *slot = job_free_slot();
    *slot = job;
    job_touch(slot);
    if (shell_jobs.interactive) {
        struct text_line report = {.used = 0};
        line_add(&report, "[");
        line_number(&report, (unsigned long)job_number(slot));
        line_add(&report, "] ");
        line_number(&report, (unsigned long)children[launched - 1]);
        line_add(&report, "\n");
        (void)line_write(STDERR_FILENO, &report);
    }
    return 0;
abort_launch:
    if (previous >= 0) close(previous);
    for (int i = 0; i < launched;) {
        ssize_t result = write(gate[1], "x", 1);
        if (result == 1) ++i;
        else if (result < 0 && errno == EINTR) continue;
        else break;
    }
    close(gate[0]); close(gate[1]);
    job.count = launched;
    job_wait(&job);
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
        if (pipeline->count == 1 && is_builtin(command) && !pipeline->background)
            status = parent_builtin(&list, command, status, exit_requested);
        else status = run_pipeline(&list, pipeline, status, line);
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
        return shell_finish(run_line(argv[2], 0, &ignored));
    }
    if (job_signals_set(SIG_IGN) < 0) { perror("oksh: signal"); return 1; }
    job_signals_ignored = 1;
    shell_jobs.interactive = 1;
    if (console_prepare() < 0) return console_finish(1);
    char line[LINE_CAPACITY];
    int previous_status = 0, exit_requested = 0;
    puts("oksh: user processes, pipelines, lists, < > >> and descriptor redirections");
    while (!exit_requested) {
        jobs_notify();
        fputs("oksh> ", stdout); flush_streams();
        int status = read_line(line, sizeof(line));
        if (!status) {
            if (exit_allowed()) break;
        } else if (status < 0) {
            perror("read");
            return shell_finish(1);
        } else if (status == 2) {
            fputs("oksh: input line too long\n", stderr);
            previous_status = 2;
        } else {
            previous_status = run_line(line, previous_status, &exit_requested);
            if (shell_console.failed) return shell_finish(1);
        }
        /* A warning about stopped jobs lasts until the next input line. */
        shell_jobs.exit_warned = shell_jobs.exit_warning;
        shell_jobs.exit_warning = 0;
    }
    return shell_finish(previous_status);
}
