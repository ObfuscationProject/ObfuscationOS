#include "../time/time_service.h"
#include <errno.h>
#include <poll.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv, char **environment)
{
    struct ts_server server;
    int ready = ts_ready_descriptor(environment);
    (void)argv;
    ts_server_reset(&server);
    if (argc != 1 || getppid() != 1 || geteuid() || getegid() || ready < 0) {
        fputs("timed: invalid service launch\n", stderr); return 1;
    }
    if (ts_service_open(&server, ready) < 0) goto done;
    for (;;) {
        uint64_t now;
        if (ts_clock(&now) < 0 || ts_server_step(&server, now) < 0) break;
        struct pollfd wait[2] = {
            {.fd = server.client.fd < 0 ? server.listener : -1, .events = POLLIN},
            {.fd = server.client.fd, .events = server.client.reply.size ? POLLOUT : POLLIN}
        };
        if (poll(wait, 2, 10) < 0 && errno != EINTR) break;
    }
done:
    perror("timed");
    ts_server_close(&server);
    return 1;
}
