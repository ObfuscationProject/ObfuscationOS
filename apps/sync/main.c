#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
int main(int argc, char **argv)
{
    // An explicit file or directory also reaches non-root data filesystems.
    for (int i = 1; i < (argc > 1 ? argc : 2); ++i)
    {
        int fd = open(argc > 1 ? argv[i] : "/", O_RDONLY);
        if (fd < 0 || fsync(fd) != 0)
        {
            perror("sync");
            if (fd >= 0) close(fd);
            return 1;
        }
        if (close(fd) != 0) { perror("sync"); return 1; }
    }
    puts("Filesystem synchronized");
    return 0;
}
