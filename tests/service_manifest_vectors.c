#include "../apps/init/service_manifest.h"
#include <stdio.h>

int main(void)
{
    char bytes[SM_BYTE_LIMIT + 1];
    size_t size = fread(bytes, 1, sizeof(bytes), stdin);
    struct service_manifest manifest;
    if (ferror(stdin) || sm_parse(&manifest, bytes, size)) return 1;
    for (unsigned i = 0; i < manifest.count; ++i) {
        const struct sm_record *record = &manifest.records[i];
        printf("%s %u %u %s %u %u\n", record->name, record->mode, record->dependencies,
               record->executable, (unsigned)record->uid, (unsigned)record->gid);
    }
    return 0;
}
