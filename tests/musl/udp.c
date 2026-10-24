#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

/* Host reference builds override only these two public IPv4 constants. */
#ifndef MUSL_UDP_LOCAL_IPV4
#define MUSL_UDP_LOCAL_IPV4 0xc0000202UL
#endif
#ifndef MUSL_UDP_PEER_IPV4
#define MUSL_UDP_PEER_IPV4 0xc0000201UL
#endif

static struct sockaddr_in peer;

static void marker(const char *text)
{
    size_t length = strlen(text);
    if (write(1, text, length) != (ssize_t)length) _Exit(2);
}

static void check(int condition, const char *reason)
{
    if (condition) return;
    marker("MUSL_UDP stage=fail reason=");
    marker(reason);
    marker("\n");
    _Exit(1);
}

static int would_block(void)
{
    return errno == EAGAIN || errno == EWOULDBLOCK;
}

static ssize_t await_receive(int fd, void *buffer, size_t size, int flags,
                             struct sockaddr *source, socklen_t *source_length)
{
    for (unsigned attempt = 0; attempt < 5000; ++attempt) {
        if (source_length) *source_length = sizeof(struct sockaddr_in);
        ssize_t result = recvfrom(fd, buffer, size, flags | MSG_DONTWAIT,
                                  source, source_length);
        if (result >= 0 || !would_block()) return result;
        const struct timespec delay = {0, 1000000};
        check(nanosleep(&delay, 0) == 0, "receive-delay");
    }
    check(0, "receive-timeout");
    return -1;
}

static void check_source(const struct sockaddr_in *source, socklen_t length)
{
    check(length == sizeof(*source) && source->sin_family == AF_INET &&
          source->sin_port == peer.sin_port &&
          source->sin_addr.s_addr == peer.sin_addr.s_addr, "source-address");
}

static void empty_queue(int fd)
{
    char byte;
    check(recvfrom(fd, &byte, sizeof(byte), MSG_DONTWAIT, 0, 0) == -1 &&
          would_block(), "queue-not-empty");
}

static void receive_text(int fd, const char *expected)
{
    char buffer[32] = {0};
    struct sockaddr_in source = {0};
    socklen_t length = sizeof(source);
    size_t size = strlen(expected);
    check(await_receive(fd, buffer, sizeof(buffer), 0,
                        (struct sockaddr *)&source, &length) == (ssize_t)size &&
          memcmp(buffer, expected, size) == 0, "receive-text");
    check_source(&source, length);
}

static void send_text(int fd, const char *text)
{
    size_t size = strlen(text);
    check(sendto(fd, text, size, MSG_DONTWAIT, (struct sockaddr *)&peer,
                 sizeof(peer)) == (ssize_t)size, "send-text");
}

static int open_socket(void)
{
    int fd = socket(AF_INET, SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC, IPPROTO_UDP);
    check(fd >= 3, "socket");
    return fd;
}

