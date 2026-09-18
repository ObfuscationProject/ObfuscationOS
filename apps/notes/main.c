#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "/tmp/notes.txt";
    if (argc > 2)
    {
        int fd = open(path, O_CREAT | O_WRONLY | O_TRUNC, 0600);
        if (fd < 0)
        {
            perror(path);
            return 1;
        }
        for (int i = 2; i < argc; ++i)
        {
            if ((i > 2 && write(fd, " ", 1) != 1) || write(fd, argv[i], strlen(argv[i])) != (ssize_t)strlen(argv[i]))
            {
                perror("save");
                close(fd);
                return 1;
            }
        }
        if (write(fd, "\n", 1) != 1)
        {
            close(fd);
            return 1;
        }
        close(fd);
        printf("Saved %s\n", path);
        return 0;
    }
    int fd = open(path, O_RDONLY);
    if (fd < 0)
    {
        puts("Usage: notes [path] [text to save]");
        puts("Default note: /tmp/notes.txt (retained until reboot)");
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
