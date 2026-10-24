/* Hosted actual CLI with deterministic inventory/output seams. No guest runs. */
#include <ok/storage.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "mountctl test:%d: %s\n", __LINE__, #value); abort(); \
} } while (0)

static struct ok_mount_info fixture[OK_MOUNT_INFO_CAPACITY];
static unsigned calls, fail_call, busy_call, mismatch_call;
static int failure, always_busy, churn, malformed_final, output_failure;
static char output[16384], diagnostic[1024];
static size_t output_size, diagnostic_size;

static int capture(FILE *stream, const char *bytes, size_t size)
{
    char *buffer = stream == stdout ? output : diagnostic;
    size_t *used = stream == stdout ? &output_size : &diagnostic_size;
    size_t capacity = stream == stdout ? sizeof(output) : sizeof(diagnostic);
    if (stream == stdout && output_failure) { errno = EIO; return -1; }
    CHECK(size < capacity - *used);
    memcpy(buffer + *used, bytes, size); *used += size; buffer[*used] = 0;
    return (int)size;
}

static int capture_fputc(int byte, FILE *stream)
{
    char value = (char)byte;
    return capture(stream, &value, 1) < 0 ? -1 : (unsigned char)byte;
}

static int capture_fputs(const char *value, FILE *stream)
{ return capture(stream, value, strlen(value)); }

static int capture_printf(const char *format, ...)
{
    char buffer[256];
    va_list arguments; va_start(arguments, format);
    int size = vsnprintf(buffer, sizeof(buffer), format, arguments);
    va_end(arguments);
    CHECK(size >= 0 && (size_t)size < sizeof(buffer));
    return capture(stdout, buffer, (size_t)size);
}

static void capture_perror(const char *prefix)
{
    char buffer[128];
    int size = snprintf(buffer, sizeof(buffer), "%s: errno=%d\n", prefix, errno);
    CHECK(size > 0 && (size_t)size < sizeof(buffer));
    (void)capture(stderr, buffer, (size_t)size);
}

int ok_mount_info(uint32_t slot, struct ok_mount_info *row)
{
    CHECK(slot < OK_MOUNT_INFO_CAPACITY); ++calls;
    if (always_busy || calls == busy_call) { errno = EBUSY; return -1; }
    if (calls == fail_call) { errno = failure; return -1; }
    *row = fixture[slot];
    if (calls == mismatch_call || (churn && slot == 1)) ++row->generation;
    if (malformed_final && calls == 10) row->capacity = 8;
    return 0;
}

#define fputc capture_fputc
#define fputs capture_fputs
#define printf capture_printf
#define perror capture_perror
#define main mountctl_application_main
#include "../apps/mountctl/main.c"
#undef main
#undef perror
#undef printf
#undef fputs
#undef fputc

static void row_path(unsigned slot, const void *bytes, size_t size)
{
    CHECK(slot < OK_MOUNT_INFO_CAPACITY && size < OK_MOUNT_INFO_PATH_CAPACITY);
    memset(fixture[slot].path, 0, sizeof(fixture[slot].path));
    memcpy(fixture[slot].path, bytes, size); fixture[slot].path_length = (uint32_t)size;
}

static void reset(void)
{
    memset(fixture, 0, sizeof(fixture));
    for (uint32_t slot = 0; slot < OK_MOUNT_INFO_CAPACITY; ++slot)
        fixture[slot] = (struct ok_mount_info){.version = 1, .size = 288,
            .generation = 3, .slot = slot, .capacity = OK_MOUNT_INFO_CAPACITY};
    fixture[0].state = OK_MOUNT_STATE_UNDERLYING_RAM; row_path(0, "/", 1);
    fixture[1].state = OK_MOUNT_STATE_OWNED_PROVIDER; row_path(1, "/", 1);
    fixture[2].state = OK_MOUNT_STATE_OWNED_RAM; fixture[2].parent_id = 1; row_path(2, "/run", 4);
    calls = fail_call = busy_call = mismatch_call = 0;
    failure = always_busy = churn = malformed_final = output_failure = 0;
    output_size = diagnostic_size = 0; output[0] = diagnostic[0] = 0;
    errno = 0;
}

static int run(void)
{
    char *arguments[] = {"mountctl", "status", 0};
    return mountctl_application_main(2, arguments);
}

static void no_output_failure(int error)
{
    CHECK(run() == 1 && errno == error && !output_size && diagnostic_size);
}

