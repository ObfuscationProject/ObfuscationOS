/* Guest clocks against the host's: for each request line read from the
 * console the probe samples CLOCK_MONOTONIC and CLOCK_REALTIME and prints them
 * at once, and scripts/test_clock_drift.py brackets every sample with its own
 * clocks to fit the drift. A 'b' line runs user code without system calls
 * for three seconds, so the kernel's timer preempts it and measures that
 * tick's latency. Prints CLOCK_READY first and CLOCK_DONE after a line
 * starting with 'q', or CLOCK_FAIL with the errno. */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

#if defined(__i386__)
#define PROBE_ARCH "i386"
#elif defined(__x86_64__)
#define PROBE_ARCH "x86_64"
#elif defined(__arm__)
#define PROBE_ARCH "arm32"
#elif defined(__aarch64__)
#define PROBE_ARCH "aarch64"
#elif defined(__riscv) && __riscv_xlen == 32
#define PROBE_ARCH "rv32"
#elif defined(__riscv) && __riscv_xlen == 64
#define PROBE_ARCH "rv64"
#elif defined(__mips64)
#define PROBE_ARCH "mips64"
#elif defined(__mips__)
#define PROBE_ARCH "mips"
#elif defined(__loongarch64)
#define PROBE_ARCH "loongarch64"
#elif defined(__powerpc__) || defined(__PPC__)
#define PROBE_ARCH "ppc"
#else
#error "Unsupported clock probe profile"
#endif

static void emit(const char *text, size_t size)
{
    while (size)
    {
        const ssize_t written = write(1, text, size);
        if (written <= 0 && errno != EINTR)
            _exit(1);
        if (written > 0)
        {
            text += written;
            size -= (size_t)written;
        }
    }
}

static int64_t monotonic(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t))
        return -1;
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

static void spin(unsigned long iterations)
{
    unsigned long value = 1;
    for (unsigned long i = 0; i < iterations; ++i)
    {
        value = value * 1103515245u + 12345u;
        __asm__ volatile("" : "+r"(value));
    }
}

// Each system call starts a fresh 10 ms quantum, so the chunks between clock
// reads grow until one takes at least 40 ms and the timer ticks inside them.
static void busy(char *out, size_t capacity)
{
    const int64_t start = monotonic();
    unsigned long chunk = 1 << 16;
    for (;;)
    {
        const int64_t before = monotonic();
        spin(chunk);
        if (monotonic() - before >= 40000000 || chunk >= (1ul << 30))
            break;
        chunk *= 2;
    }
    unsigned chunks = 0;
    while (monotonic() - start < 3000000000LL)
    {
        spin(chunk);
        ++chunks;
    }
    const int size = snprintf(out, capacity, "CLOCK_BUSY arch=%s ms=%lld chunks=%u\n", PROBE_ARCH,
                              (long long)((monotonic() - start) / 1000000), chunks);
    emit(out, (size_t)size);
}

int main(void)
{
    char line[64], out[160];
    int size = snprintf(out, sizeof out, "CLOCK_READY arch=%s\n", PROBE_ARCH);
    emit(out, (size_t)size);
    unsigned samples = 0;
    while (fgets(line, sizeof line, stdin))
    {
        if (line[0] == 'q')
            break;
        if (line[0] == 'b')
            busy(out, sizeof out);
        if (line[0] != 's')
            continue;
        struct timespec mono, real;
        if (clock_gettime(CLOCK_MONOTONIC, &mono))
        {
            size = snprintf(out, sizeof out, "CLOCK_FAIL arch=%s clock=monotonic errno=%d\n", PROBE_ARCH, errno);
            emit(out, (size_t)size);
            return 1;
        }
        // Without a wall clock CLOCK_REALTIME fails; the drift of the
        // monotonic clock is still measured.
        const int real_errno = clock_gettime(CLOCK_REALTIME, &real) ? errno : 0;
        if (real_errno)
            size = snprintf(out, sizeof out, "CLOCK seq=%u mono=%lld.%09ld real=none errno=%d\n", samples,
                            (long long)mono.tv_sec, (long)mono.tv_nsec, real_errno);
        else
            size = snprintf(out, sizeof out, "CLOCK seq=%u mono=%lld.%09ld real=%lld.%09ld\n", samples,
                            (long long)mono.tv_sec, (long)mono.tv_nsec, (long long)real.tv_sec, (long)real.tv_nsec);
        emit(out, (size_t)size);
        ++samples;
    }
    size = snprintf(out, sizeof out, "CLOCK_DONE arch=%s samples=%u\n", PROBE_ARCH, samples);
    emit(out, (size_t)size);
    return 0;
}
