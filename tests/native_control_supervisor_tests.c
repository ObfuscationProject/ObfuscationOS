#define _GNU_SOURCE
#include <stdint.h>
struct native_control;
struct service_graph;
struct nc_lifecycle;
static void actor_control_reset(struct native_control *control);
static int actor_control_open(struct native_control *control);
static int actor_control_close(struct native_control *control);
static int actor_control_commit(const struct nc_lifecycle *lifecycle);
static int actor_control_step(struct native_control *control, struct service_graph *graph,
                              struct nc_lifecycle *lifecycle, uint64_t now);
#define OK_NATIVE_INIT_CONTROL 1
#define nc_reset actor_control_reset
#define nc_open actor_control_open
#define nc_close actor_control_close
#define nc_step actor_control_step
#define nc_commit_power actor_control_commit
#define main previous_actor_controls
#include "native_supervisor_tests.c"
#undef main
#undef nc_reset
#undef nc_open
#undef nc_close
#undef nc_step
#undef nc_commit_power

/* The transport has its own real-source fault suite. These actor seams verify
 * ordering and failure containment with the feature compiled into PID1. */
static unsigned control_steps, control_closes, control_commits;
static int control_restart, control_failure, control_quiesce, control_halt;
static int control_close_error, control_commit_error;
static unsigned control_close_advance_ms;
static uint32_t committed_token;
static enum nc_operation control_power_operation = NC_HALT, committed_operation;
static struct ns_runtime *commit_runtime;
static void actor_control_reset(struct native_control *control)
{
    *control = (struct native_control){.listener = -1};
    for (unsigned i = 0; i < NC_CLIENTS; ++i) control->clients[i].fd = -1;
}
static int actor_control_open(struct native_control *control) { control->listener = 30; return 0; }
static int actor_control_close(struct native_control *control)
{
    ++control_closes; actor_control_reset(control);
    time_ms((unsigned)((uint64_t)clock_value.tv_sec * 1000 + (uint64_t)clock_value.tv_nsec / 1000000 + control_close_advance_ms));
    if (control_close_error) { errno = control_close_error; return -1; }
    return 0;
}
static int actor_control_commit(const struct nc_lifecycle *lifecycle)
{
    ++control_commits;
    assert(lifecycle->power_requested && lifecycle->completed && !lifecycle->failed &&
        lifecycle->children == NC_CHILDREN_EMPTY && lifecycle->power_token &&
        (lifecycle->power_operation == NC_HALT || lifecycle->power_operation == NC_REBOOT ||
         lifecycle->power_operation == NC_POWEROFF));
    committed_token = lifecycle->power_token;
    committed_operation = lifecycle->power_operation;
    if (commit_runtime) {
        assert(commit_runtime->control.listener < 0);
        for (unsigned i = 0; i < NC_CLIENTS; ++i) assert(commit_runtime->control.clients[i].fd < 0);
        for (unsigned i = 0; i < SG_CAPACITY; ++i)
            assert(commit_runtime->channels[i].exec_fd < 0 && commit_runtime->channels[i].ready_fd < 0);
    }
    if (control_commit_error) { errno = control_commit_error; return -1; }
    return 0;
}
static int actor_control_step(struct native_control *control, struct service_graph *graph,
                              struct nc_lifecycle *lifecycle, uint64_t now)
{
    if (control->listener < 0) return 0;
    ++control_steps;
    if (control_failure) { errno = EIO; return -1; }
    if (control_halt) {
        control_halt = 0;
        assert(!nc_begin_quiesce(graph, lifecycle, now));
        lifecycle->power_requested = 1;
        lifecycle->power_operation = control_power_operation;
        lifecycle->power_token = 0x2abc1234u;
    }
    if (control_quiesce) {
        control_quiesce = 0;
        assert(!nc_begin_quiesce(graph, lifecycle, now));
    }
    if (control_restart) {
        control_restart = 0;
        assert(graph->services[1].phase == SG_READY && graph->services[2].phase == SG_READY);
        sg_retire(&graph->services[1], SG_CRASH, now); sg_settle(graph, now);
    }
    return 0;
}
#ifndef NATIVE_CONTROL_ACTOR_TEST_ENTRY
#define NATIVE_CONTROL_ACTOR_TEST_ENTRY main
#endif
int NATIVE_CONTROL_ACTOR_TEST_ENTRY(void)
{
    assert(!previous_actor_controls());
    struct ns_runtime runtime = live_graph(); actor_control_open(&runtime.control);
    control_steps = control_closes = 0; control_restart = 1;
    assert(!ns_step(&runtime) && control_steps == 1);
    assert(runtime.graph.services[1].phase == SG_RETIRING && runtime.graph.services[2].phase == SG_RETIRING);
    assert(signals == 1 && signal_calls[0].pid == 11 && signal_calls[0].number == SIGTERM);
    reap(11, SIGTERM); assert(!ns_step(&runtime));
    assert(signals == 2 && signal_calls[1].pid == 10 && signal_calls[1].number == SIGTERM);
    runtime = live_graph(); actor_control_open(&runtime.control); control_failure = 1;
    assert(!ns_step(&runtime) && control_closes == 1 && runtime.control.listener == -1);
    assert(strstr(events, "event=control-disabled") && runtime.graph.services[1].phase == SG_READY);
    control_failure = 0; unsigned before = control_steps;
    assert(!ns_step(&runtime) && control_steps == before && control_closes == 1);
    puts("native control PID1 actor ordering and failure containment controls passed"); return 0;
}
