#include "../apps/init/service_graph.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static struct sg_token start(struct service_graph *graph, unsigned index, int pid, uint64_t now)
{
    struct sg_action action = sg_next(graph, now);
    assert(action.kind == SG_LAUNCH && action.token.index == index);
    assert(sg_launched(graph, action.token, pid, now) == 0);
    return sg_token(graph, index);
}

static void admission(void)
{
    struct sg_spec specs[] = {
        {"root", "/root", 0, SG_NOTIFY}, {"left", "/left", 1, SG_ONESHOT},
        {"right", "/right", 1, SG_SIMPLE}, {"leaf", "/leaf", 6, SG_NOTIFY}
    };
    struct service_graph graph;
    memset(&graph, 0x5a, sizeof(graph));
    struct service_graph before = graph;
    assert(sg_init(&graph, specs, 0) == -1 && memcmp(&before, &graph, sizeof(graph)) == 0);
    specs[0].dependencies = 8;
    assert(sg_init(&graph, specs, 4) == -1 && memcmp(&before, &graph, sizeof(graph)) == 0);
    specs[0].dependencies = 16;
    assert(sg_init(&graph, specs, 4) == -1);
    specs[0].dependencies = 0;
    specs[3].name = "left";
    assert(sg_init(&graph, specs, 4) == -1);
    specs[3].name = "leaf";
    specs[1].executable = "relative";
    assert(sg_init(&graph, specs, 4) == -1);
    specs[1].executable = "/left";
    specs[1].mode = (enum sg_mode)-1;
    assert(sg_init(&graph, specs, 4) == -1);
    specs[1].mode = (enum sg_mode)(SG_ONESHOT + 1);
    assert(sg_init(&graph, specs, 4) == -1);
    specs[1].mode = SG_ONESHOT;
    assert(sg_init(&graph, specs, 4) == 0);
    assert(graph.ancestors[3] == 7);
    assert(graph.order[0] == 0 && graph.order[3] == 3);
}

static void readiness_and_stale_tokens(void)
{
    const struct sg_spec specs[] = {
        {"notify", "/notify", 0, SG_NOTIFY}, {"dependent", "/dependent", 1, SG_SIMPLE}
    };
    struct service_graph graph;
    assert(sg_init(&graph, specs, 2) == 0);
    struct sg_token old = start(&graph, 0, 10, 0);
    assert(sg_next(&graph, 1).kind == SG_NONE); /* PID alone is not ready. */
    assert(sg_ack(&graph, old, 2) == 0);
    assert(sg_next(&graph, 3).kind == SG_NONE); /* Ack alone is not exec success. */
    assert(sg_exec(&graph, old, 1, 4) == 0);
    struct sg_token dependent = start(&graph, 1, 11, 5);
    assert(sg_exec(&graph, dependent, 1, 6) == 0);
    assert(sg_ack(&graph, dependent, 7) == -1);
    assert(sg_reaped(&graph, 10, 0, 10) == 0);
    assert(graph.services[1].phase == SG_RETIRING);
    assert(sg_exec(&graph, dependent, 1, 11) == -1);
    struct sg_action stop = sg_next(&graph, 11);
    assert(stop.kind == SG_TERM && stop.token.index == 1);
    assert(sg_signaled(&graph, stop, 11) == 0);
    assert(sg_reaped(&graph, 11, 1, 12) == 1);
    assert(graph.services[1].failures == 0 && graph.services[1].phase == SG_WAIT);
    assert(sg_next(&graph, 59).kind == SG_NONE);
    struct sg_token current = start(&graph, 0, 10, 60); /* Numeric PID is reused. */
    assert(current.generation == 2);
    assert(sg_ack(&graph, old, 61) == -1 && sg_exec(&graph, old, 1, 61) == -1);
    assert(sg_exec(&graph, current, 1, 62) == 0);
    assert(sg_next(&graph, 63).kind == SG_NONE);
    assert(sg_ack(&graph, current, 64) == 0);
    assert(start(&graph, 1, 12, 65).generation == 2);
}

