#ifndef OK_SERVICE_GRAPH_H
#define OK_SERVICE_GRAPH_H

#include "pid1_policy.h"
#include <stddef.h>

enum { SG_CAPACITY = 8, SG_READY_MS = 3000 };
enum sg_mode { SG_SIMPLE, SG_NOTIFY, SG_ONESHOT };
enum sg_phase { SG_WAIT, SG_RESERVED, SG_STARTING, SG_READY, SG_RETIRING, SG_STOPPED, SG_FAILED };
enum sg_stop_reason { SG_CRASH, SG_DEPENDENCY, SG_SHUTDOWN };
enum sg_action_kind { SG_NONE, SG_LAUNCH, SG_TERM, SG_KILL, SG_TIMEOUT };

struct sg_spec {
    const char *name;
    const char *executable;
    uint8_t dependencies;
    enum sg_mode mode;
};

struct sg_service {
    enum sg_phase phase;
    enum sg_stop_reason reason;
    int pid;
    uint64_t generation;
    uint64_t launched_ms, next_ms, stop_ms, kill_ms;
    uint64_t dependency_generations[SG_CAPACITY];
    unsigned launches, failures, forced_stops;
    unsigned exec_confirmed : 1;
    unsigned ready_ack : 1;
    unsigned term_sent : 1;
    unsigned kill_sent : 1;
};

struct sg_token { unsigned index; uint64_t generation; int pid; };
struct sg_action { enum sg_action_kind kind; struct sg_token token; };
struct service_graph {
    struct sg_spec specs[SG_CAPACITY];
    struct sg_service services[SG_CAPACITY];
    uint8_t ancestors[SG_CAPACITY];
    uint8_t order[SG_CAPACITY];
    unsigned count, other_exits;
    unsigned stopping : 1;
    unsigned failed : 1;
};

static inline int sg_equal(const char *a, const char *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}

