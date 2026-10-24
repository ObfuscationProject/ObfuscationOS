/* Source-only native/static-musl acceptance proposal; no execution is implied. */
#define _GNU_SOURCE 1
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <unistd.h>
#ifdef OK_NATIVE_SHARED_WRITE_SEAL_PROBE
#include <ok/socket.h>
#else
#include <sys/socket.h>
#endif

#define PAGE 4096
#define SIZE_SEALS (F_SEAL_GROW | F_SEAL_SHRINK)
#define WRITE_SEALS (SIZE_SEALS | F_SEAL_WRITE)
#define FINAL_SEALS (WRITE_SEALS | F_SEAL_SEAL)
static const char document[] = "Notes saved\n";
static const char tail[] = "English tail";
static unsigned checks;
static void check(int passed, const char *reason)
{
    ++checks;
    if (passed) return;
    fprintf(stderr, "SHARED_WRITE_SEAL_FAIL reason=%s errno=%d checks=%u\n", reason, errno, checks);
    _Exit(1);
}
static void child_success(pid_t child)
{
    int status = 0;
    check(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0,
          "producer-exited-successfully");
}
static void store_fault(volatile unsigned char *address)
{
    const pid_t child = fork();
    check(child >= 0, "fault-child-created");
    if (!child) { *address = 'X'; _Exit(96); }
    int status = 0;
    check(waitpid(child, &status, 0) == child, "fault-child-reaped");
    const int result = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    check(result == 139, "actual-readonly-store-contained");
}
static void pair_create(int pair[2])
{
#ifdef OK_NATIVE_SHARED_WRITE_SEAL_PROBE
    check(ok_socketpair(OK_AF_UNIX, OK_SOCK_STREAM | OK_SOCK_NONBLOCK, 0, pair) == 0, "native-pair");
#else
    check(socketpair(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK, 0, pair) == 0, "linux-pair");
#endif
}
static void send_snapshot(int socket, int fd)
{
#ifdef OK_NATIVE_SHARED_WRITE_SEAL_PROBE
    union { struct ok_cmsghdr align; unsigned char bytes[OK_CMSG_SPACE(sizeof(int))]; } control = {0};
    struct ok_iovec vector = {(uintptr_t)"text", 4};
    struct ok_msghdr header = {0};
    struct ok_cmsghdr *message = (struct ok_cmsghdr *)control.bytes;
    message->length = OK_CMSG_LEN(sizeof(int)); message->level = OK_SOL_SOCKET; message->type = OK_SCM_RIGHTS;
    memcpy(control.bytes + sizeof *message, &fd, sizeof fd);
    header.vectors = (uintptr_t)&vector; header.vector_count = 1;
    header.control = (uintptr_t)control.bytes; header.control_length = sizeof control.bytes;
    check(ok_sendmsg(socket, &header, OK_MSG_DONTWAIT) == 4, "native-queue-snapshot");
#else
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(sizeof(int))]; } control = {0};
    struct iovec vector = {(void *)"text", 4}; struct msghdr header = {0};
    header.msg_iov = &vector; header.msg_iovlen = 1;
    header.msg_control = control.bytes; header.msg_controllen = sizeof control.bytes;
    struct cmsghdr *message = CMSG_FIRSTHDR(&header);
    message->cmsg_len = CMSG_LEN(sizeof(int)); message->cmsg_level = SOL_SOCKET; message->cmsg_type = SCM_RIGHTS;
    memcpy(CMSG_DATA(message), &fd, sizeof fd);
    check(sendmsg(socket, &header, MSG_DONTWAIT | MSG_NOSIGNAL) == 4, "linux-queue-snapshot");
#endif
}
static int receive_snapshot(int socket)
{
    int fd = -1; char payload[4] = {0};
#ifdef OK_NATIVE_SHARED_WRITE_SEAL_PROBE
    union { struct ok_cmsghdr align; unsigned char bytes[OK_CMSG_SPACE(sizeof(int))]; } control = {0};
    struct ok_iovec vector = {(uintptr_t)payload, sizeof payload}; struct ok_msghdr header = {0};
    header.vectors = (uintptr_t)&vector; header.vector_count = 1;
    header.control = (uintptr_t)control.bytes; header.control_length = sizeof control.bytes;
    check(ok_recvmsg(socket, &header, OK_MSG_DONTWAIT | OK_MSG_CMSG_CLOEXEC) == 4,
          "native-receive-snapshot");
    const struct ok_cmsghdr *message = (const struct ok_cmsghdr *)control.bytes;
    check(header.control_length == sizeof control.bytes && !(header.flags & OK_MSG_CTRUNC) &&
          message->length == OK_CMSG_LEN(sizeof(int)) && message->level == OK_SOL_SOCKET &&
          message->type == OK_SCM_RIGHTS, "native-exact-rights-control");
    memcpy(&fd, control.bytes + sizeof *message, sizeof fd);
#else
    union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(sizeof(int))]; } control = {0};
    struct iovec vector = {payload, sizeof payload}; struct msghdr header = {0};
    header.msg_iov = &vector; header.msg_iovlen = 1;
    header.msg_control = control.bytes; header.msg_controllen = sizeof control.bytes;
    check(recvmsg(socket, &header, MSG_DONTWAIT | MSG_CMSG_CLOEXEC) == 4, "linux-receive-snapshot");
    const struct cmsghdr *message = CMSG_FIRSTHDR(&header);
    check(header.msg_controllen == sizeof control.bytes && !(header.msg_flags & MSG_CTRUNC) &&
          message && message->cmsg_len == CMSG_LEN(sizeof(int)) && message->cmsg_level == SOL_SOCKET &&
          message->cmsg_type == SCM_RIGHTS, "linux-exact-rights-control");
    memcpy(&fd, CMSG_DATA(message), sizeof fd);
