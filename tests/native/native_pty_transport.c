#include "native_fixture_record.h"
#include <ok/pty.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <sys/wait.h>

_Static_assert(sizeof(int) == 4 && OK_NATIVE_PTY_PAIR_VERSION == 1,
               "native raw PTY contract");

static unsigned cases;
static const char *nonce;

static int record(const char *stage, unsigned value)
{
    struct native_fixture_record out = {0};
    nf_text(&out, "\nNATIVE_PTY_TRANSPORT stage="); nf_text(&out, stage);
    nf_text(&out, " pid="); nf_number(&out, (unsigned)getpid());
    nf_text(&out, " value="); nf_number(&out, value);
    nf_text(&out, " nonce="); nf_text(&out, nonce); nf_text(&out, "\n");
    if (out.failed) return -1;
    ssize_t result;
    do { result = write(STDERR_FILENO, out.bytes, out.size); } while (result < 0 && errno == EINTR);
    return result == (ssize_t)out.size ? 0 : -1;
}

static int failure(unsigned code)
{
    (void)record("FAIL", code);
    return code > 0 && code < 256 ? (int)code : 255;
}
#define REQUIRE(condition, code) do { if (!(condition)) return failure(code); } while (0)

static int transfer(int fd, void *bytes, size_t size, int writing)
{
    size_t done = 0;
    while (done < size) {
        ssize_t count = writing ? write(fd, (char *)bytes + done, size - done)
                                : read(fd, (char *)bytes + done, size - done);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0 || (size_t)count > size - done) return -1;
        done += (size_t)count;
    }
    return 0;
}

static int reaped(pid_t pid)
{
    int status = 0;
    pid_t result;
    do { result = waitpid(pid, &status, 0); } while (result < 0 && errno == EINTR);
    return result == pid && WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
}

static int host_gate(unsigned expected)
{
    unsigned char byte = 0;
    ssize_t result;
    do { result = read(STDIN_FILENO, &byte, 1); } while (result < 0 && errno == EINTR);
    return result == 1 && byte == expected ? 0 : -1;
}

static int independent_streams(void)
{
    int first[2], second[2];
    REQUIRE(ok_pty_pair(first, OK_PTY_NONBLOCK | OK_PTY_CLOEXEC) == 0, 10);
    REQUIRE(ok_pty_pair(second, OK_PTY_NONBLOCK) == 0, 11);
    for (unsigned a = 0; a < 2; ++a) {
        REQUIRE(first[a] >= 3 && second[a] >= 3 && first[a] != second[0] && first[a] != second[1], 12);
        REQUIRE(fcntl(first[a], F_GETFD) == FD_CLOEXEC && fcntl(second[a], F_GETFD) == 0, 13);
    }
    REQUIRE(first[0] != first[1] && second[0] != second[1], 14);
    static const unsigned char traffic[4][5] = {
        {0, 1, 2, 0x80, 0xff}, {9, 0, 7, 0xff, 0x80},
        {0x80, 0, 3, 4, 0xff}, {0xff, 0x80, 6, 0, 8}
    };
    int ends[4] = {first[0], first[1], second[0], second[1]};
    for (unsigned index = 0; index < 4; ++index)
        REQUIRE(write(ends[index], traffic[index], sizeof(traffic[index])) == (ssize_t)sizeof(traffic[index]), 15);
    for (unsigned index = 0; index < 4; ++index) {
        unsigned char bytes[5] = {0};
        REQUIRE(read(ends[index], bytes, sizeof(bytes)) == (ssize_t)sizeof(bytes) &&
                memcmp(bytes, traffic[index ^ 1u], sizeof(bytes)) == 0, 16);
        errno = 0;
        REQUIRE(read(ends[index], bytes, 1) == -1 && errno == EAGAIN, 17);
        struct stat info;
        REQUIRE(fstat(ends[index], &info) == 0 && S_ISCHR(info.st_mode), 18);
        errno = 0;
        REQUIRE(lseek(ends[index], 0, SEEK_SET) == -1 && errno == ESPIPE, 19);
        pid_t group = 0;
        errno = 0;
        REQUIRE(ioctl(ends[index], TIOCGPGRP, &group) == -1 && errno == ENOTTY, 20);
    }
    const int alias = dup(first[0]);
    REQUIRE(alias >= 3 && alias != first[0] && alias != first[1], 21);
    REQUIRE(fcntl(alias, F_GETFD) == 0 && (fcntl(alias, F_GETFL) & O_NONBLOCK), 22);
    REQUIRE(fcntl(alias, F_SETFL, 0) == 0 && !(fcntl(first[0], F_GETFL) & O_NONBLOCK), 23);
    REQUIRE(fcntl(first[0], F_SETFL, O_NONBLOCK) == 0 && (fcntl(alias, F_GETFL) & O_NONBLOCK), 24);
    REQUIRE(close(first[0]) == 0 && write(alias, traffic[0], 5) == 5, 25);
    unsigned char bytes[5] = {0};
    REQUIRE(read(first[1], bytes, 5) == 5 && !memcmp(bytes, traffic[0], 5), 26);
    REQUIRE(close(alias) == 0 && close(first[1]) == 0 && close(second[0]) == 0 && close(second[1]) == 0, 27);
    ++cases; return record("independent-binary-streams", cases);
}

