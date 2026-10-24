/* Source-only recipe draft: independent review and actual qualification pending. */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static int emit(const char *text)
{
    size_t remaining = strlen(text);
    while (remaining) {
        ssize_t count = write(1, text, remaining);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return 172;
        text += count;
        remaining -= (size_t)count;
    }
    return 0;
}

static int failure(const char *stage, const char *reason, int status)
{
    fprintf(stderr, "SHARED_WRITE_SEAL_SUITE_FAIL stage=%s reason=%s status=%d errno=%d\n",
            stage, reason, status, errno);
    return 171;
}

static int run(const char *path, char *name, const char *begin, const char *complete)
{
    if (emit(begin)) return failure(name, "begin-write", 172);
    const pid_t child = fork();
    if (child < 0) return failure(name, "fork", -1);
    if (!child) {
        char *args[] = {name, 0};
        char *environment[] = {"PATH=/bin", 0};
        execve(path, args, environment);
        _Exit(126);
    }
    int status = 0;
    pid_t waited;
    do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
    if (waited != child) return failure(name, "wait", status);
    if (!WIFEXITED(status)) return failure(name, "signal", status);
    if (WEXITSTATUS(status) != 0) return failure(name, "exit", WEXITSTATUS(status));
    if (emit(complete)) return failure(name, "complete-write", 172);
    return 0;
}

#define RUN(name) run("/bin/" name, name, \
    "OK_SHARED_WRITE_SEAL_STAGE name=" name " state=begin\n", \
    "OK_SHARED_WRITE_SEAL_STAGE name=" name " state=complete child_exit=0\n")

int main(int argc, char **argv)
{
    const int native = argc == 2 && strcmp(argv[1], "--native") == 0;
    if (argc != 1 && !native) return failure("arguments", "usage", 2);
    int result;
    if (native) {
        result = RUN("shared-files-native");
        if (!result) result = RUN("shared-rights-native");
    } else {
        result = RUN("shared-files-suite");
    }
    if (!result) result = RUN("shared-write-seal-native");
    if (!result && !native) result = RUN("shared-write-seal-static");
    if (result) return result;
    const char *marker = native
        ? "OK_SHARED_WRITE_SEAL_SUITE version=1 legacy_suite=0 native=3 static_musl=0 child_exit=0\n"
        : "OK_SHARED_WRITE_SEAL_SUITE version=1 legacy_suite=1 native=3 static_musl=3 child_exit=0\n";
    if (emit(marker)) return failure("suite", "final-write", 172);
    return 0;
}
