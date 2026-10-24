#define NATIVE_CONTROL_TEST_ENTRY previous_halt_control_tests
#include "native_control_tests.c"

struct power_case {
    enum nc_operation operation;
    uint32_t action;
    const char *name, *request, *accepted, *command;
};
static const struct power_case power_cases[] = {
    {NC_HALT, OK_POWER_HALT, "HALT", NC_PREFIX "HALT\n",
     NC_PREFIX "HALT accepted=1 started_ms=1000 deadline_ms=19000\nEND\n", "halt"},
    {NC_REBOOT, OK_POWER_REBOOT, "REBOOT", NC_PREFIX "REBOOT\n",
     NC_PREFIX "REBOOT accepted=1 started_ms=1000 deadline_ms=19000\nEND\n", "reboot"},
    {NC_POWEROFF, OK_POWER_POWEROFF, "POWEROFF", NC_PREFIX "POWEROFF\n",
     NC_PREFIX "POWEROFF accepted=1 started_ms=1000 deadline_ms=19000\nEND\n", "poweroff"}
};

static void power_prepare_policy(const struct power_case *test)
{
    reset(); struct service_graph graph = graph_ready(), before = graph;
    struct nc_lifecycle old = lifecycle; struct nc_buffer reply;
    struct nc_request parsed = nc_parse(test->request, strlen(test->request));
    assert(parsed.operation == test->operation && !parsed.service[0]);
    assert(!nc_response(test->accepted, strlen(test->accepted)));
    const char *suffixes[] = {" service\n", " \n", "\r\n", "\nHALT\n", "",
        "X\n", "\n\n", "\nREBOOT\n", "\nPOWEROFF\n"};
    for (unsigned i = 0; i < sizeof(suffixes) / sizeof(suffixes[0]); ++i) {
        char bad[NC_REQUEST_BYTES];
        int size = snprintf(bad, sizeof(bad), NC_PREFIX "%s%s", test->name, suffixes[i]);
        assert(size > 0 && (size_t)size < sizeof(bad)); dispatch(&graph, 0, bad, &reply);
        assert(nc_response(reply.bytes, reply.size) == 1 && !power_prepares);
        assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
        assert(nc_exchange(bad, (size_t)size, &reply) < 0 && errno == EINVAL && !socket_calls);
    }
    char lowercase[NC_REQUEST_BYTES];
    int size = snprintf(lowercase, sizeof(lowercase), NC_PREFIX "%s\n", test->command);
    assert(size > 0 && (size_t)size < sizeof(lowercase));
    dispatch(&graph, 0, lowercase, &reply); assert(strstr(reply.bytes, "code=protocol") && !power_prepares);
    assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    char embedded[NC_REQUEST_BYTES]; size_t request_size = strlen(test->request);
    assert(request_size + 1 < sizeof(embedded)); memcpy(embedded, test->request, request_size);
    embedded[request_size - 1] = '\0'; embedded[request_size] = '\n';
    assert(nc_parse(embedded, request_size + 1).operation == NC_INVALID);
    nc_dispatch(&graph, &lifecycle, 0, embedded, request_size + 1, 1000, &reply);
    assert(nc_response(reply.bytes, reply.size) == 1 && strstr(reply.bytes, "code=protocol") && !power_prepares);
    assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    assert(nc_exchange(embedded, request_size + 1, &reply) < 0 && errno == EINVAL && !socket_calls);
    dispatch(&graph, 1000, test->request, &reply);
    assert(strstr(reply.bytes, "code=denied") && !power_prepares);
    assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    const int errors[] = {EOPNOTSUPP, ENOSYS, EPERM, EACCES, EBUSY, EIO};
    for (unsigned i = 0; i < sizeof(errors) / sizeof(errors[0]); ++i) {
        power_prepare_error = errors[i]; dispatch(&graph, 0, test->request, &reply);
        assert(nc_response(reply.bytes, reply.size) == 1 && power_prepared_action == test->action);
        assert(strstr(reply.bytes, i < 2 ? "code=unsupported" : i < 4 ? "code=denied" : "code=busy"));
        assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)) && !power_commits);
    }
    power_prepare_error = 0;
    power_token = 0; dispatch(&graph, 0, test->request, &reply);
    assert(nc_response(reply.bytes, reply.size) == 1 && !memcmp(&graph, &before, sizeof(graph)) &&
        !memcmp(&lifecycle, &old, sizeof(old)) && !power_commits);
    power_token = 0x40000000; dispatch(&graph, 0, test->request, &reply);
    assert(nc_response(reply.bytes, reply.size) == 1 && !memcmp(&graph, &before, sizeof(graph)) &&
        !memcmp(&lifecycle, &old, sizeof(old)) && !power_commits);
    power_token = (int)OK_POWER_TOKEN_MAX; unsigned prepares = power_prepares;
    power_prepare_advance_ms = 5000;
    dispatch(&graph, 0, test->request, &reply);
    assert(reply.size == strlen(test->accepted) && !memcmp(reply.bytes, test->accepted, reply.size));
    assert(graph.stopping && lifecycle.requested && lifecycle.power_requested && !lifecycle.completed);
    assert(lifecycle.power_operation == test->operation && power_prepared_action == test->action);
    assert(lifecycle.power_token == OK_POWER_TOKEN_MAX && power_prepares == prepares + 1 && !power_commits);
    assert(milliseconds == 6000 && lifecycle.started_ms == 1000 && lifecycle.deadline_ms == 19000);
    before = graph; old = lifecycle;
    nc_dispatch(&graph, &lifecycle, 0, test->request, strlen(test->request), 18000, &reply);
    assert(!nc_response(reply.bytes, reply.size) && power_prepares == prepares + 1);
    assert(reply.size == strlen(test->accepted) && !memcmp(reply.bytes, test->accepted, reply.size));
    assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    for (unsigned i = 0; i < sizeof(power_cases) / sizeof(power_cases[0]); ++i) {
        const struct power_case *other = &power_cases[i];
        if (other->operation == test->operation) continue;
        nc_dispatch(&graph, &lifecycle, 0, other->request, strlen(other->request), 18000, &reply);
        assert(strstr(reply.bytes, "code=busy") && power_prepares == prepares + 1 && !power_commits);
        assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
        dispatch(&graph, 1000, other->request, &reply);
        assert(strstr(reply.bytes, "code=denied") && power_prepares == prepares + 1);
        assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    }
    dispatch(&graph, 0, NC_PREFIX "RESTART provider\n", &reply);
    assert(strstr(reply.bytes, "code=busy") && !power_commits);
    assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    reset(); graph = graph_ready(); assert(!nc_begin_quiesce(&graph, &lifecycle, 1000));
    before = graph; old = lifecycle; dispatch(&graph, 0, test->request, &reply);
    assert(strstr(reply.bytes, "code=busy") && !power_prepares);
    assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    for (unsigned fault = 0; fault < 4; ++fault) {
        reset(); graph = graph_ready();
        if (fault == 0) graph.failed = 1;
        if (fault == 1) lifecycle.failed = 1;
        if (fault == 2) graph.stopping = 1;
        before = graph; old = lifecycle;
        nc_dispatch(&graph, &lifecycle, 0, test->request, strlen(test->request),
                    fault == 3 ? UINT64_MAX - NC_QUIESCE_MS + 1 : 1000, &reply);
        assert(nc_response(reply.bytes, reply.size) == 1 && !power_prepares);
        assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    }
    reset(); graph = graph_ready(); before = graph; old = lifecycle;
    const enum nc_operation invalid[] = {NC_QUIESCE, NC_INVALID, NC_STATUS, NC_RESTART, NC_STATE};
    for (unsigned i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
        assert(nc_begin_power(&graph, &lifecycle, invalid[i], 1000) < 0 && errno == EINVAL && !power_prepares);
        assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    }
}

