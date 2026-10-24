#include <errno.h>
#include <fcntl.h>
#include <ok/socket.h>
#include <ok/syscall.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#define REQUIRE(value, code) do { if (!(value)) return code; } while (0)
static const char socket_path[] = "/run/user/1000/native.sock";
static const char data_path[] = "/run/user/1000/native-data";
static struct ok_sockaddr_un address(void)
{
    struct ok_sockaddr_un value = {0}; value.family = OK_AF_UNIX;
    memcpy(value.path, socket_path, sizeof socket_path); return value;
}
static int client(int synchronization)
{
    const int stream = ok_socket(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC, 0);
    REQUIRE(stream >= 0, 181);
    struct ok_sockaddr_un name = address();
    int connected = -1;
    for (unsigned attempt = 0; attempt < 100000; ++attempt)
    {
        connected = ok_connect(stream, &name, (ok_socklen_t)(2 + sizeof socket_path));
        if (!connected) break;
        REQUIRE(errno == ENOENT || errno == ECONNREFUSED || errno == EAGAIN, 182);
        (void)ok_syscall0(OK_SYS_SCHED_YIELD);
    }
    REQUIRE(!connected, 183);
    struct ok_ucred peer = {0}; ok_socklen_t length = sizeof peer;
    REQUIRE(!ok_getsockopt(stream, OK_SOL_SOCKET, OK_SO_PEERCRED, &peer, &length) &&
            length == sizeof peer && peer.pid == getppid() && peer.uid == geteuid() && peer.gid == getegid(), 184);
    int file = open(data_path, O_RDWR | O_CREAT | O_TRUNC, 0600);
    REQUIRE(file >= 0 && write(file, "abcdef", 6) == 6 && lseek(file, 0, SEEK_SET) == 0, 185);
    const int rights[2] = {file, file};
    union { struct ok_cmsghdr align; unsigned char bytes[OK_CMSG_SPACE(sizeof rights)]; } control = {0};
    struct ok_cmsghdr *header = (struct ok_cmsghdr *)control.bytes;
    header->length = OK_CMSG_LEN(sizeof rights); header->level = OK_SOL_SOCKET; header->type = OK_SCM_RIGHTS;
    memcpy(control.bytes + sizeof *header, rights, sizeof rights);
    struct ok_iovec vector = {(uintptr_t)"fd", 2}; struct ok_msghdr message = {0};
    message.vectors = (uintptr_t)&vector; message.vector_count = 1;
    message.control = (uintptr_t)control.bytes; message.control_length = sizeof control.bytes;
    REQUIRE(ok_sendmsg(stream, &message, OK_MSG_DONTWAIT) == 2 && !close(file), 186);
    REQUIRE(write(synchronization, "x", 1) == 1 && !close(synchronization) && !close(stream), 187);
    return 0;
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
        char *arguments[] = {"unix-pathname-runner", "client", descriptor, 0}; char *environment[] = {"PATH=/bin", 0};
        execve("/bin/unix-pathname-runner", arguments, environment); _Exit(190);
    }
    REQUIRE(!close(synchronization[1]), 191);
    // Both processes create sockets after fork; the client also executes a new
    // image before socket creation. No stream endpoint crosses fork or exec.
    const int listener = ok_socket(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC, 0);
    REQUIRE(listener >= 0, 192); struct ok_sockaddr_un name = address();
    REQUIRE(!ok_bind(listener, &name, (ok_socklen_t)(2 + sizeof socket_path)) && !ok_listen(listener, 2), 193);
    char signal = 0; REQUIRE(read(synchronization[0], &signal, 1) == 1 && signal == 'x' && !close(synchronization[0]), 194);
    const int accepted = ok_accept4(listener, 0, 0, OK_SOCK_NONBLOCK | OK_SOCK_CLOEXEC);
    REQUIRE(accepted >= 0, 195);
    const int accepted_flags = fcntl(accepted, F_GETFD);
    REQUIRE(accepted_flags >= 0 && (accepted_flags & FD_CLOEXEC), 195);
    struct ok_ucred peer = {0}; ok_socklen_t length = sizeof peer;
    REQUIRE(!ok_getsockopt(accepted, OK_SOL_SOCKET, OK_SO_PEERCRED, &peer, &length) &&
            length == sizeof peer && peer.pid == child && peer.uid == geteuid() && peer.gid == getegid(), 196);
    union { struct ok_cmsghdr align; unsigned char bytes[OK_CMSG_SPACE(2 * sizeof(int))]; } control = {0};
    char payload[8] = {0}; struct ok_iovec vector = {(uintptr_t)payload, sizeof payload}; struct ok_msghdr message = {0};
    message.vectors = (uintptr_t)&vector; message.vector_count = 1;
    message.control = (uintptr_t)control.bytes; message.control_length = sizeof control.bytes;
    REQUIRE(ok_recvmsg(accepted, &message, OK_MSG_DONTWAIT | OK_MSG_CMSG_CLOEXEC) == 2 && !memcmp(payload, "fd", 2), 197);
    const struct ok_cmsghdr *header = (const struct ok_cmsghdr *)control.bytes;
    REQUIRE(message.control_length >= OK_CMSG_LEN(2 * sizeof(int)) &&
            header->level == OK_SOL_SOCKET && header->type == OK_SCM_RIGHTS &&
            header->length == OK_CMSG_LEN(2 * sizeof(int)), 198);
    int rights[2]; memcpy(rights, control.bytes + sizeof *header, sizeof rights);
    REQUIRE(rights[0] >= 0 && rights[1] >= 0 && rights[0] != rights[1], 198);
    const int first_flags = fcntl(rights[0], F_GETFD), second_flags = fcntl(rights[1], F_GETFD);
    REQUIRE(first_flags >= 0 && second_flags >= 0 && (first_flags & FD_CLOEXEC) && (second_flags & FD_CLOEXEC), 198);
    REQUIRE(read(rights[0], payload, 3) == 3 && !memcmp(payload, "abc", 3) &&
            read(rights[1], payload, 3) == 3 && !memcmp(payload, "def", 3), 199);
    REQUIRE(!close(rights[0]) && !close(rights[1]) && !close(accepted) && !close(listener), 200);
    int status = 0; REQUIRE(waitpid(child, &status, 0) == child && WIFEXITED(status) && !WEXITSTATUS(status), 201);
    REQUIRE(!unlink(socket_path) && !unlink(data_path), 202);
    const char record[] = "OK_NATIVE_UNIX_PATHNAME processes=distinct exec=client credentials=kernel rights=preaccept shared_offset=pass cloexec=pass\n";
    REQUIRE(write(1, record, sizeof record - 1) == sizeof record - 1, 203); return 0;
}
