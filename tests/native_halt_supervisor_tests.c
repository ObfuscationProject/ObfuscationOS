#define NATIVE_CONTROL_ACTOR_TEST_ENTRY previous_halt_actor_controls
#include "native_control_supervisor_tests.c"

static void power_actor(struct ns_runtime *runtime)
{
    control_restart = control_failure = control_quiesce = control_halt = 0;
    control_close_error = control_commit_error = 0;
    control_steps = control_closes = control_commits = control_close_advance_ms = 0;
    committed_token = 0; committed_operation = NC_INVALID; commit_runtime = 0;
    *runtime = live_graph(); actor_control_open(&runtime->control);
    event_size = 0; events[0] = 0; commit_runtime = runtime;
    control_halt = 1;
    assert(!ns_step(runtime) && runtime->lifecycle.power_requested && !runtime->lifecycle.completed);
    assert(runtime->lifecycle.started_ms == 1000 && runtime->lifecycle.deadline_ms == 19000);
    assert(runtime->lifecycle.power_token == 0x2abc1234 && !control_commits);
    assert(runtime->lifecycle.power_operation == control_power_operation);
    assert(signals == 1 && signal_calls[0].pid == 11 && signal_calls[0].number == SIGTERM);
}

static void stop_services(struct ns_runtime *runtime)
{
    reap(11, SIGTERM); assert(!ns_step(runtime));
    assert(signals == 2 && signal_calls[1].pid == 10 && signal_calls[1].number == SIGTERM);
    reap(10, SIGTERM); assert(!ns_step(runtime));
    assert(sg_stopped(&runtime->graph) && runtime->lifecycle.graph_stopped && !runtime->lifecycle.completed);
    assert(runtime->lifecycle.children == NC_CHILDREN_LIVE && !control_commits);
    assert(runtime->lifecycle.started_ms == 1000 && runtime->lifecycle.deadline_ms == 19000);
    assert(!strstr(events, "event=restart ") && !strstr(events, "event=launch "));
}

static void assert_terminal(struct ns_runtime *runtime, int error)
{
    assert(runtime->terminal_error == error && runtime->lifecycle.failed && !runtime->lifecycle.power_committed);
    assert(runtime->lifecycle.started_ms == 1000 && runtime->lifecycle.deadline_ms == 19000);
    struct service_graph stopped = runtime->graph; struct nc_lifecycle failed = runtime->lifecycle;
    unsigned old_waits = waits, old_reads = reads, old_steps = control_steps, old_forks = forks;
    unsigned old_closes = closes, old_control_closes = control_closes, old_commits = control_commits;
    close_error = clock_error = read_error = write_error = wait_repeated_error = control_failure = 0;
    control_commit_error = control_close_error = 0; time_ms(1001);
    assert(ns_step(runtime) < 0 && errno == error);
    assert(waits == old_waits && reads == old_reads && control_steps == old_steps && forks == old_forks &&
        closes == old_closes && control_closes == old_control_closes && control_commits == old_commits);
    assert(!memcmp(&runtime->graph, &stopped, sizeof(stopped)) &&
        !memcmp(&runtime->lifecycle, &failed, sizeof(failed)));
}

static void fresh_echild_then_closed_descriptors_then_exact_commit(void)
{
    struct ns_runtime runtime; power_actor(&runtime); stop_services(&runtime);
    unsigned old_forks = forks, old_waits = waits;
    runtime.lifecycle.children = NC_CHILDREN_EMPTY;
    assert(!ns_step(&runtime) && waits > old_waits && !control_commits && !runtime.lifecycle.completed);
    assert(runtime.lifecycle.children == NC_CHILDREN_LIVE);
    reap(42, 0); assert(!ns_step(&runtime) && runtime.graph.other_exits == 1 && !control_commits);
    /* Include a descriptor outside the active graph to exercise the entire
     * original channel ownership array at the final boundary. */
    runtime.channels[SG_CAPACITY - 1].exec_fd = 40;
    runtime.channels[SG_CAPACITY - 1].ready_fd = 41;
    runtime.control.clients[0].fd = 31;
    wait_empty = 1; old_waits = waits;
    assert(ns_step(&runtime) == 1 && runtime.lifecycle.power_committed && runtime.lifecycle.completed);
    assert(waits >= old_waits + 3 && control_commits == 1 && control_closes == 1);
    assert(committed_token == 0x2abc1234 && runtime.control.listener < 0 && forks == old_forks);
    assert(committed_operation == control_power_operation);
    assert(runtime.lifecycle.started_ms == 1000 && runtime.lifecycle.deadline_ms == 19000);
    assert(!strstr(events, "event=launch ") && !strstr(events, "event=restart "));
    old_waits = waits; unsigned old_steps = control_steps, old_reads = reads;
    unsigned old_closes = closes, old_control_closes = control_closes, old_signals = signals;
    unsigned old_event_writes = event_write_calls;
    struct service_graph stopped = runtime.graph; struct nc_lifecycle queued = runtime.lifecycle;
    /* Hosted COMMIT success acknowledges queuing. A later actor step must
     * preserve that boundary without reopening admission or retrying COMMIT. */
    control_halt = 1; control_failure = 1; clock_error = EIO;
    time_ms(30000); assert(ns_step(&runtime) == 1);
    assert(waits == old_waits && control_steps == old_steps && reads == old_reads && control_commits == 1);
    assert(closes == old_closes && control_closes == old_control_closes && signals == old_signals &&
        event_write_calls == old_event_writes && forks == old_forks);
    assert(!memcmp(&runtime.graph, &stopped, sizeof(stopped)) &&
        !memcmp(&runtime.lifecycle, &queued, sizeof(queued)));
}

