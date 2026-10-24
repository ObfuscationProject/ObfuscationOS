# OS input drivers (feat/display-input-drivers)

Target: input backends move out of the kernel and emit `ok_input_event` records
(`ok/uapi/input.h`, draft) through per-device queues owned by the kernel input
mechanism.

| Backend | Today | Here |
| --- | --- | --- |
| virtio-input (MMIO and PCI) | `ObfuscationKernel/include/ok/driver/qemu_virt/virtio_input.hpp`, `virtio_pci_input.hpp` | `drivers/input/virtio_input.cpp`, IRQ-driven |
| PS/2 keyboard and mouse | `ObfuscationKernel/src/driver/bus_input.cpp` | `drivers/input/ps2.cpp` |
| USB HID (xHCI) | kernel model | `drivers/input/usb_hid.cpp`, after a real xHCI driver |

Rules: the kernel keeps bounded per-device queues and reports drops; the seat
lease holder is the only reader; the rescue console keeps a kernel-side keyboard
path so diagnostics work without user space.
