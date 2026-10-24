#ifndef LINUX_CHMOD_FIXTURE_H
#define LINUX_CHMOD_FIXTURE_H

/* Test-only fixture contract. These paths must be absent on a fresh image. */
#define CHMOD_FILE "/home/chmod-file"
#define CHMOD_ALIAS "/home/chmod-alias"
#define CHMOD_LINK "/home/chmod-link"
#define CHMOD_DANGLING "/home/chmod-dangling"
#define CHMOD_LOOP "/home/chmod-loop"
#define CHMOD_MISSING "/home/chmod-missing"
#define CHMOD_HELD_PATH "/home/chmod-held"
#define CHMOD_DIR_OLD "/home/chmod-dir"
#define CHMOD_DIR "/home/chmod-renamed-dir"
#define CHMOD_CWD "/home/chmod-cwd"
#define CHMOD_EMPTY "/home/chmod-empty"
#define CHMOD_HOLE "/home/chmod-hole"
#define CHMOD_PROBE "/bin/musl-linux-chmod"
#define CHMOD_CONTENT "linux-chmod-fixture"
#define CHMOD_CONTENT_SIZE (sizeof(CHMOD_CONTENT) - 1)
#define CHMOD_HELD_FD 10
#define CHMOD_DIR_FD 11
#define CHMOD_PAGE_SIZE 4096
#define CHMOD_HOLE_SIZE 12305
#define CHMOD_EMPTY_PATH 0x1000
#define CHMOD_NO_AUTOMOUNT 0x800
#define CHMOD_FORCE_SYNC 0x2000
#define CHMOD_DONT_SYNC 0x4000
#define CHMOD_BASIC_MASK 0x7ffU

#endif
