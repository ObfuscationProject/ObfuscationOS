# Ordinary signal qualification

`tools/qualify_native_signal_production.py` builds a fresh OS consumer using an
explicit exported Kernel SDK. It never opens or compiles a Kernel checkout.
The admitted service is SDK31 `native_signal_profile=bounded-bootcpu-v1`, with
the canonical `OK_NATIVE_SIGNAL_RUNTIME` definition and no private signal
fixture. Both ordinary Debug and Release are supported across all ten Kernel
architecture profiles. This qualification does not expand the four-architecture
distribution support matrix.

The runner reuses the unchanged static-musl programs `native_child_exit.c`
and `native_child_exit_pressure.c`, one selected program per fresh qualification.
It executes the program twice, with a native `hello | cat` pipeline before and
after. The policy journal verifies all 18 cases, including child notification,
ignore/NOCLDWAIT observations, coalescing, fork and exec inheritance. The pressure
journal verifies three bounded fork-pressure waves, nine failed fork attempts,
and three successful recovery children. All emitted siginfo payloads must match
the complete 128-byte target layout, including padding and target byte order.

Ordinary kernels still emit generic image, frame and entry-stack records.
The collector uses their existing strict decoders, requires image admission at
the appropriate initial/exec boundaries, fresh resource activity and return to
the shell resource baseline. Ordinary Debug also emits generic child/pipe waits;
their existing typed parsers check complete bounded records. Release rejects
these Debug-only records. Private signal, pipe-origin and child EXIT/REAP
diagnostics are rejected. Command offsets refer to the original serial bytes;
only the existing exact known-banner/child-wait normalization is admitted.

These observations do not prove internal blocked reads, physical autoreap
identity, unpublished fork-rollback identity, the kernel's exact first queued
sender, or a complete internal reclaim ledger. They do not qualify SMP,
physical hardware, full POSIX/Linux conformance, or fault injection. Those
claims remain separate from the ordinary user-observation campaign.

The explicit `--mode debug|release` is the Kernel SDK and distribution mode.
The separately required `--musl-mode debug` describes the pinned static libc
actually linked into the probe. A Release kernel run with this archive is
recorded as Release kernel/distribution plus Debug musl; it is never reported as
Release musl. The archive's source pin, architecture, compiler ABI, compiler
tools and runtime are revalidated. The MIPS64 binary128 supplement is checked
against the musl mode. The probe's existing compilation recipe uses `-O2` in
both kernel modes; the exact command and dependencies are retained.

Run `freeze --output /explicit/new/source-inventory.json` first, then `run` with
explicit `--arch`, `--mode`, `--musl-mode debug`, `--probe child-exit-policy` or
`--probe child-exit-pressure`, source inventory and digest, SDK path and manifest
digest, toolchain and C++ compiler digest, QEMU path and digest, musl build and
manifest digest, and a new `--output` directory outside the source tree.
MIPS64 additionally requires the explicit binary128 build and manifest digest;
PPC requires its explicit Clang frontend. `run --help` lists the exact options.

The runner preserves copied sources/SDK/sysroot, transitive probe dependencies,
commands, original serial, command byte boundaries, initial/final disk images,
filesystem checks and input hashes. Inputs are rechecked after execution.
`executed=true` means a complete probe BEGIN, FAIL or PASS was observed; it is
retained even if the invocation subsequently fails. The raw BEGIN count is
distinct from invocation starts: the policy guest emits 18 BEGIN records per
invocation. `native_execution_accepted=true` is set only after both command
collections, filesystem checks and final input revalidation pass.

`tests/tools/test_native_signal_production.py` provides compiler-free synthetic
journal, command, SDK capability, libc-mode and partial/failing-execution
controls. Its results are parser/model evidence. No hosted test or transcript
replay by itself constitutes fresh target execution.

## Accepted automated campaign

The integration campaign has forty fresh ordinary qualifiers (all ten profiles,
Debug and Release, policy and pressure), each executing two commands. A separate
twenty-qualifier private Debug campaign checks the deeper lifecycle joins.
One earlier x86_64 Debug representative executed two additional commands;
these are outside the eighty-command complete ordinary matrix count.

MIPS64 must emit exactly `N64_SIGNAL_PLATFORM_PASS before-cxx=1 fp=fr1` as the
first complete normalized boot record. Missing, duplicate, late, wrapped,
malformed, cross-profile and private platform records are rejected. The final
collector tightened this admission after the native campaign; all forty
original receipts replay with identical complete execution objects. Original
source and collector hashes remain in the receipts. This replay creates no new
native execution. The first matrix's forty inventory-schema rejections happened
before compilation or QEMU and remain preserved as failed attempts.

`tests/tools/audit_native_signal_production.py` retains six independent hosted
methods: 40 positive, 1,884 negative and 1,500 observation controls. They test
parsing and accurate failed-execution reporting, not hardware or POSIX breadth.
Physical and manual desktop acceptance remain deferred.
