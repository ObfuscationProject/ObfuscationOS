#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include "native_fixture_record.h"

static int brief(void)
{
    const struct timespec pause = {0, 10000000};
    int result;
    do { result = nanosleep(&pause, 0); } while (result < 0 && errno == EINTR);
    return result;
}

static int parent_record(pid_t parent, pid_t live, pid_t zombie)
{
    struct native_fixture_record record = {0};
    nf_text(&record, "\nNATIVE_ADOPTION_PARENT pid="); nf_number(&record, (unsigned)parent);
    nf_text(&record, " live="); nf_number(&record, (unsigned)live);
    nf_text(&record, " zombie="); nf_number(&record, (unsigned)zombie);
    nf_text(&record, "\n");
    return nf_emit(&record);
}

int main(void)
{
    const pid_t original_parent = getpid();
    if (getppid() != 1) return 81;
    int ready[2];
    if (pipe(ready)) return 82;
    const pid_t live = fork();
    if (live < 0) return 83;
    if (!live) {
        if (close(ready[0]) || close(ready[1])) _Exit(84);
        for (unsigned i = 0; i < 500; ++i) {
            const pid_t parent = getppid();
            if (parent == 1) {
                struct native_fixture_record record = {0};
                nf_text(&record, "\nNATIVE_ADOPTION_CHILD pid="); nf_number(&record, (unsigned)getpid());
                nf_text(&record, " old_parent="); nf_number(&record, (unsigned)original_parent);
                nf_text(&record, " new_parent=1 exit=23\n");
                _Exit(nf_emit(&record) ? 85 : 23);
            }
            if (parent != original_parent || brief()) break;
        }
        (void)nf_marker("\nNATIVE_ADOPTION_FAIL live_parent\n");
        _Exit(86);
    }
    const pid_t zombie = fork();
    if (zombie < 0) return 87;
    if (!zombie) {
        if (close(ready[0]) || write(ready[1], "Z", 1) != 1) _Exit(88);
        /* Keep the only writer until exit cleanup publishes EOF. */
        _Exit(31);
    }
    if (close(ready[1])) return 89;
    char message;
    if (read(ready[0], &message, 1) != 1 || message != 'Z') return 90;
    /* Serialized exit retires the writer before this parent resumes at EOF. */
    if (read(ready[0], &message, 1) != 0 || close(ready[0])) return 91;
    if (parent_record(original_parent, live, zombie)) return 92;
    return 0;
}
