/* Explicit non-default fixture for the bounded native TCP immediate profile. */
#include <ok/syscall.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifndef OK_NATIVE_TCP_PEER_PORT
#error "TCP execution fixture requires an explicit host peer port"
#endif
_Static_assert(OK_NATIVE_TCP_PEER_PORT > 1024 && OK_NATIVE_TCP_PEER_PORT < 65535, "host peer port interval");
_Static_assert(sizeof(struct ok_sockaddr_in) == 16, "native TCP copied address layout");

static const struct ok_sockaddr_in local = {OK_AF_INET, {0xd4, 0x31}, {10, 0, 2, 15}, {0}};
static const struct ok_sockaddr_in peer = {OK_AF_INET,
    {(OK_NATIVE_TCP_PEER_PORT >> 8) & 255, OK_NATIVE_TCP_PEER_PORT & 255}, {10, 0, 2, 2}, {0}};
static const struct ok_sockaddr_in refused_peer = {OK_AF_INET,
    {((OK_NATIVE_TCP_PEER_PORT + 1) >> 8) & 255, (OK_NATIVE_TCP_PEER_PORT + 1) & 255}, {10, 0, 2, 2}, {0}};
static const struct ok_sockaddr_in refused_local = {OK_AF_INET, {0xd4, 0x32}, {10, 0, 2, 15}, {0}};

static void marker(const char *record)
{
    const size_t size = strlen(record);
    if (write(1, record, size) != (ssize_t)size) _Exit(2);
}
static void check(int passed, const char *reason)
{
    if (passed) return;
    marker("OK_NATIVE_TCP acceptance=FAIL reason="); marker(reason); marker("\n"); _Exit(1);
}
static void delay(void)
{
    const struct timespec interval = {0, 1000000};
    check(nanosleep(&interval, 0) == 0, "retry-clock");
}
static long await_io(unsigned long number, int fd, void *bytes, unsigned long size)
{
    for (unsigned int attempt = 0; attempt < 5000; ++attempt)
    {
        const long result = ok_syscall3(number, fd, (long)bytes, (long)size);
        if (result != -OK_EAGAIN) return result;
        delay();
    }
    check(0, "io-timeout"); return -1;
}
static long stream(void)
{
    const long fd = ok_syscall3(OK_SYS_SOCKET, OK_AF_INET,
        OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC, OK_IPPROTO_TCP);
    check(fd >= 3, "socket"); return fd;
}
int main(void)
{
    marker("OK_NATIVE_TCP phase=begin peer=host-os-socket\n");
    const long fd = stream();
    check(ok_syscall3(OK_SYS_BIND, fd, (long)&local, sizeof(local)) == 0, "bind");
    check(ok_syscall3(OK_SYS_CONNECT, fd, (long)&peer, sizeof(peer)) == -OK_EINPROGRESS, "connect-start");
    const long duplicate = ok_syscall1(OK_SYS_DUP, fd); check(duplicate >= 3, "dup");
    const pid_t child = fork(); check(child >= 0, "fork");
    if (!child)
    {
        check(close((int)fd) == 0 && close((int)duplicate) == 0, "child-inherited-close");
        marker("OK_NATIVE_TCP phase=fork-close\n"); return 0;
    }
    int status = 0;
    check(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0, "wait-child");
    check(close((int)fd) == 0, "original-close");
    char request[] = "HELLO";
    check(await_io(OK_SYS_WRITE, (int)duplicate, request, 5) == 5, "handshake-write");
    marker("OK_NATIVE_TCP phase=handshake-payload\n");
    check(ok_syscall2(OK_SYS_SHUTDOWN, duplicate, OK_SHUT_WR) == 0, "write-shutdown");
    check(ok_syscall3(OK_SYS_WRITE, duplicate, (long)request, 1) == -OK_EPIPE, "write-after-shutdown");
    check(ok_syscall3(OK_SYS_READ, duplicate, 0, 0) == 0, "zero-read");
    /* A failed output interval must leave bytes available for the next read. */
    for (unsigned int attempt = 0;; ++attempt)
    {
        const long result = ok_syscall3(OK_SYS_READ, duplicate, 0, 8);
        if (result == -OK_EFAULT) break;
        check(result == -OK_EAGAIN && attempt < 5000, "fault-read-preservation"); delay();
    }
    char response[8] = {0}; unsigned long complete = 0; unsigned int reads = 0;
    while (complete < sizeof(response))
    {
        const unsigned long remaining = sizeof(response) - complete;
        const long result = await_io(OK_SYS_READ, (int)duplicate, response + complete,
                                    remaining < 3 ? remaining : 3);
        check(result > 0 && (unsigned long)result <= sizeof(response) - complete, "partial-read");
        complete += (unsigned long)result; ++reads;
    }
    check(reads >= 3 && memcmp(response, "RESPONSE", sizeof(response)) == 0, "english-response");
    char byte = 0; check(await_io(OK_SYS_READ, (int)duplicate, &byte, 1) == 0, "fin-eof");
    check(close((int)duplicate) == 0, "final-close");
    const long reserved = stream();
    check(ok_syscall3(OK_SYS_BIND, reserved, (long)&local, sizeof(local)) == -OK_EEXIST, "time-wait-reservation");
    check(close((int)reserved) == 0, "unbound-close");
    marker("OK_NATIVE_TCP phase=partial-english-fin-close\n");
    const long failure = stream();
    check(ok_syscall3(OK_SYS_BIND, failure, (long)&refused_local, sizeof(refused_local)) == 0, "refused-bind");
    check(ok_syscall3(OK_SYS_CONNECT, failure, (long)&refused_peer, sizeof(refused_peer)) == -OK_EINPROGRESS, "refused-start");
    check(await_io(OK_SYS_READ, (int)failure, &byte, 1) == -OK_ECONNREFUSED, "owned-host-port-refusal");
    check(close((int)failure) == 0, "refused-close");
    marker("OK_NATIVE_TCP acceptance=pass guest=1 virtio=1 host_os_socket=1 physical_machine=0\n");
    return 0;
}
