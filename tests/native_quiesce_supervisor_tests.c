#define NATIVE_CONTROL_ACTOR_TEST_ENTRY previous_quiesce_actor_controls
#include "native_control_supervisor_tests.c"

static unsigned event_count(const char *event)
{
    unsigned count = 0; const char *at = events;
    while ((at = strstr(at, event))) { ++count; at += strlen(event); }
    return count;
}

static struct ns_runtime quiesce_actor(void)
{
    control_restart = control_failure = control_quiesce = 0;
    control_steps = control_closes = 0;
    struct ns_runtime runtime = live_graph(); actor_control_open(&runtime.control);
    event_size = 0; events[0] = 0;
    return runtime;
}

static void begin_quiesce(struct ns_runtime *runtime)
{
    runtime->lifecycle.children = NC_CHILDREN_EMPTY;
    control_quiesce = 1;
    assert(!ns_step(runtime) && runtime->lifecycle.requested && !runtime->lifecycle.completed);
    assert(runtime->lifecycle.children == NC_CHILDREN_UNKNOWN);
    assert(runtime->lifecycle.started_ms == 1000 && runtime->lifecycle.deadline_ms == 1000 + NC_QUIESCE_MS);
    assert(runtime->graph.stopping && signals == 1 && signal_calls[0].pid == 11 && signal_calls[0].number == SIGTERM);
    assert(event_count("event=quiesce-started ") == 1 && !strstr(events, "event=launch "));
}

static void stop_graph_with_live_child(struct ns_runtime *runtime)
{
    reap(11, SIGTERM); assert(!ns_step(runtime));
    assert(signals == 2 && signal_calls[1].pid == 10 && signal_calls[1].number == SIGTERM);
    reap(10, SIGTERM); assert(!ns_step(runtime));
    assert(sg_stopped(&runtime->graph) && runtime->lifecycle.graph_stopped && !runtime->lifecycle.completed);
    assert(runtime->lifecycle.children == NC_CHILDREN_LIVE && event_count("event=graph-stopped ") == 1);
    assert(!strstr(events, "event=restart ") && !strstr(events, "event=launch ") && !strstr(events, "event=quiesced "));
}

static void dependency_and_adopted_child_drain(void)
{
    struct ns_runtime runtime = quiesce_actor(); begin_quiesce(&runtime);
    unsigned launched = forks;
    struct nc_lifecycle original = runtime.lifecycle; struct service_graph original_graph = runtime.graph;
    assert(!nc_begin_quiesce(&runtime.graph, &runtime.lifecycle, 2000));
    assert(!memcmp(&original, &runtime.lifecycle, sizeof(original)) && !memcmp(&original_graph, &runtime.graph, sizeof(original_graph)));
    stop_graph_with_live_child(&runtime);
    time_ms(2000); assert(!ns_step(&runtime));
    assert(!runtime.lifecycle.completed && runtime.lifecycle.children == NC_CHILDREN_LIVE && forks == launched);
    /* Stale emptiness is discarded: the post-graph boundary must wait again. */
    runtime.lifecycle.children = NC_CHILDREN_EMPTY;
    unsigned before_waits = waits; assert(!ns_quiesce_progress(&runtime));
    assert(waits > before_waits && !runtime.lifecycle.completed && runtime.lifecycle.children == NC_CHILDREN_LIVE);
    reap(42, 37 << 8); assert(!ns_step(&runtime));
    assert(runtime.graph.other_exits == 1 && !runtime.lifecycle.completed && runtime.lifecycle.children == NC_CHILDREN_LIVE);
    assert(strstr(events, "event=other-child service=none pid=42 generation=0") && strstr(events, "status=9472\n"));
    wait_empty = 1; before_waits = waits; assert(!ns_step(&runtime));
    assert(waits >= before_waits + 2 && runtime.lifecycle.completed && runtime.lifecycle.children == NC_CHILDREN_EMPTY);
    const char *reaped = strstr(events, "event=other-child "), *quiesced = strstr(events, "event=quiesced ");
    assert(reaped && quiesced && reaped < quiesced && event_count("event=quiesced ") == 1);
    assert(runtime.control.listener == 30 && !control_closes && forks == launched);
    original = runtime.lifecycle; original_graph = runtime.graph;
    time_ms(25000); assert(!ns_step(&runtime));
    assert(runtime.lifecycle.completed && runtime.control.listener == 30 && !control_closes && forks == launched);
    assert(event_count("event=quiesced ") == 1 && event_count("event=graph-stopped ") == 1);
    assert(!nc_begin_quiesce(&runtime.graph, &runtime.lifecycle, 30000));
    assert(!memcmp(&original, &runtime.lifecycle, sizeof(original)) && !memcmp(&original_graph, &runtime.graph, sizeof(original_graph)));
}

static void all_empty_requires_post_graph_echild(void)
{
    struct ns_runtime runtime = quiesce_actor(); begin_quiesce(&runtime);
    reap(11, SIGTERM); assert(!ns_step(&runtime));
    reap(10, SIGTERM); wait_empty = 1;
    unsigned before = waits; assert(!ns_step(&runtime));
    assert(runtime.lifecycle.completed && waits >= before + 3);
    const char *graph = strstr(events, "event=graph-stopped "), *complete = strstr(events, "event=quiesced ");
    assert(graph && complete && graph < complete && runtime.control.listener == 30 && !control_closes);
}

