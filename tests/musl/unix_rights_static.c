#define _GNU_SOURCE 1
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <sched.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdlib.h>

#define REQUIRE(value, code) do { if (!(value)) _Exit(code); } while (0)
static ssize_t send_rights(int socket, const char *data, size_t size, const int *fds, size_t count)
{
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(8 * sizeof(int))]; } control = {0};
    struct iovec vector = {(void *)data, size};
    struct msghdr header = {0};
    header.msg_iov = &vector; header.msg_iovlen = 1;
    if (count)
    {
        header.msg_control = control.bytes; header.msg_controllen = CMSG_SPACE(count * sizeof(int));
        struct cmsghdr *cmsg = CMSG_FIRSTHDR(&header);
        cmsg->cmsg_len = CMSG_LEN(count * sizeof(int)); cmsg->cmsg_level = SOL_SOCKET; cmsg->cmsg_type = SCM_RIGHTS;
        memcpy(CMSG_DATA(cmsg), fds, count * sizeof(int));
    }
    return sendmsg(socket, &header, MSG_DONTWAIT | MSG_NOSIGNAL);
}
static ssize_t receive_rights(int socket, char *data, size_t size, int *fds, size_t capacity, int flags, int *result_flags)
{
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(8 * sizeof(int))]; } control = {0};
    struct iovec vector = {data, size}; struct msghdr header = {0};
    header.msg_iov = &vector; header.msg_iovlen = 1;
    header.msg_control = capacity ? control.bytes : 0;
    header.msg_controllen = capacity ? CMSG_LEN(capacity * sizeof(int)) : 0;
    const ssize_t result = recvmsg(socket, &header, flags | MSG_DONTWAIT);
    if (result >= 0)
    {
        *result_flags = header.msg_flags;
        struct cmsghdr *cmsg = CMSG_FIRSTHDR(&header);
        if (cmsg)
        {
            REQUIRE(cmsg->cmsg_level == SOL_SOCKET && cmsg->cmsg_type == SCM_RIGHTS, 101);
            const size_t count = (cmsg->cmsg_len - CMSG_LEN(0)) / sizeof(int);
            REQUIRE(count <= capacity, 102); memcpy(fds, CMSG_DATA(cmsg), count * sizeof(int));
            for (size_t at = count; at < capacity; ++at) fds[at] = -1;
        }
        else for (size_t at = 0; at < capacity; ++at) fds[at] = -1;
    }
    return result;
}
static ssize_t retry_receive(int socket, char *data, size_t size, int *fds, size_t capacity, int flags, int *result_flags)
{
    for (unsigned attempt = 0; attempt < 100000; ++attempt)
    {
        const ssize_t result = receive_rights(socket, data, size, fds, capacity, flags, result_flags);
        if (result >= 0 || (errno != EAGAIN && errno != EINTR)) return result;
        sched_yield();
    }
    return -1;
}
int main(void)
{
    int pair[2]; char buffer[32] = {0}; int flags = 0, received[2] = {-1, -1};
    REQUIRE(socketpair(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK, 0, pair) == 0, 110);
    const char *path = "/tmp/unix-rights-basic.txt";
    int fd = open(path, O_RDWR | O_CREAT | O_TRUNC, 0600); REQUIRE(fd >= 0, 111);
    REQUIRE(write(fd, "abcdefghij", 10) == 10 && lseek(fd, 0, SEEK_SET) == 0, 112);
    const int duplicate[2] = {fd, fd};
    REQUIRE(send_rights(pair[0], "file", 4, duplicate, 2) == 4 && close(fd) == 0, 113);
    pid_t child = fork(); REQUIRE(child >= 0, 114);
    if (!child)
    {
        REQUIRE(close(pair[0]) == 0, 115);
        REQUIRE(receive_rights(pair[1], buffer, sizeof buffer, received, 2, MSG_CMSG_CLOEXEC, &flags) == 4, 116);
        REQUIRE(received[0] >= 0 && received[1] >= 0 && received[0] != received[1], 117);
        REQUIRE((flags & MSG_CMSG_CLOEXEC) && (fcntl(received[0], F_GETFD) & FD_CLOEXEC), 118);
        REQUIRE(read(received[0], buffer, 3) == 3 && !memcmp(buffer, "abc", 3), 119);
        REQUIRE(read(received[1], buffer, 3) == 3 && !memcmp(buffer, "def", 3), 120);
        REQUIRE(close(received[0]) == 0 && send_rights(pair[1], "back", 4, &received[1], 1) == 4, 121);
        REQUIRE(close(received[1]) == 0 && close(pair[1]) == 0, 122); _Exit(0);
    }
    REQUIRE(close(pair[1]) == 0, 123);
    REQUIRE(retry_receive(pair[0], buffer, sizeof buffer, received, 1, 0, &flags) == 4 && !memcmp(buffer, "back", 4), 124);
    fd = received[0]; REQUIRE(fd >= 0 && !(fcntl(fd, F_GETFD) & FD_CLOEXEC), 125);
    REQUIRE(read(fd, buffer, 4) == 4 && !memcmp(buffer, "ghij", 4), 126);
    int status = 0; REQUIRE(waitpid(child, &status, 0) == child && WIFEXITED(status) && !WEXITSTATUS(status), 127);
    REQUIRE(close(pair[0]) == 0, 128);
    REQUIRE(write(fd, " saved", 6) == 6 && fsync(fd) == 0 && close(fd) == 0, 129);
    fd = open(path, O_RDONLY); REQUIRE(fd >= 0 && read(fd, buffer, sizeof buffer) == 16 && !memcmp(buffer, "abcdefghij saved", 16), 130);
    REQUIRE(socketpair(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK, 0, pair) == 0, 131);
    int twice[2] = {fd, fd}; REQUIRE(send_rights(pair[0], "peek", 4, twice, 2) == 4, 132);
    REQUIRE(receive_rights(pair[1], buffer, sizeof buffer, received, 1, MSG_PEEK | MSG_CMSG_CLOEXEC, &flags) == 4, 133);
    REQUIRE((flags & MSG_CTRUNC) && (flags & MSG_CMSG_CLOEXEC) && received[0] >= 0, 134);
    REQUIRE(close(received[0]) == 0, 135);
    REQUIRE(receive_rights(pair[1], buffer, sizeof buffer, received, 0, 0, &flags) == 4 && (flags & MSG_CTRUNC), 136);
    REQUIRE(send_rights(pair[0], "fault", 5, &fd, 1) == 5, 137);
    struct iovec vector = {buffer, sizeof buffer}; struct msghdr invalid = {0};
    invalid.msg_iov = &vector; invalid.msg_iovlen = 1; invalid.msg_control = (void *)(uintptr_t)1; invalid.msg_controllen = CMSG_SPACE(sizeof(int));
    errno = 0; REQUIRE(recvmsg(pair[1], &invalid, MSG_DONTWAIT) == -1 && errno == EFAULT, 138);
    REQUIRE(receive_rights(pair[1], buffer, sizeof buffer, received, 1, 0, &flags) == 5 && !memcmp(buffer, "fault", 5), 139);
    REQUIRE(received[0] >= 0 && close(received[0]) == 0, 140);
    REQUIRE(send_rights(pair[0], "drop", 4, &fd, 1) == 4 && read(pair[1], buffer, sizeof buffer) == 4, 141);
    errno = 0; REQUIRE(receive_rights(pair[1], buffer, sizeof buffer, received, 1, 0, &flags) == -1 && errno == EAGAIN, 142);
    REQUIRE(send_rights(pair[0], "", 0, &fd, 1) == 0 && write(pair[0], "plain", 5) == 5, 143);
    REQUIRE(receive_rights(pair[1], buffer, sizeof buffer, received, 1, 0, &flags) == 5 && received[0] == -1, 144);
    REQUIRE(close(pair[0]) == 0 && close(pair[1]) == 0 && close(fd) == 0 && unlink(path) == 0, 145);
    for (unsigned attempt = 0; attempt < 32; ++attempt)
    {
        REQUIRE(socketpair(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK, 0, pair) == 0, 146);
        REQUIRE(send_rights(pair[0], "cycle", 5, &pair[1], 1) == 5, 147);
        REQUIRE(close(pair[0]) == 0 && close(pair[1]) == 0, 148);
    }
    static const char record[] = "OK_STATIC_UNIX_RIGHTS transfer=pass shared_offset=pass file_reopen=pass cloexec=pass peek=pass ctrunc=pass fault=pass read_discard=pass cycles=pass\n";
    REQUIRE(write(1, record, sizeof record - 1) == sizeof record - 1, 149);
    return 0;
}
