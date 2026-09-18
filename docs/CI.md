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
Broader packaging checks remain available through `xmake distro-test`. The model
tests retain their separate scope; their boot markers alone do not prove native
execution. Native execution does not imply hardware SMP or runtime module loading.
