#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    puts("Notes");
    puts("tiny-c scratchpad placeholder");
    printf("cwd: ");
    char cwd[128];
    if (getcwd(cwd, sizeof(cwd)) != NULL) {
        puts(cwd);
    } else {
        puts("/");
    }
    return 0;
}
