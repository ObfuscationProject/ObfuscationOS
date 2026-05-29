#include <errno.h>
#include <ok/syscall.h>
#include <stddef.h>
#include <stdio.h>

static const char *default_module_path = "/boot/modules/system-gui.okmod";
static const char *default_module_set[] = {
    "/boot/modules/system-gui.okmod",
    "/boot/modules/apps/shell.okmod",
    "/boot/modules/apps/settings.okmod",
    "/boot/modules/apps/tasks.okmod",
    "/boot/modules/apps/notes.okmod",
    "/boot/modules/apps/about.okmod",
};

static int load_one(const char *path)
{
    long result = ok_syscall_ret(ok_syscall1(OK_SYS_LOAD_MODULE, (long)path));
    if (result < 0) {
        printf("kmodload: failed to load %s: errno=%d\n", path, errno);
        return 1;
    }
    printf("kmodload: loaded %s\n", path);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc > 1 && argv[1][0] == '-' && argv[1][1] == '-' && argv[1][2] == 'a' && argv[1][3] == 'l' &&
        argv[1][4] == 'l' && argv[1][5] == '\0') {
        int rc = 0;
        for (size_t i = 0; i < sizeof(default_module_set) / sizeof(default_module_set[0]); ++i) {
            if (load_one(default_module_set[i]) != 0) {
                rc = 1;
            }
        }
        return rc;
    }

    if (argc <= 1) {
        return load_one(default_module_path);
    }
    int rc = 0;
    for (int i = 1; i < argc; ++i) {
        if (load_one(argv[i]) != 0) {
            rc = 1;
        }
    }
    return rc;
}
