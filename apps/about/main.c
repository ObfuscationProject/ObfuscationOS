#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

int main(void)
{
    puts("ObfuscationOS / 0.1 development");
    puts("A C++ kernel with a small POSIX user space.");
    puts("Desktop and applications are provided by ObfuscationOS.");
    int fd = open("/etc/os-release", O_RDONLY);
    if (fd < 0)
    {
        perror("os-release");
        return 1;
    }
    char buffer[256];
    ssize_t count;
    while ((count = read(fd, buffer, sizeof(buffer))) > 0)
        if (write(1, buffer, (size_t)count) != count)
        {
            close(fd);
            return 1;
        }
    close(fd);
    return count < 0 ? 1 : 0;
}