static inline int sg_string(const char *value, unsigned limit, int path)
{
    if (!value || !*value || (path && *value != '/')) return 0;
    for (unsigned i = 0; i <= limit; ++i) {
        unsigned char c = (unsigned char)value[i];
        if (!c) return i > 0;
        if (c < 33 || c > 126 || (!path && !((c >= 'a' && c <= 'z') ||
            (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_')))
            return 0;
    }
    return 0;
}

/* Validate the whole graph before replacing a caller's existing state. */
static inline int sg_init(struct service_graph *graph, const struct sg_spec *specs, unsigned count)
{
    if (!graph || !specs || !count || count > SG_CAPACITY) return -1;
    struct service_graph prepared = {0};
    prepared.count = count;
    const unsigned valid = (1u << count) - 1u;
    for (unsigned i = 0; i < count; ++i) {
        if (!sg_string(specs[i].name, 31, 0) || !sg_string(specs[i].executable, 95, 1) ||
            (unsigned)specs[i].mode > SG_ONESHOT ||
            (specs[i].dependencies & ~valid) || (specs[i].dependencies & (1u << i))) return -1;
        for (unsigned j = 0; j < i; ++j)
            if (sg_equal(specs[i].name, specs[j].name)) return -1;
        prepared.specs[i] = specs[i];
        prepared.ancestors[i] = specs[i].dependencies;
    }
    for (unsigned pass = 0; pass < count; ++pass)
        for (unsigned i = 0; i < count; ++i)
            for (unsigned j = 0; j < count; ++j)
                if (prepared.ancestors[i] & (1u << j)) prepared.ancestors[i] |= prepared.ancestors[j];
    for (unsigned i = 0; i < count; ++i)
        if (prepared.ancestors[i] & (1u << i)) return -1;
    unsigned ordered = 0;
    for (unsigned position = 0; position < count; ++position) {
        unsigned selected = count;
        for (unsigned i = 0; i < count; ++i)
            if (!(ordered & (1u << i)) && !(specs[i].dependencies & ~ordered)) { selected = i; break; }
        if (selected == count) return -1;
        prepared.order[position] = (uint8_t)selected;
        ordered |= 1u << selected;
    }
    *graph = prepared;
    return 0;
}

static inline int sg_dependencies_ready(const struct service_graph *graph, unsigned index)
{
    for (unsigned i = 0; i < graph->count; ++i)
        if ((graph->specs[index].dependencies & (1u << i)) && graph->services[i].phase != SG_READY) return 0;
    return 1;
}

static inline struct sg_token sg_token(const struct service_graph *graph, unsigned index)
{
    const struct sg_service *service = &graph->services[index];
    return (struct sg_token){ index, service->generation, service->pid };
}

static inline int sg_matches(const struct service_graph *graph, struct sg_token token)
{
    return token.index < graph->count && token.pid > 0 &&
        graph->services[token.index].pid == token.pid &&
        graph->services[token.index].generation == token.generation;
}

static inline int sg_dependency_generation_matches(const struct service_graph *graph, unsigned index)
{
    for (unsigned i = 0; i < graph->count; ++i)
        if ((graph->specs[index].dependencies & (1u << i)) &&
            graph->services[index].dependency_generations[i] != graph->services[i].generation) return 0;
    return sg_dependencies_ready(graph, index);
}

static inline int sg_time_budget(uint64_t now, uint64_t duration)
{ return duration <= UINT64_MAX - now; }

static inline void sg_retire(struct sg_service *service, enum sg_stop_reason reason, uint64_t now)
{
    service->exec_confirmed = service->ready_ack = 0;
    if (service->phase == SG_RETIRING) {
        if (reason == SG_SHUTDOWN) service->reason = reason;
        return;
    }
    service->reason = reason;
    service->stop_ms = now;
    service->term_sent = service->kill_sent = 0;
    service->phase = service->pid > 0 ? SG_RETIRING : (reason == SG_SHUTDOWN ? SG_STOPPED : SG_WAIT);
}

/* Withdraw readiness transitively before publishing another launch or signal. */
static inline void sg_settle(struct service_graph *graph, uint64_t now)
{
    for (unsigned position = 0; position < graph->count; ++position) {
        unsigned i = graph->order[position];
        struct sg_service *service = &graph->services[i];
        if (graph->stopping) {
            if (service->phase != SG_STOPPED && service->phase != SG_FAILED)
                sg_retire(service, SG_SHUTDOWN, now);
        } else if ((service->phase == SG_READY || service->phase == SG_STARTING || service->phase == SG_RESERVED) &&
                   !sg_dependency_generation_matches(graph, i)) {
            sg_retire(service, SG_DEPENDENCY, now);
        } else if (service->phase == SG_STARTING && now >= service->launched_ms &&
                   now - service->launched_ms >= SG_READY_MS) {
            sg_retire(service, SG_CRASH, now);
        }
        if (service->phase == SG_RETIRING && service->kill_sent && now >= service->kill_ms &&
            now - service->kill_ms >= PID1_STOP_KILL_MS) {
            service->phase = SG_FAILED;
            graph->failed = 1;
        }
    }
}

static inline void sg_shutdown(struct service_graph *graph, uint64_t now)
{
    graph->stopping = 1;
    sg_settle(graph, now);
}

static inline int sg_active_dependent(const struct service_graph *graph, unsigned index)
{
    for (unsigned i = 0; i < graph->count; ++i)
        if ((graph->ancestors[i] & (1u << index)) && graph->services[i].pid > 0) return 1;
    return 0;
}

static inline struct sg_action sg_next(struct service_graph *graph, uint64_t now)
{
    sg_settle(graph, now);
    for (unsigned position = graph->count; position > 0; --position) {
        unsigned i = graph->order[position - 1];
        struct sg_service *service = &graph->services[i];
        if (service->phase == SG_FAILED && service->pid > 0)
            return (struct sg_action){ SG_TIMEOUT, sg_token(graph, i) };
        if (service->phase != SG_RETIRING) continue;
        if (!service->term_sent) {
            if (!sg_active_dependent(graph, i))
                return (struct sg_action){ SG_TERM, sg_token(graph, i) };
        } else if (now >= service->stop_ms && now - service->stop_ms >= PID1_STOP_TERM_MS) {
            if (!service->kill_sent) return (struct sg_action){ SG_KILL, sg_token(graph, i) };
        }
    }
    if (!graph->stopping)
        for (unsigned position = 0; position < graph->count; ++position) {
            unsigned i = graph->order[position];
            struct sg_service *service = &graph->services[i];
            if (service->phase == SG_WAIT && now >= service->next_ms && sg_dependencies_ready(graph, i)) {
                if (service->generation == UINT64_MAX || service->launches == ~0u || !sg_time_budget(now, SG_READY_MS)) {
                    service->phase = SG_FAILED;
                    graph->failed = 1;
                    continue;
                }
                service->generation++;
                service->phase = SG_RESERVED;
                for (unsigned j = 0; j < graph->count; ++j)
                    service->dependency_generations[j] = graph->services[j].generation;
                struct sg_token token = { i, service->generation, 0 };
                return (struct sg_action){ SG_LAUNCH, token };
            }
        }
    return (struct sg_action){ SG_NONE, {0} };
}

static inline int sg_launched(struct service_graph *graph, struct sg_token token, int pid, uint64_t now)
{
    if (token.index >= graph->count || pid <= 1 || graph->stopping) return -1;
    struct sg_service *service = &graph->services[token.index];
    if (service->phase != SG_RESERVED || token.pid != 0 || token.generation != service->generation ||
        !sg_dependency_generation_matches(graph, token.index) || now < service->next_ms ||
        !sg_time_budget(now, SG_READY_MS) || service->launches == ~0u) return -1;
    for (unsigned i = 0; i < graph->count; ++i) if (graph->services[i].pid == pid) return -1;
    service->pid = pid;
    service->launches++;
    service->launched_ms = now;
    service->exec_confirmed = service->ready_ack = service->term_sent = service->kill_sent = 0;
    service->phase = SG_STARTING;
    return 0;
}

static inline void sg_backoff(struct sg_service *service, uint64_t now)
{
    if (service->failures < PID1_MAX_BURST) service->failures++;
    uint64_t delay;
    if (service->failures == PID1_MAX_BURST) {
        service->failures = 0;
        delay = PID1_COOLDOWN_MS;
    } else {
        delay = (uint64_t)PID1_BACKOFF_BASE_MS << (service->failures - 1);
        if (delay > PID1_BACKOFF_CAP_MS) delay = PID1_BACKOFF_CAP_MS;
    }
    service->next_ms = pid1_saturating_add(now, delay);
    service->phase = SG_WAIT;
}

static inline int sg_launch_failed(struct service_graph *graph, struct sg_token token, uint64_t now)
{
    if (token.index >= graph->count) return -1;
    sg_settle(graph, now);
    struct sg_service *service = &graph->services[token.index];
    if (service->phase != SG_RESERVED || token.pid != 0 || token.generation != service->generation) return -1;
    sg_backoff(service, now);
    return 0;
}

static inline int sg_exec(struct service_graph *graph, struct sg_token token, int success, uint64_t now)
{
    sg_settle(graph, now);
    if (!sg_matches(graph, token)) return -1;
    struct sg_service *service = &graph->services[token.index];
    if (service->phase != SG_STARTING || service->exec_confirmed) return -1;
    if (!success) { sg_retire(service, SG_CRASH, now); sg_settle(graph, now); return 0; }
    service->exec_confirmed = 1;
    if (graph->specs[token.index].mode == SG_SIMPLE ||
        (graph->specs[token.index].mode == SG_NOTIFY && service->ready_ack)) service->phase = SG_READY;
    return 0;
}

static inline int sg_ack(struct service_graph *graph, struct sg_token token, uint64_t now)
{
    sg_settle(graph, now);
    if (!sg_matches(graph, token) || graph->specs[token.index].mode != SG_NOTIFY) return -1;
    struct sg_service *service = &graph->services[token.index];
    if (service->phase != SG_STARTING || service->ready_ack) return -1;
    service->ready_ack = 1;
    if (service->exec_confirmed) service->phase = SG_READY;
    return 0;
}

static inline int sg_fail(struct service_graph *graph, struct sg_token token, uint64_t now)
{
    if (!sg_matches(graph, token)) return -1;
    struct sg_service *service = &graph->services[token.index];
    if (service->phase != SG_STARTING && service->phase != SG_READY) return -1;
    sg_retire(service, SG_CRASH, now);
    sg_settle(graph, now);
    return 0;
}

static inline int sg_signaled(struct service_graph *graph, struct sg_action action, uint64_t now)
{
    if (!sg_matches(graph, action.token)) return -1;
    struct sg_service *service = &graph->services[action.token.index];
    if (service->phase != SG_RETIRING) return -1;
    if (action.kind == SG_TERM && !service->term_sent && !sg_active_dependent(graph, action.token.index)) {
        if (!sg_time_budget(now, PID1_STOP_TERM_MS + PID1_STOP_KILL_MS)) {
            service->phase = SG_FAILED; graph->failed = 1; return -1;
        }
        service->term_sent = 1;
        service->stop_ms = now; /* Deadline begins at the actual TERM attempt. */
    } else if (action.kind == SG_KILL && service->term_sent && !service->kill_sent) {
        if (!sg_time_budget(now, PID1_STOP_KILL_MS)) {
            service->phase = SG_FAILED; graph->failed = 1; return -1;
        }
        service->kill_sent = 1;
        service->kill_ms = now;
        service->forced_stops++;
    } else return -1;
    return 0;
}

/* The runtime must consume the closed exec channel before calling this. */
static inline int sg_reaped(struct service_graph *graph, int pid, int clean_exit, uint64_t now)
{
    sg_settle(graph, now);
    for (unsigned i = 0; i < graph->count; ++i) {
        struct sg_service *service = &graph->services[i];
        if (pid <= 0 || pid != service->pid) continue;
        service->pid = 0;
        if (service->phase == SG_FAILED) {
            graph->failed = 1;
        } else if (graph->stopping || (service->phase == SG_RETIRING && service->reason == SG_SHUTDOWN)) {
            service->phase = SG_STOPPED;
        } else if (service->phase == SG_RETIRING && service->reason == SG_DEPENDENCY) {
            service->phase = SG_WAIT;
            service->next_ms = now;
        } else if (service->phase == SG_STARTING && service->exec_confirmed && clean_exit &&
                   graph->specs[i].mode == SG_ONESHOT && sg_dependencies_ready(graph, i)) {
            service->phase = SG_READY;
        } else {
            if (now >= service->launched_ms && now - service->launched_ms >= PID1_STABLE_MS)
                service->failures = 0;
            sg_backoff(service, now);
        }
        if (service->phase != SG_READY) service->exec_confirmed = service->ready_ack = 0;
        sg_settle(graph, now);
        return (int)i;
    }
    if (graph->other_exits != ~0u) graph->other_exits++;
    return -1;
}

static inline int sg_stopped(const struct service_graph *graph)
{
    if (!graph->stopping || graph->failed) return 0;
    for (unsigned i = 0; i < graph->count; ++i)
        if (graph->services[i].pid > 0 || (graph->services[i].phase != SG_STOPPED &&
            graph->services[i].phase != SG_FAILED)) return 0;
    return 1;
}

#endif
