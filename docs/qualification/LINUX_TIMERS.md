# Linux interval timers on the guest

`tests/musl/linux_timers.c` is a static musl probe for the kernel's Linux
interval timers (kernel `docs/abi/linux-timers.md`, WT1.2 slice 5). It runs
in the guest's Linux personality and prints one line:

```
TIMERS_PASS arch=<arch> checks=<n> oneshot_late_us=<µs> overrun=<n> thread_calls=<n> realtime=<abstime|absent>
```

or `TIMERS_FAIL arch=<arch> code=<case><check> detail=<value> errno=<errno>`.
The cases, in order:

- `alarm` returns the old remainder rounded up and shares `ITIMER_REAL`.
- A 50 ms one-shot `ITIMER_REAL` wakes `sigsuspend` with `SIGALRM` as
  `SI_KERNEL`; `oneshot_late_us` is how far after 50 ms the handler ran.
- A 20 ms periodic `ITIMER_REAL` delivers five `SIGALRM`s to `sigwaitinfo` in
  at least 100 ms; disarming returns the old interval.
- `SIGALRM` interrupts a one-second `nanosleep` with `EINTR` and the remainder.
- `SIGEV_SIGNAL` carries `SI_TIMER`, `si_timerid`, the `sival_ptr` and a zero
  overrun; a deleted timer is `EINVAL`.
- A 10 ms periodic timer whose signal stays blocked for 105 ms reports its
  missed intervals as `si_overrun` (`overrun=`, at least 3), the same value
  from `timer_getoverrun`, and a remaining time within one interval; deleting
  it leaves no signal pending.
- `SIGEV_NONE` reports a decreasing remainder and zero once expired.
- musl's `SIGEV_THREAD` calls its function on the helper thread at least three
  times; deleting the timer ends the detached helper (`thread_calls=`).
- With a wall clock, a `TIMER_ABSTIME` `CLOCK_REALTIME` timer expires at the
  requested wall-clock time (`realtime=abstime`).
- A forked child has no `ITIMER_REAL` and no POSIX timer; across `exec` the
  probe (re-run as `exec-child`) keeps `ITIMER_REAL` and loses its POSIX timer.

`scripts/test_linux_timers.py` admits the probe only as the mode-matching
`tools/build_musl_probe.py` build of this source, installs it as
`/bin/linux-timers` in a copy of the staged rootfs, packages scratch ext4 with
`tools/mkext4.py`, boots it and runs the command from the shell. It requires
the `TIMERS_PASS` line for the selected architecture and the kernel's
`OK_TIMERS` counters after the probe exits, and keeps `serial.log` and
`result.json`:

```sh
python3 -B tools/build_musl_probe.py --arch ARCH --musl-build MUSL --toolchain TC \
  --source tests/musl/linux_timers.c --linker-script tests/musl/bootstrap.ld --out PROBE
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/test_linux_timers.py --arch ARCH --mode debug \
  --qemu QEMU --kernel build/ARCH/debug/distro/kernel.bin --kernel-sdk SDK \
  --rootfs-tree build/ARCH/debug/rootfs --probe PROBE/bootstrap.elf --musl-build MUSL --out OUT
```

Result (QEMU 10.2.0, kernel and OS `feat/irq-wait-time`, ABI 77): the probe
passes on all ten profiles; the per-profile lines are in the kernel's
`docs/qualification/PLATFORM_INTERRUPTS.md`. This is single-CPU QEMU
evidence. Timer granularity is the kernel's 100 Hz tick, so the lateness
figures are tick-sized and are not a latency measurement; `ITIMER_VIRTUAL`,
`ITIMER_PROF` and CPU-time clocks are not exercised because the kernel
refuses them.
