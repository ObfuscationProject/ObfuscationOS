#ifndef OK_NATIVE_CONTROL_H
#define OK_NATIVE_CONTROL_H
#include "native_control_protocol.h"
#include "service_graph.h"

struct nc_client {
    int fd;
    uint32_t uid;
    uint64_t deadline;
    char request[NC_REQUEST_BYTES];
    size_t used, sent;
    struct nc_buffer reply;
};
struct native_control { int listener; struct nc_client clients[NC_CLIENTS]; };

enum nc_children { NC_CHILDREN_UNKNOWN, NC_CHILDREN_LIVE, NC_CHILDREN_EMPTY };
/* Enough for eight serial dependency retirements and one bounded orphan drain.
 * QUIESCE remains service-only; each power action retains this absolute deadline. */
enum { NC_QUIESCE_MS = (SG_CAPACITY + 1) * (PID1_STOP_TERM_MS + PID1_STOP_KILL_MS) };
struct nc_lifecycle {
    enum nc_children children;
    uint64_t started_ms, deadline_ms;
    uint32_t power_token;
    enum nc_operation power_operation;
    unsigned requested : 1;
    unsigned graph_stopped : 1;
    unsigned completed : 1;
    unsigned announced : 1;
    unsigned power_requested : 1;
    unsigned power_committed : 1;
    unsigned failed : 1;
};
/* Only PID1's serialized actor calls this after peer authorization. */
static inline int nc_begin_quiesce(struct service_graph *graph, struct nc_lifecycle *lifecycle, uint64_t now)
{
    if (graph->failed) return -1;
    if (lifecycle->requested) return 0;
    if (graph->stopping || !sg_time_budget(now, NC_QUIESCE_MS)) return -1;
    *lifecycle = (struct nc_lifecycle){.requested = 1, .started_ms = now, .deadline_ms = now + NC_QUIESCE_MS};
    sg_shutdown(graph, now);
    return 0;
}

void nc_reset(struct native_control *control);
int nc_open(struct native_control *control);
int nc_close(struct native_control *control);
/* PREPARE precedes graph mutation. The original token never enters a reply. */
int nc_begin_power(struct service_graph *graph, struct nc_lifecycle *lifecycle,
                   enum nc_operation operation, uint64_t now);
int nc_commit_power(const struct nc_lifecycle *lifecycle);
int nc_step(struct native_control *control, struct service_graph *graph,
            struct nc_lifecycle *lifecycle, uint64_t now);
/* Serialized policy entry, also exercised with hosted syscall seams. */
void nc_dispatch(struct service_graph *graph, struct nc_lifecycle *lifecycle,
                 uint32_t uid, const char *bytes, size_t size,
                 uint64_t now, struct nc_buffer *reply);
#endif
