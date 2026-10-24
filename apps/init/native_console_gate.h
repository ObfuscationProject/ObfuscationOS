#ifndef NATIVE_CONSOLE_GATE_H
#define NATIVE_CONSOLE_GATE_H

#include <ok/console.h>

struct ns_console_gate { int reader, writer; };

static int ns_console_gate_close(struct ns_console_gate *gate)
{
    int first = ns_close(&gate->reader), saved = errno;
    int second = ns_close(&gate->writer);
    if (first < 0) { errno = saved; return -1; }
    return second;
}

static int ns_console_gate_prepare(struct ns_console_gate *gate, int selected)
{
    *gate = (struct ns_console_gate){-1, -1};
    if (!selected) return 0;
    int ends[2];
    if (pipe2(ends, O_CLOEXEC) < 0) return -1;
    gate->reader = ends[0]; gate->writer = ends[1];
    return 0;
}

static int ns_console_gate_child(struct ns_console_gate *gate, uint32_t *epoch)
{
    *epoch = 0;
    if (gate->reader < 0) return 0;
    if (ns_close(&gate->writer) < 0) return -1;
    unsigned char message[5] = {0};
    size_t size = 0;
    int error = 0;
    while (size < sizeof(message)) {
        ssize_t count = read(gate->reader, message + size, sizeof(message) - size);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) { error = count < 0 ? errno : EIO; break; }
        size += (size_t)count;
    }
    if (ns_close(&gate->reader) < 0) return -1;
    if (error) { errno = error; return -1; }
    uint32_t received = (uint32_t)message[1] | (uint32_t)message[2] << 8 |
                        (uint32_t)message[3] << 16 | (uint32_t)message[4] << 24;
    if (message[0] != 0x43 || !received || received > 0x3fffffffU) { errno = EIO; return -1; }
    *epoch = received;
    return 0;
}

static int ns_console_gate_parent(struct ns_console_gate *gate, pid_t pid, uint32_t *epoch)
{
    if (gate->writer < 0) return 0;
    if (ns_close(&gate->reader) < 0) return -1;
    int claimed = ok_console_claim(pid);
    if (claimed <= 0 || claimed > 0x3fffffff) { if (claimed >= 0) errno = EIO; return -1; }
    *epoch = (uint32_t)claimed;
    const unsigned char message[] = {0x43, (unsigned char)*epoch, (unsigned char)(*epoch >> 8),
        (unsigned char)(*epoch >> 16), (unsigned char)(*epoch >> 24)};
    ssize_t count;
    do { count = write(gate->writer, message, sizeof(message)); } while (count < 0 && errno == EINTR);
    int error = count < 0 ? errno : EIO;
    if (ns_close(&gate->writer) < 0) return -1;
    if (count != sizeof(message)) { errno = error; return -1; }
    return 0;
}

#endif
