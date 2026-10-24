#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#include "native_fixture_record.h"

#define CHECK(condition) do { if (!(condition)) { printf("OKSH_NATIVE_FAIL line=%d errno=%d\n", __LINE__, errno); return 1; } } while (0)

static int launch(const char *command)
{
    pid_t child = fork();
    if (child < 0) return -1;
    if (!child) {
        char *argv[] = {"oksh", "-c", (char *)command, 0};
        char *env[] = {"PATH=/bin", 0};
        execve("/bin/oksh", argv, env);
        _Exit(127);
    }
    int status;
    pid_t result;
    do { result = waitpid(child, &status, 0); } while (result < 0 && errno == EINTR);
    if (result != child) return -1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}

static int contents(const char *path, const char *expected)
{
    char buffer[128];
    int fd = open(path, O_RDONLY);
    if (fd < 0) return 0;
    ssize_t size = read(fd, buffer, sizeof(buffer));
    int closed = close(fd);
    return size == (ssize_t)strlen(expected) && !memcmp(buffer, expected, (size_t)size) && !closed;
}

static int absent(const char *path)
{
    int fd = open(path, O_RDONLY);
    if (fd >= 0) { close(fd); return 0; }
    return errno == ENOENT;
}

static int emit(void)
{
    char buffer[257];
    memset(buffer, 'x', sizeof(buffer));
    size_t remaining = 12289;
    while (remaining) {
        size_t count = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
        ssize_t size = write(1, buffer, count);
        if (size < 0 && errno == EINTR) continue;
        if (size <= 0) return 1;
        remaining -= (size_t)size;
    }
    return 0;
}

