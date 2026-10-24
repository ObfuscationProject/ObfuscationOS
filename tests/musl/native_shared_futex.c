/* Static-musl guest for the isolated SDK39 shared-anonymous futex successor.
 * Parent/child handshakes use pipes; WAKE == 1, not elapsed time, proves that
 * the ordinary shared WAIT was actually queued. Kernel-arm serial events must
 * precede the replacement event before claiming stale-key isolation.
 */
#include <errno.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define PAGE 4096
#define FUTEX_WAIT 0
#define FUTEX_WAKE 1
#define FUTEX_PRIVATE_FLAG 128

static int failed(int step)
{
    char message[] = "SHARED_FUTEX_FAIL step=000 errno=000\n";
    int error = errno;
    for (int i = 2; i >= 0; --i) {
        message[23 + i] = '0' + step % 10;
        step /= 10;
        message[33 + i] = '0' + error % 10;
        error /= 10;
    }
    ssize_t written = write(2, message, sizeof message - 1);
    (void)written;
    return 1;
}
#define CHECK(test, step) do { if (!(test)) return failed(step); } while (0)

static long futex_call(volatile uint32_t *word, int operation, uint32_t value,
                       const struct timespec *timeout)
{
#ifdef SYS_futex_time64
    long number = timeout ? SYS_futex_time64 : SYS_futex;
#else
    long number = SYS_futex;
#endif
    return syscall(number, word, operation, value, timeout);
}

static int receive(int fd, char wanted)
{
    char byte = 0;
    return read(fd, &byte, 1) == 1 && byte == wanted;
}

static int send(int fd, char byte)
{
    return write(fd, &byte, 1) == 1;
}

static int child_status(pid_t pid)
{
    int status = 0;
    return waitpid(pid, &status, 0) == pid && WIFEXITED(status) && WEXITSTATUS(status) == 0;
}

static int shared_wait_wake(volatile uint32_t *word)
{
    int ready[2], done[2];
    CHECK(pipe(ready) == 0 && pipe(done) == 0, 101);
    pid_t child = fork();
    CHECK(child >= 0, 102);
    if (!child) {
        close(ready[0]); close(done[0]);
        if (!send(ready[1], 'R')) _exit(103);
        if (futex_call(word, FUTEX_WAIT, 0, 0) != 0) _exit(104);
        if (!send(done[1], 'D')) _exit(105);
        _exit(0);
    }
    close(ready[1]); close(done[1]);
    CHECK(receive(ready[0], 'R'), 106);
    int woke = 0;
    for (int attempt = 0; attempt < 2000 && !woke; ++attempt) {
        long unrelated = futex_call(word + 1, FUTEX_WAKE, 1, 0);
        long private_domain = futex_call(word, FUTEX_WAKE | FUTEX_PRIVATE_FLAG, 1, 0);
        CHECK(unrelated == 0 && private_domain == 0, 107);
        long result = futex_call(word, FUTEX_WAKE, 1, 0);
        CHECK(result == 0 || result == 1, 108);
        woke = result == 1;
        if (!woke) {
            struct timespec pace = {0, 1000000};
            (void)nanosleep(&pace, 0);
        }
    }
    CHECK(woke, 109);
    CHECK(receive(done[0], 'D') && child_status(child), 110);
    close(ready[0]); close(done[0]);
    static const char marker[] = "SHARED_FUTEX_EVENT parent_child_wake=1 offset_wake=0 private_wake=0 child_exit=0\n";
    CHECK(write(1, marker, sizeof marker - 1) == sizeof marker - 1, 111);
    return 0;
}

static int replacement_isolation(volatile uint32_t *word)
{
    int ready[2];
    CHECK(pipe(ready) == 0, 201);
    pid_t child = fork();
    CHECK(child >= 0, 202);
    if (!child) {
        close(ready[0]);
        if (!send(ready[1], 'R')) _exit(203);
        struct timespec limit = {0, 200000000};
        errno = 0;
        if (futex_call(word, FUTEX_WAIT, 0, &limit) != -1 || errno != ETIMEDOUT) _exit(204);
        _exit(0);
    }
    close(ready[1]);
    CHECK(receive(ready[0], 'R'), 205);
    void *replacement = mmap((void *)word, PAGE, PROT_READ | PROT_WRITE,
                             MAP_SHARED | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    CHECK(replacement == (void *)word, 206);
    CHECK(futex_call(word, FUTEX_WAKE, 1, 0) == 0, 207);
    static const char marker[] = "SHARED_FUTEX_EVENT replacement_wake=0\n";
    CHECK(write(1, marker, sizeof marker - 1) == sizeof marker - 1, 208);
    CHECK(child_status(child), 209);
    close(ready[0]);
    return 0;
}

int main(void)
{
    volatile uint32_t *word = mmap(0, PAGE, PROT_READ | PROT_WRITE,
                                   MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)word != MAP_FAILED, 1);
    word[0] = 0; word[1] = 0;
    errno = 0;
    CHECK(futex_call(word, FUTEX_WAIT, 1, 0) == -1 && errno == EAGAIN, 2);
    static const char mismatch[] = "SHARED_FUTEX_EVENT mismatch=eagain\n";
    CHECK(write(1, mismatch, sizeof mismatch - 1) == sizeof mismatch - 1, 6);
    if (shared_wait_wake(word)) return 1;
    struct timespec limit = {0, 20000000};
    errno = 0;
    CHECK(futex_call(word, FUTEX_WAIT, 0, &limit) == -1 && errno == ETIMEDOUT, 3);
    static const char timed[] = "SHARED_FUTEX_EVENT timeout=etimedout\n";
    CHECK(write(1, timed, sizeof timed - 1) == sizeof timed - 1, 7);
    if (replacement_isolation(word)) return 1;
    CHECK(munmap((void *)word, PAGE) == 0, 4);
    static const char success[] = "OK_MUSL_SHARED_FUTEX scope=actual-native anonymous=pass fork=pass pipe_order=pass wake=1 mismatch=pass timeout=pass private_domain=pass offset=pass map_fixed=pass child_exit=pass\n";
    CHECK(write(1, success, sizeof success - 1) == sizeof success - 1, 5);
    return 0;
}
