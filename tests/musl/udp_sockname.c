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

#ifndef MUSL_UDP_LOCAL_IPV4
#define MUSL_UDP_LOCAL_IPV4 0xc0000202UL
#endif
#ifndef MUSL_UDP_PEER_IPV4
#define MUSL_UDP_PEER_IPV4 0xc0000201UL
#endif
_Static_assert(sizeof(socklen_t) == 4, "target socklen width");
_Static_assert(sizeof(struct sockaddr_in) == 16, "target IPv4 name width");

static struct sockaddr_in peer;
struct guarded_name { uint64_t before; struct sockaddr_in value; uint64_t after; };
struct guarded_length { uint32_t before; socklen_t value; uint32_t after; };
_Static_assert(offsetof(struct guarded_name, after) == offsetof(struct guarded_name, value) + 16,
               "contiguous address suffix guard");
_Static_assert(offsetof(struct guarded_length, after) == offsetof(struct guarded_length, value) + 4,
               "contiguous length suffix guard");

static void marker(const char *text)
{
    size_t length = strlen(text);
    if (write(1, text, length) != (ssize_t)length) _Exit(2);
}
static void check(int condition, const char *reason)
{
    if (condition) return;
    marker("MUSL_UDP_NAME stage=fail reason="); marker(reason); marker("\n"); _Exit(1);
}
static void decimal(uint32_t value)
{
    char text[11]; unsigned size = 0;
    do { text[size++] = (char)('0' + value % 10); value /= 10; } while (value);
    for (unsigned index = 0; index < size / 2; ++index) {
        char swap = text[index]; text[index] = text[size - 1 - index]; text[size - 1 - index] = swap;
    }
    check(write(1, text, size) == (ssize_t)size, "name-record-write");
}
static int would_block(void) { return errno == EAGAIN || errno == EWOULDBLOCK; }
static int open_socket(void)
{
    int fd = socket(AF_INET, SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC, IPPROTO_UDP);
    check(fd >= 3, "socket"); return fd;
}
static void empty_queue(int fd)
{
    char byte;
    check(recvfrom(fd, &byte, 1, MSG_DONTWAIT, 0, 0) == -1 && would_block(), "queue-not-empty");
}
static void receive_text(int fd, const char *expected)
{
    char buffer[32]; struct sockaddr_in source; socklen_t length;
    ssize_t count = -1;
    for (unsigned attempt = 0; attempt < 5000; ++attempt) {
        memset(buffer, 0, sizeof(buffer)); memset(&source, 0, sizeof(source)); length = sizeof(source);
        count = recvfrom(fd, buffer, sizeof(buffer), MSG_DONTWAIT, (struct sockaddr *)&source, &length);
        if (count >= 0 || !would_block()) break;
        const struct timespec delay = {0, 1000000};
        check(nanosleep(&delay, 0) == 0, "receive-delay");
    }
    check(count == (ssize_t)strlen(expected) && memcmp(buffer, expected, strlen(expected)) == 0,
          "receive-text");
    check(length == sizeof(source) && source.sin_family == AF_INET && source.sin_port == peer.sin_port &&
          source.sin_addr.s_addr == peer.sin_addr.s_addr, "source-address");
}
static void send_text(int fd, const char *text)
{
    size_t size = strlen(text);
    check(sendto(fd, text, size, MSG_DONTWAIT, (struct sockaddr *)&peer, sizeof(peer)) == (ssize_t)size,
          "send-text");
}
static struct sockaddr_in query_name(int fd, uint32_t address, unsigned port)
{
    struct guarded_name output; struct guarded_length length;
    memset(&output, 0xcc, sizeof(output)); memset(&length, 0xdd, sizeof(length));
    length.value = sizeof(output.value);
    check(getsockname(fd, (struct sockaddr *)&output.value, &length.value) == 0, "query-name");
    check(output.before == UINT64_C(0xcccccccccccccccc) && output.after == output.before &&
          length.before == UINT32_C(0xdddddddd) && length.after == length.before && length.value == 16,
          "query-guards-and-length");
    check(output.value.sin_family == AF_INET && ntohl(output.value.sin_addr.s_addr) == address &&
          (port == UINT_MAX ? ntohs(output.value.sin_port) != 0 : ntohs(output.value.sin_port) == port),
          "query-endpoint");
    for (size_t index = 0; index < sizeof(output.value.sin_zero); ++index)
        check(output.value.sin_zero[index] == 0, "query-zero-padding");
    return output.value;
}
static unsigned report_name(int fd, const char *phase, uint32_t address, unsigned port)
{
    struct sockaddr_in name = query_name(fd, address, port);
    marker("MUSL_UDP_NAME stage=name phase="); marker(phase);
    marker(" family=2 address="); decimal(ntohl(name.sin_addr.s_addr));
    marker(" port="); decimal(ntohs(name.sin_port)); marker(" length=16\n");
    return ntohs(name.sin_port);
}
static void capacity_checks(int fd)
{
    struct sockaddr_in expected = {0}; expected.sin_family = AF_INET;
    expected.sin_port = htons(54322); expected.sin_addr.s_addr = htonl(MUSL_UDP_LOCAL_IPV4);
    const unsigned capacities[] = {0, 1, 2, 3, 7, 15, 16, 17, INT_MAX};
    for (size_t index = 0; index < sizeof(capacities) / sizeof(capacities[0]); ++index) {
        struct guarded_name output; struct guarded_length length;
        memset(&output, 0xcc, sizeof(output)); memset(&length, 0xdd, sizeof(length));
        length.value = capacities[index];
        check(getsockname(fd, (struct sockaddr *)&output.value, &length.value) == 0, "capacity-query");
        size_t copied = capacities[index] < 16 ? capacities[index] : 16;
        check(memcmp(&output.value, &expected, copied) == 0, "capacity-prefix");
        const unsigned char *bytes = (const unsigned char *)&output.value;
        for (size_t offset = copied; offset < 16; ++offset) check(bytes[offset] == 0xcc, "capacity-tail");
        check(output.before == UINT64_C(0xcccccccccccccccc) && output.after == output.before &&
              length.before == UINT32_C(0xdddddddd) && length.after == length.before && length.value == 16,
              "capacity-guards-and-length");
    }
    struct guarded_length length; memset(&length, 0xdd, sizeof(length)); length.value = 0;
    check(getsockname(fd, 0, &length.value) == 0 && length.value == 16 &&
          length.before == UINT32_C(0xdddddddd) && length.after == length.before, "null-zero-capacity");
}
static void closed_name(int fd)
{
    struct guarded_name output, original; struct guarded_length length, old_length;
    memset(&output, 0xcc, sizeof(output)); memset(&length, 0xdd, sizeof(length)); length.value = 16;
    original = output; old_length = length;
    check(getsockname(fd, (struct sockaddr *)&output.value, &length.value) == -1 && errno == EBADF &&
          memcmp(&output, &original, sizeof(output)) == 0 && memcmp(&length, &old_length, sizeof(length)) == 0,
          "closed-descriptor-query");
}
int main(void)
{
    peer.sin_family = AF_INET; peer.sin_port = htons(12345); peer.sin_addr.s_addr = htonl(MUSL_UDP_PEER_IPV4);
    struct sockaddr_in local = {0}; local.sin_family = AF_INET;
    local.sin_port = htons(54322); local.sin_addr.s_addr = htonl(MUSL_UDP_LOCAL_IPV4);
    marker("MUSL_UDP_NAME stage=start\n");
    int fd = open_socket();
    marker("MUSL_UDP_NAME stage=unbound-ready\n"); report_name(fd, "unbound", INADDR_ANY, 0);
    marker("MUSL_UDP_NAME stage=unbound-pass\n");
    check(bind(fd, (struct sockaddr *)&local, sizeof(local)) == 0, "fixed-bind");
    empty_queue(fd); marker("MUSL_UDP_NAME stage=fixed-ready port=54322\n");
    report_name(fd, "fixed", MUSL_UDP_LOCAL_IPV4, 54322);
    receive_text(fd, "GO:NAME:FIXED"); send_text(fd, "MUSL:NAME:FIXED"); receive_text(fd, "ACK:NAME:FIXED");
    empty_queue(fd); marker("MUSL_UDP_NAME stage=fixed-pass\n");
    marker("MUSL_UDP_NAME stage=capacity-ready\n"); capacity_checks(fd); marker("MUSL_UDP_NAME stage=capacity-pass\n");
    marker("MUSL_UDP_NAME stage=duplicate-ready port=54322\n");
    int alias = dup(fd); check(alias >= 3 && alias != fd, "duplicate");
    check(close(fd) == 0, "close-original"); closed_name(fd);
    report_name(alias, "duplicate", MUSL_UDP_LOCAL_IPV4, 54322);
    send_text(alias, "MUSL:NAME:DUP"); receive_text(alias, "ACK:NAME:DUP"); empty_queue(alias);
    check(close(alias) == 0, "close-alias"); closed_name(alias); closed_name(fd);
    fd = open_socket(); check(bind(fd, (struct sockaddr *)&local, sizeof(local)) == 0, "last-close-rebind");
    query_name(fd, MUSL_UDP_LOCAL_IPV4, 54322); check(close(fd) == 0, "replacement-close");
    marker("MUSL_UDP_NAME stage=duplicate-pass\n");
    fd = open_socket(); local.sin_port = 0; local.sin_addr.s_addr = htonl(INADDR_ANY);
    check(bind(fd, (struct sockaddr *)&local, sizeof(local)) == 0, "bind-zero");
    marker("MUSL_UDP_NAME stage=bind-zero-ready\n");
    unsigned port = report_name(fd, "bind-zero-before", INADDR_ANY, UINT_MAX);
    send_text(fd, "MUSL:NAME:BIND0:1"); report_name(fd, "bind-zero-after-first", INADDR_ANY, port);
    receive_text(fd, "ACK:NAME:BIND0:1");
    send_text(fd, "MUSL:NAME:BIND0:2"); report_name(fd, "bind-zero-after-second", INADDR_ANY, port);
    receive_text(fd, "ACK:NAME:BIND0:2"); empty_queue(fd); check(close(fd) == 0, "bind-zero-close");
    marker("MUSL_UDP_NAME stage=bind-zero-pass\n");
    fd = open_socket(); marker("MUSL_UDP_NAME stage=implicit-ready\n");
    report_name(fd, "implicit-before", INADDR_ANY, 0);
    send_text(fd, "MUSL:NAME:AUTO:1"); port = report_name(fd, "implicit-after-first", INADDR_ANY, UINT_MAX);
    receive_text(fd, "ACK:NAME:AUTO:1");
    send_text(fd, "MUSL:NAME:AUTO:2"); report_name(fd, "implicit-after-second", INADDR_ANY, port);
    receive_text(fd, "ACK:NAME:AUTO:2"); empty_queue(fd); check(close(fd) == 0, "implicit-close");
    marker("MUSL_UDP_NAME stage=implicit-pass\n"); marker("MUSL_UDP_NAME stage=pass\n"); return 0;
}