static void exact_commit_token(const struct power_case *test)
{
    reset(); struct service_graph graph = graph_ready();
    assert(!nc_begin_power(&graph, &lifecycle, test->operation, 1000) && power_prepares == 1);
    assert(power_prepared_action == test->action);
    assert(nc_commit_power(&lifecycle) < 0 && !power_commits);
    lifecycle.completed = 1; lifecycle.children = NC_CHILDREN_EMPTY;
    struct nc_lifecycle good = lifecycle;
    for (unsigned fault = 0; fault < 9; ++fault) {
        lifecycle = good;
        if (fault == 0) lifecycle.power_requested = 0;
        if (fault == 1) lifecycle.failed = 1;
        if (fault == 2) lifecycle.power_committed = 1;
        if (fault == 3) lifecycle.children = NC_CHILDREN_LIVE;
        if (fault == 4) lifecycle.power_token = 0;
        if (fault == 5) lifecycle.power_token = 0x40000000;
        if (fault == 6) lifecycle.completed = 0;
        if (fault == 7) lifecycle.power_operation = NC_QUIESCE;
        if (fault == 8) lifecycle.children = NC_CHILDREN_UNKNOWN;
        assert(nc_commit_power(&lifecycle) < 0 && !power_commits);
    }
    lifecycle = good; power_commit_error = EBUSY;
    assert(nc_commit_power(&lifecycle) < 0 && errno == EBUSY && power_commits == 1);
    assert(power_committed_token == (uint32_t)power_token);
    power_commit_error = 0; assert(!nc_commit_power(&lifecycle) && power_commits == 2);
    assert(power_committed_token == good.power_token && !memcmp(&lifecycle, &good, sizeof(good)));
}

