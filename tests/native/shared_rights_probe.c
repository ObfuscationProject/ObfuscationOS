/* Private native/static-musl integration probe; guest execution is pending. */
#define _GNU_SOURCE 1
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#ifdef OK_SHARED_RIGHTS_NATIVE
#include <ok/socket.h>
#else
#include <sys/socket.h>
#include <sys/uio.h>
#endif

#define PAGE 4096
static unsigned checks;
static void check(int value, const char *reason)
{
    ++checks;
    if (value) return;
    fprintf(stderr, "SHARED_RIGHTS_FAIL reason=%s errno=%d checks=%u\n", reason, errno, checks);
    _Exit(1);
}
static void pair_create(int pair[2])
{
#ifdef OK_SHARED_RIGHTS_NATIVE
    check(ok_socketpair(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK, 0, pair) == 0, "native-pair");
#else
    check(socketpair(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK, 0, pair) == 0, "linux-pair");
#endif
}
static ssize_t send_rights(int socket, const char *bytes, size_t size, const int *fds, size_t count)
{
    check(count <= 2, "send-control-bound");
#ifdef OK_SHARED_RIGHTS_NATIVE
    union { struct ok_cmsghdr align; unsigned char bytes[OK_CMSG_SPACE(2 * sizeof(int))]; } control = {0};
    struct ok_iovec vector = {(uintptr_t)bytes, size};
    struct ok_msghdr header = {0};
    header.vectors = (uintptr_t)&vector; header.vector_count = 1;
    if (count) {
        struct ok_cmsghdr *message = (struct ok_cmsghdr *)control.bytes;
        message->length = OK_CMSG_LEN(count * sizeof(int));
        message->level = OK_SOL_SOCKET; message->type = OK_SCM_RIGHTS;
        memcpy(control.bytes + sizeof *message, fds, count * sizeof(int));
        header.control = (uintptr_t)control.bytes; header.control_length = OK_CMSG_SPACE(count * sizeof(int));
    }
    return ok_sendmsg(socket, &header, OK_MSG_DONTWAIT);
#else
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(2 * sizeof(int))]; } control = {0};
    struct iovec vector = {(void *)bytes, size}; struct msghdr header = {0};
    header.msg_iov = &vector; header.msg_iovlen = 1;
    if (count) {
        header.msg_control = control.bytes; header.msg_controllen = CMSG_SPACE(count * sizeof(int));
        struct cmsghdr *message = CMSG_FIRSTHDR(&header);
        message->cmsg_len = CMSG_LEN(count * sizeof(int)); message->cmsg_level = SOL_SOCKET; message->cmsg_type = SCM_RIGHTS;
        memcpy(CMSG_DATA(message), fds, count * sizeof(int));
    }
    return sendmsg(socket, &header, MSG_DONTWAIT | MSG_NOSIGNAL);
#endif
}
static ssize_t receive_right(int socket, char *bytes, size_t size, int *fd, int *truncated)
{
    if (fd) *fd = -1;
    *truncated = 0;
#ifdef OK_SHARED_RIGHTS_NATIVE
    union { struct ok_cmsghdr align; unsigned char bytes[OK_CMSG_SPACE(sizeof(int))]; } control = {0};
    struct ok_iovec vector = {(uintptr_t)bytes, size}; struct ok_msghdr header = {0};
    header.vectors = (uintptr_t)&vector; header.vector_count = 1;
    if (fd) { header.control = (uintptr_t)control.bytes; header.control_length = sizeof control.bytes; }
    const ssize_t result = ok_recvmsg(socket, &header, OK_MSG_DONTWAIT | OK_MSG_CMSG_CLOEXEC);
    if (result >= 0) {
        *truncated = (header.flags & OK_MSG_CTRUNC) != 0;
        if (fd) {
            const struct ok_cmsghdr *message = (const struct ok_cmsghdr *)control.bytes;
            check(header.control_length == OK_CMSG_SPACE(sizeof(int)) && message->length == OK_CMSG_LEN(sizeof(int)) &&
                  message->level == OK_SOL_SOCKET && message->type == OK_SCM_RIGHTS, "native-received-control");
            memcpy(fd, control.bytes + sizeof *message, sizeof *fd);
        }
    }
#else
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(sizeof(int))]; } control = {0};
    struct iovec vector = {bytes, size}; struct msghdr header = {0};
    header.msg_iov = &vector; header.msg_iovlen = 1;
    if (fd) { header.msg_control = control.bytes; header.msg_controllen = sizeof control.bytes; }
    const ssize_t result = recvmsg(socket, &header, MSG_DONTWAIT | MSG_CMSG_CLOEXEC);
    if (result >= 0) {
        *truncated = (header.msg_flags & MSG_CTRUNC) != 0;
        if (fd) {
            const struct cmsghdr *message = CMSG_FIRSTHDR(&header);
            check(message && message->cmsg_len == CMSG_LEN(sizeof(int)) && message->cmsg_level == SOL_SOCKET &&
                  message->cmsg_type == SCM_RIGHTS, "linux-received-control");
            memcpy(fd, CMSG_DATA(message), sizeof *fd);
        }
    }