static int retired_sides(void)
{
    for (unsigned closed_side = 0; closed_side < 2; ++closed_side) {
        int fds[2];
        REQUIRE(ok_pty_pair(fds, OK_PTY_NONBLOCK) == 0, 30);
        unsigned char bytes[3] = {0, 0x80, 0xff}, received[3] = {0};
        REQUIRE(write(fds[closed_side], bytes, 3) == 3 && close(fds[closed_side]) == 0, 31);
        const int live = fds[closed_side ^ 1u];
        struct pollfd descriptor = {live, 0, 0};
        REQUIRE(poll(&descriptor, 1, 0) == 1 && (descriptor.revents & POLLHUP), 32);
        REQUIRE(!!(descriptor.revents & POLLERR) == (closed_side == 0), 33);
        REQUIRE(!(descriptor.revents & (POLLIN | POLLOUT)), 34);
        descriptor.events = POLLIN | POLLOUT;
        REQUIRE(poll(&descriptor, 1, 0) == 1 && (descriptor.revents & POLLIN) &&
                (descriptor.revents & POLLHUP) && !(descriptor.revents & POLLOUT), 35);
        REQUIRE(read(live, received, 3) == 3 && !memcmp(bytes, received, 3), 36);
        errno = 0;
        const ssize_t final_read = read(live, received, 1);
        REQUIRE(closed_side == 0 ? final_read == 0 : final_read == -1 && errno == EIO, 37);
        errno = 0;
        REQUIRE(write(live, bytes, 1) == -1 && errno == EIO, 38);
        REQUIRE(read(live, received, 0) == 0 && write(live, bytes, 0) == 0 && close(live) == 0, 39);
    }
    ++cases; return record("peer-retire-drain-eof-eio-hangup", cases);
}

static int vector_stdio(void)
{
    int fds[2];
    REQUIRE(ok_pty_pair(fds, 0) == 0, 40);
    const pid_t child = fork();
    REQUIRE(child >= 0, 41);
    if (!child) {
        if (close(fds[0]) || dup2(fds[1], STDIN_FILENO) != STDIN_FILENO ||
            dup2(fds[1], STDOUT_FILENO) != STDOUT_FILENO || close(fds[1])) _Exit(42);
        unsigned char first[3] = {0}, second[4] = {0};
        struct iovec input[2] = {{first, sizeof(first)}, {second, sizeof(second)}};
        if (readv(STDIN_FILENO, input, 2) != 7) _Exit(43);
        if (first[0] != 0 || first[1] != 0x80 || first[2] != 0xff ||
            second[0] != 'r' || second[1] != 0 || second[2] != 'w' || second[3] != 0x80) _Exit(44);
        struct iovec output[2] = {{second, sizeof(second)}, {first, sizeof(first)}};
        if (writev(STDOUT_FILENO, output, 2) != 7) _Exit(45);
        _Exit(0);
    }
    REQUIRE(close(fds[1]) == 0, 46);
    unsigned char input[7] = {0, 0x80, 0xff, 'r', 0, 'w', 0x80}, response[7] = {0};
    REQUIRE(transfer(fds[0], input, sizeof(input), 1) == 0 &&
            transfer(fds[0], response, sizeof(response), 0) == 0, 47);
    REQUIRE(!memcmp(response, input + 3, 4) && !memcmp(response + 4, input, 3), 48);
    REQUIRE(reaped(child) == 0 && close(fds[0]) == 0, 49);
    ++cases; return record("fork-dup2-vector-stdio", cases);
}

