# OS display drivers (feat/display-input-drivers)

Target: the display backends that live in the kernel today move here and are
exposed to user space through the draft `ok/uapi/display.h` from the paired
kernel worktree `feat/display-input-uapi`.

| Backend | Today | Here |
| --- | --- | --- |
| ramfb (fw_cfg DMA) | `ObfuscationKernel/include/ok/driver/qemu_virt/ramfb.hpp` | `drivers/display/ramfb.cpp`, dumb buffers only |
| virtio-gpu-pci | `ObfuscationKernel/src/driver/display.cpp` | `drivers/display/virtio_gpu.cpp`, 2D scanout, vblank via config IRQ |
| VGA text / memory framebuffer | kernel | stays in the kernel as the rescue console |

Contract: a driver publishes modes and allocates dumb buffers through the kernel
display mechanism (`ok::display::*`, to be added by the kernel worktree); it
never parses protocol bytes from user space and never owns scanout policy, which
belongs to the seat lease holder (`seatd`). Drivers are built as loadable
`.okmod` modules once `feat/module-loader` lands; until then they link into
`distro_image` like `drivers/virtio/block.cpp`.

Exit gate (OS side): a user-space program opens `/dev/display0`, allocates a
buffer, maps it, draws and presents; a second program cannot read the first
program's buffer or present without the seat lease.