static void ordinary_and_states(void)
{
    reset(); CHECK(!run() && calls == 10 && !diagnostic_size);
    CHECK(strstr(output, "MOUNTS version=1 generation=3 capacity=9\n"));
    CHECK(strstr(output, "slot=0 state=underlying-ram-namespace parent=0 path=\"/\" covered=1\n"));
    CHECK(strstr(output, "slot=1 state=owned-provider parent=0 path=\"/\"\n"));
    CHECK(strstr(output, "slot=2 state=owned-ram parent=1 path=\"/run\"\n"));
    CHECK(strstr(output, "slot=8 state=unused parent=0 path=\"\"\n"));
    reset(); fixture[1].state = OK_MOUNT_STATE_BORROWED;
    fixture[3].state = OK_MOUNT_STATE_DETACHED; fixture[3].parent_id = 1; row_path(3, "/old", 4);
    for (unsigned i = 0; i < 9; ++i) fixture[i].generation = 5;
    CHECK(!run()); CHECK(strstr(output, "state=borrowed-provider")); CHECK(strstr(output, "state=detached-history"));
    reset(); fixture[1].state = OK_MOUNT_STATE_UNUSED; row_path(1, "", 0); fixture[2].parent_id = 0;
    for (unsigned i = 0; i < 9; ++i) fixture[i].generation = 2;
    CHECK(!run()); CHECK(strstr(output, "path=\"/\" covered=0\n"));
    reset();
    for (unsigned i = 0; i < 9; ++i) fixture[i].generation = 17;
    for (unsigned i = 1; i < 9; ++i) {
        char path[] = {'/', 'm', (char)('0' + i)};
        fixture[i].state = OK_MOUNT_STATE_DETACHED; fixture[i].parent_id = 0;
        row_path(i, path, sizeof(path));
    }
    CHECK(!run()); CHECK(strstr(output, "generation=17"));
}

static void retries_and_errors(void)
{
    for (unsigned point = 1; point <= 10; ++point) {
        reset(); busy_call = point;
        CHECK(!run() && calls == point + 10 && !diagnostic_size);
    }
    for (unsigned point = 1; point <= 10; ++point) {
        reset(); mismatch_call = point;
        CHECK(!run() && calls > 10 && calls <= 20 && !diagnostic_size);
    }
    reset(); always_busy = 1; no_output_failure(EBUSY); CHECK(calls == MOUNTCTL_ATTEMPTS);
    reset(); churn = 1; no_output_failure(EBUSY); CHECK(calls == MOUNTCTL_ATTEMPTS * 2);
    for (unsigned point = 1; point <= 10; ++point)
        for (unsigned i = 0; i < 4; ++i) {
            static const int errors[] = {EFAULT, ENOSYS, EIO, EINTR};
            reset(); fail_call = point; failure = errors[i]; no_output_failure(failure); CHECK(calls == point);
        }
    reset(); malformed_final = 1; no_output_failure(EIO); CHECK(calls == 10);
}

static void malformed_rows(void)
{
    for (unsigned variant = 0; variant < 23; ++variant) {
        reset();
        switch (variant) {
        case 0: fixture[2].version = 2; break;
        case 1: fixture[2].size = 287; break;
        case 2: fixture[2].generation = 0; break;
        case 3: fixture[2].generation = 18; break;
        case 4: fixture[2].slot = 3; break;
        case 5: fixture[2].capacity = 8; break;
        case 6: fixture[2].state = 6; break;
        case 7: fixture[2].parent_id = 9; break;
        case 8: fixture[2].path_length = 256; break;
        case 9: fixture[2].path[2] = 0; break;
        case 10: fixture[2].path[255] = 'x'; break;
        case 11: fixture[0].state = OK_MOUNT_STATE_OWNED_RAM; break;
        case 12: fixture[0].parent_id = 1; break;
        case 13: fixture[2].state = OK_MOUNT_STATE_UNDERLYING_RAM; break;
        case 14: fixture[2].parent_id = 2; break;
        case 15: fixture[3].path[0] = 'x'; fixture[3].path_length = 1; break;
        case 16: fixture[2].parent_id = 8; break;
        case 17: row_path(2, "/", 1); break;
        case 18: for (unsigned i = 0; i < 9; ++i) fixture[i].generation = 4; break;
        case 19: fixture[0].path[0] = 'x'; break;
        case 20: fixture[3].parent_id = 1; break;
        case 21: fixture[1].parent_id = 2; break;
        case 22:
            fixture[3].state = OK_MOUNT_STATE_DETACHED; fixture[3].parent_id = 8; row_path(3, "/old", 4);
            for (unsigned i = 0; i < 9; ++i) fixture[i].generation = 5;
            break;
        }
        no_output_failure(EIO);
    }
    static const char *const paths[] = {"", "run", "/run/", "//run", "/./run", "/run/..", "/run//child"};
    for (unsigned i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i) {
        reset(); row_path(2, paths[i], strlen(paths[i])); no_output_failure(EIO);
    }
}

static void escaping_and_output(void)
{
    reset(); static const unsigned char path[] = {'/', 'r', '\\', '"', 0x1b, '\n', 0x7f, 0x80, 0xff};
    row_path(2, path, sizeof(path)); CHECK(!run());
    CHECK(strstr(output, "path=\"/r\\\\\\\"\\x1b\\x0a\\x7f\\x80\\xff\"\n"));
    CHECK(!strchr(output, 0x1b));
    reset(); char long_path[255]; memset(long_path, 'a', sizeof(long_path)); long_path[0] = '/';
    row_path(2, long_path, sizeof(long_path)); CHECK(!run()); CHECK(calls == 10);
    reset(); output_failure = 1; CHECK(run() == 1 && calls == 10);
    reset(); char *arguments[] = {"mountctl", "mount", 0};
    CHECK(mountctl_application_main(2, arguments) == 2 && !calls && !output_size && diagnostic_size);
    reset(); CHECK(mountctl_application_main(1, arguments) == 2 && !calls && !output_size);
}

int main(void)
{
    ordinary_and_states(); retries_and_errors(); malformed_rows(); escaping_and_output();
    puts("mountctl actual-code controls passed; guest=0 mutation=0");
    return 0;
}
