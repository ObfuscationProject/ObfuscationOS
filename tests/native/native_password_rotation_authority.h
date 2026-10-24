#ifndef OK_NATIVE_PASSWORD_ROTATION_AUTHORITY_H
#define OK_NATIVE_PASSWORD_ROTATION_AUTHORITY_H

#include <sys/stat.h>

/* Qualification only. Reuse the retained inherited-reader fixture mechanisms;
 * its original entry and archive-only test remain unchanged. */
#define main native_rotation_lease_reference_main
#include "native_console_lease_probe.c"
#undef main

static int rotation_wait(unsigned complete)
{
    for (unsigned ticks = 0; ticks != 3000; ++ticks) {
        int all = 1;
        for (unsigned role = 0; role != 3; ++role) {
            char path[40];
            if (old_path(path, role, (int)complete)) return -1;
            int present = exists(path);
            if (present < 0) return -1;
            all &= present;
        }
        if (all) return 0;
        pause_ms(10);
    }
    return -1;
}

static int rotation_record(const char *event, uint32_t epoch)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_ROTATION_"); nf_text(&record, event);
    nf_text(&record, " pid="); nf_number(&record, (unsigned)getpid());
    nf_text(&record, " parent="); nf_number(&record, (unsigned)getppid());
    nf_text(&record, " epoch="); nf_number(&record, epoch); nf_text(&record, "\n");
    return nf_emit(&record);
}

#endif
