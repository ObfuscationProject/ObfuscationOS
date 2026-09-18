#include <stdio.h>
#include <unistd.h>

int main(void)
{
    puts("Workspace settings");
    puts("Appearance: light surfaces, cool gray, blue accent");
    puts("Open Settings in the desktop to select an accent.");
    puts("Select an account on the sign-in screen.");
    printf("Current user: %u\n", (unsigned)geteuid());
    char cwd[128];
    if (getcwd(cwd, sizeof(cwd)))
        printf("Working directory: %s\n", cwd);
    return 0;
}
