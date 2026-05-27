#include <errno.h>
#include <ok/syscall.h>
#include <stdio.h>

static const char *default_module_path = "/boot/modules/system-gui.okmod";

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : default_module_path;
    long result = ok_syscall_ret(ok_syscall1(OK_SYS_LOAD_MODULE, (long)path));
    if (result < 0) {
        printf("kmodload: failed to load %s: errno=%d\n", path, errno);
        return 1;
    }
    printf("kmodload: loaded %s\n", path);
    return 0;
}