static void power_transport_cli_and_framing(const struct power_case *test)
{
    struct native_control control; struct nc_buffer reply;
    reset(); struct service_graph graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control));
    struct service_graph before = graph; struct nc_lifecycle old = lifecycle;
    queue(4, test->request); ends[4].peer.uid = 1000;
    assert(!nc_step(&control, &graph, 1000) && !power_prepares && !graph.stopping);
    assert(ends[4].closed && nc_response(ends[4].output, ends[4].written) == 1 &&
        strstr(ends[4].output, "code=denied"));
    assert(!memcmp(&graph, &before, sizeof(graph)) && !memcmp(&lifecycle, &old, sizeof(old)));
    reset(); graph = graph_ready(); nc_reset(&control); assert(!nc_open(&control));
    queue(4, test->request); ends[4].chunk = 2; ends[4].send_chunk = 3;
    for (unsigned step = 0; step < 200 && !ends[4].closed; ++step) assert(!nc_step(&control, &graph, 1000 + step));
    assert(ends[4].closed && !nc_response(ends[4].output, ends[4].written) && power_prepares == 1);
    assert(lifecycle.power_requested && lifecycle.power_operation == test->operation && !power_commits && control.listener == 3);
    const char *suffixes[] = {" accepted=0 started_ms=1000 deadline_ms=19000\nEND\n",
        " accepted=1 started_ms=1000 deadline_ms=1000\nEND\n",
        " accepted=1 started_ms=1000 deadline_ms=19000 token=1\nEND\n",
        " accepted=1 started_ms=1000 deadline_ms=19000\nEND\nextra",
        "X accepted=1 started_ms=1000 deadline_ms=19000\nEND\n",
        " accepted=1 started_ms=1000 deadline_ms=19000\r\nEND\n",
        " accepted=1 started_ms=1000 deadline_ms=19000\nEND\nEND\n"};
    for (unsigned i = 0; i < sizeof(suffixes) / sizeof(suffixes[0]); ++i) {
        char bad[NC_REPLY_BYTES]; int size = snprintf(bad, sizeof(bad), NC_PREFIX "%s%s", test->name, suffixes[i]);
        assert(size > 0 && (size_t)size < sizeof(bad) && nc_response(bad, (size_t)size) < 0);
        reset(); ends[3].input = bad; ends[3].size = (size_t)size;
        assert(nc_exchange(test->request, strlen(test->request), &reply) < 0 && errno == EIO);
    }
    char embedded[NC_REPLY_BYTES]; size_t accepted_size = strlen(test->accepted);
    assert(accepted_size < sizeof(embedded)); memcpy(embedded, test->accepted, accepted_size);
    embedded[sizeof(NC_PREFIX) - 1] = '\0';
    assert(nc_response(embedded, accepted_size) < 0);
    reset(); ends[3].input = embedded; ends[3].size = accepted_size;
    assert(nc_exchange(test->request, strlen(test->request), &reply) < 0 && errno == EIO);
    reset(); ends[3].input = test->accepted; ends[3].size = strlen(test->accepted);
    ends[3].chunk = 2; ends[3].send_chunk = 3;
    assert(!nc_exchange(test->request, strlen(test->request), &reply));
    const char *quiesce = NC_PREFIX "QUIESCE accepted=1 started_ms=1000 deadline_ms=19000\nEND\n";
    reset(); ends[3].input = quiesce; ends[3].size = strlen(quiesce);
    assert(nc_exchange(test->request, strlen(test->request), &reply) < 0 && errno == EIO);
    reset(); ends[3].input = test->accepted; ends[3].size = strlen(test->accepted);
    assert(nc_exchange(NC_PREFIX "QUIESCE\n", sizeof(NC_PREFIX "QUIESCE\n") - 1, &reply) < 0 && errno == EIO);
    for (unsigned i = 0; i < sizeof(power_cases) / sizeof(power_cases[0]); ++i) {
        const struct power_case *other = &power_cases[i];
        if (other->operation == test->operation) continue;
        reset(); ends[3].input = other->accepted; ends[3].size = strlen(other->accepted);
        assert(nc_exchange(test->request, strlen(test->request), &reply) < 0 && errno == EIO);
        reset(); ends[3].input = test->accepted; ends[3].size = strlen(test->accepted);
        assert(nc_exchange(other->request, strlen(other->request), &reply) < 0 && errno == EIO);
    }
    char *args[] = {"service-ctl", (char *)test->command, 0};
    reset(); cli_size = cli_errors = 0; ends[3].input = test->accepted; ends[3].size = strlen(test->accepted);
    assert(!control_cli_main(2, args) && cli_size == strlen(test->accepted));
    assert(ends[3].written == strlen(test->request) && !memcmp(ends[3].output, test->request, ends[3].written));
    reset(); cli_size = cli_errors = 0; ends[3].input = NC_PREFIX "ERROR code=unsupported\nEND\n";
    ends[3].size = strlen(ends[3].input);
    assert(control_cli_main(2, args) == 1 && cli_size == ends[3].size && !cli_errors);
    char *extra[] = {"service-ctl", (char *)test->command, "provider", 0};
    reset(); cli_size = cli_errors = 0; assert(control_cli_main(3, extra) == 2 && !socket_calls);
}

int main(void)
{
    assert(!previous_halt_control_tests());
    for (unsigned i = 0; i < sizeof(power_cases) / sizeof(power_cases[0]); ++i) {
        power_prepare_policy(&power_cases[i]); exact_commit_token(&power_cases[i]);
        power_transport_cli_and_framing(&power_cases[i]);
    }
    puts("native halt/reboot/poweroff hosted PREPARE refusal, root authorization, exact token and CLI controls passed");
    return 0;
}
