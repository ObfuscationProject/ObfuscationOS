# Concurrent stress on several vCPUs

`tests/musl/smp_stress.c` is the static musl probe for the exit gate of
kernel WT2.1 `feat/smp-bringup`: concurrent filesystem, socket and fork stress
on two to four vCPUs on x86_64, aarch64 and rv64. `smp-stress [W [R]]` forks
W workers (default and maximum 6) and releases them together; each runs R
rounds (default 40) of

- a file in its own directory under `/tmp` on the ext4 root: a known pattern
  written in two parts, `fsync`, `rename` in place, reopened, its size taken
  from `lseek`, read back, compared and unlinked;
- a second file renamed from its own directory into one directory all workers
  share, so they race that directory's updates, read back there and unlinked;
- `socketpair(AF_UNIX, SOCK_STREAM)` with a forked child: four messages of
  1–768 bytes, each answered with a transform the worker checks; the child
  exits 0 only once it reads end of file after the last one;
- a forked child that execs the probe again (even rounds) or exits directly
  (odd rounds) with a status computed from the worker and round, checked by
  `waitpid`;
- a thread that keeps writing and checking its own pages while the worker
  maps, write-protects and unmaps other regions, so the address space changes
  under a thread that may run on another CPU.

Each worker writes one record to a pipe all workers share and exits 0 only if
every check held. The parent reaps and checks every worker and prints one line:

```
SMP_STRESS_PASS arch=<arch> workers=W rounds=R files=<2WR> messages=<4WR> forks=<2WR> seconds=<s>
```

or `SMP_STRESS_FAIL arch=<arch> reason=<token>`, where a worker's failure is
`worker-<w>-round-<r>-line-<probe line>-errno-<errno>`. `forks` counts every
child the workers reaped (socket peers and exec/exit children). The kernel has
16 stream buffers system-wide (a pipe takes one, a socketpair two), which bounds
the probe to six workers; `stat`/`fstat` are refused on mounts without a
qualified stat policy, so the probe does not use them.

`scripts/test_smp_stress.py` admits the probe only as the mode-matching
`tools/build_musl_probe.py` build of this source, installs it as
`/bin/smp-stress` in a copy of the staged rootfs, packages scratch ext4 with
`tools/mkext4.py` and boots it with `command_for(..., cpus=N)` (`--smp N`,
default 2), which adds `-smp N`. It requires

- exactly one kernel `OK_SMP scope=hardware` line before the prompt; on
  x86_64, aarch64 and rv64 with N > 1 it must show `cpus=N online=N`, a
  start method other than `unsupported`, `ipi=pass` and no reason; every
  other profile, and every N = 1 run, must report `online=1
  ap_start=unsupported` with a reason;
- `SMP_STRESS_PASS` for the selected architecture with exactly the requested
  counts;
- after it, the kernel report the probe's exit prints; with more than one CPU
  online its `OK_SMP_CPUS` line must name CPUs 0..N-1 and each must have
  entered user mode during the probe (its `user_entries` above the last
  `OK_SMP_CPUS` before the probe, or nonzero without one).

`--allow-up` is for developing this tooling before AP start lands: it accepts
`online=1` on the three SMP profiles and then skips the per-CPU check. It does
not pass the gate. `result.json` records `cpus`, `smp`, `allow_up`,
`online_cpus`, the kernel lines, the per-CPU counters and
`per_cpu_user_entries` (`pass` or `skipped-up`), with `physical=false`. The
native PPC profile is single-CPU, so ppc runs only with `--smp 1`.

```sh
python3 -B tools/build_musl_probe.py --arch ARCH --musl-build MUSL --toolchain TC \
  --source tests/musl/smp_stress.c --linker-script tests/musl/bootstrap.ld --out PROBE
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/test_smp_stress.py --arch ARCH --mode debug --smp 2 \
  --qemu QEMU --kernel build/ARCH/debug/distro/kernel.bin --kernel-sdk SDK \
  --rootfs-tree build/ARCH/debug/rootfs --probe PROBE/bootstrap.elf --musl-build MUSL --out OUT
```

`qemu_distro.py --smp N` (`xmake qemu-distro --smp=N`) applies the same
`OK_SMP` rule to the ordinary boot gates.

