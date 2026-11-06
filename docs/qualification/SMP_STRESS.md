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
  `waitpid`.

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
commit 4e93bc9): three runs per configuration, 6 workers x 40 rounds, every
run `files=480 messages=960 forks=480` with user entries on every online CPU.

| Profile | vCPUs | Runs | Guest seconds |
| --- | --- | --- | --- |
| x86_64 | 2 | 3/3 | 49.4, 54.4, 49.9 |
| x86_64 | 4 | 3/3 | 72.6, 92.8, 92.4 |
| aarch64 | 2 | 3/3 | 50.6, 42.5, 34.0 |
| aarch64 | 4 | 3/3 | 39.8, 37.3, 37.0 |
| rv64 | 2 | 3/3 | 30.5, 31.7, 30.2 |
| rv64 | 4 | 3/3 | 33.1, 32.2, 30.2 |

With one vCPU the probe passes on x86_64 in 42.6 s. `qemu_distro.py --smp N`
boots the native distro to `OK_USERLAND scope=hardware acceptance=pass` on the
three profiles with N = 2 and 4. The workers are single-threaded processes, so
the gate exercises no TLB shootdown; the kernel's execution probes do.
