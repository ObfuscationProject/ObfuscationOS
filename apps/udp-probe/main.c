#include <ok/syscall.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

_Static_assert(sizeof(struct ok_sockaddr_in) == 16, "native UDP address size");

#if defined(OK_USER_ARCH_I386)
#define OK_NATIVE_UDP_ARCH "i386"
#elif defined(OK_USER_ARCH_X86_64)
#define OK_NATIVE_UDP_ARCH "x86_64"
#elif defined(OK_USER_ARCH_AARCH64)
#define OK_NATIVE_UDP_ARCH "aarch64"
#elif defined(OK_USER_ARCH_ARM32)
#define OK_NATIVE_UDP_ARCH "arm32"
#elif defined(OK_USER_ARCH_RV64)
#define OK_NATIVE_UDP_ARCH "rv64"
#elif defined(OK_USER_ARCH_RV32)
#define OK_NATIVE_UDP_ARCH "rv32"
#elif defined(OK_USER_ARCH_LOONGARCH64)
#define OK_NATIVE_UDP_ARCH "loongarch64"
#elif defined(OK_USER_ARCH_MIPS)
#define OK_NATIVE_UDP_ARCH "mips"
#elif defined(OK_USER_ARCH_MIPS64)
#define OK_NATIVE_UDP_ARCH "mips64"
#elif defined(OK_USER_ARCH_PPC)
#define OK_NATIVE_UDP_ARCH "ppc"
#else
#error "native UDP probe requires an explicit user architecture"
#endif

#if defined(OK_NATIVE_UDP_TEST_DEBUG) && !defined(OK_NATIVE_UDP_TEST_RELEASE)
#define OK_NATIVE_UDP_MODE "debug"
#elif defined(OK_NATIVE_UDP_TEST_RELEASE) && !defined(OK_NATIVE_UDP_TEST_DEBUG)
#define OK_NATIVE_UDP_MODE "release"
#else
#error "native UDP probe requires exactly one build mode"
#endif

static const struct ok_sockaddr_in peer = {OK_AF_INET, {0x30, 0x39}, {192, 0, 2, 1}, {0}};
static const struct ok_sockaddr_in parent_address = {OK_AF_INET, {0xd4, 0x31}, {192, 0, 2, 2}, {0}};
static const struct ok_sockaddr_in child_address = {OK_AF_INET, {0xd4, 0x30}, {0}, {0}};

static void marker(const char *record)
{
    size_t length = strlen(record);
    if (write(1, record, length) != (ssize_t)length) _Exit(2);
}

static void check(int condition, const char *reason)
{
    if (condition) return;
    static const char prefix[] = "OK_NATIVE_UDP scope=hardware acceptance=FAIL reason=";
    char record[160];
    size_t prefix_length = sizeof(prefix) - 1;
    size_t reason_length = strlen(reason);
    if (prefix_length + reason_length + 1 >= sizeof(record)) _Exit(2);
    memcpy(record, prefix, prefix_length);
    memcpy(record + prefix_length, reason, reason_length);
    record[prefix_length + reason_length] = '\n';
    if (write(1, record, prefix_length + reason_length + 1) !=
        (ssize_t)(prefix_length + reason_length + 1)) _Exit(2);
    _Exit(1);
}

static long receive(int fd, void *buffer, unsigned long length,
                    struct ok_sockaddr_in *source, unsigned int *source_length)
{
    return ok_syscall6(OK_SYS_RECVFROM, fd, (long)buffer, (long)length, 0,
                       (long)source, (long)source_length);
}

static long await_receive(int fd, void *buffer, unsigned long length,
                          struct ok_sockaddr_in *source, unsigned int *source_length)
{
    for (unsigned int attempt = 0; attempt < 5000; ++attempt)
    {
        long result = receive(fd, buffer, length, source, source_length);
        if (result != -OK_EAGAIN) return result;
        const struct timespec delay = {0, 1000000};
        check(nanosleep(&delay, 0) == 0, "receive-delay");
    }
    check(0, "receive-timeout");
    return -1;
}

static void check_source(const struct ok_sockaddr_in *source, unsigned int length)
{
    check(length == sizeof(*source) && source->family == OK_AF_INET &&
          source->port_be[0] == 0x30 && source->port_be[1] == 0x39 &&
          memcmp(source->address, peer.address, sizeof(source->address)) == 0,
          "source-address");
}

