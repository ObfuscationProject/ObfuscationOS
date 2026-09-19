# External Virtio block driver

`drivers/virtio/block.cpp` implements a real disk driver in ObfuscationOS. The
factory `os::drivers::probe_virtio_block()` returns a static-lifetime
`ok::driver::BlockDevice *` and does not change disk contents during discovery.
It consumes the exported Kernel SDK interface; the OS never compiles Kernel
sources to provide the driver.

The transport is selected at compile time. ARM32/AArch64 and RV32/RV64 scan their
QEMU virt Virtio MMIO apertures and support legacy version 1 and modern version
2. x86/i386 and LoongArch use the modern PCI capabilities of transitional or
modern Virtio block devices. PCI discovery currently scans bus 0. The x86 block
BARs are assigned within `0x30000000..0x32000000`, inside the existing kernel
identity map and above the supported runner's RAM. LoongArch uses
`0x50000000..0x52000000`, separately from the GUI input BAR window.

Use `virtio-blk-device` on the ARM/RISC-V runners and `virtio-blk-pci` on x86 and
LoongArch. MIPS/MIPS64 and PPC currently return `not_found`; their PCI host bridge
support is a separate task. No architecture falls back to an in-memory fake disk.

The driver negotiates `VIRTIO_F_VERSION_1` on modern transports and the block
read-only/flush features. It exposes 512-byte sectors, submits up to 4 KiB per
request and implements `VIRTIO_BLK_T_IN`, `OUT` and `FLUSH`. A split descriptor
queue and bounce buffer have static lifetime, so timeout failure never releases
memory that a device may still access. It checks capacity, sector alignment,
completion indices, descriptor ids, returned lengths and the device status byte.
Legitimate device errors may complete with only the status byte; they return an
I/O error while leaving the queue usable. Successful reads require the full data.
A malformed completion or bounded polling timeout marks the device failed;
subsequent requests cannot reuse its queue. A device is writable only when it
also supports FLUSH. The driver does not format a disk.

The current implementation polls one queue on the boot CPU. It relies on the
coherent DMA model and identity/direct mappings of these QEMU profiles. Physical
board discovery, IOMMU mappings, noncoherent cache maintenance, interrupt-driven
I/O, hardware SMP synchronization and multiple disks are not claimed.

## SDK consumer hardware tests

For example, with a matching freshly exported debug SDK:

```sh
python3 scripts/test_virtio_block.py \
  --arch x86_64 \
  --kernel-sdk ../ObfuscationKernel/build/sdk/x86_64/debug \
  --toolchain ../ObfuscationKernel/toolchains/x86_64-elf \
  --output /tmp/virtio-block-x86
```

The same runner supports `i386`, `arm32`, `aarch64`, `rv32`, `rv64` and
`loongarch64`; use the matching SDK and toolchain. Add `--modern-mmio` on ARM or
RISC-V to exercise MMIO version 2 independently of QEMU's legacy default.

The probe validates SDK contents and compiler identity, extracts exactly one
`boot.S.o` member from the SDK boot archive, and compiles only OS-owned sources.
It creates its own scratch disk, checks multi-request reads/writes and queue
wrapping, flushes, starts a new VM and reads the persisted bytes, then checks a
read-only disk, a one-shot QEMU `blkdebug` read error with queue recovery, and an
absent device. The host compares the entire disk after
every VM and rejects changes outside the intended 16-sector region. These are
direct block-driver tests; filesystem/VFS/POSIX persistence is validated by the
separate distribution integration tests.
