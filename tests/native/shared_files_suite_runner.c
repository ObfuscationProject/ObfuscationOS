#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

static int run(const char *path, char *name)
{
    const pid_t child = fork();
    if (child < 0) return 170;
    if (!child) {
        char *args[] = {name, 0};
        char *environment[] = {"PATH=/bin", 0};
        execve(path, args, environment);
        _Exit(126);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status)) return 171;
    return 0;
}

int main(void)
{
    int result = run("/bin/shared-files-native", "shared-files-native");
    if (!result) result = run("/bin/shared-rights-native", "shared-rights-native");
    if (!result) result = run("/bin/shared-files-static", "shared-files-static");
    if (!result) result = run("/bin/shared-rights-static", "shared-rights-static");
    if (result) return result;
    static const char marker[] = "OK_SHARED_FILES_SUITE native=2 static_musl=2 child_exit=0\n";
    return write(1, marker, sizeof marker - 1) == sizeof marker - 1 ? 0 : 172;
}