#endif
    check(fd >= 3 && !memcmp(payload, "text", 4), "exact-snapshot-received");
    check(fcntl(fd, F_GETFD) == FD_CLOEXEC, "received-cloexec");
    return fd;
}
static void produce_snapshot(int socket)
{
    const int fd = memfd_create("English Notes snapshot", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    check(fd >= 3 && ftruncate(fd, 2 * PAGE) == 0, "create-size");
    check(pwrite(fd, document, sizeof document - 1, 0) == sizeof document - 1, "seed-English-document");
    check(pwrite(fd, tail, sizeof tail - 1, PAGE - 4) == sizeof tail - 1, "seed-cross-page-tail");
    check(fcntl(fd, F_ADD_SEALS, SIZE_SEALS) == 0, "seal-size");
    unsigned char *writer = mmap(0, 2 * PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    check(writer != MAP_FAILED, "pre-seal-writable-alias");
    errno = 0;
    check(fcntl(fd, F_ADD_SEALS, F_SEAL_WRITE | F_SEAL_SEAL) == -1 && errno == EBUSY &&
          fcntl(fd, F_GET_SEALS) == SIZE_SEALS, "writable-alias-combined-seal-rollback");
    check(mprotect(writer, 2 * PAGE, PROT_READ) == 0, "pre-seal-readonly-alias");
    errno = 0;
    check(fcntl(fd, F_ADD_SEALS, F_SEAL_WRITE | F_SEAL_SEAL) == -1 && errno == EBUSY &&
          fcntl(fd, F_GET_SEALS) == SIZE_SEALS, "readonly-alias-combined-seal-rollback");
    check(mprotect(writer, 2 * PAGE, PROT_NONE) == 0, "pre-seal-inaccessible-alias");
    errno = 0;
    check(fcntl(fd, F_ADD_SEALS, F_SEAL_WRITE | F_SEAL_SEAL) == -1 && errno == EBUSY &&
          fcntl(fd, F_GET_SEALS) == SIZE_SEALS, "inaccessible-alias-combined-seal-rollback");
    check(munmap(writer, 2 * PAGE) == 0, "complete-alias-retirement");
    check(fcntl(fd, F_ADD_SEALS, F_SEAL_WRITE) == 0 && fcntl(fd, F_GET_SEALS) == WRITE_SEALS,
          "seal-content-after-retirement");
    unsigned char *reader = mmap(0, 2 * PAGE, PROT_READ, MAP_SHARED, fd, 0);
    check(reader != MAP_FAILED && !memcmp(reader, document, sizeof document - 1), "sealed-readonly-alias");
    check(fcntl(fd, F_ADD_SEALS, F_SEAL_WRITE) == 0 && fcntl(fd, F_GET_SEALS) == WRITE_SEALS,
          "existing-write-seal-idempotent");
    check(fcntl(fd, F_ADD_SEALS, F_SEAL_SEAL) == 0 && fcntl(fd, F_GET_SEALS) == FINAL_SEALS,
          "finalize-seals");
    check(munmap(reader, 2 * PAGE) == 0, "retire-producer-reader");
    send_snapshot(socket, fd);
    check(close(fd) == 0 && close(socket) == 0, "queue-holds-only-snapshot-owner");
}
int main(void)
{
    int pair[2]; pair_create(pair);
    /* The producer creates the file after fork. The receiver never inherits a
     * file descriptor or alias, and waits for producer exit before receiving. */
    const pid_t producer = fork(); check(producer >= 0, "producer-fork");
    if (!producer) {
        check(close(pair[1]) == 0, "producer-close-receiver");
        produce_snapshot(pair[0]); _Exit(0);
    }
    check(close(pair[0]) == 0, "receiver-close-producer");
    child_success(producer);
    const int fd = receive_snapshot(pair[1]);
    check(close(pair[1]) == 0, "retire-transfer-socket");
    check(fcntl(fd, F_GET_SEALS) == FINAL_SEALS, "seals-survive-producer-exit");
    const int duplicate = dup(fd); check(duplicate >= 3, "duplicate-snapshot");
    check(lseek(fd, 19, SEEK_SET) == 19, "set-shared-offset");
    unsigned char *reader = mmap(0, 2 * PAGE, PROT_READ, MAP_SHARED, fd, 0);
    check(reader != MAP_FAILED && !memcmp(reader, document, sizeof document - 1) &&
          !memcmp(reader + PAGE - 4, tail, sizeof tail - 1), "English-snapshot-readable");
    errno = 0;
    check(write(duplicate, "Changed", 7) == -1 && errno == EPERM, "write-refused");
    errno = 0;
    check(pwrite(fd, "Changed", 7, 0) == -1 && errno == EPERM, "pwrite-refused");
    struct iovec vectors[2] = {{(void *)"Changed", 7}, {(void *)"again", 5}};
    errno = 0;
    check(writev(fd, vectors, 2) == -1 && errno == EPERM, "writev-refused");
    check(lseek(duplicate, 0, SEEK_CUR) == 19, "refused-writes-preserve-shared-offset");
    struct iovec empty[2] = {{0, 0}, {0, 0}};
    check(write(fd, 0, 0) == 0 && pwrite(fd, 0, 0, 0) == 0 && writev(fd, empty, 2) == 0,
          "Linux-empty-writes-noop");
    check(lseek(duplicate, 0, SEEK_CUR) == 19, "empty-writes-preserve-offset");
    errno = 0;
    check(mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0) == MAP_FAILED && errno == EPERM,
          "writable-mapping-refused");
    errno = 0;
    check(mmap(reader, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_FIXED, fd, 0) == MAP_FAILED &&
          errno == EPERM && !memcmp(reader, document, sizeof document - 1), "fixed-write-refusal-preserves-old-map");
    errno = 0;
    check(mprotect(reader, 2 * PAGE, PROT_READ | PROT_WRITE) == -1 && errno == EACCES,
          "write-protection-upgrade-refused");
    store_fault(reader);
    check(mprotect(reader, 2 * PAGE, PROT_NONE) == 0, "sealed-none");
    errno = 0;
    check(mprotect(reader, 2 * PAGE, PROT_WRITE) == -1 && errno == EACCES,
          "none-to-write-upgrade-refused");
    check(mprotect(reader, 2 * PAGE, PROT_READ) == 0, "sealed-read-restored");
    unsigned char *mixed = mmap(0, 2 * PAGE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    check(mixed != MAP_FAILED, "mixed-range-private-allocation");
    check(mmap(mixed + PAGE, PAGE, PROT_READ, MAP_SHARED | MAP_FIXED, fd, 0) == mixed + PAGE,
          "mixed-range-sealed-page");
    check(mprotect(mixed, PAGE, PROT_READ) == 0, "mixed-range-private-readonly");
    errno = 0;
    check(mprotect(mixed, 2 * PAGE, PROT_READ | PROT_WRITE) == -1 && errno == EACCES,
          "mixed-range-upgrade-atomic-refusal");
    store_fault(mixed);
    check(!memcmp(mixed + PAGE, document, sizeof document - 1), "mixed-range-snapshot-preserved");
    check(munmap(mixed, 2 * PAGE) == 0, "mixed-range-retired");
    check(!memcmp(reader, document, sizeof document - 1) &&
          !memcmp(reader + PAGE - 4, tail, sizeof tail - 1), "all-refusals-preserve-snapshot");
    check(close(fd) == 0 && close(duplicate) == 0, "close-all-snapshot-descriptors");
    check(!memcmp(reader, document, sizeof document - 1), "readonly-alias-survives-final-close");
    check(munmap(reader, 2 * PAGE) == 0, "final-snapshot-retirement");
#ifdef OK_NATIVE_SHARED_WRITE_SEAL_PROBE
    static const char marker[] = "OK_NATIVE_SHARED_WRITE_SEAL scope=hardware english=1 producer_exit=pass queue_owner=pass readonly=pass busy_aliases=pass combined_rollback=pass idempotent=pass write=refused vectors=refused empty=noop mmap=refused mprotect=refused fixed_rollback=pass mixed_rollback=pass store_fault=pass final_close=pass\n";
#else
    static const char marker[] = "OK_STATIC_SHARED_WRITE_SEAL scope=hardware english=1 producer_exit=pass queue_owner=pass readonly=pass busy_aliases=pass combined_rollback=pass idempotent=pass write=refused vectors=refused empty=noop mmap=refused mprotect=refused fixed_rollback=pass mixed_rollback=pass store_fault=pass final_close=pass\n";
#endif
    check(write(1, marker, sizeof marker - 1) == sizeof marker - 1, "completion-marker");
    return 0;
}
