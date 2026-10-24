#define NATIVE_CONTROL_TEST_ENTRY previous_native_control_tests
#include "native_control_tests.c"

/* Reuse the actual server/client syscall seams. These remain hosted controls,
 * independent of the target's adopted-child quiescence witness. */
static const char running_state[] = NC_PREFIX "STATE phase=running graph=running children=live started_ms=0 deadline_ms=0\nEND\n";
static const char accepted_quiesce[] = NC_PREFIX "QUIESCE accepted=1 started_ms=1000 deadline_ms=19000\nEND\n";
static const char stopped_state[] = NC_PREFIX "STATE phase=quiesced graph=stopped children=empty started_ms=1000 deadline_ms=19000\nEND\n";

static void quiesce_policy(void)
{
    reset(); struct service_graph graph = graph_ready(), before = graph; struct nc_buffer reply;
    struct nc_state state;
    const char *bad[] = {NC_PREFIX "QUIESCE provider\n", NC_PREFIX "STATE provider\n", NC_PREFIX "QUIESCE \n",
        NC_PREFIX "STATE\r\n", NC_PREFIX "QUIESCE\nSTATE\n", NC_PREFIX "STATE\n\n", NC_PREFIX "QUIESCE"};
    for (unsigned i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) {
        dispatch(&graph, 0, bad[i], &reply); assert(nc_response(reply.bytes, reply.size) == 1);
        assert(!memcmp(&before, &graph, sizeof(graph)) && !lifecycle.requested);
    }
    const char nul[] = NC_PREFIX "QUIESCE\0\n";
    assert(nc_parse(nul, sizeof(nul) - 1).operation == NC_INVALID);
    lifecycle.children = NC_CHILDREN_EMPTY;
    struct nc_lifecycle old = lifecycle;
    dispatch(&graph, 1001, NC_PREFIX "QUIESCE\n", &reply);
    assert(nc_response(reply.bytes, reply.size) == 1 && strstr(reply.bytes, "code=denied"));
    assert(!memcmp(&before, &graph, sizeof(graph)) && !memcmp(&old, &lifecycle, sizeof(old)));
    dispatch(&graph, 1001, NC_PREFIX "STATE\n", &reply);
    assert(!nc_state_snapshot(&reply, &state) && !strcmp(state.phase, "running") && !strcmp(state.children, "empty"));
    assert(!memcmp(&before, &graph, sizeof(graph)) && !memcmp(&old, &lifecycle, sizeof(old)));
    dispatch(&graph, 0, NC_PREFIX "QUIESCE\n", &reply);
    assert(reply.size == sizeof(accepted_quiesce) - 1 && !memcmp(reply.bytes, accepted_quiesce, reply.size));
    assert(lifecycle.requested && !lifecycle.completed && lifecycle.children == NC_CHILDREN_UNKNOWN && graph.stopping);
    assert(lifecycle.started_ms == 1000 && lifecycle.deadline_ms == 1000 + NC_QUIESCE_MS);
    old = lifecycle; before = graph;
    nc_dispatch(&graph, &lifecycle, 0, NC_PREFIX "QUIESCE\n", sizeof(NC_PREFIX "QUIESCE\n") - 1, 8000, &reply);
    assert(reply.size == sizeof(accepted_quiesce) - 1 && !memcmp(reply.bytes, accepted_quiesce, reply.size));
    assert(!memcmp(&before, &graph, sizeof(graph)) && !memcmp(&old, &lifecycle, sizeof(old)));
    dispatch(&graph, 0, NC_PREFIX "RESTART provider\n", &reply);
    assert(nc_response(reply.bytes, reply.size) == 1 && strstr(reply.bytes, "code=busy"));
    assert(!memcmp(&before, &graph, sizeof(graph)) && !memcmp(&old, &lifecycle, sizeof(old)));
    dispatch(&graph, 1001, NC_PREFIX "STATE\n", &reply);
    assert(!nc_state_snapshot(&reply, &state) && !strcmp(state.phase, "quiescing") && !strcmp(state.graph, "stopping"));
    struct sg_action action = sg_next(&graph, 1000); assert(action.kind == SG_TERM && action.token.pid == 11);
    assert(!sg_signaled(&graph, action, 1000)); assert(sg_reaped(&graph, 11, 0, 1001) == 1);
    action = sg_next(&graph, 1001); assert(action.kind == SG_TERM && action.token.pid == 10);
    assert(!sg_signaled(&graph, action, 1001)); assert(sg_reaped(&graph, 10, 0, 1002) == 0);
    assert(sg_stopped(&graph) && sg_next(&graph, 100000).kind == SG_NONE);
    lifecycle.children = NC_CHILDREN_LIVE;
    dispatch(&graph, 1001, NC_PREFIX "STATE\n", &reply);
    assert(!nc_state_snapshot(&reply, &state) && !strcmp(state.phase, "quiescing") && !strcmp(state.graph, "stopped") && !strcmp(state.children, "live"));
    lifecycle.completed = 1; lifecycle.children = NC_CHILDREN_EMPTY;
    dispatch(&graph, 1001, NC_PREFIX "STATE\n", &reply);
    assert(reply.size == sizeof(stopped_state) - 1 && !memcmp(reply.bytes, stopped_state, reply.size));
    old = lifecycle; before = graph;
    nc_dispatch(&graph, &lifecycle, 0, NC_PREFIX "QUIESCE\n", sizeof(NC_PREFIX "QUIESCE\n") - 1, 20000, &reply);
    assert(!nc_response(reply.bytes, reply.size) && !memcmp(&before, &graph, sizeof(graph)) && !memcmp(&old, &lifecycle, sizeof(old)));
    reset(); graph = graph_ready(); before = graph;
    nc_dispatch(&graph, &lifecycle, 0, NC_PREFIX "QUIESCE\n", sizeof(NC_PREFIX "QUIESCE\n") - 1, UINT64_MAX - NC_QUIESCE_MS + 1, &reply);
    assert(nc_response(reply.bytes, reply.size) == 1 && !lifecycle.requested && !memcmp(&before, &graph, sizeof(graph)));
    graph.failed = 1; dispatch(&graph, 0, NC_PREFIX "QUIESCE\n", &reply);
    assert(nc_response(reply.bytes, reply.size) == 1 && !lifecycle.requested);
}

