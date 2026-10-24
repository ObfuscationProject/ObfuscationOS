#include "../resolver/resolver.h"
#include <errno.h>
#include <poll.h>
#include <stdio.h>
#include <unistd.h>

static struct rs_hosts hosts;
static struct rs_workspace workspace;
static struct rs_server server;

int main(int argc, char **argv, char **environment)
{
    int ready = rs_ready_descriptor(environment);
    (void)argv;
    rs_server_reset(&server);
    if (argc != 1 || getppid() != 1 || geteuid() || getegid() || ready < 0) {
        fputs("resolved: invalid service launch\n", stderr); return 1;
    }
    if (rs_service_open(&server, &hosts, &workspace, ready) < 0) goto done;
    for (;;) {
        uint64_t now;
        if (rs_clock(&now) < 0 || rs_server_step(&server, now) < 0) break;
        struct pollfd wait[2] = {
            {.fd = server.client.fd < 0 ? server.listener : -1, .events = POLLIN},
            {.fd = server.client.fd, .events = server.client.reply.size ? POLLOUT : POLLIN}
        };
        if (poll(wait, 2, 10) < 0 && errno != EINTR) break;
    }
done:
    perror("resolved"); rs_server_close(&server); return 1;
}
