#ifndef LINUX_STAT_FIXTURE_H
#define LINUX_STAT_FIXTURE_H

/* Test-only fixture contract. These paths must be absent on a fresh image. */
#define STAT_FILE "/home/stat-file"
#define STAT_ALIAS "/home/stat-alias"
#define STAT_LINK "/home/stat-link"
#define STAT_DANGLING "/home/stat-dangling"
#define STAT_LOOP "/home/stat-loop"
#define STAT_MISSING "/home/stat-missing"
#define STAT_HELD_PATH "/home/stat-held"
#define STAT_DIR_OLD "/home/stat-dir"
#define STAT_DIR "/home/stat-renamed-dir"
#define STAT_CWD "/home/stat-cwd"
#define STAT_EMPTY "/home/stat-empty"
#define STAT_HOLE "/home/stat-hole"
#define STAT_PROBE "/bin/musl-linux-stat"
#define STAT_CONTENT "linux-stat-fixture"
#define STAT_CONTENT_SIZE (sizeof(STAT_CONTENT) - 1)
#define STAT_HELD_FD 10
#define STAT_DIR_FD 11
#define STAT_PAGE_SIZE 4096
#define STAT_HOLE_SIZE 12305
#define STAT_EMPTY_PATH 0x1000
#define STAT_NO_AUTOMOUNT 0x800
#define STAT_FORCE_SYNC 0x2000
#define STAT_DONT_SYNC 0x4000
#define STAT_BASIC_MASK 0x7ffU

#endif
