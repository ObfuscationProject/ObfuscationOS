/* Actual shared-futex wait retirement through signal, process kill and exec. */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define FUTEX_WAIT 0
#define FUTEX_WAKE 1

static volatile sig_atomic_t handled;

static int failure(int step)
{
    char message[] = "SHARED_FUTEX_CLEANUP_FAIL step=000 errno=000\n";
    int error = errno;
    for (int digit = 2; digit >= 0; --digit) {
        message[31 + digit] = '0' + step % 10;
        step /= 10;
        message[41 + digit] = '0' + error % 10;
        error /= 10;
    }
    (void)write(2, message, sizeof(message) - 1);
    return 1;
}
#define CHECK(test, step) do { if (!(test)) return failure(step); } while (0)

static int emit(const char *line, size_t length)
{
    return write(1, line, length) == (ssize_t)length;
}
#define EMIT(text) emit((text), sizeof(text) - 1)

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

static int receive(int fd, char expected)
{
    char value = 0;
    return read(fd, &value, 1) == 1 && value == expected;
}

static int send(int fd, char value)
{
    return write(fd, &value, 1) == 1;
}

static void pause_for_arm(void)
{
    const struct timespec duration = {0, 50000000};
    (void)nanosleep(&duration, 0);
}

static void handle_signal(int signal)
{
    if (signal == SIGUSR1) handled = 1;
}

static int signal_retirement(volatile uint32_t *word)
{
    int ready[2], done[2];
    CHECK(pipe(ready) == 0 && pipe(done) == 0, 101);
    pid_t child = fork();
    CHECK(child >= 0, 102);
    if (!child) {
        close(ready[0]); close(done[0]);
        struct sigaction action = {0};
        action.sa_handler = handle_signal;
        sigemptyset(&action.sa_mask);
        if (sigaction(SIGUSR1, &action, 0) != 0 || !send(ready[1], 'R')) _exit(103);
        struct timespec timeout = {2, 0};
        errno = 0;
        long result = futex_call(word, FUTEX_WAIT, 0, &timeout);
        if (result != -1 || errno != EINTR || handled != 1 || !send(done[1], 'D')) _exit(104);
        _exit(0);
    }
    close(ready[1]); close(done[1]);
    CHECK(receive(ready[0], 'R'), 105);
    pause_for_arm();
    CHECK(EMIT("SHARED_FUTEX_CLEANUP_EVENT signal_send\n"), 106);
    CHECK(kill(child, SIGUSR1) == 0 && receive(done[0], 'D'), 107);
    int status = 0;
    CHECK(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0, 108);
    CHECK(futex_call(word, FUTEX_WAKE, 1, 0) == 0, 109);
    CHECK(EMIT("SHARED_FUTEX_CLEANUP_EVENT signal_pass\n"), 110);
    close(ready[0]); close(done[0]);
    return 0;
}

static int kill_retirement(volatile uint32_t *word)
{
    int ready[2];
    CHECK(pipe(ready) == 0, 201);
    pid_t child = fork();
    CHECK(child >= 0, 202);
    if (!child) {
        close(ready[0]);
        if (!send(ready[1], 'R')) _exit(203);
        struct timespec timeout = {2, 0};
        (void)futex_call(word, FUTEX_WAIT, 0, &timeout);
        _exit(204);
    }
    close(ready[1]);
    CHECK(receive(ready[0], 'R'), 205);
    pause_for_arm();
    CHECK(EMIT("SHARED_FUTEX_CLEANUP_EVENT kill_send\n"), 206);
    CHECK(kill(child, SIGKILL) == 0, 207);
    int status = 0;
    CHECK(waitpid(child, &status, 0) == child && WIFSIGNALED(status) && WTERMSIG(status) == SIGKILL, 208);
    CHECK(futex_call(word, FUTEX_WAKE, 1, 0) == 0, 209);
    CHECK(EMIT("SHARED_FUTEX_CLEANUP_EVENT kill_pass\n"), 210);
    close(ready[0]);
    return 0;
}

struct ExecWait {
    volatile uint32_t *word;
    int ready;
};

static void *exec_waiter(void *opaque)
{
    struct ExecWait *wait = opaque;
    if (!send(wait->ready, 'R')) _exit(301);
    struct timespec timeout = {2, 0};
    (void)futex_call(wait->word, FUTEX_WAIT, 0, &timeout);
    _exit(302);
}

static int exec_retirement(volatile uint32_t *word)
{
    int ready[2];
    CHECK(pipe(ready) == 0, 303);
    pid_t child = fork();
    CHECK(child >= 0, 304);
    if (!child) {
        close(ready[0]);
        struct ExecWait wait = {word, ready[1]};
        pthread_t thread;
        if (pthread_create(&thread, 0, exec_waiter, &wait) != 0) _exit(305);
        pause_for_arm();
        if (!EMIT("SHARED_FUTEX_CLEANUP_EVENT exec_begin\n")) _exit(306);
        char *const argv[] = {"hello", 0};
        char *const envp[] = {0};
        execve("/bin/hello", argv, envp);
        _exit(307);
    }
    close(ready[1]);
    CHECK(receive(ready[0], 'R'), 308);
    int status = 0;
    CHECK(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0, 309);
    CHECK(futex_call(word, FUTEX_WAKE, 1, 0) == 0, 310);
    CHECK(EMIT("SHARED_FUTEX_CLEANUP_EVENT exec_pass\n"), 311);
    close(ready[0]);
    return 0;
}

int main(void)
{
    volatile uint32_t *word = mmap(0, 4096, PROT_READ | PROT_WRITE,
                                   MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)word != MAP_FAILED, 1);
    *word = 0;
    if (signal_retirement(word) || kill_retirement(word) || exec_retirement(word)) return 1;
    CHECK(munmap((void *)word, 4096) == 0, 2);
    CHECK(EMIT("OK_MUSL_SHARED_FUTEX_CLEANUP scope=actual-native signal=pass kill=pass exec=pass\n"), 3);
    return 0;
}
