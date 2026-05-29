#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    puts("Task Manager");
    puts("scheduler: use the GUI window for live process counts");
    printf("pid: %d\n", (int)getpid());
    return 0;
}
