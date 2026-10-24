#include "../time/time_service.h"
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    struct ts_request request = {0};
    uint64_t seconds, nanoseconds = 0;
    if (argc == 2 && !strcmp(argv[1], "status")) request.operation = TS_STATUS;
    else if ((argc == 3 || argc == 4) && !strcmp(argv[1], "set") &&
             !ts_unsigned(argv[2], strlen(argv[2]), TS_MAX_SECONDS - 1, &seconds) &&
             (argc == 3 || !ts_unsigned(argv[3], strlen(argv[3]), 999999999, &nanoseconds)))
        request = (struct ts_request){TS_SET, (int64_t)seconds, (uint32_t)nanoseconds};
    else { fputs("usage: timectl status | set SECONDS [NANOSECONDS]\n", stderr); return 2; }
    struct ts_buffer wire;
    struct ts_reply reply;
    if (ts_exchange(&request, &wire, &reply) < 0) { perror("timectl"); return 1; }
    FILE *output = reply.operation == TS_ERROR ? stderr : stdout;
    for (size_t i = 0; i < wire.size; ++i)
        if (fputc((unsigned char)wire.bytes[i], output) < 0) return 1;
    return reply.operation == TS_ERROR ? 1 : 0;
}
