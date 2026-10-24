#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <limits.h>
#include <netinet/in.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define LOCAL_ADDRESS UINT32_C(0xc0000202)
#define PEER_ADDRESS UINT32_C(0xc0000201)
_Static_assert(sizeof(socklen_t) == 4, "target socklen width");
_Static_assert(sizeof(sa_family_t) == 2, "target family width");
_Static_assert(sizeof(struct sockaddr_in) == 16, "target IPv4 name width");
struct guarded_name { uint64_t before; struct sockaddr_in value; uint64_t after; };
struct guarded_length { uint32_t before; socklen_t value; uint32_t after; };
_Static_assert(offsetof(struct guarded_name, after) == offsetof(struct guarded_name, value) + 16,
               "contiguous address suffix guard");
_Static_assert(offsetof(struct guarded_length, after) == offsetof(struct guarded_length, value) + 4,
               "contiguous length suffix guard");

static void marker(const char *text)
{
    size_t size = strlen(text);
    if (write(1, text, size) != (ssize_t)size) _Exit(2);
}
static void check(int condition, const char *reason)
{
    if (condition) return;
    marker("MUSL_UDP_CONNECTED stage=fail reason="); marker(reason); marker("\n"); _Exit(1);
}
static void decimal(uint32_t value)
{
    char text[11]; unsigned size = 0;
    do { text[size++] = (char)('0' + value % 10); value /= 10; } while (value);
    for (unsigned i = 0; i < size / 2; ++i) {
        char saved = text[i]; text[i] = text[size - i - 1]; text[size - i - 1] = saved;
    }
    check(write(1, text, size) == (ssize_t)size, "name-record-write");
}
static struct sockaddr_in endpoint(uint32_t address, unsigned port)
{
    struct sockaddr_in value = {0}; value.sin_family = AF_INET;
    value.sin_addr.s_addr = htonl(address); value.sin_port = htons((uint16_t)port);
    return value;
}
static int open_socket(void)
{
    int fd = socket(AF_INET, SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC, IPPROTO_UDP);
    check(fd >= 3, "socket"); return fd;
}
static int would_block(void) { return errno == EAGAIN || errno == EWOULDBLOCK; }
static void empty_queue(int fd)
{
    char byte; check(recv(fd, &byte, 1, MSG_DONTWAIT) == -1 && would_block(), "queue-not-empty");
}
static void receive_text(int fd, const char *expected, unsigned source_port, int copied_source)
{
    char bytes[40]; struct sockaddr_in source; socklen_t length;
    ssize_t count = -1;
    for (unsigned attempt = 0; attempt < 5000; ++attempt) {
        memset(bytes, 0, sizeof(bytes)); memset(&source, 0, sizeof(source)); length = sizeof(source);
        count = copied_source ? recvfrom(fd, bytes, sizeof(bytes), MSG_DONTWAIT,
                                        (struct sockaddr *)&source, &length)
                              : recv(fd, bytes, sizeof(bytes), MSG_DONTWAIT);
        if (count >= 0 || !would_block()) break;
        const struct timespec delay = {0, 1000000};
        check(nanosleep(&delay, 0) == 0, "receive-delay");
    }
    check(count == (ssize_t)strlen(expected) && memcmp(bytes, expected, strlen(expected)) == 0,
          "receive-text");
    if (copied_source)
        check(length == 16 && source.sin_family == AF_INET && ntohl(source.sin_addr.s_addr) == PEER_ADDRESS &&
              ntohs(source.sin_port) == source_port, "received-source");
}
static void send_text(int fd, const char *text, unsigned override_port)
{
    struct sockaddr_in peer = endpoint(PEER_ADDRESS, override_port);
    size_t size = strlen(text);
    ssize_t count = override_port ? sendto(fd, text, size, MSG_DONTWAIT,
                                          (struct sockaddr *)&peer, sizeof(peer))
                                  : send(fd, text, size, MSG_DONTWAIT);
    check(count == (ssize_t)size, "send-text");
}
static unsigned report_name(int fd, const char *phase, int remote, uint32_t address, unsigned port)
{
    struct guarded_name output; struct guarded_length length;
    memset(&output, 0xcc, sizeof(output)); memset(&length, 0xdd, sizeof(length)); length.value = 16;
    int status = remote ? getpeername(fd, (struct sockaddr *)&output.value, &length.value)
                        : getsockname(fd, (struct sockaddr *)&output.value, &length.value);
    check(status == 0 && length.value == 16 && output.before == UINT64_C(0xcccccccccccccccc) &&
          output.after == output.before && length.before == UINT32_C(0xdddddddd) && length.after == length.before,
          "query-guards-and-length");
    check(output.value.sin_family == AF_INET && ntohl(output.value.sin_addr.s_addr) == address &&
          (port == UINT_MAX ? ntohs(output.value.sin_port) != 0 : ntohs(output.value.sin_port) == port),
          "query-endpoint");
    for (size_t i = 0; i < sizeof(output.value.sin_zero); ++i)
        check(output.value.sin_zero[i] == 0, "query-zero-padding");
    marker("MUSL_UDP_CONNECTED stage=name phase="); marker(phase);
    marker(remote ? " kind=peer family=2 address=" : " kind=local family=2 address=");
    decimal(ntohl(output.value.sin_addr.s_addr)); marker(" port="); decimal(ntohs(output.value.sin_port));
    marker(" length=16\n"); return ntohs(output.value.sin_port);
}
static void refused_peer(int fd, int expected_error)
{
    struct guarded_name output, previous; struct guarded_length length, old_length;
    memset(&output, 0xcc, sizeof(output)); memset(&length, 0xdd, sizeof(length)); length.value = 16;
    previous = output; old_length = length;
    check(getpeername(fd, (struct sockaddr *)&output.value, &length.value) == -1 && errno == expected_error &&
          memcmp(&output, &previous, sizeof(output)) == 0 && memcmp(&length, &old_length, sizeof(length)) == 0,
          "refused-peer-unchanged");
    if (expected_error == ENOTCONN)
        check(getpeername(fd, 0, 0) == -1 && errno == ENOTCONN, "peer-error-before-output");
}
static void peer_capacity(int fd, unsigned port)
{
    struct sockaddr_in expected = endpoint(PEER_ADDRESS, port);
    const unsigned capacities[] = {0, 1, 2, 7, 15, 16, 17, INT_MAX};
    for (size_t i = 0; i < sizeof(capacities) / sizeof(capacities[0]); ++i) {
        struct guarded_name output; struct guarded_length length;
        memset(&output, 0xcc, sizeof(output)); memset(&length, 0xdd, sizeof(length)); length.value = capacities[i];
        check(getpeername(fd, (struct sockaddr *)&output.value, &length.value) == 0 && length.value == 16,
              "capacity-peer");
        size_t copied = capacities[i] < 16 ? capacities[i] : 16;
        check(memcmp(&output.value, &expected, copied) == 0, "capacity-prefix");
        const unsigned char *bytes = (const unsigned char *)&output.value;
        for (size_t offset = copied; offset < 16; ++offset) check(bytes[offset] == 0xcc, "capacity-tail");
        check(output.before == UINT64_C(0xcccccccccccccccc) && output.after == output.before &&
              length.before == UINT32_C(0xdddddddd) && length.after == length.before, "capacity-guards");
    }
    struct guarded_length length; memset(&length, 0xdd, sizeof(length)); length.value = 0;
    check(getpeername(fd, 0, &length.value) == 0 && length.value == 16 &&
          length.before == UINT32_C(0xdddddddd) && length.after == length.before, "null-zero-capacity");
}
static void associate(int fd, unsigned port)
{
    struct sockaddr_in peer = endpoint(PEER_ADDRESS, port);
    check(connect(fd, (struct sockaddr *)&peer, sizeof(peer)) == 0, "connect");
}
static void disconnect_peer(int fd)
{
    struct sockaddr value = {0}; value.sa_family = AF_UNSPEC;
    check(connect(fd, &value, sizeof(value.sa_family)) == 0, "disconnect-two-byte");
    refused_peer(fd, ENOTCONN);
}
static void bind_local(int fd, unsigned port)
{
    struct sockaddr_in local = endpoint(LOCAL_ADDRESS, port);
    check(bind(fd, (struct sockaddr *)&local, sizeof(local)) == 0, "bind-local");
}
static void missing_default(int fd)
{
    check(send(fd, "missing", 7, MSG_DONTWAIT) == -1 && errno == EDESTADDRREQ, "unconnected-default-send");
}
int main(void)
{
    marker("MUSL_UDP_CONNECTED stage=start\n");
    int fd = open_socket(); report_name(fd, "unbound", 0, INADDR_ANY, 0); refused_peer(fd, ENOTCONN);
    bind_local(fd, 54324); associate(fd, 12345); peer_capacity(fd, 12345);
    report_name(fd, "associated-local", 0, LOCAL_ADDRESS, 54324);
    report_name(fd, "associated-peer", 1, PEER_ADDRESS, 12345);
    empty_queue(fd); marker("MUSL_UDP_CONNECTED stage=associated-ready\n");
    receive_text(fd, "GO:S6:ASSOC", 12345, 1); send_text(fd, "MUSL:S6:ASSOC", 0);
    receive_text(fd, "ACK:S6:ASSOC", 12345, 1); empty_queue(fd);
    marker("MUSL_UDP_CONNECTED stage=associated-pass\n");

    int alias = dup(fd); check(alias >= 3 && alias != fd, "duplicate");
    check(close(fd) == 0, "close-original"); refused_peer(fd, EBADF);
    report_name(alias, "duplicate-local", 0, LOCAL_ADDRESS, 54324);
    report_name(alias, "duplicate-peer", 1, PEER_ADDRESS, 12345);
    marker("MUSL_UDP_CONNECTED stage=duplicate-ready\n"); send_text(alias, "MUSL:S6:DUP", 0);
    receive_text(alias, "ACK:S6:DUP", 12345, 0); empty_queue(alias);
    check(close(alias) == 0, "close-alias"); refused_peer(alias, EBADF);
    fd = open_socket(); bind_local(fd, 54324); check(close(fd) == 0, "last-close-rebind");
    marker("MUSL_UDP_CONNECTED stage=duplicate-pass\n");

    fd = open_socket(); bind_local(fd, 54325); associate(fd, 0); refused_peer(fd, ENOTCONN);
    report_name(fd, "zero-before", 0, LOCAL_ADDRESS, 54325);
    struct sockaddr_in supplied_zero = endpoint(PEER_ADDRESS, 0);
    check(sendto(fd, "forbidden-zero", 14, MSG_DONTWAIT, (struct sockaddr *)&supplied_zero,
                 sizeof(supplied_zero)) == -1 && errno == EINVAL, "supplied-zero-port-refusal");
    report_name(fd, "zero-after-refusal", 0, LOCAL_ADDRESS, 54325); refused_peer(fd, ENOTCONN);
    marker("MUSL_UDP_CONNECTED stage=zero-ready\n"); send_text(fd, "MUSL:S6:ZERO", 0);
    receive_text(fd, "ACK:S6:ZERO0", 0, 1); receive_text(fd, "ACK:S6:ZEROOTHER", 12346, 1); empty_queue(fd);
    refused_peer(fd, ENOTCONN); marker("MUSL_UDP_CONNECTED stage=zero-pass\n");

    disconnect_peer(fd); report_name(fd, "disconnected-fixed", 0, LOCAL_ADDRESS, 54325); missing_default(fd);
    marker("MUSL_UDP_CONNECTED stage=disconnect-ready\n"); send_text(fd, "MUSL:S6:DISC", 12345);
    receive_text(fd, "ACK:S6:DISC", 12346, 1); empty_queue(fd); check(close(fd) == 0, "disconnect-close");
    marker("MUSL_UDP_CONNECTED stage=disconnect-pass\n");

    fd = open_socket(); bind_local(fd, 0);
    unsigned port = report_name(fd, "retained-before", 0, LOCAL_ADDRESS, UINT_MAX);
    associate(fd, 12345); report_name(fd, "retained-connected", 0, LOCAL_ADDRESS, port);
    report_name(fd, "retained-peer", 1, PEER_ADDRESS, 12345); disconnect_peer(fd);
    report_name(fd, "retained-disconnected", 0, LOCAL_ADDRESS, 0); missing_default(fd);
    port = report_name(fd, "retained-autobind", 0, LOCAL_ADDRESS, UINT_MAX);
    marker("MUSL_UDP_CONNECTED stage=retained-ready\n"); send_text(fd, "MUSL:S6:RETAIN", 12345);
    report_name(fd, "retained-after-send", 0, LOCAL_ADDRESS, port);
    receive_text(fd, "ACK:S6:RETAIN", 12345, 1); empty_queue(fd);
    marker("MUSL_UDP_CONNECTED stage=retained-pass\n");
    associate(fd, 12346); report_name(fd, "reconnected-local", 0, LOCAL_ADDRESS, port);
    report_name(fd, "reconnected-peer", 1, PEER_ADDRESS, 12346);
    marker("MUSL_UDP_CONNECTED stage=reconnect-ready\n"); send_text(fd, "MUSL:S6:RECONNECT", 0);
    receive_text(fd, "ACK:S6:RECONNECT", 12346, 1); empty_queue(fd); check(close(fd) == 0, "reconnect-close");
    marker("MUSL_UDP_CONNECTED stage=reconnect-pass\n"); marker("MUSL_UDP_CONNECTED stage=pass\n"); return 0;
}