static int gated_read(void)
{
    int fds[2];
    REQUIRE(ok_pty_pair(fds, 0) == 0, 50);
    const pid_t child = fork();
    REQUIRE(child >= 0, 51);
    if (!child) {
        if (close(fds[0]) || record("read-enter", (unsigned)fds[1])) _Exit(52);
        unsigned char bytes[5] = {0};
        if (transfer(fds[1], bytes, 5, 0) || memcmp(bytes, "r\0\200\377x", 5) ||
            record("read-complete", 5)) _Exit(53);
        _Exit(0);
    }
    REQUIRE(close(fds[1]) == 0 && record("read-host-gate", (unsigned)child) == 0, 54);
    // The external observer must inspect an armed PTY wait before releasing
    // this gate. Enter/complete records alone do not prove scheduler blocking.
    REQUIRE(host_gate('R') == 0, 55);
    unsigned char bytes[5] = {'r', 0, 0x80, 0xff, 'x'};
    REQUIRE(transfer(fds[0], bytes, 5, 1) == 0 && reaped(child) == 0 && close(fds[0]) == 0, 56);
    ++cases; return record("gated-read-finished-observer-proof-required", cases);
}

static int gated_write(void)
{
    int fds[2];
    REQUIRE(ok_pty_pair(fds, OK_PTY_NONBLOCK) == 0, 60);
    static unsigned char buffer[4096];
    for (unsigned index = 0; index < sizeof(buffer); ++index) buffer[index] = (unsigned char)index;
    REQUIRE(write(fds[0], buffer, sizeof(buffer)) == (ssize_t)sizeof(buffer), 61);
    errno = 0;
    REQUIRE(write(fds[0], buffer, 1) == -1 && errno == EAGAIN, 62);
    REQUIRE(fcntl(fds[0], F_SETFL, 0) == 0 && fcntl(fds[1], F_SETFL, 0) == 0, 63);
    const pid_t child = fork();
    REQUIRE(child >= 0, 64);
    if (!child) {
        const unsigned char byte = 0xd3;
        if (close(fds[1]) || record("write-enter", (unsigned)fds[0]) ||
            write(fds[0], &byte, 1) != 1 || record("write-complete", 1)) _Exit(65);
        _Exit(0);
    }
    REQUIRE(close(fds[0]) == 0 && record("write-host-gate", (unsigned)child) == 0, 66);
    REQUIRE(host_gate('W') == 0 && transfer(fds[1], buffer, sizeof(buffer), 0) == 0, 67);
    for (unsigned index = 0; index < sizeof(buffer); ++index) REQUIRE(buffer[index] == (unsigned char)index, 68);
    unsigned char final_byte = 0;
    REQUIRE(transfer(fds[1], &final_byte, 1, 0) == 0 && final_byte == 0xd3, 69);
    REQUIRE(reaped(child) == 0 && close(fds[1]) == 0, 70);
    ++cases; return record("gated-write-finished-observer-proof-required", cases);
}

int main(int argc, char **argv)
{
    if (argc != 3 || strlen(argv[1]) != 32 ||
        (strcmp(argv[2], "auto") && strcmp(argv[2], "gated"))) return 2;
    nonce = argv[1];
    for (unsigned index = 0; index < 32; ++index)
        if (!((nonce[index] >= '0' && nonce[index] <= '9') || (nonce[index] >= 'a' && nonce[index] <= 'f'))) return 2;
    REQUIRE(record("BEGIN", !strcmp(argv[2], "gated")) == 0, 3);
    if (independent_streams() || retired_sides() || vector_stdio()) return 4;
    if (!strcmp(argv[2], "gated") && (gated_read() || gated_write())) return 5;
    REQUIRE(record("PASS", cases) == 0, 6);
    return 0;
}
