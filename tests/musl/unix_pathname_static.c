#define _GNU_SOURCE 1
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <unistd.h>

#define REQUIRE(value, code) do { if (!(value)) return code; } while (0)
static const char socket_path[] = "/run/user/1000/musl.sock";
static const char data_path[] = "/run/user/1000/musl-data";
static struct sockaddr_un address(void)
{
    struct sockaddr_un value = {0}; value.sun_family = AF_UNIX;
    memcpy(value.sun_path, socket_path, sizeof socket_path); return value;
}
static int client(int synchronization)
{
    const int stream = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    REQUIRE(stream >= 0, 181); struct sockaddr_un name = address();
    int connected = -1;
    for (unsigned attempt = 0; attempt < 100000; ++attempt)
    {
        connected = connect(stream, (struct sockaddr *)&name, 2 + sizeof socket_path);
        if (!connected) break;
        REQUIRE(errno == ENOENT || errno == ECONNREFUSED || errno == EAGAIN, 182); sched_yield();
    }
    REQUIRE(!connected, 183); struct ucred peer = {0}; socklen_t length = sizeof peer;
    REQUIRE(!getsockopt(stream, SOL_SOCKET, SO_PEERCRED, &peer, &length) && length == sizeof peer &&
            peer.pid == getppid() && peer.uid == geteuid() && peer.gid == getegid(), 184);
    int file = open(data_path, O_RDWR | O_CREAT | O_TRUNC, 0600);
    REQUIRE(file >= 0 && write(file, "abcdef", 6) == 6 && lseek(file, 0, SEEK_SET) == 0, 185);
    const int rights[2] = {file, file};
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(sizeof rights)]; } control = {0};
    struct iovec vector = {(void *)"fd", 2}; struct msghdr message = {0};
    message.msg_iov = &vector; message.msg_iovlen = 1;
    message.msg_control = control.bytes; message.msg_controllen = sizeof control.bytes;
    struct cmsghdr *header = CMSG_FIRSTHDR(&message);
    header->cmsg_len = CMSG_LEN(sizeof rights); header->cmsg_level = SOL_SOCKET; header->cmsg_type = SCM_RIGHTS;
    memcpy(CMSG_DATA(header), rights, sizeof rights);
    REQUIRE(sendmsg(stream, &message, MSG_DONTWAIT | MSG_NOSIGNAL) == 2 && !close(file), 186);
    REQUIRE(write(synchronization, "x", 1) == 1 && !close(synchronization) && !close(stream), 187); return 0;
}
int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "client")) return client(atoi(argv[2]));
    int synchronization[2]; REQUIRE(!pipe(synchronization), 188);
    const pid_t child = fork(); REQUIRE(child >= 0, 189);
    if (!child)
    {
        close(synchronization[0]); char descriptor[16]; unsigned value = (unsigned)synchronization[1], at = 0;
        do { descriptor[at++] = (char)('0' + value % 10); value /= 10; } while (value);
        for (unsigned i = 0; i < at / 2; ++i) { char swap = descriptor[i]; descriptor[i] = descriptor[at - i - 1]; descriptor[at - i - 1] = swap; }
        descriptor[at] = 0;
        char *arguments[] = {"unix-pathname-static", "client", descriptor, 0}; char *environment[] = {"PATH=/bin", 0};
        execve("/bin/unix-pathname-static", arguments, environment); _Exit(190);
    }
    REQUIRE(!close(synchronization[1]), 191);
    // Parent and exec'd child each create their own socket after fork.
    const int listener = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    REQUIRE(listener >= 0, 192); struct sockaddr_un name = address();
    REQUIRE(!bind(listener, (struct sockaddr *)&name, 2 + sizeof socket_path) && !listen(listener, 2), 193);
    char signal = 0; REQUIRE(read(synchronization[0], &signal, 1) == 1 && signal == 'x' && !close(synchronization[0]), 194);
    const int accepted = accept4(listener, 0, 0, SOCK_NONBLOCK | SOCK_CLOEXEC);
    REQUIRE(accepted >= 0, 195);
    const int accepted_flags = fcntl(accepted, F_GETFD);
    REQUIRE(accepted_flags >= 0 && (accepted_flags & FD_CLOEXEC), 195);
    struct ucred peer = {0}; socklen_t length = sizeof peer;
    REQUIRE(!getsockopt(accepted, SOL_SOCKET, SO_PEERCRED, &peer, &length) && length == sizeof peer && peer.pid == child &&
            peer.uid == geteuid() && peer.gid == getegid(), 196);
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(2 * sizeof(int))]; } control = {0};
    char payload[8] = {0}; struct iovec vector = {payload, sizeof payload}; struct msghdr message = {0};
    message.msg_iov = &vector; message.msg_iovlen = 1;
    message.msg_control = control.bytes; message.msg_controllen = sizeof control.bytes;
    REQUIRE(recvmsg(accepted, &message, MSG_DONTWAIT | MSG_CMSG_CLOEXEC) == 2 && !memcmp(payload, "fd", 2), 197);
    struct cmsghdr *header = CMSG_FIRSTHDR(&message);
    REQUIRE(header && header->cmsg_level == SOL_SOCKET && header->cmsg_type == SCM_RIGHTS && header->cmsg_len == CMSG_LEN(2 * sizeof(int)), 198);
    int rights[2]; memcpy(rights, CMSG_DATA(header), sizeof rights);
    REQUIRE(rights[0] >= 0 && rights[1] >= 0 && rights[0] != rights[1], 199);
    const int first_flags = fcntl(rights[0], F_GETFD), second_flags = fcntl(rights[1], F_GETFD);
    REQUIRE(first_flags >= 0 && second_flags >= 0 && (first_flags & FD_CLOEXEC) && (second_flags & FD_CLOEXEC), 199);
    REQUIRE(read(rights[0], payload, 3) == 3 && !memcmp(payload, "abc", 3) &&
            read(rights[1], payload, 3) == 3 && !memcmp(payload, "def", 3), 200);
    REQUIRE(!close(rights[0]) && !close(rights[1]) && !close(accepted) && !close(listener), 201);
    int status = 0; REQUIRE(waitpid(child, &status, 0) == child && WIFEXITED(status) && !WEXITSTATUS(status), 202);
    REQUIRE(!unlink(socket_path) && !unlink(data_path), 203);
    const char record[] = "OK_MUSL_UNIX_PATHNAME processes=distinct exec=client credentials=kernel rights=preaccept shared_offset=pass cloexec=pass\n";
    REQUIRE(write(1, record, sizeof record - 1) == sizeof record - 1, 204); return 0;
}
