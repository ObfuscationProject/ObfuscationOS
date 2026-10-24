#include "../init/native_control_client.h"
#include <errno.h>
#include <stdio.h>
#include <unistd.h>

static int emit(int fd, const char *bytes, size_t size)
{
    size_t sent = 0;
    while (sent < size) {
        ssize_t count = write(fd, bytes + sent, size - sent);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return -1;
        sent += (size_t)count;
    }
    return 0;
}
int main(int argc, char **argv)
{
    const char *operation = 0, *service = 0;
    if (argc >= 2 && !strcmp(argv[1], "status") && argc <= 3) operation = "STATUS";
    else if (argc == 3 && !strcmp(argv[1], "restart")) operation = "RESTART";
    else if (argc == 2 && !strcmp(argv[1], "state")) operation = "STATE";
    else if (argc == 2 && !strcmp(argv[1], "quiesce")) operation = "QUIESCE";
    else if (argc == 2 && !strcmp(argv[1], "halt")) operation = "HALT";
    else if (argc == 2 && !strcmp(argv[1], "reboot")) operation = "REBOOT";
    else if (argc == 2 && !strcmp(argv[1], "poweroff")) operation = "POWEROFF";
    if (argc == 3) service = argv[2];
    if (!operation || (service && !nc_name(service, strlen(service)))) {
        static const char usage[] = "usage: service-ctl status [SERVICE] | restart SERVICE | state | quiesce | halt | reboot | poweroff\n";
        (void)emit(STDERR_FILENO, usage, sizeof(usage) - 1); return 2;
    }
    struct nc_buffer request = {0}, reply;
    nc_text(&request, NC_PREFIX); nc_text(&request, operation);
    if (service) { nc_text(&request, " "); nc_text(&request, service); }
    nc_text(&request, "\n");
    int result = nc_exchange(request.bytes, request.size, &reply);
    if (result < 0) { perror("service-ctl"); return 1; }
    if (emit(STDOUT_FILENO, reply.bytes, reply.size) < 0) { perror("service-ctl"); return 1; }
    return result;
}
