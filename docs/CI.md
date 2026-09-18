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
xmake qemu-distro --fs=simplefs --timeout=30
```

CI waits for the final OS-owned System GUI boot marker in QEMU. Broader
integration remains available through `xmake distro-test`. Model tests and
boot markers do not claim hardware/user-mode execution coverage.
