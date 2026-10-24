# Linux chmod user fixture (isolated prototype)

The distribution-owned fixture is prepared after the frozen SDK21 candidate; it
is not part of delivered support or a completed workstation milestone. Kernel
owns checked mode-change mechanisms; OS owns these user programs and qualification
policy. The new C++ boundary requires a later SDK generation, with exact exported
artifacts; no OS build may compile the Kernel source shadow.

`tests/native/linux_chmod_runner.c` prepares user1000 files, a hardlink, symlinks,
a sparse file, an unlinked held fd10, renamed directory fd11 and detached cwd. It
then execs `/bin/musl-linux-chmod`. `tests/musl/linux_chmod.c` invokes the public
musl chmod/fchmod/fchmodat APIs and raw fchmodat2, checks metadata with statx, tests
same-mode ctime sampling, stored special permission bits, fd position/flags,
NULL/empty-path distinctions, guarded path copies, owner denial, retained node
identity and explicit fsync. Four final named-node statx snapshots are emitted
for a future independent raw-image/Linux oracle.

All ten static musl fixtures compile and link against explicit
`ARCH/debug-optimized-v1` source-build artifacts. This is build evidence only.
The native runner has not yet been compiled or executed. Actual chmod guests,
root and foreign-group fixtures, readonly/unqualified policy fixtures, independent
mode/ctime disk oracle, Linux interoperability, new SDK producer/OS consumption
and all20 Debug/Release rows remain to implement/qualify. POSIX conformance,
concurrent credentials, set-ID execution and crash durability are not established
by this fixture.
