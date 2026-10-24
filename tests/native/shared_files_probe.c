/* Proposed native/static-musl probe. No execution is implied by this source. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <unistd.h>
/* Both variants call the actual selected libc wrappers. The native variant
 * requires the new exported SDK constants and the reviewed okcrt seal argument
 * forwarding change; no raw-syscall bypass hides a missing wrapper. */
#define CREATE_FLAGS (MFD_CLOEXEC | MFD_ALLOW_SEALING)
/* Native bounded-policy refusal and Linux malformed flags have distinct,
 * exact errno contracts; neither variant accepts the other error. */
#ifdef OK_NATIVE_SHARED_FILE_PROBE
#define UNSUPPORTED_CREATE_ERRNO ENOSYS
#else
#define UNSUPPORTED_CREATE_ERRNO EINVAL
#endif
#define ADD_SEALS F_ADD_SEALS
#define GET_SEALS F_GET_SEALS
#define SIZE_SEALS (F_SEAL_GROW | F_SEAL_SHRINK)
#define FINAL_SEAL F_SEAL_SEAL
/* Rejected Linux seal bits are test operands, not added native UAPI promises. */
#define REJECTED_UNKNOWN_SEAL 32U
#define REJECTED_FUTURE_WRITE_SEAL 16U
#define FILE_SLOTS 16
#define FILE_PAGES 64
static int create_file(const char *name, unsigned flags) { return memfd_create(name, flags); }
#define PAGE 4096
static unsigned checks;
static void check(int passed, const char *reason)
{
    ++checks;
    if (passed) return;
    fprintf(stderr, "SHARED_FILES_FAIL reason=%s errno=%d checks=%u\n", reason, errno, checks);
    _Exit(1);
}
static void marker(const char *record)
{
    const size_t count = strlen(record);
    check(write(1, record, count) == (ssize_t)count, "marker-write");
}
static void status(pid_t child)
{
    int value = 0;
    check(waitpid(child, &value, 0) == child && WIFEXITED(value) && WEXITSTATUS(value) == 0, "child-status");
}
static unsigned exhaust_pages(void)
{
    int fds[FILE_SLOTS];
    unsigned opened = 0, pages = 0;
    int exhausted = 0;
    while (opened < FILE_SLOTS && !exhausted) {
        int fd = create_file("English capacity", CREATE_FLAGS);
        check(fd >= 3, "page-capacity-create");
        fds[opened++] = fd;
        unsigned count = FILE_PAGES;
        for (;;) {
            errno = 0;
            if (ftruncate(fd, count * PAGE) == 0) {
                pages += count;
                break;
            }
            check(errno == ENOMEM, "page-capacity-refusal");
            struct stat unchanged;
            check(fstat(fd, &unchanged) == 0 && unchanged.st_size == 0,
                  "page-capacity-rollback");
            if (--count == 0) {
                exhausted = 1;
                break;
            }
        }
    }
    check(exhausted, "page-capacity-reached");
    while (opened) check(close(fds[--opened]) == 0, "page-capacity-close");
    return pages;
}
static void capacities(void)
{
    int files[FILE_SLOTS];
    for (unsigned index = 0; index < FILE_SLOTS; ++index) {
        files[index] = create_file("English file capacity", CREATE_FLAGS);
        check(files[index] >= 3, "file-capacity-create");
    }
    errno = 0;
    check(create_file("English file overflow", CREATE_FLAGS) == -1 && errno == ENFILE,
          "file-capacity-refusal");
    check(close(files[0]) == 0, "file-capacity-free");
    files[0] = create_file("English file reuse", CREATE_FLAGS);
    check(files[0] >= 3, "file-capacity-reuse");
    for (unsigned index = 0; index < FILE_SLOTS; ++index)
        check(close(files[index]) == 0, "file-capacity-close");

    int fd = create_file("English descriptor capacity", CREATE_FLAGS);
    check(fd >= 3, "descriptor-capacity-create");
    int duplicates[32];
    unsigned count = 0;
    for (;;) {
        errno = 0;
        int duplicate = dup(fd);
        if (duplicate == -1) {
            check(errno == EMFILE, "descriptor-capacity-refusal");
            break;
        }
        check(count < sizeof(duplicates) / sizeof(duplicates[0]), "descriptor-capacity-bound");
        duplicates[count++] = duplicate;
    }
    check(count != 0, "descriptor-capacity-progress");
    while (count) check(close(duplicates[--count]) == 0, "descriptor-capacity-close");
    check(close(fd) == 0, "descriptor-capacity-provider-close");

    const unsigned first = exhaust_pages();
    const unsigned second = exhaust_pages();
    check(first == second && first != 0, "page-capacity-repeat-accounting");
    /* Equal capacity is an independent negative boundary, not an exact owner
     * ledger. The run recipe must also bind the final five zero ledger fields. */
}
int main(void)
{
    marker("SHARED_FILES_EVENT phase=begin name=English-buffer\n");
    errno = 0;
    check(create_file("missing sealing", 0) == -1 && errno == ENOSYS, "bounded-sealing-policy");
    errno = 0;
    check(create_file("unsupported flags", CREATE_FLAGS | 4U) == -1 && errno == UNSUPPORTED_CREATE_ERRNO,
          "unsupported-create-flags");
    int fd = create_file("English shared notes", CREATE_FLAGS);
    check(fd >= 3, "create");
    check(fcntl(fd, F_GETFD) == FD_CLOEXEC && fcntl(fd, GET_SEALS) == 0, "creation-flags");
    struct stat before;
    check(fstat(fd, &before) == 0 && S_ISREG(before.st_mode) && before.st_size == 0, "empty-stat");
    check(ftruncate(fd, 2 * PAGE) == 0, "initialize-size");
    errno = 0;
    check(mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0) == MAP_FAILED && errno == ENOSYS,
          "unsealed-map-refusal");
    errno = 0;
    check(fcntl(fd, ADD_SEALS, F_SEAL_GROW | REJECTED_UNKNOWN_SEAL) == -1 && errno == ENOSYS &&
          fcntl(fd, GET_SEALS) == 0, "mixed-seal-rollback");
    errno = 0;
    check(fcntl(fd, ADD_SEALS, F_SEAL_SHRINK | REJECTED_FUTURE_WRITE_SEAL) == -1 && errno == ENOSYS &&
          fcntl(fd, GET_SEALS) == 0, "future-write-seal-rollback");
    check(fcntl(fd, ADD_SEALS, F_SEAL_GROW) == 0 && fcntl(fd, GET_SEALS) == F_SEAL_GROW,
          "additive-grow-seal");
    errno = 0;
    check(mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0) == MAP_FAILED && errno == ENOSYS,
          "one-size-seal-map-refusal");
    check(fcntl(fd, ADD_SEALS, F_SEAL_SHRINK) == 0 && fcntl(fd, GET_SEALS) == SIZE_SEALS,
          "additive-shrink-seal");
    check(ftruncate(fd, 2 * PAGE) == 0, "same-size-truncate");
    struct stat sized;
    check(fstat(fd, &sized) == 0 && sized.st_size == 2 * PAGE && sized.st_ino == before.st_ino, "stable-stat");
    unsigned char *first = mmap(0, 2 * PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    unsigned char *second = mmap(0, 2 * PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    check(first != MAP_FAILED && second != MAP_FAILED && first != second, "two-distinct-user-aliases");
    first[0] = 'A'; second[PAGE] = 'B';
    check(second[0] == 'A' && first[PAGE] == 'B', "two-page-alias-coherence");
    char output[16] = {0};
    check(pread(fd, output, 1, 0) == 1 && output[0] == 'A', "alias-to-pread");
    check(pwrite(fd, "cross", 5, PAGE - 2) == 5, "cross-page-pwrite");
    check(first[PAGE - 2] == 'c' && second[PAGE] == 'o' && second[PAGE + 2] == 's', "pwrite-to-alias");
    check(lseek(fd, 0, SEEK_CUR) == 0, "positioned-io-preserves-offset");
    unsigned char *offset_alias = mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, PAGE);
    check(offset_alias != MAP_FAILED && offset_alias != first && offset_alias != second,
          "nonzero-file-offset-alias");
    offset_alias[33] = 'O';
    check(first[PAGE + 33] == 'O' && second[PAGE + 33] == 'O', "offset-alias-coherence");
    check(munmap(offset_alias, PAGE) == 0, "offset-alias-unmap");
    const int duplicate = dup(fd);
    check(duplicate >= 3 && fcntl(duplicate, F_GETFD) == 0, "dup");
    check(lseek(fd, 64, SEEK_SET) == 64 && write(duplicate, "English", 7) == 7, "shared-offset-write");
    check(lseek(fd, 0, SEEK_CUR) == 71 && memcmp(first + 64, "English", 7) == 0, "shared-offset-observed");
    struct iovec input[2] = {{(void *)"Notes", 5}, {(void *)"Files", 5}};
    check(lseek(fd, PAGE - 3, SEEK_SET) == PAGE - 3 && writev(fd, input, 2) == 10, "cross-page-vectored-write");
    check(memcmp(first + PAGE - 3, "NotesFiles", 10) == 0 &&
          memcmp(second + PAGE - 3, "NotesFiles", 10) == 0, "vector-to-both-aliases");
    memcpy(first + PAGE - 3, "Saved", 5);
    memcpy(second + PAGE + 2, "Again", 5);
    struct iovec vectors[2] = {{output, 5}, {output + 5, 5}};
    check(lseek(duplicate, PAGE - 3, SEEK_SET) == PAGE - 3 && readv(duplicate, vectors, 2) == 10 &&
          memcmp(output, "SavedAgain", 10) == 0, "both-aliases-to-cross-page-vector");
    check(lseek(fd, 0, SEEK_CUR) == PAGE + 7, "vector-shared-offset");
    struct iovec bad_write[2] = {{(void *)"Bad", 3}, {0, 1}};
    check(lseek(fd, PAGE - 3, SEEK_SET) == PAGE - 3, "malformed-vector-offset-setup");
    errno = 0;
    check(writev(fd, bad_write, 2) == -1 && errno == EFAULT &&
          lseek(duplicate, 0, SEEK_CUR) == PAGE - 3 &&
          memcmp(first + PAGE - 3, "SavedAgain", 10) == 0 &&
          memcmp(second + PAGE - 3, "SavedAgain", 10) == 0, "later-write-vector-rollback");
    memset(output, 'U', sizeof(output));
    struct iovec bad_read[2] = {{output, 3}, {0, 1}};
    errno = 0;
    check(readv(duplicate, bad_read, 2) == -1 && errno == EFAULT &&
          lseek(fd, 0, SEEK_CUR) == PAGE - 3 && output[0] == 'U' && output[2] == 'U',
          "later-read-vector-preflight");
    struct iovec empty_vector[2] = {{0, 0}, {0, 0}};
    check(writev(fd, empty_vector, 2) == 0 && readv(fd, empty_vector, 2) == 0 &&
          lseek(fd, 0, SEEK_CUR) == PAGE - 3, "zero-vector-offset-preserved");
    check(read(fd, 0, 0) == 0 && write(fd, 0, 0) == 0, "empty-io");
    errno = 0;
    check(mmap(0, PAGE, PROT_READ, MAP_PRIVATE, fd, 0) == MAP_FAILED && errno == ENOSYS, "private-map-refusal");
    errno = 0;
    check(mmap(0, PAGE, PROT_READ, MAP_SHARED, fd, 2 * PAGE) == MAP_FAILED && errno == ENOSYS, "beyond-eof-map");
    errno = 0;
    check(mmap(0, PAGE + 1, PROT_READ, MAP_SHARED, fd, 0) == MAP_FAILED && errno == ENOSYS, "partial-page-map");
    errno = 0;
    check(mmap(0, PAGE, PROT_READ, MAP_SHARED, fd, 1) == MAP_FAILED && errno == EINVAL,
          "unaligned-file-offset");
    errno = 0;
    check(fsync(fd) == -1 && errno == ENOSYS, "volatile-fsync-refusal");
    errno = 0;
    check(mprotect(first, PAGE, PROT_READ | PROT_EXEC) == -1 && errno == EINVAL, "execute-protection-refusal");
    check(mprotect(first, PAGE, PROT_NONE) == 0 && pwrite(fd, "N", 1, 0) == 1 && second[0] == 'N', "none-keeps-canonical-frame");
    check(mprotect(first, PAGE, PROT_READ | PROT_WRITE) == 0 && first[0] == 'N', "protection-restored");
    const pid_t child = fork(); check(child >= 0, "fork");
    if (!child) {
        first[PAGE + 32] = 'C';
        check(second[PAGE + 32] == 'C', "child-alias");
        check(close(fd) == 0 && close(duplicate) == 0, "child-close");
        check(munmap(first, 2 * PAGE) == 0 && munmap(second, 2 * PAGE) == 0, "child-unmap");
        _Exit(0);
    }
    status(child);
    check(first[PAGE + 32] == 'C' && second[PAGE + 32] == 'C', "fork-shared-observed");
    check(pread(duplicate, output, 1, PAGE + 32) == 1 && output[0] == 'C', "child-alias-to-parent-file");
    check(fcntl(fd, ADD_SEALS, FINAL_SEAL) == 0 &&
          fcntl(fd, GET_SEALS) == (SIZE_SEALS | FINAL_SEAL), "seal-final");
    errno = 0;
    check(fcntl(fd, ADD_SEALS, 0) == -1 && errno == EPERM &&
          fcntl(fd, GET_SEALS) == (SIZE_SEALS | FINAL_SEAL), "final-seal-mutation-refusal");
    errno = 0;
    check(ftruncate(fd, PAGE) == -1 && errno == EPERM, "sealed-shrink");
    errno = 0;
    check(ftruncate(fd, 3 * PAGE) == -1 && errno == EPERM, "sealed-grow");
    errno = 0;
    check(pwrite(fd, "x", 1, 2 * PAGE) == -1 && errno == EPERM, "sealed-eof-write");
    check(pwrite(fd, "tail", 4, 2 * PAGE - 1) == 1, "bounded-eof-short-write");
    check(pread(fd, output, sizeof(output), 2 * PAGE) == 0, "eof-read");
    int other_fd = create_file("English replacement", CREATE_FLAGS);
    check(other_fd >= 3 && ftruncate(other_fd, PAGE) == 0 &&
          fcntl(other_fd, ADD_SEALS, SIZE_SEALS) == 0, "replacement-file-setup");
    unsigned char *other = mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, other_fd, 0);
    check(other != MAP_FAILED, "replacement-file-alias");
    other[0] = 'R';
    void *file_replacement = mmap(first, PAGE, PROT_READ | PROT_WRITE,
                                  MAP_SHARED | MAP_FIXED, other_fd, 0);
    check(file_replacement == first && first[0] == 'R' && second[0] == 'N' &&
          first[PAGE + 32] == 'C', "file-to-file-fixed-replacement");
    first[0] = 'T';
    check(other[0] == 'T' && second[0] == 'N', "replacement-provider-distinct");
    check(close(other_fd) == 0 && munmap(other, PAGE) == 0, "replacement-provider-survives-descriptor");
    check(close(fd) == 0 && close(duplicate) == 0, "final-descriptor-close");
    second[0] = 'L'; check(first[0] == 'T', "mapped-survives-distinct-providers");
    check(munmap(first, PAGE) == 0, "partial-first-alias-unmap");
    check(first[PAGE + 32] == 'C' && second[PAGE + 32] == 'C', "partial-unmap-keeps-other-file-page");
    check(munmap(first + PAGE, PAGE) == 0, "remaining-first-alias-unmap");
    check(second[0] == 'L' && second[PAGE + 32] == 'C', "remaining-alias-survives");
    void *replacement = mmap(second, PAGE, PROT_READ | PROT_WRITE,
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    check(replacement == second && second[0] == 0 && second[PAGE + 32] == 'C', "fixed-replacement-preserves-other-page");
    check(munmap(second, 2 * PAGE) == 0, "last-alias-unmap");
    /* More than the sixteen file slots and sixteen pool-page allocation cycles
     * must remain usable after all descriptor/alias references have retired. */
    for (unsigned attempt = 0; attempt < 40; ++attempt) {
        fd = create_file("English reuse", CREATE_FLAGS);
        check(fd >= 3 && ftruncate(fd, PAGE) == 0 && fcntl(fd, ADD_SEALS, SIZE_SEALS) == 0, "reclamation-create");
        unsigned char *alias = mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        check(alias != MAP_FAILED && alias[0] == 0, "reclamation-map");
        check(close(fd) == 0, "reclamation-close");
        alias[0] = (unsigned char)attempt;
        check(munmap(alias, PAGE) == 0, "reclamation-unmap");
    }
    capacities();
#ifdef OK_NATIVE_SHARED_FILE_PROBE
    marker("OK_NATIVE_SHARED_FILES acceptance=pass version=3 actual_native_alias=1 guest=1 physical_machine=0 english=1 distinct_vas=1 canonical_io=1 vectors=1 vector_rollback=1 additive_seals=1 final_seals=1 dup=1 fork=1 prot_none=1 offset_alias=1 partial_unmap=1 map_fixed=1 file_replacement=1 file_capacity=1 descriptor_capacity=1 page_capacity=1 reclamation=40\n");
#else
    marker("OK_MUSL_SHARED_FILES acceptance=pass version=3 actual_native_alias=1 guest=1 physical_machine=0 english=1 distinct_vas=1 canonical_io=1 vectors=1 vector_rollback=1 additive_seals=1 final_seals=1 dup=1 fork=1 prot_none=1 offset_alias=1 partial_unmap=1 map_fixed=1 file_replacement=1 file_capacity=1 descriptor_capacity=1 page_capacity=1 reclamation=40\n");
#endif
    return 0;
}