int main(void)
{
    peer.sin_family = AF_INET;
    peer.sin_port = htons(12345);
    peer.sin_addr.s_addr = htonl(MUSL_UDP_PEER_IPV4);
    struct sockaddr_in local = {0};
    local.sin_family = AF_INET;
    local.sin_port = htons(54322);
    local.sin_addr.s_addr = htonl(MUSL_UDP_LOCAL_IPV4);
    marker("MUSL_UDP stage=start\n");
    int fd = open_socket();
    check(bind(fd, (struct sockaddr *)&local, sizeof(local)) == 0, "explicit-bind");
    empty_queue(fd);
    marker("MUSL_UDP stage=basic-ready port=54322\n");
    receive_text(fd, "GO:BASIC");
    send_text(fd, "MUSL:BASIC");
    receive_text(fd, "ACK:BASIC");
    empty_queue(fd);
    marker("MUSL_UDP stage=basic-pass\n");

    char buffer[16] = {0};
    struct sockaddr_in source = {0};
    socklen_t length = sizeof(source);
    marker("MUSL_UDP stage=peek-ready\n");
    check(await_receive(fd, buffer, 3, MSG_PEEK, (struct sockaddr *)&source,
                        &length) == 3 && memcmp(buffer, "PEE", 3) == 0, "peek-prefix");
    check_source(&source, length);
    length = sizeof(source);
    check(recvfrom(fd, buffer, 3, MSG_DONTWAIT | MSG_PEEK | MSG_TRUNC,
                   (struct sockaddr *)&source, &length) == 9 &&
          memcmp(buffer, "PEE", 3) == 0, "peek-trunc");
    check_source(&source, length);
    length = sizeof(source);
    check(recvfrom(fd, buffer, 3, MSG_DONTWAIT | MSG_TRUNC,
                   (struct sockaddr *)&source, &length) == 9 &&
          memcmp(buffer, "PEE", 3) == 0, "trunc-consume");
    check_source(&source, length);
    empty_queue(fd);
    marker("MUSL_UDP stage=peek-pass\n");

    marker("MUSL_UDP stage=short-ready\n");
    check(await_receive(fd, buffer, 3, 0, (struct sockaddr *)&source, &length) == 3 &&
          memcmp(buffer, "SHO", 3) == 0, "ordinary-truncation");
    check_source(&source, length);
    empty_queue(fd);
    marker("MUSL_UDP stage=short-pass\n");

    marker("MUSL_UDP stage=zero-ready\n");
    check(await_receive(fd, 0, 0, 0, (struct sockaddr *)&source, &length) == 0,
          "empty-datagram-receive");
    check_source(&source, length);
    empty_queue(fd);
    check(sendto(fd, 0, 0, MSG_DONTWAIT, (struct sockaddr *)&peer,
                 sizeof(peer)) == 0, "empty-datagram-send");
    marker("MUSL_UDP stage=zero-pass\n");

    /* Source output faults happen after selection; payload-range faults do not. */
    marker("MUSL_UDP stage=fault-ready\n");
    buffer[0] = 0;
    check(await_receive(fd, buffer, 1, 0, (struct sockaddr *)(uintptr_t)1,
                        &length) == -1 && errno == EFAULT && buffer[0] == 'F',
          "source-fault-consumed");
    empty_queue(fd);
    marker("MUSL_UDP stage=fault-pass\n");

    marker("MUSL_UDP stage=peekfault-ready\n");
    buffer[0] = 0;
    check(await_receive(fd, buffer, 1, MSG_PEEK, (struct sockaddr *)(uintptr_t)1,
                        &length) == -1 && errno == EFAULT && buffer[0] == 'P',
          "peek-source-fault");
    length = sizeof(source);
    check(recvfrom(fd, buffer, 1, MSG_DONTWAIT, (struct sockaddr *)&source,
                   &length) == 1 && buffer[0] == 'P', "peek-fault-retained");
    check_source(&source, length);
    empty_queue(fd);
    check(close(fd) == 0, "explicit-close");
    marker("MUSL_UDP stage=peekfault-pass\n");

    /* Execution of this phase requires the admitted bind-zero successor. */
    fd = open_socket();
    local.sin_port = 0;
    local.sin_addr.s_addr = htonl(INADDR_ANY);
    check(bind(fd, (struct sockaddr *)&local, sizeof(local)) == 0, "bind-zero");
    marker("MUSL_UDP stage=bind-zero-ready\n");
    send_text(fd, "MUSL:BIND0:1");
    receive_text(fd, "ACK:BIND0:1");
    send_text(fd, "MUSL:BIND0:2");
    receive_text(fd, "ACK:BIND0:2");
    empty_queue(fd);
    check(close(fd) == 0, "bind-zero-close");
    marker("MUSL_UDP stage=bind-zero-pass\n");

    fd = open_socket();
    marker("MUSL_UDP stage=implicit-ready\n");
    send_text(fd, "MUSL:AUTO:1");
    receive_text(fd, "ACK:AUTO:1");
    send_text(fd, "MUSL:AUTO:2");
    receive_text(fd, "ACK:AUTO:2");
    empty_queue(fd);
    check(close(fd) == 0, "implicit-close");
    marker("MUSL_UDP stage=implicit-pass\n");
    marker("MUSL_UDP stage=pass\n");
    return 0;
}
