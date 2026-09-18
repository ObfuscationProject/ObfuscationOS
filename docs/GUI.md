# System GUI

ObfuscationOS owns the system desktop. ObfuscationKernel owns the basic compositor,
window services, platform presentation and kernel diagnostics. OS builds consume
an exported, matching architecture/mode Kernel SDK; there is no kernel checkout
inside the OS repository and no kernel source compilation in the OS build.

## Implementation and boot

`modules/system-gui/external_module.hpp` and `.cpp` contain the greeter, session
selection, dock and window renderers. `system_gui_runtime.hpp` and `.cpp` own app
paths, package lookup, launch policy, process cleanup and compositor recovery.
They use `ok::KernelExtension` through composition, not inheritance from Kernel.
The optional C factory `ok_boot_extension()` registers the statically linked
extension during boot. A standalone kernel boots its basic GUI without this hook.
In release builds the extension starts independently of `kernel_gui`; that option
controls the standalone kernel diagnostic GUI, not the OS desktop.

The package `modules/system-gui/system-gui.okmod`, staged as
`/boot/modules/system-gui.okmod`, configures the prelinked desktop. The OS runtime
owns the fallback package and SimpleFS path mapping. `OK_SYS_LOAD_MODULE` parses
metadata and dispatches it to this extension; it does not relocate or execute
newly compiled native code. The C++ extension interface requires the matching
Kernel SDK, compiler version and ABI flags.

The desktop provides root/user selection, Enter/Space or mouse login, a status
panel and dock, and windows for Tiny Shell, Settings, Tasks, Notes and About.
App files live under `/bin`. The current app path validates ELF metadata and
creates selected-user scheduler records while the OS runtime renders the windows.
It is a model of user application integration, not evidence that those ELF
instructions execute in an isolated user address space. A user GUI drawing ABI
and real executable module loading remain future work.

## Build

Export a Kernel SDK from the sibling kernel repository, then configure OS against
it. Use the same mode, architecture and compiler in both builds:

```sh
cd ../ObfuscationKernel
xmake f -y -m debug -a x86_64
xmake build -y kernel-sdk
cd ../ObfuscationOS
xmake f -y -m debug -a x86_64 --kernel_sdk=../ObfuscationKernel/build/sdk/x86_64/debug
xmake build -y distro_image
xmake build -y rootfs-simplefs
xmake qemu-distro-window --fs=simplefs
```

An existing local SysToolchain can be selected explicitly with
`--systoolchain_dir=<installation>`. SDK validation rejects architecture, mode,
compiler or ABI mismatches before linking.

## Tests

`modules/system-gui/system_gui_tests.cpp` owns the five desktop integration model
tests migrated from the kernel: package activation, user selection/login, dock
focus, app process/window close, and recovery after diagnostic GUI cleanup.
Additional regression checks ensure repeated startup/package loading preserves
the greeter selection, logged-in credentials, app processes and windows, while
invalid same-name packages are still rejected.
Debug OS images invoke them through `KernelExtension::self_test` after the core
suite. Their fixture app ELFs use the disposable test disk. A successful run emits
`OK_EXTENSION_TEST scope=model result=pass` before `OK_TEST_PASS`; failures prevent
the overall pass marker. Release images do not execute these fixtures.
Both modes emit the OS-owned `OK_SYSTEM_GUI boot=complete` marker only after
successful desktop startup. In debug mode this also requires all self-tests and
their cleanup to have succeeded; a kernel boot marker alone cannot pass the OS
QEMU runner.
