# Guest clock drift against the host

`tests/musl/clock_drift.c` is a static musl probe for the kernel's clocks
(kernel WT1.2 slice 6, `docs/qualification/PLATFORM_CLOCKS.md`). It runs in
the guest's Linux personality, prints `CLOCK_READY arch=<arch>`, and answers
each `s` line typed on the console with one line:

```
CLOCK seq=<n> mono=<s>.<ns> real=<s>.<ns>|none
```

sampling `CLOCK_MONOTONIC` and then `CLOCK_REALTIME`; a `q` line ends it
with `CLOCK_DONE`.

`scripts/test_clock_drift.py` admits the probe only as the mode-matching
`tools/build_musl_probe.py` build of this source, installs it as
`/bin/clock-drift` in a copy of the staged rootfs, packages scratch ext4 with
`tools/mkext4.py`, boots it and starts it from the shell. It sends 13
requests spread evenly over 120 s (`--samples`, `--window`) and reads the
host's `CLOCK_MONOTONIC` and wall clock just before writing each request and
just after its answer arrives, so each guest read lies inside a known host
interval. From these it reports:

- `monotonic_drift_ppm`: the least-squares slope of guest against host
  monotonic time, minus one;
- `monotonic_drift_bound_ppm`: the strict bound from the first and last
  brackets: the guest span divided by the longest and shortest host span the
  brackets allow;
- `realtime_offset_ms` and `realtime_drift_ppm`: the guest wall clock
  against the host's, which QEMU's RTC follows.

It passes when the fitted drift is within `--limit-ppm` (100 by default) and
the strict bound reaches inside that limit, and keeps `serial.log` and
`result.json` with every sample:

```sh
python3 -B tools/build_musl_probe.py --arch ARCH --musl-build MUSL --toolchain TC \
  --source tests/musl/clock_drift.c --linker-script tests/musl/bootstrap.ld --out PROBE
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/test_clock_drift.py --arch ARCH --mode debug \
  --qemu QEMU --kernel build/ARCH/debug/distro/kernel.bin --kernel-sdk SDK \
  --rootfs-tree build/ARCH/debug/rootfs --probe PROBE/bootstrap.elf --musl-build MUSL --out OUT
```

After the samples a `b` line makes the probe run three seconds of user code
without system calls, in chunks that each outlast the kernel's 10 ms quantum
(`CLOCK_BUSY`), so the kernel's `OK_TIMER_LATENCY` line after the probe exits
also covers the timer tick that preempts user code.

The wall clock is anchored to QEMU's RTC only where the kernel qualifies one
(PL031 on arm32 and aarch64, Goldfish on rv64 and rv32). On i386, x86_64,
mips, mips64 and ppc, and on loongarch64, whose LS7A TOY oscillator nothing
enables under `-kernel`, it starts from the root's provisional timestamp, so
its offset is not a claim; its drift is the monotonic clock's. This is
single-CPU QEMU evidence: under TCG the guest counters follow QEMU's virtual
clock, which follows the host's, so the test measures the kernel's counter
calibration and conversion, not a crystal.

Result (QEMU 10.2.0, kernel and OS `feat/irq-wait-time`, ABI 77): the probe
passes on all ten profiles. The monotonic drift is within ±6 ppm on eight;
mips and mips64, whose Count frequency comes from polling Malta's RTC, measure
+3 to +22 ppm across runs with strict bounds within ±60 ppm. The
RTC-anchored wall clocks are 0.3–0.9 s behind the host's: QEMU starts both
RTCs from a whole-second date. The first runs found the PC TSC calibration
502 ppm (x86_64) and 686 ppm (i386) off; the per-profile figures and the
latency are in the kernel's `docs/qualification/PLATFORM_INTERRUPTS.md`.
