#include <fcntl.h>
#include <ok/syscall.h>
#include <stddef.h>
#include <stdio.h>
#include <unistd.h>

static const char *system_gui_modules[] = {
    "/boot/modules/system-gui.okmod",
};

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    puts("ObfuscationOS init: userland online");
    puts("ObfuscationOS init: tiny-c /bin apps are staged for shell and System GUI");
    for (size_t i = 0; i < sizeof(system_gui_modules) / sizeof(system_gui_modules[0]); ++i) {
        if (ok_syscall_ret(ok_syscall1(OK_SYS_LOAD_MODULE, (long)system_gui_modules[i])) == 0) {
            puts("ObfuscationOS init: loaded GUI module");
        } else {
            puts("ObfuscationOS init: GUI module not loaded");
        }
    }

    int fd = open("/etc/os-release", O_RDONLY);
    if (fd >= 0) {
        char buf[256];
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n > 0) {
            write(STDOUT_FILENO, buf, (size_t)n);
            if (buf[n - 1] != '\n') {
                putchar('\n');
            }
        }
        close(fd);
    }

    return 0;
}
