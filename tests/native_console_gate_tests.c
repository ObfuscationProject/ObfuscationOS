#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static char trace[64];
static unsigned used, interrupted;
static int pipe_error, close_error, io_error, claim_result;
static ssize_t io_count;
static unsigned char input_message[5];
static size_t input_offset;

static void event(char value) { assert(used + 1 < sizeof(trace)); trace[used++] = value; trace[used] = 0; }
static int gate_pipe(int ends[2], int flags)
{
    event('P'); assert(flags == O_CLOEXEC);
    if (pipe_error) { errno = pipe_error; return -1; }
    ends[0] = 3; ends[1] = 4; return 0;
}
static int ns_close(int *owner)
{
    if (*owner < 0) return 0;
    assert(*owner == 3 || *owner == 4); *owner = -1; event('C');
    if (close_error) { errno = EIO; return -1; }
    return 0;
}
int ok_console_claim(pid_t pid)
{
    assert(pid == 17); event('Q');
    if (claim_result < 0) errno = EACCES;
    return claim_result;
}
static ssize_t gate_write(int fd, const void *bytes, size_t size)
{
    assert(fd == 4 && size == 5 && !memcmp(bytes, "\x43\x1d\0\0\0", 5)); event('W');
    if (interrupted) { --interrupted; errno = EINTR; return -1; }
    if (io_error) { errno = io_error; return -1; }
    return io_count;
}
static ssize_t gate_read(int fd, void *bytes, size_t size)
{
    assert(fd == 3 && size > 0 && size <= 5); event('R');
    if (interrupted) { --interrupted; errno = EINTR; return -1; }
    if (io_error) { errno = io_error; return -1; }
    size_t count = io_count < (ssize_t)size ? (size_t)io_count : size;
    memcpy(bytes, input_message + input_offset, count); input_offset += count; return (ssize_t)count;
}

#define pipe2 gate_pipe
#define read gate_read
#define write gate_write
#include "../apps/init/native_console_gate.h"

static struct ns_console_gate reset(void)
{
    used = interrupted = 0; trace[0] = 0;
    pipe_error = close_error = io_error = 0;
    claim_result = 29; io_count = 5; input_offset = 0;
    memcpy(input_message, "\x43\x1d\0\0\0", 5);
    struct ns_console_gate gate;
    assert(!ns_console_gate_prepare(&gate, 1)); assert(!strcmp(trace, "P"));
    used = 0; trace[0] = 0; return gate;
}

int main(void)
{
    struct ns_console_gate gate;
    uint32_t epoch = 0;
    assert(!ns_console_gate_prepare(&gate, 0));
    assert(gate.reader == -1 && gate.writer == -1 && !used);
    assert(!ns_console_gate_child(&gate, &epoch) && !ns_console_gate_parent(&gate, 17, &epoch) && !epoch);
    pipe_error = EMFILE;
    assert(ns_console_gate_prepare(&gate, 1) == -1 && errno == EMFILE && gate.reader == -1 && gate.writer == -1);

    gate = reset();
    assert(!ns_console_gate_parent(&gate, 17, &epoch) && epoch == 29 && !strcmp(trace, "CQWC"));
    assert(!ns_console_gate_close(&gate) && !strcmp(trace, "CQWC"));
    gate = reset(); interrupted = 1; epoch = 0;
    assert(!ns_console_gate_parent(&gate, 17, &epoch) && epoch == 29 && !strcmp(trace, "CQWWC"));
    gate = reset(); claim_result = -1; epoch = 0;
    assert(ns_console_gate_parent(&gate, 17, &epoch) == -1 && errno == EACCES && !epoch && !strcmp(trace, "CQ"));
    assert(!ns_console_gate_close(&gate) && !strcmp(trace, "CQC"));
    gate = reset(); claim_result = 0; epoch = 0;
    assert(ns_console_gate_parent(&gate, 17, &epoch) == -1 && errno == EIO && !epoch && !strcmp(trace, "CQ"));
    assert(!ns_console_gate_close(&gate));
    for (int fault = 0; fault < 2; ++fault) {
        gate = reset(); epoch = 0;
        if (fault) io_error = EPIPE; else io_count = 0;
        assert(ns_console_gate_parent(&gate, 17, &epoch) == -1 && epoch == 29);
        assert(errno == (fault ? EPIPE : EIO) && !strcmp(trace, "CQWC"));
        assert(gate.writer == -1 && !ns_console_gate_close(&gate));
    }
    gate = reset(); close_error = 1; epoch = 0;
    assert(ns_console_gate_parent(&gate, 17, &epoch) == -1 && !epoch && !strcmp(trace, "C"));
    close_error = 0; assert(!ns_console_gate_close(&gate));

    gate = reset();
    assert(!ns_console_gate_child(&gate, &epoch) && !strcmp(trace, "CRC") && !ns_console_gate_close(&gate));
    gate = reset(); interrupted = 1;
    assert(!ns_console_gate_child(&gate, &epoch) && !strcmp(trace, "CRRC"));
    gate = reset(); io_count = 1; epoch = 0;
    assert(!ns_console_gate_child(&gate, &epoch) && epoch == 29 && !strcmp(trace, "CRRRRRC"));
    gate = reset(); memset(input_message + 1, 0, 4); epoch = 0;
    assert(ns_console_gate_child(&gate, &epoch) == -1 && errno == EIO && !epoch);
    for (int fault = 0; fault < 3; ++fault) {
        gate = reset();
        if (fault == 0) io_count = 0;
        if (fault == 1) input_message[0] = 0;
        if (fault == 2) io_error = EACCES;
        assert(ns_console_gate_child(&gate, &epoch) == -1 && errno == (fault == 2 ? EACCES : EIO));
        assert(!strcmp(trace, "CRC") && !ns_console_gate_close(&gate));
    }
    puts("Hosted console gate ownership and failure controls passed; no guest isolation claim");
}
