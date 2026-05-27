#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    puts("ObfuscationOS init: userland online");
    puts("ObfuscationOS init: /bin/oksh is available once execve lands in the kernel");

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