static void quiesce_reply_framing(void)
{
    assert(!nc_response(running_state, sizeof(running_state) - 1));
    assert(!nc_response(accepted_quiesce, sizeof(accepted_quiesce) - 1));
    assert(!nc_response(stopped_state, sizeof(stopped_state) - 1));
    const char *bad[] = {
        NC_PREFIX "QUIESCE accepted=0 started_ms=1000 deadline_ms=19000\nEND\n",
        NC_PREFIX "QUIESCE accepted=1 started_ms=1000 deadline_ms=1000\nEND\n",
        NC_PREFIX "QUIESCE accepted=1 started_ms=1000 deadline_ms=999\nEND\n",
        NC_PREFIX "QUIESCE accepted=1 started_ms=18446744073709551616 deadline_ms=19000\nEND\n",
        NC_PREFIX "QUIESCE accepted=1 started_ms=1000 deadline_ms=19000\nEND\nextra",
        NC_PREFIX "STATE phase=running graph=stopping children=live started_ms=0 deadline_ms=0\nEND\n",
        NC_PREFIX "STATE phase=running graph=running children=live started_ms=1 deadline_ms=2\nEND\n",
        NC_PREFIX "STATE phase=quiescing graph=running children=live started_ms=1000 deadline_ms=19000\nEND\n",
        NC_PREFIX "STATE phase=quiescing graph=stopped children=live started_ms=1000 deadline_ms=1000\nEND\n",
        NC_PREFIX "STATE phase=quiesced graph=stopped children=live started_ms=1000 deadline_ms=19000\nEND\n",
        NC_PREFIX "STATE phase=quiesced graph=stopping children=empty started_ms=1000 deadline_ms=19000\nEND\n",
        NC_PREFIX "STATE phase=failed graph=stopped children=empty started_ms=1000 deadline_ms=19000\nEND\n",
        NC_PREFIX "STATE phase=quiesced graph=stopped children=none started_ms=1000 deadline_ms=19000\nEND\n",
        NC_PREFIX "STATE phase=quiesced graph=stopped children=empty started_ms=1000 deadline_ms=19000\r\nEND\n",
        NC_PREFIX "STATE phase=quiesced graph=stopped children=empty started_ms=1000 deadline_ms=19000\nEND\nEND\n"
    };
    for (unsigned i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) assert(nc_response(bad[i], strlen(bad[i])) < 0);
    const char embedded[] = NC_PREFIX "STATE phase=running graph=running children=live started_ms=0 deadline_ms=0\0\nEND\n";
    assert(nc_response(embedded, sizeof(embedded) - 1) < 0);
}

