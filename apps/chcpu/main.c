/* chcpu: enable, disable or list CPUs through /sys/devices/system/cpu.
 *
 *   chcpu -e LIST   write "1" to cpuN/online for every CPU in LIST
 *   chcpu -d LIST   write "0" to cpuN/online for every CPU in LIST
 *   chcpu -l        list every present CPU and whether it is online
 *
 * LIST is a cpulist ("1", "1,3", "1-3"). Messages and exit codes follow
 * util-linux chcpu: 0 when every CPU succeeded, 1 when none did, 64 when
 * some did. -l is local; util-linux lists CPUs with lscpu -e. */
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

#define CPU_ROOT "/sys/devices/system/cpu"
#define MAX_CPUS 16
#define EXIT_SOME_OK 64


/* okcrt has no strcat. */
static void append(char *buffer, const char *text)
{
    while (*buffer) ++buffer;
    while ((*buffer++ = *text++)) {}
}

/* One write per message: the console interleaves kernel lines with output
   written in pieces. */
static void say(int fd, const char *a, int cpu, const char *b, const char *c)
{
    char text[160];
    text[0] = 0;
    append(text, a);
    if (cpu >= 0)
    {
        char digits[4] = {0};
        int size = 0;
        if (cpu >= 10) digits[size++] = (char)('0' + cpu / 10);
        digits[size++] = (char)('0' + cpu % 10);
        append(text, digits);
    }
    append(text, b);
    append(text, c);
    append(text, "\n");
    size_t length = 0;
    while (text[length]) ++length;
    ssize_t ignored = write(fd, text, length);
    (void)ignored;
}

static void usage(void)
{
    say(2, "Usage: chcpu -e|-d CPU-LIST\n       chcpu -l", -1, "", "");
}

/* Reads a small sysfs attribute; returns its length or -1 with errno set. */
static int read_attribute(const char *path, char *buffer, int size)
{
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    int total = 0;
    for (;;) {
        ssize_t got = read(fd, buffer + total, (size_t)(size - 1 - total));
        if (got < 0) {
            int saved = errno;
            close(fd);
            errno = saved;
            return -1;
        }
        if (got == 0 || total + got >= size - 1) {
            total += (int)got;
            break;
        }
        total += (int)got;
    }
    close(fd);
    buffer[total] = 0;
    return total;
}

/* A cpulist ("0-3,5\n") as a mask; -1 when it is not one. */
static long parse_list(const char *text)
{
    long mask = 0;
    const char *p = text;
    while (*p && *p != '\n') {
        if (*p < '0' || *p > '9') return -1;
        long first = 0;
        while (*p >= '0' && *p <= '9') first = first * 10 + (*p++ - '0');
        long last = first;
        if (*p == '-') {
            ++p;
            if (*p < '0' || *p > '9') return -1;
            last = 0;
            while (*p >= '0' && *p <= '9') last = last * 10 + (*p++ - '0');
        }
        if (first > last || last >= MAX_CPUS) return -1;
        for (long cpu = first; cpu <= last; ++cpu) mask |= 1L << cpu;
        if (*p == ',') {
            ++p;
            if (!*p || *p == '\n') return -1;
        } else if (*p && *p != '\n') {
            return -1;
        }
    }
    return mask;
}

static long read_mask(const char *name)
{
    char path[64];
    char text[64];
    strcpy(path, CPU_ROOT "/");
    append(path, name);
    if (read_attribute(path, text, (int)sizeof text) < 0) return -1;
    return parse_list(text);
}

static int count(long mask)
{
    int total = 0;
    for (; mask; mask &= mask - 1) ++total;
    return total;
}

static void cpu_path(char *path, int cpu)
{
    char digits[4];
    int size = 0;
    if (cpu >= 10) digits[size++] = (char)('0' + cpu / 10);
    digits[size++] = (char)('0' + cpu % 10);
    digits[size] = 0;
    strcpy(path, CPU_ROOT "/cpu");
    append(path, digits);
    append(path, "/online");
}

static int list_cpus(void)
{
    long present = read_mask("present");
    long online = read_mask("online");
    if (present < 0 || online < 0) {
        say(2, "chcpu: cannot read " CPU_ROOT ": ", -1, strerror(errno), "");
        return 1;
    }
    say(1, "CPU ONLINE", -1, "", "");
    for (int cpu = 0; cpu < MAX_CPUS; ++cpu)
        if (present & (1L << cpu)) say(1, "", cpu, (online & (1L << cpu)) ? " yes" : " no", "");
    return 0;
}

static int change(long cpus, int enable)
{
    long present = read_mask("present");
    if (present < 0) {
        say(2, "chcpu: cannot read " CPU_ROOT ": ", -1, strerror(errno), "");
        return 1;
    }
    int ok = 0, failed = 0;
    for (int cpu = 0; cpu < MAX_CPUS; ++cpu) {
        if (!(cpus & (1L << cpu))) continue;
        if (!(present & (1L << cpu))) {
            say(2, "chcpu: CPU ", cpu, " does not exist", "");
            ++failed;
            continue;
        }
        char path[64];
        char state[8];
        cpu_path(path, cpu);
        if (read_attribute(path, state, (int)sizeof state) < 0) {
            say(2, "chcpu: CPU ", cpu, " is not hot pluggable", "");
            ++failed;
            continue;
        }
        if (state[0] == '1' && enable) {
            say(1, "CPU ", cpu, " is already enabled", "");
            ++ok;
            continue;
        }
        if (state[0] == '0' && !enable) {
            say(1, "CPU ", cpu, " is already disabled", "");
            ++ok;
            continue;
        }
        if (!enable) {
            long online = read_mask("online");
            if (online >= 0 && count(online) == 1) {
                say(1, "CPU ", cpu, " disable failed (last enabled CPU)", "");
                ++failed;
                continue;
            }
        }
        int fd = open(path, O_WRONLY);
        ssize_t wrote = -1;
        if (fd >= 0) {
            wrote = write(fd, enable ? "1" : "0", 1);
            int saved = errno;
            close(fd);
            errno = saved;
        }
        if (wrote != 1) {
            say(2, "chcpu: CPU ", cpu, enable ? " enable failed: " : " disable failed: ", strerror(errno));
            ++failed;
            continue;
        }
        say(1, "CPU ", cpu, enable ? " enabled" : " disabled", "");
        ++ok;
    }
    if (!failed) return 0;
    return ok ? EXIT_SOME_OK : 1;
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "-l") == 0) return list_cpus();
    if (argc != 3 || (strcmp(argv[1], "-e") != 0 && strcmp(argv[1], "-d") != 0)) {
        usage();
        return 1;
    }
    long cpus = parse_list(argv[2]);
    if (cpus <= 0) {
        say(2, "chcpu: failed to parse CPU list: ", -1, argv[2], "");
        return 1;
    }
    return change(cpus, argv[1][1] == 'e');
}