static void oneshot_and_dependency_loss(void)
{
    const struct sg_spec specs[] = {
        {"setup", "/setup", 0, SG_ONESHOT}, {"daemon", "/daemon", 1, SG_NOTIFY}
    };
    struct service_graph graph;
    assert(sg_init(&graph, specs, 2) == 0);
    struct sg_token setup = start(&graph, 0, 20, 0);
    assert(sg_ack(&graph, setup, 1) == -1);
    assert(sg_exec(&graph, setup, 1, 2) == 0);
    assert(sg_next(&graph, 3).kind == SG_NONE);
    assert(sg_reaped(&graph, 20, 1, 4) == 0);
    assert(graph.services[0].phase == SG_READY && graph.services[0].pid == 0);
    struct sg_token daemon = start(&graph, 1, 21, 5);
    assert(sg_exec(&graph, daemon, 1, 6) == 0);
    assert(sg_ack(&graph, daemon, 7) == 0);
    sg_shutdown(&graph, 8);
    assert(graph.services[0].phase == SG_STOPPED);
    struct sg_action action = sg_next(&graph, 8);
    assert(action.kind == SG_TERM && action.token.index == 1);
    assert(sg_signaled(&graph, action, 8) == 0);
    assert(sg_reaped(&graph, 21, 1, 9) == 1 && sg_stopped(&graph));
    assert(sg_ack(&graph, daemon, 10) == -1 && sg_next(&graph, 10).kind == SG_NONE);
    assert(sg_init(&graph, specs, 2) == 0);
    setup = start(&graph, 0, 22, 0);
    assert(sg_exec(&graph, setup, 1, 0) == 0);
    assert(sg_reaped(&graph, 22, 0, 1) == 0 && graph.services[0].phase == SG_WAIT);
    assert(sg_next(&graph, 50).kind == SG_NONE);
}

static void reverse_shutdown_and_deadlines(void)
{
    const struct sg_spec specs[] = {
        {"a", "/a", 0, SG_SIMPLE}, {"b", "/b", 1, SG_SIMPLE}, {"c", "/c", 2, SG_SIMPLE}
    };
    struct service_graph graph;
    assert(sg_init(&graph, specs, 3) == 0);
    for (unsigned i = 0; i < 3; ++i) {
        struct sg_token token = start(&graph, i, (int)i + 30, i);
        assert(sg_exec(&graph, token, 1, i) == 0);
    }
    sg_shutdown(&graph, 100);
    struct sg_action leaf = sg_next(&graph, 100);
    assert(leaf.kind == SG_TERM && leaf.token.index == 2);
    assert(sg_signaled(&graph, leaf, 400) == 0);
    assert(sg_next(&graph, 1899).kind == SG_NONE);
    struct sg_action kill = sg_next(&graph, 1900);
    assert(kill.kind == SG_KILL && kill.token.index == 2);
    assert(sg_signaled(&graph, kill, 1900) == 0);
    assert(sg_next(&graph, 2399).kind == SG_NONE);
    assert(sg_next(&graph, 2400).kind == SG_TIMEOUT && !sg_stopped(&graph));
    assert(sg_reaped(&graph, 32, 0, 2401) == 2 && graph.failed && !sg_stopped(&graph));
    /* A failed shutdown must stay failed even after every late child is reaped. */
    assert(sg_reaped(&graph, 31, 1, 2402) == 1);
    assert(sg_reaped(&graph, 30, 1, 2403) == 0 && !sg_stopped(&graph));
    assert(sg_init(&graph, specs, 3) == 0);
    for (unsigned i = 0; i < 3; ++i) {
        struct sg_token token = start(&graph, i, (int)i + 30, i);
        assert(sg_exec(&graph, token, 1, i) == 0);
    }
    sg_shutdown(&graph, 100);
    leaf = sg_next(&graph, 100);
    assert(sg_signaled(&graph, leaf, 100) == 0);
    assert(sg_reaped(&graph, 32, 1, 110) == 2);
    struct sg_action middle = sg_next(&graph, 2402);
    assert(middle.kind == SG_TERM && middle.token.index == 1);
    assert(sg_signaled(&graph, middle, 9000) == 0);
    assert(sg_next(&graph, 10499).kind == SG_NONE); /* Wait did not age its TERM timer. */
    assert(sg_reaped(&graph, 31, 1, 10500) == 1);
    struct sg_action root = sg_next(&graph, 10501);
    assert(root.kind == SG_TERM && root.token.index == 0);
    assert(sg_signaled(&graph, root, 10501) == 0);
    assert(sg_reaped(&graph, 30, 1, 10502) == 0 && sg_stopped(&graph));
    assert(sg_signaled(&graph, leaf, 10503) == -1);
}

