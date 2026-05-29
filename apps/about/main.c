#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    puts("ObfuscationOS");
    puts("user desktop app");
    printf("uid: %d\n", (int)geteuid());
    return 0;
}
