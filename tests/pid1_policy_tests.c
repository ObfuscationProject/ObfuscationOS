#include "../apps/init/pid1_policy.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static void crash(struct pid1_policy *policy, int pid, uint64_t launch,
                  uint64_t finish, uint64_t next)
{
    assert(pid1_policy_launch_due(policy, launch));
    pid1_policy_launched(policy, pid, launch);
    assert(!pid1_policy_launch_due(policy, finish));
    assert(pid1_policy_reaped(policy, pid, finish));
    assert(policy->next_launch_ms == next);
    assert(!pid1_policy_launch_due(policy, next - 1));
    assert(pid1_policy_launch_due(policy, next));
}

static void restart_budget(void)
{
    struct pid1_policy policy;
    pid1_policy_init(&policy);
    crash(&policy, 10, 0, 1, 51);
    crash(&policy, 11, 51, 52, 152);
    crash(&policy, 12, 152, 153, 353);
    crash(&policy, 13, 353, 354, 2354);
    assert(policy.launches == PID1_MAX_BURST);
    assert(policy.consecutive_failures == 0);
    crash(&policy, 14, 2354, 2355, 2405);
    assert(policy.launches == 5);
}

static void adopted_unknown_and_stable_reset(void)
{
    struct pid1_policy policy;
    pid1_policy_init(&policy);
    pid1_policy_launched(&policy, 20, 100);
    assert(!pid1_policy_reaped(&policy, 21, 101));
    assert(!pid1_policy_reaped(&policy, 22, 101));
    assert(policy.other_exits == 2 && policy.service_pid == 20);
    assert(policy.phase == PID1_RUNNING && policy.launches == 1);
    assert(pid1_policy_reaped(&policy, 20, 5100));
    assert(policy.consecutive_failures == 1 && policy.next_launch_ms == 5150);
    pid1_policy_launched(&policy, 23, 5150);
    assert(pid1_policy_reaped(&policy, 23, 5160));
    assert(policy.consecutive_failures == 2 && policy.next_launch_ms == 5260);
}

static void shutdown_races(void)
{
    struct pid1_policy policy;
    pid1_policy_init(&policy);
    pid1_policy_shutdown(&policy, 40);
    assert(policy.phase == PID1_STOPPED);
    assert(!pid1_policy_launch_due(&policy, UINT64_MAX));
    pid1_policy_init(&policy);
    pid1_policy_launched(&policy, 30, 0);
    pid1_policy_shutdown(&policy, 100);
    pid1_policy_shutdown(&policy, 200);
    assert(policy.stop_started_ms == 100);
    assert(!pid1_policy_force_due(&policy, 1599));
    assert(pid1_policy_force_due(&policy, 1600));
    pid1_policy_force_sent(&policy);
    assert(!pid1_policy_force_due(&policy, 1700));
    assert(!pid1_policy_stop_expired(&policy, 2099));
    assert(pid1_policy_stop_expired(&policy, 2100));
    assert(!pid1_policy_reaped(&policy, 31, 2100));
    assert(policy.phase == PID1_STOPPING);
    assert(pid1_policy_reaped(&policy, 30, 2101));
    assert(policy.phase == PID1_STOPPED && policy.forced_stops == 1);
    assert(!pid1_policy_launch_due(&policy, UINT64_MAX));
}

static void saturation(void)
{
    struct pid1_policy policy;
    pid1_policy_init(&policy);
    pid1_policy_launched(&policy, 40, UINT64_MAX - 1);
    assert(pid1_policy_reaped(&policy, 40, UINT64_MAX));
    assert(policy.next_launch_ms == UINT64_MAX);
    pid1_policy_shutdown(&policy, UINT64_MAX);
    assert(policy.phase == PID1_STOPPED);
}

static void allocation_failures(void)
{
    struct pid1_policy policy;
    pid1_policy_init(&policy);
    pid1_policy_launch_failed(&policy, 100);
    assert(policy.phase == PID1_WAIT_LAUNCH && !policy.service_pid && !policy.launches);
    assert(policy.next_launch_ms == 150);
    pid1_policy_launch_failed(&policy, 150);
    assert(policy.next_launch_ms == 250 && !policy.launches);
    pid1_policy_launched(&policy, 50, 250);
    pid1_policy_launch_failed(&policy, 260);
    assert(policy.service_pid == 50 && policy.phase == PID1_RUNNING && policy.launches == 1);
}

int main(void)
{
    restart_budget();
    adopted_unknown_and_stable_reset();
    shutdown_races();
    saturation();
    allocation_failures();
    puts("PID1_POLICY_MODEL_PASS restart=5 unknown=2 shutdown=bounded saturation=pass");
    return 0;
}