#endif
    return result;
}
static int queued_file(int socket)
{
    int fd = memfd_create("English queued Notes buffer", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    check(fd >= 3 && ftruncate(fd, PAGE) == 0, "file-create-size");
    check(fcntl(fd, F_ADD_SEALS, F_SEAL_GROW | F_SEAL_SHRINK) == 0, "file-size-seals");
    char *mapping = mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    check(mapping != MAP_FAILED, "initial-file-map");
    memcpy(mapping, "Notes saved", 12);
    check(send_rights(socket, "file", 4, &fd, 1) == 4, "queue-file");
    check(munmap(mapping, PAGE) == 0 && close(fd) == 0, "queue-is-last-file-owner");
    return fd;
}
int main(void)
{
    int pair[2]; char bytes[16] = {0}; int fd = -1, truncated = 0;
    pair_create(pair);
    const int former_fd = queued_file(pair[0]);
    errno = 0;
    check(fcntl(former_fd, F_GETFD) == -1 && errno == EBADF, "sender-descriptor-gone");
    /* Fork occurs after both the original descriptor and every mapping retired.
     * The child can obtain this file only through the canonical queued right. */
    pid_t child = fork(); check(child >= 0, "fork-queued-owner");
    if (!child) {
        check(close(pair[0]) == 0, "child-close-other-peer");
        check(receive_right(pair[1], bytes, sizeof bytes, &fd, &truncated) == 4 &&
              !memcmp(bytes, "file", 4) && !truncated && fd >= 3, "child-receive-file");
        check(fcntl(fd, F_GETFD) == FD_CLOEXEC &&
              fcntl(fd, F_GET_SEALS) == (F_SEAL_GROW | F_SEAL_SHRINK), "child-flags-seals");
        char *mapping = mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        check(mapping != MAP_FAILED && !memcmp(mapping, "Notes saved", 12), "child-new-canonical-alias");
        check(send_rights(pair[1], "back", 4, &fd, 1) == 4 && close(fd) == 0, "child-return-close-file");
        memcpy(mapping, "Files reopened", 15);
        check(munmap(mapping, PAGE) == 0 && close(pair[1]) == 0, "child-final-alias-retirement");
        _Exit(0);
    }
    check(close(pair[1]) == 0, "parent-close-other-peer");
    int status = 0;
    check(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0, "child-success");
    check(receive_right(pair[0], bytes, sizeof bytes, &fd, &truncated) == 4 &&
          !memcmp(bytes, "back", 4) && !truncated && fd >= 3, "parent-returned-file");
    char *mapping = mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    check(mapping != MAP_FAILED && !memcmp(mapping, "Files reopened", 15), "returned-canonical-bytes");
    check(close(fd) == 0 && close(pair[0]) == 0, "parent-close-file-socket");
    memcpy(mapping + 32, "English alias", 14);
    check(!memcmp(mapping + 32, "English alias", 14), "alias-after-all-descriptors-close");
    check(munmap(mapping, PAGE) == 0, "final-file-retirement");
    for (unsigned attempt = 0; attempt < 32; ++attempt) {
        pair_create(pair); queued_file(pair[0]);
        if (attempt & 1) {
            check(receive_right(pair[1], bytes, sizeof bytes, 0, &truncated) == 4 && truncated, "queued-file-ctrunc-discard");
        } else {
            check(read(pair[1], bytes, sizeof bytes) == 4, "queued-file-ordinary-read-discard");
        }
        check(close(pair[0]) == 0 && close(pair[1]) == 0, "discard-close-peers");
    }
#ifdef OK_SHARED_RIGHTS_NATIVE
    static const char marker[] = "OK_NATIVE_SHARED_RIGHTS queue_last_owner=pass roundtrip=pass cloexec=pass alias=pass discard=pass\n";
#else
    static const char marker[] = "OK_STATIC_SHARED_RIGHTS queue_last_owner=pass roundtrip=pass cloexec=pass alias=pass discard=pass\n";
#endif
    check(write(1, marker, sizeof marker - 1) == sizeof marker - 1, "completion-marker");
    return 0;
}