static void terminal_failures_do_not_retry_commit_or_resume_services(void)
{
    struct ns_runtime runtime;
    power_actor(&runtime); stop_services(&runtime); wait_empty = 1;
    runtime.channels[SG_CAPACITY - 1].exec_fd = 40; close_error = EIO;
    assert(ns_step(&runtime) < 0 && errno == EIO && !control_commits);
    assert_terminal(&runtime, EIO);
    power_actor(&runtime); stop_services(&runtime); wait_empty = 1; control_close_error = EIO;
    assert(ns_step(&runtime) < 0 && errno == EIO && control_closes == 1 && !control_commits);
    assert_terminal(&runtime, EIO);
    power_actor(&runtime); stop_services(&runtime); wait_empty = 1; control_commit_error = EBUSY;
    assert(ns_step(&runtime) < 0 && errno == EBUSY && control_commits == 1 && control_closes == 1);
    assert_terminal(&runtime, EBUSY);
    power_actor(&runtime); control_failure = 1;
    assert(ns_step(&runtime) < 0 && errno == EIO && !control_commits);
    assert_terminal(&runtime, EIO);
    power_actor(&runtime); wait_repeated_error = EIO;
    assert(ns_step(&runtime) < 0 && !control_commits); assert_terminal(&runtime, EIO);
    power_actor(&runtime); clock_error = EIO;
    assert(ns_step(&runtime) < 0 && !control_commits); assert_terminal(&runtime, EIO);
}

static void one_deadline_includes_echild_closure_and_commit(void)
{
    struct ns_runtime runtime;
    power_actor(&runtime); stop_services(&runtime); wait_empty = 1;
    time_ms(19000); assert(ns_step(&runtime) < 0 && errno == EIO && !control_commits);
    assert_terminal(&runtime, EIO);
    power_actor(&runtime); stop_services(&runtime); wait_empty = 1;
    time_ms(18999); wait_advance_ms = 1;
    assert(ns_step(&runtime) < 0 && errno == EIO && !control_commits); assert_terminal(&runtime, EIO);
    power_actor(&runtime); stop_services(&runtime); wait_empty = 1;
    runtime.channels[SG_CAPACITY - 1].exec_fd = 40; close_advance_ms = 18000;
    assert(ns_step(&runtime) < 0 && errno == EIO && !control_commits); assert_terminal(&runtime, EIO);
    power_actor(&runtime); stop_services(&runtime); wait_empty = 1; control_close_advance_ms = 18000;
    assert(ns_step(&runtime) < 0 && errno == EIO && control_closes == 1 && !control_commits);
    assert_terminal(&runtime, EIO);
    power_actor(&runtime); wait_repeated_error = EINTR; wait_advance_ms = 1000;
    unsigned before = waits;
    assert(ns_step(&runtime) < 0 && errno == EIO && waits - before <= NC_QUIESCE_MS / 1000 + 1);
    assert(!control_commits); assert_terminal(&runtime, EIO);
}

int main(void)
{
    assert(!previous_halt_actor_controls());
    const enum nc_operation operations[] = {NC_HALT, NC_REBOOT, NC_POWEROFF};
    for (unsigned i = 0; i < sizeof(operations) / sizeof(operations[0]); ++i) {
        control_power_operation = operations[i];
        fresh_echild_then_closed_descriptors_then_exact_commit();
        terminal_failures_do_not_retry_commit_or_resume_services();
        one_deadline_includes_echild_closure_and_commit();
    }
    puts("native halt/reboot/poweroff hosted dependency drain, fresh ECHILD, checked close, immutable deadline and terminal hold controls passed");
    return 0;
}
