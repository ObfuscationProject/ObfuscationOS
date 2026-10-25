# CI

The workflow has two isolated jobs. `kernel-sdk` checks out the independent
ObfuscationKernel repository, builds `kernel-sdk` for x86_64/debug, and uploads
the export. `distro` checks out only ObfuscationOS and downloads that artifact;
it has no kernel source checkout, gitlink, or recursive-submodule requirement.

The distro job validates manifest architecture/mode, compiler ABI, artifact
hashes, UAPI and libc, host compatibility models, rootfs formats, and links the
OS-owned GUI extension to the exported kernel/runtime archives. Cross-repository
changes to the SDK producer and consumer must be published together before CI
can consume the new kernel target.

Local equivalent after exporting the matching kernel SDK:

```sh
xmake f -y -m debug -a x86_64 --kernel_sdk=/path/to/kernel-sdk
xmake -y -b artifact-test
xmake -y -b kernel-sdk-check
xmake -y -b uapi-test
xmake -y -b libc-test
xmake -y -b compat-test
xmake -y -b distro_image
xmake -y -b linux-driver-compat
xmake -y -b rootfs-simplefs
xmake -y -b rootfs-ext4
xmake qemu-distro --fs=simplefs --require-native --timeout=30
```

CI requires the OS-owned System GUI completion marker, actual native timer
preemption, and the debug init/POSIX/external-pipeline acceptance marker in QEMU.
It also boots a real Virtio-backed ext4 root twice, saves and synchronizes a note,
reads it after restart, and checks the disk with `e2fsck` and `debugfs`. This
uses the explicitly supported non-journalled ext4 format; it does not establish
crash consistency or physical hardware support. The local architecture matrix
contains ten native profiles; the CI fast lane runs x86_64, arm32 and ppc, with
the ext4 persistence check on x86_64 only.
`distro-test` still builds ext4 images on MIPS/MIPS64/PPC but explicitly skips
their native ext4 boot check until those platforms have a block transport.
Broader packaging checks remain available through `xmake distro-test`. The model
tests retain their separate scope; their boot markers alone do not prove native
execution. Native execution does not imply hardware SMP or runtime module loading.

`artifact-test` runs every suite under `tests/tools` against the SDK artifact,
with `OK_TEST_KERNEL_SDK`, `OK_TEST_KERNEL_ARCH` and `OK_TEST_KERNEL_MODE` set.
Suites that also compare against the kernel itself (its SDK producer
`tools/export_sdk.py` or its source headers) import `tests/tools/kernel_checkout.py`
and skip without a sibling `ObfuscationKernel` checkout, which CI does not have.
They run in the umbrella workspace (`python3 scripts/workspace.py cross-tests`,
also part of `distro-all` and `matrix`), where `OK_REQUIRE_KERNEL_CHECKOUT=1`
makes a missing checkout an error; `OK_KERNEL_CHECKOUT` points them at a paired
`wt/kernel-*` worktree.
