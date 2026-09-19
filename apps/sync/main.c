#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
int main(void)
{
    int fd = open("/", O_RDONLY | O_DIRECTORY);
    if (fd < 0 || fsync(fd) != 0)
    {
        perror("sync");
        if (fd >= 0) close(fd);
        return 1;
    }
    close(fd);
    puts("Filesystem synchronized");
    return 0;
}
