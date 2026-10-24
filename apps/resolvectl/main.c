#include "../resolver/resolver.h"
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    struct rs_request request = {0};
    if (argc == 2 && !strcmp(argv[1], "status")) request.operation = RS_STATUS;
    else if (argc == 3 && !strcmp(argv[1], "lookup") &&
             !rs_query_normalize(argv[2], strlen(argv[2]), request.name)) request.operation = RS_LOOKUP;
    else { fputs("usage: resolvectl status | lookup NAME\n", stderr); return 2; }
    struct rs_buffer wire; struct rs_reply reply;
    if (rs_exchange(&request, &wire, &reply) < 0) { perror("resolvectl"); return 1; }
    FILE *output = reply.operation == RS_ERROR ? stderr : stdout;
    for (size_t i = 0; i < wire.size; ++i)
        if (fputc((unsigned char)wire.bytes[i], output) < 0) return 1;
    return reply.operation == RS_ERROR ? 1 : 0;
}