static void quiesce_transport_and_cli(void)
{
    struct native_control control; struct service_graph graph; struct nc_buffer reply; struct nc_state state;
    reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control));
    queue(4, NC_PREFIX "QUIESCE\n"); ends[4].peer.uid = 1001;
    queue(5, NC_PREFIX "STATE\n"); ends[5].peer.uid = 1001;
    assert(!nc_step(&control, &graph, 1000));
    assert(nc_response(ends[4].output, ends[4].written) == 1 && !graph.stopping && !lifecycle.requested);
    memcpy(reply.bytes, ends[5].output, ends[5].written); reply.size = ends[5].written;
    assert(!nc_state_snapshot(&reply, &state) && !strcmp(state.phase, "running"));
    reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control));
    queue(4, NC_PREFIX "QUIESCE\n"); queue(5, NC_PREFIX "STATE\n");
    ends[4].chunk = 2; ends[4].send_chunk = 3; ends[4].recv_interrupt = ends[4].send_interrupt = 1;
    for (unsigned step = 0; step < 300 && !ends[4].closed; ++step) assert(!nc_step(&control, &graph, 1000 + step));
    assert(lifecycle.requested && ends[4].closed && !nc_response(ends[4].output, ends[4].written));
    assert(control.listener == 3 && !ends[3].closed); assert(!nc_close(&control));
    const char *requests[] = {NC_PREFIX "STATE\n", NC_PREFIX "QUIESCE\n"};
    const char *responses[] = {running_state, accepted_quiesce};
    for (unsigned i = 0; i < 2; ++i) {
        reset(); ends[3].input = responses[i]; ends[3].size = strlen(responses[i]); ends[3].chunk = 2; ends[3].send_chunk = 3;
        assert(!nc_exchange(requests[i], strlen(requests[i]), &reply));
        assert(ends[3].written == strlen(requests[i]) && !memcmp(ends[3].output, requests[i], ends[3].written));
        reset(); ends[3].input = responses[1 - i]; ends[3].size = strlen(ends[3].input);
        assert(nc_exchange(requests[i], strlen(requests[i]), &reply) < 0 && errno == EIO);
        reset(); ends[3].input = success; ends[3].size = sizeof(success) - 1;
        assert(nc_exchange(requests[i], strlen(requests[i]), &reply) < 0);
        reset(); ends[3].recv_again = -1;
        assert(nc_exchange(requests[i], strlen(requests[i]), &reply) < 0 && milliseconds == 2000);
        char *args[] = {"service-ctl", i ? "quiesce" : "state", 0};
        reset(); cli_size = cli_errors = 0; ends[3].input = responses[i]; ends[3].size = strlen(responses[i]);
        assert(!control_cli_main(2, args) && cli_size == strlen(responses[i]) && !memcmp(cli_output, responses[i], cli_size));
        char *extra[] = {"service-ctl", i ? "quiesce" : "state", "provider", 0};
        reset(); cli_size = cli_errors = 0;
        assert(control_cli_main(3, extra) == 2 && !socket_calls && cli_size);
    }
}

int main(void)
{
    assert(!previous_native_control_tests());
    quiesce_policy(); quiesce_reply_framing(); quiesce_transport_and_cli();
    puts("native quiesce hosted authorization, idempotence, framing, transport and CLI controls passed");
    return 0;
}
