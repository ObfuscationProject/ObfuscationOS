#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <ok/socket.h>
#include <string.h>
static int native_transfer(void)
{
    int pair[2];
    if (ok_socketpair(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK, 0, pair)) return 160;
    const char *path = "/tmp/unix-native-rights-basic.txt";
    int fd = open(path, O_RDWR | O_CREAT | O_TRUNC, 0600);
    if (fd < 0 || write(fd, "native", 6) != 6 || lseek(fd, 0, SEEK_SET)) return 161;
    union { struct ok_cmsghdr align; unsigned char bytes[OK_CMSG_SPACE(sizeof(int))]; } control = {0};
    struct ok_cmsghdr *cmsg = (struct ok_cmsghdr *)control.bytes;
    cmsg->length = OK_CMSG_LEN(sizeof(int)); cmsg->level = OK_SOL_SOCKET; cmsg->type = OK_SCM_RIGHTS;
    memcpy(control.bytes + sizeof *cmsg, &fd, sizeof fd);
    char buffer[16] = {0}; struct ok_iovec vector = {(uintptr_t)"fd", 2};
    struct ok_msghdr header = {0}; header.vectors = (uintptr_t)&vector; header.vector_count = 1;
    header.control = (uintptr_t)control.bytes; header.control_length = sizeof control.bytes;
    if (ok_sendmsg(pair[0], &header, OK_MSG_DONTWAIT) != 2 || close(fd)) return 162;
    vector.base = (uintptr_t)buffer; vector.length = sizeof buffer;
    if (ok_recvmsg(pair[1], &header, OK_MSG_DONTWAIT | OK_MSG_CMSG_CLOEXEC) != 2 || memcmp(buffer, "fd", 2)) return 163;
    memcpy(&fd, control.bytes + sizeof *cmsg, sizeof fd);
    if (fd < 0 || !(header.flags & OK_MSG_CMSG_CLOEXEC) || !(fcntl(fd, F_GETFD) & FD_CLOEXEC)) return 164;
    if (read(fd, buffer, sizeof buffer) != 6 || memcmp(buffer, "native", 6) || write(fd, " saved", 6) != 6 || fsync(fd) || close(fd)) return 165;
    fd = open(path, O_RDONLY);
    if (fd < 0 || read(fd, buffer, sizeof buffer) != 12 || memcmp(buffer, "native saved", 12)) return 166;
    if (close(fd) || close(pair[0]) || close(pair[1]) || unlink(path)) return 167;
    static const char record[] = "OK_NATIVE_UNIX_RIGHTS transfer=pass cloexec=pass file_reopen=pass\n";
    return write(1, record, sizeof record - 1) == sizeof record - 1 ? 0 : 168;
}
int main(void)
{
    const int native_result = native_transfer(); if (native_result) return native_result;
    pid_t child = fork(); if (child < 0) return 150;
    if (!child)
    {
        char *argv[] = {"unix-rights-static", 0}; char *envp[] = {"PATH=/bin", 0};
        execve("/bin/unix-rights-static", argv, envp); _Exit(126);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status)) return 151;
    static const char record[] = "OK_STATIC_UNIX_RIGHTS_RUNNER child_exit=0\n";
    return write(1, record, sizeof record - 1) == sizeof record - 1 ? 0 : 152;
}
