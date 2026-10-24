#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static void marker(const char *text)
{
    size_t size = strlen(text);
    if (write(1, text, size) != (ssize_t)size) _Exit(2);
}

int main(void)
{
    marker("MUSL_UDP_CONNECTED_RUNNER stage=start\n");
    pid_t child = fork();
    if (child < 0) {
        marker("MUSL_UDP_CONNECTED_RUNNER stage=fail reason=fork\n"); return 1;
    }
    if (child == 0) {
        char *arguments[] = {"musl-udp-connected-probe", 0};
        char *environment[] = {"PATH=/bin", 0};
        execve("/bin/musl-udp-connected-probe", arguments, environment);
        marker("MUSL_UDP_CONNECTED_RUNNER stage=fail reason=exec\n"); _Exit(127);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        marker("MUSL_UDP_CONNECTED_RUNNER stage=fail reason=child-status\n"); return 1;
    }
    marker("MUSL_UDP_CONNECTED_RUNNER stage=pass child_status=0\n"); return 0;
}
