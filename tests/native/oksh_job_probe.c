/* Native child for the oksh job-control guest checks (scripts/test_oksh_jobs.py
 * at the maintenance console, scripts/test_getty_login.py on a login pts).
 *
 *   oksh-jobs stop STATUS   stop itself with SIGSTOP, then exit STATUS once continued
 *   oksh-jobs sleep SECONDS exit after SECONDS
 *   oksh-jobs stdin         count standard input bytes until end of file
 *   oksh-jobs session       report its process, group, session and terminal identity
 *   oksh-jobs hold SECONDS  report its group and the terminal's foreground group,
 *                           then exit after SECONDS (a target for ^C and ^Z)
 *   oksh-jobs alive PID     report whether process PID still exists (kill with signal 0)
 *
 * Each report is one write so it cannot interleave with the shell's prompt. A
 * failed call is reported as -1.
 */
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

struct field {
    const char *name;
    long value;
};

static size_t append_text(char *line, size_t used, const char *text)
{
    while (*text) line[used++] = *text++;
    return used;
}

static size_t append_number(char *line, size_t used, long number)
{
    char digits[24];
    int count = 0;
    unsigned long value = number < 0 ? 0UL - (unsigned long)number : (unsigned long)number;
    if (number < 0) line[used++] = '-';
    do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (count) line[used++] = digits[--count];
    return used;
}

/* "OKSH_JOBS <what> name=value ...": at most 8 fields with names below 16 bytes. */
static void report(const char *what, const struct field *fields, int count)
{
    char line[320];
    size_t used = append_text(line, 0, "OKSH_JOBS ");
    used = append_text(line, used, what);
    for (int i = 0; i < count; ++i) {
        line[used++] = ' ';
        used = append_text(line, used, fields[i].name);
        line[used++] = '=';
        used = append_number(line, used, fields[i].value);
    }
    line[used++] = '\n';
    (void)write(STDOUT_FILENO, line, used);
}

static void say(const char *text, long number)
{
    char line[96];
    size_t used = 0;
    while (*text && used < sizeof(line) - 24) line[used++] = *text++;
    used = append_number(line, used, number);
    line[used++] = '\n';
    (void)write(STDOUT_FILENO, line, used);
}

static int pause_seconds(int seconds)
{
    struct timespec request = {.tv_sec = seconds, .tv_nsec = 0};
    int result;
    while ((result = nanosleep(&request, &request)) != 0 && errno == EINTR) {}
    return result;
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "stop")) {
        say("OKSH_JOBS stop pid=", (long)getpid());
        say("OKSH_JOBS group pgrp=", (long)getpgrp());
        if (kill(getpid(), SIGSTOP) != 0) return 3;
        say("OKSH_JOBS continued pid=", (long)getpid());
        return atoi(argv[2]);
    }
    if (argc == 3 && !strcmp(argv[1], "sleep")) {
        if (pause_seconds(atoi(argv[2])) != 0) return 3;
        say("OKSH_JOBS slept seconds=", atoi(argv[2]));
        return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "stdin")) {
        char buffer[64];
        long total = 0;
        ssize_t count;
        while ((count = read(STDIN_FILENO, buffer, sizeof(buffer))) > 0) total += count;
        say("OKSH_JOBS stdin bytes=", total);
        return count < 0 ? 3 : 0;
    }
    if (argc == 2 && !strcmp(argv[1], "session")) {
        struct stat st;
        const struct field fields[] = {
            {"pid", (long)getpid()}, {"ppid", (long)getppid()}, {"pgrp", (long)getpgrp()},
            {"sid", (long)getsid(0)}, {"tty_pgrp", (long)tcgetpgrp(STDIN_FILENO)},
            {"tty_sid", (long)tcgetsid(STDIN_FILENO)},
            {"tty_ino", fstat(STDIN_FILENO, &st) == 0 ? (long)st.st_ino : -1L},
        };
        report("session", fields, (int)(sizeof(fields) / sizeof(fields[0])));
        return 0;
    }
    if (argc == 3 && !strcmp(argv[1], "hold")) {
        const struct field fields[] = {
            {"pid", (long)getpid()}, {"pgrp", (long)getpgrp()},
            {"tty_pgrp", (long)tcgetpgrp(STDIN_FILENO)}, {"seconds", atoi(argv[2])},
        };
        report("hold", fields, (int)(sizeof(fields) / sizeof(fields[0])));
        if (pause_seconds(atoi(argv[2])) != 0) return 3;
        say("OKSH_JOBS held seconds=", atoi(argv[2]));
        return 0;
    }
    if (argc == 3 && !strcmp(argv[1], "alive")) {
        long pid = strtol(argv[2], 0, 10);
        int alive = pid > 0 && (kill((pid_t)pid, 0) == 0 || errno == EPERM);
        const struct field fields[] = {{"pid", pid}, {"alive", alive}};
        report("alive", fields, (int)(sizeof(fields) / sizeof(fields[0])));
        return 0;
    }
    return 2;
}