static int verify_stream(void)
{
    size_t total = 0;
    for (;;) {
        char buffer[317];
        ssize_t size = read(0, buffer, sizeof(buffer));
        if (size < 0 && errno == EINTR) continue;
        CHECK(size >= 0);
        if (!size) break;
        for (ssize_t i = 0; i < size; ++i) CHECK(buffer[i] == 'x');
        total += (size_t)size;
    }
    CHECK(total == 12289);
    puts("OKSH_STREAM bytes=12289");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 2) {
        if (!strcmp(argv[1], "emit")) return emit();
        if (!strcmp(argv[1], "verify")) return verify_stream();
        if (!strcmp(argv[1], "both")) return write(1, "out\n", 4) == 4 && write(2, "err\n", 4) == 4 ? 0 : 1;
        if (!strcmp(argv[1], "fail")) return 23;
        return 2;
    }
    CHECK(launch("echo 'quoted | value' \"\" escaped\\ space|cat|cat>/tmp/oksh-quoted") == 0);
    CHECK(contents("/tmp/oksh-quoted", "quoted | value  escaped space\n"));
    CHECK(launch("cat</tmp/oksh-quoted|cat>/tmp/oksh-copy") == 0);
    CHECK(launch("echo tail>>/tmp/oksh-copy") == 0);
    CHECK(contents("/tmp/oksh-copy", "quoted | value  escaped space\ntail\n"));
    CHECK(launch("echo replaced>/tmp/oksh-copy") == 0);
    CHECK(contents("/tmp/oksh-copy", "replaced\n"));
    CHECK(launch("oksh-acceptance both >/tmp/oksh-both 2>&1") == 0);
    CHECK(contents("/tmp/oksh-both", "out\nerr\n"));
    CHECK(launch("oksh-acceptance both 2>&1 >/tmp/oksh-out | cat >/tmp/oksh-err") == 0);
    CHECK(contents("/tmp/oksh-out", "out\n"));
    CHECK(contents("/tmp/oksh-err", "err\n"));
    CHECK(launch("oksh-acceptance both >/tmp/oksh-out 2>>/tmp/oksh-err") == 0);
    CHECK(contents("/tmp/oksh-err", "err\nerr\n"));
    /* The RAM VFS file limit is 4096 bytes. Verify a larger-than-pipe stream
     * in the final process, then redirect its small result record. */
    CHECK(launch("oksh-acceptance emit | cat | cat | oksh-acceptance verify >/tmp/oksh-large") == 0);
    CHECK(contents("/tmp/oksh-large", "OKSH_STREAM bytes=12289\n"));
    CHECK(launch("oksh-acceptance fail | cat") == 0);
    CHECK(launch("echo ignored | oksh-acceptance fail") == 23);
    CHECK(launch("exit 19") == 19);
    CHECK(launch("echo failure 1>&-") == 1);
    CHECK(launch("missing-oksh-command") == 127);
    CHECK(launch("echo fail >/absent/oksh-target") == 1);
    CHECK(launch("echo fail >/tmp/oksh-no-side |") == 2);
    CHECK(absent("/tmp/oksh-no-side"));
    CHECK(launch("echo first >/tmp/oksh-lists;oksh-acceptance fail&&echo skipped >>/tmp/oksh-lists||echo fallback >>/tmp/oksh-lists;echo final >>/tmp/oksh-lists;") == 0);
    CHECK(contents("/tmp/oksh-lists", "first\nfallback\nfinal\n"));
    /* Equal left-associative precedence makes the final && run after the
     * successful first command, even though the intervening || was skipped. */
    CHECK(launch("echo first >/tmp/oksh-list-left||echo skipped >/tmp/oksh-list-no-side&&echo left >/tmp/oksh-list-left") == 0);
    CHECK(contents("/tmp/oksh-list-left", "left\n"));
    CHECK(absent("/tmp/oksh-list-no-side"));
    CHECK(launch("oksh-acceptance fail&&echo skipped;exit") == 23);
    CHECK(launch("exit 19;echo unreachable >/tmp/oksh-list-exit") == 19);
    CHECK(absent("/tmp/oksh-list-exit"));
    CHECK(launch("exit 4|cat&&echo alive >/tmp/oksh-list-child-exit") == 0);
    CHECK(contents("/tmp/oksh-list-child-exit", "alive\n"));
    CHECK(launch("echo side >/tmp/oksh-list-invalid;echo invalid&&") == 2);
    CHECK(absent("/tmp/oksh-list-invalid"));
    CHECK(launch("echo side >/tmp/oksh-list-invalid||echo invalid >") == 2);
    CHECK(absent("/tmp/oksh-list-invalid"));
    CHECK(launch("cd /tmp&&echo from-temp >oksh-list-cwd;cd /&&cat </tmp/oksh-list-cwd >/tmp/oksh-list-cwd-copy") == 0);
    CHECK(contents("/tmp/oksh-list-cwd-copy", "from-temp\n"));
    CHECK(launch("oksh-acceptance fail|cat&&echo pipeline >/tmp/oksh-list-pipeline") == 0);
    CHECK(contents("/tmp/oksh-list-pipeline", "pipeline\n"));
    CHECK(launch("echo failure 1>&-||echo recovered >/tmp/oksh-list-restored;echo visible >>/tmp/oksh-list-restored") == 0);
    CHECK(contents("/tmp/oksh-list-restored", "recovered\nvisible\n"));
    for (unsigned round = 0; round < 20; ++round)
        CHECK(launch("echo repeat | cat | cat >/tmp/oksh-repeat&&echo list >/tmp/oksh-list-repeat;echo after >/tmp/oksh-list-after") == 0);
    CHECK(contents("/tmp/oksh-repeat", "repeat\n"));
    CHECK(contents("/tmp/oksh-list-repeat", "list\n"));
    CHECK(contents("/tmp/oksh-list-after", "after\n"));
    CHECK(nf_marker("\nOKSH_LISTS sequential=pass short-circuit=pass left-associative=pass pipeline=pass parent-builtin=pass exit=pass syntax=pass repeat=pass\n") == 0);
    return nf_marker("\nOK_OKSH_NATIVE scope=hardware pipeline=pass redirection=pass append=pass stderr=pass order=pass status=pass quoting=pass errors=pass repeat=pass bytes=12289\n") ? 1 : 0;
}