int main(void)
{
    marker("OK_NATIVE_UDP profile=" OK_NATIVE_UDP_MODE " arch=" OK_NATIVE_UDP_ARCH "\n");
    long blocking = ok_syscall3(OK_SYS_SOCKET, OK_AF_INET, OK_SOCK_DGRAM, 0);
    check(blocking >= 3, "blocking-admission");
    check(close((int)blocking) == 0, "blocking-close");
    long parent = ok_syscall3(OK_SYS_SOCKET, OK_AF_INET,
                              OK_SOCK_DGRAM | OK_SOCK_NONBLOCK, OK_IPPROTO_UDP);
    check(parent >= 3, "parent-socket");
    check(ok_syscall3(OK_SYS_BIND, parent, (long)&parent_address,
                      sizeof(parent_address)) == 0, "parent-bind");
    long child = ok_syscall0(OK_SYS_FORK);
    check(child >= 0, "fork");
    if (child == 0)
    {
        check(close((int)parent) == 0, "child-close-inherited");
        long socket = ok_syscall3(OK_SYS_SOCKET, OK_AF_INET,
                                  OK_SOCK_DGRAM | OK_SOCK_NONBLOCK, 0);
        check(socket >= 3, "child-socket");
        check(ok_syscall3(OK_SYS_BIND, socket, (long)&child_address,
                          sizeof(child_address)) == 0, "child-bind");
        marker("OK_NATIVE_UDP child=ready port=54320\n");
        char byte = 0;
        struct ok_sockaddr_in source = {0};
        unsigned int source_length = sizeof(source);
        check(await_receive((int)socket, &byte, 1, &source, &source_length) == 1 &&
              byte == 'C', "child-receive");
        check_source(&source, source_length);
        check(close((int)socket) == 0, "child-close");
        marker("OK_NATIVE_UDP child=pass port=54320\n");
        return 0;
    }

    marker("OK_NATIVE_UDP parent=ready port=54321\n");
    const char request[] = "HELLO";
    check(ok_syscall6(OK_SYS_SENDTO, parent, (long)request, 5, 0,
                      (long)&peer, sizeof(peer)) == 5, "sendto");
    char buffer[16] = {0};
    struct ok_sockaddr_in source = {0};
    unsigned int source_length = sizeof(source);
    check(await_receive((int)parent, buffer, sizeof(buffer), &source, &source_length) == 8 &&
          memcmp(buffer, "RESPONSE", 8) == 0, "parent-receive");
    check_source(&source, source_length);
    check(receive((int)parent, buffer, sizeof(buffer), 0, 0) == -OK_EAGAIN,
          "port-isolation");

    marker("OK_NATIVE_UDP parent=trunc-ready\n");
    source_length = sizeof(source);
    check(await_receive((int)parent, buffer, 3, &source, &source_length) == 3 &&
          memcmp(buffer, "ABC", 3) == 0, "truncated-receive");
    check(receive((int)parent, buffer, sizeof(buffer), 0, 0) == -OK_EAGAIN,
          "truncation-consumed");

    marker("OK_NATIVE_UDP parent=zero-ready\n");
    check(await_receive((int)parent, 0, 0, 0, 0) == 0, "zero-length-receive");
    check(receive((int)parent, buffer, sizeof(buffer), 0, 0) == -OK_EAGAIN,
          "zero-length-consumed");

    marker("OK_NATIVE_UDP parent=fault-ready\n");
    for (unsigned int attempt = 0; attempt < 5000; ++attempt)
    {
        long result = receive((int)parent, (void *)(unsigned long)~0UL, 1, 0, 0);
        if (result == -OK_EFAULT) break;
        check(result == -OK_EAGAIN, "fault-result");
        const struct timespec delay = {0, 1000000};
        check(nanosleep(&delay, 0) == 0, "fault-delay");
        check(attempt != 4999, "fault-timeout");
    }
    unsigned int invalid_length = sizeof(source);
    check(receive((int)parent, buffer, 1,
                  (struct ok_sockaddr_in *)(unsigned long)~0UL,
                  &invalid_length) == -OK_EFAULT, "source-copy-failure");
    invalid_length = 8;
    check(receive((int)parent, buffer, 1, &source, &invalid_length) == -OK_EINVAL,
          "short-source-capacity");
    check(receive((int)parent, buffer, 1, 0, 0) == 1 && buffer[0] == 'Q',
          "copy-failure-retained");

    long duplicate = ok_syscall1(OK_SYS_DUP, parent);
    check(duplicate >= 3 && close((int)parent) == 0, "dup-close");
    marker("OK_NATIVE_UDP parent=dup-ready\n");
    check(await_receive((int)duplicate, buffer, 1, 0, 0) == 1 && buffer[0] == 'D',
          "duplicate-reference");
    check(close((int)duplicate) == 0, "last-reference-close");
    long reused = ok_syscall3(OK_SYS_SOCKET, OK_AF_INET,
                              OK_SOCK_DGRAM | OK_SOCK_NONBLOCK, 0);
    check(reused >= 3 && ok_syscall3(OK_SYS_BIND, reused, (long)&parent_address,
                                     sizeof(parent_address)) == 0, "port-reuse");
    marker("OK_NATIVE_UDP parent=reuse-ready\n");
    check(await_receive((int)reused, buffer, 1, 0, 0) == 1 && buffer[0] == 'R',
          "reused-port-receive");
    check(close((int)reused) == 0, "reuse-close");
    int child_status = 0;
    check(waitpid((pid_t)child, &child_status, 0) == child &&
          WIFEXITED(child_status) && WEXITSTATUS(child_status) == 0, "child-exit");
    marker("OK_NATIVE_UDP scope=hardware acceptance=pass processes=2 ports=2\n");
    return 0;
}