static void failure_and_deadline_controls(void)
{
    struct ns_runtime runtime = quiesce_actor(); begin_quiesce(&runtime);
    wait_empty = 1; assert(ns_step(&runtime) < 0 && errno == EIO);
    assert(!runtime.lifecycle.completed && runtime.graph.services[1].pid == 10 && !strstr(events, "event=quiesced "));
    runtime = quiesce_actor(); begin_quiesce(&runtime);
    wait_repeated_error = EIO; assert(ns_step(&runtime) < 0 && errno == EIO && !runtime.lifecycle.completed);
    runtime = quiesce_actor(); begin_quiesce(&runtime);
    wait_repeated_error = EINTR; wait_advance_ms = 1000;
    unsigned before = waits; assert(ns_step(&runtime) < 0 && errno == EIO);
    assert(waits - before <= NC_QUIESCE_MS / 1000 + 1 && !runtime.lifecycle.completed && !strstr(events, "event=quiesced "));
    runtime = quiesce_actor(); begin_quiesce(&runtime); stop_graph_with_live_child(&runtime);
    uint64_t deadline = runtime.lifecycle.deadline_ms;
    assert(!nc_begin_quiesce(&runtime.graph, &runtime.lifecycle, deadline - 1) && runtime.lifecycle.deadline_ms == deadline);
    time_ms((unsigned)deadline); before = waits;
    assert(ns_step(&runtime) < 0 && errno == EIO && waits == before && !runtime.lifecycle.completed);
    runtime = quiesce_actor(); begin_quiesce(&runtime); stop_graph_with_live_child(&runtime);
    wait_empty = 1; wait_advance_ms = 1; time_ms((unsigned)runtime.lifecycle.deadline_ms - 1);
    assert(ns_step(&runtime) < 0 && errno == EIO && !runtime.lifecycle.completed && !strstr(events, "event=quiesced "));
    runtime = quiesce_actor(); begin_quiesce(&runtime); stop_graph_with_live_child(&runtime);
    clock_error = EIO; assert(ns_step(&runtime) < 0 && errno == EIO && !runtime.lifecycle.completed);
    runtime = quiesce_actor(); begin_quiesce(&runtime); stop_graph_with_live_child(&runtime);
    time_ms(999); assert(ns_step(&runtime) < 0 && errno == EOVERFLOW && !runtime.lifecycle.completed);
    runtime = quiesce_actor(); begin_quiesce(&runtime);
    time_ms(2500); assert(!ns_step(&runtime) && signal_calls[1].pid == 11 && signal_calls[1].number == SIGKILL);
    time_ms(3000); assert(ns_step(&runtime) < 0 && runtime.graph.failed && !runtime.lifecycle.completed);
    assert(!strstr(events, "event=quiesced ") && !strstr(events, "event=launch "));
}

static void interrupted_channels_and_events_are_bounded(void)
{
    struct ns_runtime runtime = quiesce_actor(); begin_quiesce(&runtime);
    /* A still-open exec-error channel can repeatedly interrupt during shutdown. */
    runtime.channels[1].exec_fd = 40; read_error = EINTR; read_advance_ms = 1000;
    unsigned before = reads;
    assert(ns_step(&runtime) < 0 && errno == EIO && reads - before <= NC_QUIESCE_MS / 1000 + 1);
    assert(!runtime.lifecycle.completed && !strstr(events, "event=quiesced "));
    runtime = quiesce_actor(); begin_quiesce(&runtime);
    runtime.channels[1].ready_fd = 40; read_error = EINTR; read_advance_ms = 1000; before = reads;
    assert(ns_drain_ready(&runtime, 1) < 0 && errno == EIO && reads - before <= NC_QUIESCE_MS / 1000 + 1);
    assert(!runtime.lifecycle.completed && !strstr(events, "event=quiesced "));
    runtime = quiesce_actor(); begin_quiesce(&runtime);
    write_error = EINTR; write_advance_ms = 1000;
    assert(ns_event(&runtime, (struct sg_token){SG_CAPACITY, 0, 1}, "test-interruption", 0, 0) < 0 && errno == EIO);
    assert(runtime.now >= runtime.lifecycle.deadline_ms && !runtime.lifecycle.completed && !strstr(events, "test-interruption"));
    runtime = quiesce_actor(); begin_quiesce(&runtime); stop_graph_with_live_child(&runtime);
    time_ms((unsigned)runtime.lifecycle.deadline_ms); before = event_write_calls;
    assert(ns_event(&runtime, (struct sg_token){SG_CAPACITY, 0, 1}, "quiesced", 0, 0) < 0 && errno == EIO);
    assert(event_write_calls == before && !strstr(events, "event=quiesced "));
    assert(!ns_event(&runtime, (struct sg_token){SG_CAPACITY, 0, 1}, "fatal-hold", EIO, 0));
    assert(event_write_calls == before + 1 && strstr(events, "event=fatal-hold "));
}

int main(void)
{
    assert(!previous_quiesce_actor_controls());
    dependency_and_adopted_child_drain(); all_empty_requires_post_graph_echild(); failure_and_deadline_controls();
    interrupted_channels_and_events_are_bounded();
    puts("native quiesce hosted dependency stop, fresh ECHILD, adopted child, deadline and endpoint controls passed");
    return 0;
}
