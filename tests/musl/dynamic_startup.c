#define _GNU_SOURCE
#include <errno.h>
#include <elf.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/auxv.h>
#include <sys/random.h>
#include <unistd.h>

static volatile int initial_value = 37;
static volatile int *volatile relocated_pointer = &initial_value;
extern void _start(void);

static void emit(const char *line)
{
    size_t length = strlen(line);
    if (write(STDOUT_FILENO, line, length) != (ssize_t)length)
        _Exit(90);
}

static int inspect_initial_images(void)
{
    uintptr_t loader_base = getauxval(AT_BASE);
    uintptr_t table_address = getauxval(AT_PHDR);
    uintptr_t main_entry = getauxval(AT_ENTRY);
    size_t header_count = getauxval(AT_PHNUM);
    if (!loader_base || loader_base % 4096 || !table_address ||
        main_entry != (uintptr_t)&_start || header_count == 0 || header_count > 32)
        return 0;
    const Elf64_Ehdr *loader = (const Elf64_Ehdr *)loader_base;
    if (memcmp(loader->e_ident, ELFMAG, SELFMAG) != 0 || loader->e_type != ET_DYN ||
        loader->e_machine != EM_X86_64 || !loader->e_entry || !loader->e_phnum)
        return 0;
    const Elf64_Phdr *headers = (const Elf64_Phdr *)table_address;
    uintptr_t main_base = 0;
    for (size_t i = 0; i < header_count; ++i)
        if (headers[i].p_type == PT_PHDR && table_address >= headers[i].p_vaddr)
            main_base = table_address - headers[i].p_vaddr;
    if (!main_base || main_base % 4096 || main_base == loader_base)
        return 0;
    const Elf64_Ehdr *main_image = (const Elf64_Ehdr *)main_base;
    if (memcmp(main_image->e_ident, ELFMAG, SELFMAG) != 0 || main_image->e_type != ET_DYN ||
        main_image->e_machine != EM_X86_64 || main_image->e_phnum != header_count ||
        main_base + main_image->e_phoff != table_address ||
        main_base + main_image->e_entry != main_entry)
        return 0;
    return 1;
}

int main(int argc, char **argv, char **envp)
{
    if (argc != 1 || !argv || !argv[0] || !envp || *relocated_pointer != 37)
        _Exit(91);
    if (getauxval(AT_BASE) == 0 || getauxval(AT_PHDR) == 0 || getauxval(AT_ENTRY) == 0 ||
        getauxval(AT_PHENT) != 56 || getauxval(AT_PHNUM) == 0 || getauxval(AT_PAGESZ) != 4096)
        _Exit(92);
    if (!inspect_initial_images())
        _Exit(94);
    const unsigned char *startup_random = (const unsigned char *)getauxval(AT_RANDOM);
    unsigned char syscall_random[16];
    if (!startup_random)
    {
        emit("DYNAMIC_ENTROPY missing-at-random\n");
        _Exit(95);
    }
    ssize_t random_count = getrandom(syscall_random, sizeof syscall_random, 0);
    if (random_count != sizeof syscall_random)
    {
        char diagnostic[96];
        int count = snprintf(diagnostic, sizeof diagnostic, "DYNAMIC_ENTROPY getrandom=%ld errno=%d\n",
                             (long)random_count, errno);
        if (count > 0 && (size_t)count < sizeof diagnostic) emit(diagnostic);
        _Exit(95);
    }
    if (memcmp(startup_random, syscall_random, sizeof syscall_random) == 0)
    {
        emit("DYNAMIC_ENTROPY repeated-block\n");
        _Exit(95);
    }
    errno = 0;
    int missing = open("/no-such", O_RDONLY);
    int missing_errno = errno;
    if (missing != -1 || missing_errno != ENOENT)
    {
        char diagnostic[96];
        int count = snprintf(diagnostic, sizeof(diagnostic), "DYNAMIC_OPEN fd=%d errno=%d expected=%d\n",
                             missing, missing_errno, ENOENT);
        if (count > 0 && (size_t)count < sizeof(diagnostic))
            emit(diagnostic);
        _Exit(93);
    }
    emit("OK_SHARED_MUSL_STARTUP interpreter=pass main_entry=pass loader_identity=pass relocation=pass auxv=pass tls_errno=pass entropy=pass\n");
    return 0;
}
