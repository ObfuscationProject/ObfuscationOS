#include <fcntl.h>
#include <ok/syscall.h>
#include <stdio.h>
#include <unistd.h>

static const char *system_gui_module_path = "/boot/modules/system-gui.okmod";

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    puts("ObfuscationOS init: userland online");
    puts("ObfuscationOS init: /bin/oksh is available once execve lands in the kernel");
    if (ok_syscall_ret(ok_syscall1(OK_SYS_LOAD_MODULE, (long)system_gui_module_path)) == 0) {
        puts("ObfuscationOS init: loaded system GUI module");
    } else {
        puts("ObfuscationOS init: system GUI module not loaded");
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
