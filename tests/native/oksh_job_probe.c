/* Native child for the oksh job-control guest check (scripts/test_oksh_jobs.py).
 *
 *   oksh-jobs stop STATUS   stop itself with SIGSTOP, then exit STATUS once continued
 *   oksh-jobs sleep SECONDS exit after SECONDS
 *   oksh-jobs stdin         count standard input bytes until end of file
 *
 * Each report is one write so it cannot interleave with the shell's prompt.
 */
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static void say(const char *text, long number)
{
    char line[96];
    size_t used = 0;
    while (*text && used < sizeof(line) - 24) line[used++] = *text++;
    char digits[24];
    int count = 0;
    unsigned long value = (unsigned long)number;
    do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (count) line[used++] = digits[--count];
    line[used++] = '\n';
    (void)write(STDOUT_FILENO, line, used);
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
        struct timespec request = {.tv_sec = atoi(argv[2]), .tv_nsec = 0};
        int result;
        while ((result = nanosleep(&request, &request)) != 0 && errno == EINTR) {}
        if (result != 0) return 3;
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
    return 2;
}