Results (QEMU 10.2.0 TCG, kernel `feat/smp-bringup` debug SDK at kernel
commit c0f82db): three runs per configuration, 6 workers x 40 rounds, every
run `files=480 messages=960 forks=480`, with user entries and TLB shootdowns
waited for on every online CPU (the address-space phase).

| Profile | vCPUs | Runs | Guest seconds |
| --- | --- | --- | --- |
| x86_64 | 2 | 3/3 | 35.6, 36.3, 36.7 |
| x86_64 | 4 | 3/3 | 33.7, 33.8, 34.0 |
| aarch64 | 2 | 3/3 | 50.9, 47.4, 45.8 |
| aarch64 | 4 | 3/3 | 41.5, 41.4, 40.3 |
| rv64 | 2 | 3/3 | 39.0, 43.3, 40.7 |
| rv64 | 4 | 3/3 | 34.2, 33.6, 34.1 |

With one vCPU the probe passes on x86_64. `qemu_distro.py --smp N` boots the
native distro to `OK_USERLAND scope=hardware acceptance=pass` on the three
profiles with N = 2 and 4.

## Lifting the bring-up limits (kernel ABI 80)

The kernel follow-up runs Linux identity, clock and ext4 regular-file calls as
kernel sections without the big lock, routes device lines to any CPU, makes
futex user words atomic, synchronizes x86 TSCs, tags user TLB entries and can
stop and restart secondary CPUs. The gate grew with it:

- With `--smp-sections on` (the default on x86_64, aarch64 and rv64, the only
  profiles that build kernel sections) the probe's exit report must carry
  `OK_SMP_KERNEL`, `OK_SMP_KERNEL_FAMILIES` and `OK_SMP_KERNEL_DECLINES`: the
  section families cover the probe's file traffic (`fsync >= files`; `read`,
  `write`, `lseek >= 2 * files`); with two or more vCPUs sections run on two or
  more CPUs and overlap other kernel work (`concurrent`, `witnessed` > 0,
  `max_parallel >= 2`); `debug=` matches `--mode`; the assertion counters a
  release kernel keeps (`exclusive_asserts`, `section_asserts`,
  `cow_refused`, shadow mismatches) are 0, and on a debug kernel all of them.
  `--smp-sections off` (a `smp_sections=n` kernel, and the default on every
  other profile, which refuses `on`) requires no `OK_SMP_KERNEL` line. The
  receipt records QEMU's TCG thread mode from its host thread names
  (`-name ...,debug-threads=on`).
- `--require-hotplug` (a `smp_hotplug_test=y` kernel): `OK_SMP_HOTPLUG`
  counters never go back, and between the last line before the probe and the
  probe's exit report the cycles advance with `failures=0` on a secondary CPU;
  a printed `OK_SMP_HOTPLUG_BOOT` must pass every check.
- `scripts/test_futex_smp_atomic.py` runs `tests/musl/futex_smp_atomic.c`:
  FUTEX_WAKE_OP updates of one word race user atomics on the same word from
  another thread, then a copy-on-write word is checked after fork; it prints
  `FUTEX_SMP_ATOMIC_PASS ... alternated=N`. `alternated` counts alternation
  of kernel and user updates, not proven simultaneity; the lost-update check is
  the evidence.

Results (QEMU 10.2.0 TCG, kernel bf3c63c with this tree at 3ed4160, debug
unless noted, every run multi-threaded TCG with two or more vCPUs): 27 of 27
stress runs with sections (x86_64, aarch64, rv64 at 1, 2 and 4 vCPUs, three
runs each; `concurrent` 996-2027 and `max_parallel` 2-4 with two or more
vCPUs), 12 of 12 hotplug runs (two per profile at 2 and 4 vCPUs; 286-531
cycles during the probe, no failures), 6 of 6 futex runs, the
`smp_sections=n` arm and one release run per profile at 2 vCPUs. Guest
seconds with and without sections are about equal (x86_64 34.8-37.1 s with,
34.9 s without), so the section overlap brings no measurable speed-up under
TCG. Receipts: ObfuscationEvidence
`receipts/ObfuscationKernel@bf3c63c/feat/smp-bringup/smp-gates/`.
