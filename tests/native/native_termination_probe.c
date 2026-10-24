#include <errno.h>
#include <signal.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "native_fixture_record.h"

static int terminate_blocked(int signal_number)
{
    int report[2], blocked[2];
    if (pipe(report) || pipe(blocked)) return 1;
    pid_t child = fork();
    if (child < 0) return 2;
    if (!child) {
        close(report[0]);
        if (write(report[1], "R", 1) != 1 || close(report[1])) _Exit(81);
        /* Retain the writer: the read has neither input nor an EOF source. */
        char byte;
        (void)read(blocked[0], &byte, 1);
        _Exit(82);
    }
    close(report[1]); close(blocked[0]);
    char ready = 0;
    if (read(report[0], &ready, 1) != 1 || ready != 'R' || close(report[0])) return 3;
    const struct timespec delay = {0, 50000000};
    if (nanosleep(&delay, 0) || kill(child, 0) || kill(child, signal_number)) return 4;
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status) || WTERMSIG(status) != signal_number) return 5;
    if (close(blocked[1])) return 6;
    errno = 0;
    if (kill(child, 0) != -1 || errno != ESRCH) return 7;
    struct native_fixture_record record = {0};
    nf_text(&record, "NATIVE_TERMINATION signal="); nf_number(&record, (unsigned)signal_number);
    nf_text(&record, " child="); nf_number(&record, (unsigned)child);
    nf_text(&record, " wait_signal="); nf_number(&record, (unsigned)WTERMSIG(status));
    nf_text(&record, " retired=pass\n");
    if (nf_emit(&record)) return 8;
    return 0;
}

int main(void)
{
    int result = terminate_blocked(SIGTERM);
    if (result) { (void)nf_marker("NATIVE_TERMINATION_FAIL term\n"); return result; }
    result = terminate_blocked(SIGKILL);
    if (result) { (void)nf_marker("NATIVE_TERMINATION_FAIL kill\n"); return result + 10; }
    pid_t child = fork();
    if (child < 0) return 21;
    if (!child) {
        if (kill(getpid(), SIGKILL)) _Exit(83);
        _Exit(84);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status) || WTERMSIG(status) != SIGKILL) return 22;
    if (nf_marker("NATIVE_TERMINATION_PASS term_wait=15 kill_wait=9 self_kill=9\n")) return 23;
    return 0;
}