static void exhaustion_and_partial_launch(void)
{
    const struct sg_spec spec = {"one", "/one", 0, SG_NOTIFY};
    struct service_graph graph;
    assert(sg_init(&graph, &spec, 1) == 0);
    struct sg_action action = sg_next(&graph, UINT64_MAX - 10000);
    assert(action.kind == SG_LAUNCH);
    assert(sg_launch_failed(&graph, action.token, UINT64_MAX - 10000) == 0);
    assert(graph.services[0].next_ms == UINT64_MAX - 9950 && graph.services[0].generation == 1);
    assert(sg_launch_failed(&graph, action.token, UINT64_MAX - 9999) == -1);
    assert(sg_launched(&graph, action.token, 40, UINT64_MAX - 9950) == -1);
    struct sg_token token = start(&graph, 0, 40, UINT64_MAX - 9950);
    assert(sg_ack(&graph, token, UINT64_MAX - 9949) == 0 && sg_exec(&graph, token, 1, UINT64_MAX - 9948) == 0);
    sg_shutdown(&graph, UINT64_MAX - 2000);
    action = sg_next(&graph, UINT64_MAX - 2000);
    assert(action.kind == SG_TERM && sg_signaled(&graph, action, UINT64_MAX - 2000) == 0);
    assert(sg_next(&graph, UINT64_MAX - 501).kind == SG_NONE);
    action = sg_next(&graph, UINT64_MAX - 500);
    assert(action.kind == SG_KILL && sg_signaled(&graph, action, UINT64_MAX - 500) == 0);
    assert(sg_next(&graph, UINT64_MAX).kind == SG_TIMEOUT && !sg_stopped(&graph));
    assert(sg_reaped(&graph, 40, 1, UINT64_MAX) == 0 && !sg_stopped(&graph));
    assert(sg_init(&graph, &spec, 1) == 0);
    assert(sg_next(&graph, UINT64_MAX - SG_READY_MS + 1).kind == SG_NONE && graph.failed);
    assert(sg_init(&graph, &spec, 1) == 0);
    graph.services[0].generation = UINT64_MAX;
    assert(sg_next(&graph, 0).kind == SG_NONE && graph.services[0].phase == SG_FAILED);
    assert(sg_init(&graph, &spec, 1) == 0);
    token = start(&graph, 0, 41, 0);
    sg_settle(&graph, SG_READY_MS);
    assert(graph.services[0].phase == SG_RETIRING && sg_ack(&graph, token, SG_READY_MS) == -1);
    assert(sg_reaped(&graph, 41, 0, SG_READY_MS) == 0 && graph.services[0].failures == 1);
    assert(sg_reaped(&graph, 999, 1, 3100) == -1 && graph.other_exits == 1);
}

static void late_completion_and_reserved_launch(void)
{
    struct service_graph graph;
    const struct sg_spec oneshot = {"setup", "/setup", 0, SG_ONESHOT};
    assert(sg_init(&graph, &oneshot, 1) == 0);
    struct sg_token token = start(&graph, 0, 50, 0);
    assert(sg_exec(&graph, token, 1, 1) == 0);
    assert(sg_reaped(&graph, 50, 1, SG_READY_MS + 1) == 0 && graph.services[0].phase == SG_WAIT);
    const struct sg_spec pair[] = {{"provider", "/provider", 0, SG_SIMPLE},
        {"consumer", "/consumer", 1, SG_NOTIFY}};
    assert(sg_init(&graph, pair, 2) == 0);
    token = start(&graph, 0, 51, 0);
    assert(sg_exec(&graph, token, 1, 1) == 0);
    struct sg_action old = sg_next(&graph, 2);
    assert(old.kind == SG_LAUNCH && old.token.index == 1 && graph.services[1].phase == SG_RESERVED);
    assert(sg_next(&graph, 3).kind == SG_NONE); /* Reservation is exclusive. */
    assert(sg_reaped(&graph, 51, 0, 4) == 0 && graph.services[1].phase == SG_WAIT);
    token = start(&graph, 0, 51, 54);
    assert(sg_exec(&graph, token, 1, 55) == 0);
    assert(sg_launched(&graph, old.token, 52, 56) == -1);
    struct sg_token replacement = start(&graph, 1, 52, 57);
    assert(replacement.generation != old.token.generation);
    assert(sg_ack(&graph, replacement, 58) == 0 && sg_exec(&graph, replacement, 1, 59) == 0);
}

int main(void)
{
    admission();
    readiness_and_stale_tokens();
    oneshot_and_dependency_loss();
    reverse_shutdown_and_deadlines();
    exhaustion_and_partial_launch();
    late_completion_and_reserved_launch();
    puts("SERVICE_GRAPH_HOSTED_PASS");
    return 0;
}
