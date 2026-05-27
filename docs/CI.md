# Continuous Integration

The root CI workflow lives at `.github/workflows/ci.yml`. It validates the distro side of the project:

- checks out the kernel submodule recursively;
- installs xmake and host image-building dependencies;
- builds or restores the x86_64 freestanding userland toolchain;
- runs the kernel submodule baseline check;
- validates the exported UAPI and libc shim;
- builds SimpleFS and EXT4 root filesystem images, including `/bin/kmodload`
  and the staged `/boot/modules/system-gui.okmod` OS-side system GUI module
  package.

The first CI baseline intentionally avoids graphical QEMU. The kernel submodule has its own heavier QEMU workflow, while the root repository focuses on the SDK, user programs, and image assembly needed by ObfuscationOS.

Run the closest local equivalent with:

```sh
xmake f -c -m debug -a x86_64
xmake -y -b kernel-submodule-check
xmake -y -b uapi-test
xmake -y -b libc-test
xmake -y -b rootfs-simplefs
xmake -y -b rootfs-ext4
```
