# Native Virtio network device boundary

The external OS driver in `drivers/virtio/net.cpp` supports a single modern
Virtio net device on coherent QEMU RAM. A statically selected transport handles
MMIO on aarch64, arm32, rv64 and rv32, or PCI on i386, x86_64, loongarch64,
mips, mips64 and ppc. The Ethernet queue, DMA ownership ledger, frame bounds,
restart and error retirement logic is shared without a runtime virtual
interface.

PCI discovery scans bus zero, slots 0–31 and functions 0–7 using the platform
configuration mechanism also used by the external Virtio block driver. It
requires a Virtio net ID, an explicit mapped memory BAR window, valid and
nonoverlapping modern common, notify, ISR and net-device capabilities, and a
bounded queue notification offset. It rejects legacy-only devices. Both
transports require VERSION_1 and a stable MAC, negotiate no checksum or
segmentation offloads, and use two eight-entry split rings. Once the kernel's
interrupt service runs, starting the link binds the device's line
(`virtio_mmio_line`, `pci_intx_line`), clears `VIRTQ_AVAIL_F_NO_INTERRUPT`
and the PCI INTx disable bit (again after a restart, whose reset set them),
and posts the kernel's network event source once for frames used before. The
bottom half then reads the ISR and, when the device had raised its interrupt,
signals a waiting transmit and posts the source, so the kernel reads the RX
queue and the TX ledger only after the device interrupted. Without the
service or a line, or with the `virtio_polling` build option, the boot CPU
polls. A reset must acknowledge
DMA quiescence before static queue storage is reused.

`xmake virtio-net-test` invokes the SDK-only probe for any of the ten retained
profiles. It requires an explicit architecture/mode Kernel SDK and matching
cross compiler. The native scenario uses QEMU's framed socket backend with a
separate local peer. The peer compares all 96 transmitted frames byte for byte,
returns their Ethernet replies, and the guest verifies the received frames.
The other scenarios require absence to report not-found and a legacy-only
device to report unsupported. Receipts record SDK, tool, source, image and
serial hashes, external captures and actual execution status. A compile-only
switch makes no execution claim. The older `virtio-net-mmio-test` entry point
remains available for the four MMIO profiles.

This is a raw Ethernet device boundary. There is no IP stack, userspace socket
service, IRQ-driven path, noncoherent-DMA proof, physical hardware
qualification, SMP qualification or distro desktop network integration.
