# System GUI

For the proposed isolated user-space compositor, toolkit and system applications,
see the [desktop implementation plan](plans/DESKTOP_APPS.md). This document
describes the current prelinked implementation, not that future architecture.

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
panel and launchers for Terminal, Settings, Tasks, Notes, About and Files. The
shared visual system uses a light canvas, cool gray surfaces and blue accents at
480 x 270 logical pixels. See [the workspace guide and real renderer screenshots](gui/README.md).
Terminal provides a small set of filesystem commands; Settings changes the
application accent; Tasks reads live scheduler records; Files navigates directories
and previews text; Notes supports editing and Ctrl+S.

GUI notes are saved as `/tmp/notes-root.txt` or `/tmp/notes-user.txt` with mode 0600.
Reopening a window reloads its file, but `/tmp` does not persist across reboot.
The native `notes` CLI has a separate default path, `/home/notes.txt`, and accepts
an explicit path. It saves through an exclusive temporary file in the same
directory, checks the file sync and close, replaces the destination, and checks
the parent directory sync. Before replacement, a failure preserves the existing
document. A later failure reports that replacement occurred without reporting a
completed save. This bounded path requires a caller-owned directory without group
or other write permission and an ordinary caller-owned single-link destination.
The final metadata check does not provide writer locking or inode identity.
These interfaces currently use the existing ASCII bitmap font.

App files live under `/bin`. The GUI launch path validates ELF metadata and creates
selected-user scheduler records while the prelinked OS extension renders and handles
the windows in kernel service context. This GUI path does not execute those ELF
instructions in an isolated address space, and the Terminal window is not the native
`oksh` process. Native console user execution through `/init` is a separate runtime
path. A user GUI drawing ABI and loadable executable GUI extensions remain future work.

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

Run the CLI's 40 scratch-file and injected-failure controls with an unused
output directory:

```sh
xmake notes-save-check --output=/tmp/notes-plain
xmake notes-save-check --output=/tmp/notes-sanitized --sanitize
```

The second command enables ASan/UBSan with leak checking disabled. These hosted
checks are separate from `scripts/test_notes_workflow.py`, which exercises basic
English editing and file management through native shell processes in QEMU.
The shell workflow uses RAM/SimpleFS and does not qualify reboot persistence,
ext4 power-loss durability or isolated graphical applications.

`modules/system-gui/system_gui_tests.cpp` owns the five desktop integration model
tests migrated from the kernel: package activation, user selection/login, dock
focus, app process/window close, and recovery after diagnostic GUI cleanup.
Additional regression checks ensure repeated startup/package loading preserves
the greeter selection, logged-in credentials, app processes and windows, while
invalid same-name packages are still rejected. Notes checks verify saved contents,
0600 mode and selected-user ownership, including input arriving after another
process was selected by the scheduler. Files checks cover launcher focus and
navigation. Hosted rendering uses the production compositor and input path; the
[screenshot fixture](../tests/gui/render_workspace.py) links only OS sources against
a checksum-validated Kernel SDK.
Debug OS images invoke them through `KernelExtension::self_test` after the core
suite. Their fixture app ELFs use the disposable test disk. A successful run emits
`OK_EXTENSION_TEST scope=model result=pass` before `OK_TEST_PASS`; failures prevent
the overall pass marker. Release images do not execute these fixtures.
Both modes emit the OS-owned `OK_SYSTEM_GUI boot=complete` marker only after
successful desktop startup. In debug mode this also requires all self-tests and
their cleanup to have succeeded; a kernel boot marker alone cannot pass the OS
QEMU runner.
