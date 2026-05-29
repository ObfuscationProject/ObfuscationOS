#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    puts("System Settings");
    puts("palette: mint / blue / rose");
    puts("input: pointer and keyboard enabled");
    printf("uid: %d\n", (int)geteuid());
    return 0;
}
