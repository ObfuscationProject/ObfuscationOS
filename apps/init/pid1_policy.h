#ifndef OK_PID1_POLICY_H
#define OK_PID1_POLICY_H

#include <stdint.h>

/* One foreground service is the first, deliberately bounded N2 policy. */
enum pid1_phase {
    PID1_WAIT_LAUNCH,
    PID1_RUNNING,
    PID1_STOPPING,
    PID1_STOPPED
};

struct pid1_policy {
    enum pid1_phase phase;
    int service_pid;
    unsigned launches;
    unsigned consecutive_failures;
    unsigned other_exits;
    unsigned forced_stops;
    uint64_t launched_at_ms;
    uint64_t next_launch_ms;
    uint64_t stop_started_ms;
    int stop_kill_sent;
};

enum {
    PID1_MAX_BURST = 4,
    PID1_BACKOFF_BASE_MS = 50,
    PID1_BACKOFF_CAP_MS = 400,
    PID1_COOLDOWN_MS = 2000,
    PID1_STABLE_MS = 5000,
    PID1_STOP_TERM_MS = 1500,
    PID1_STOP_KILL_MS = 500
};

static inline uint64_t pid1_saturating_add(uint64_t a, uint64_t b)
{
    return UINT64_MAX - a < b ? UINT64_MAX : a + b;
}

static inline void pid1_policy_init(struct pid1_policy *policy)
{
    *policy = (struct pid1_policy){ .phase = PID1_WAIT_LAUNCH };
}

static inline int pid1_policy_launch_due(const struct pid1_policy *policy, uint64_t now_ms)
{
    return policy->phase == PID1_WAIT_LAUNCH && now_ms >= policy->next_launch_ms;
}

static inline void pid1_policy_launched(struct pid1_policy *policy, int pid, uint64_t now_ms)
{
    policy->service_pid = pid;
    policy->launches++;
    policy->launched_at_ms = now_ms;
    policy->phase = PID1_RUNNING;
}

static inline void pid1_policy_retry(struct pid1_policy *policy, uint64_t now_ms)
{
    if (policy->consecutive_failures < PID1_MAX_BURST)
        policy->consecutive_failures++;
    if (policy->consecutive_failures == PID1_MAX_BURST) {
        policy->consecutive_failures = 0;
        policy->next_launch_ms = pid1_saturating_add(now_ms, PID1_COOLDOWN_MS);
    } else {
        uint64_t delay = (uint64_t)PID1_BACKOFF_BASE_MS <<
            (policy->consecutive_failures - 1);
        if (delay > PID1_BACKOFF_CAP_MS) delay = PID1_BACKOFF_CAP_MS;
        policy->next_launch_ms = pid1_saturating_add(now_ms, delay);
    }
    policy->phase = PID1_WAIT_LAUNCH;
}

/* Allocation/fork failed: no PID was published and no launch was counted. */
static inline void pid1_policy_launch_failed(struct pid1_policy *policy, uint64_t now_ms)
{
    if (policy->phase == PID1_WAIT_LAUNCH && !policy->service_pid)
        pid1_policy_retry(policy, now_ms);
}

/* Returns 1 only for the foreground service. An adopted orphan is still reaped. */
static inline int pid1_policy_reaped(struct pid1_policy *policy, int pid, uint64_t now_ms)
{
    if (pid != policy->service_pid || pid <= 0) {
        policy->other_exits++;
        return 0;
    }
    policy->service_pid = 0;
    if (policy->phase == PID1_STOPPING) {
        policy->phase = PID1_STOPPED;
        return 1;
    }
    if (now_ms >= policy->launched_at_ms &&
        now_ms - policy->launched_at_ms >= PID1_STABLE_MS)
        policy->consecutive_failures = 0;
    pid1_policy_retry(policy, now_ms);
    return 1;
}

static inline void pid1_policy_shutdown(struct pid1_policy *policy, uint64_t now_ms)
{
    if (policy->phase == PID1_STOPPED || policy->phase == PID1_STOPPING)
        return;
    policy->phase = policy->service_pid ? PID1_STOPPING : PID1_STOPPED;
    policy->stop_started_ms = now_ms;
}

static inline int pid1_policy_force_due(const struct pid1_policy *policy, uint64_t now_ms)
{
    return policy->phase == PID1_STOPPING && policy->service_pid > 0 &&
        !policy->stop_kill_sent && now_ms >= policy->stop_started_ms &&
        now_ms - policy->stop_started_ms >= PID1_STOP_TERM_MS;
}

static inline void pid1_policy_force_sent(struct pid1_policy *policy)
{
    policy->stop_kill_sent = 1;
    policy->forced_stops++;
}

static inline int pid1_policy_stop_expired(const struct pid1_policy *policy, uint64_t now_ms)
{
    return policy->phase == PID1_STOPPING && policy->stop_kill_sent &&
        now_ms >= policy->stop_started_ms &&
        now_ms - policy->stop_started_ms >= PID1_STOP_TERM_MS + PID1_STOP_KILL_MS;
}

#endif
