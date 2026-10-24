#include "save.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "/home/notes.txt";
    if (argc > 2)
    {
        enum notes_save_result result = notes_save_words(path, argc - 2, argv + 2);
        if (result != NOTES_SAVE_DONE) {
            if (result == NOTES_SAVE_REPLACED_ERROR)
                fputs("File replaced; save completion failed.\n", stderr);
            perror("save");
            return 1;
        }
        printf("Saved %s\n", path);
        return 0;
    }
    int fd = open(path, O_RDONLY);
    if (fd < 0)
    {
        puts("Usage: notes [path] [text to save]");
        puts("Default note: /home/notes.txt (persistent when booted with ext4)");
        return 1;
    }
    char buffer[256];
    ssize_t count;
    for (;;) {
        count = read(fd, buffer, sizeof(buffer));
        if (count < 0 && errno == EINTR)
            continue;
        if (count <= 0)
            break;
        if (notes_write_all(1, buffer, (size_t)count) < 0) {
            close(fd);
            return 1;
        }
    }
    if (count < 0) {
        int error = errno;
        close(fd);
        errno = error;
        perror("read");
        return 1;
    }
    if (close(fd) < 0) {
        perror("close");
        return 1;
    }
    return 0;
}
