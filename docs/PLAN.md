# ObfuscationOS implementation plan

Status: active plan, written 2026-10-24 from the architecture review. The target
and the M0–M12 exit gates are in [plans/README.md](plans/README.md); the
per-requirement state is the generated [plans/STATUS.md](plans/STATUS.md). This
document is the OS-side execution plan, organised as worktrees paired with the
kernel worktrees in ObfuscationKernel `docs/PLAN.md`.

## Rules

1. One worktree per topic under `../wt/os-<topic>`, branch `feat/<topic>`,
   `fix/<topic>` or `chore/<topic>`. Lifetime at most 4–6 weeks.
2. An OS worktree never compiles kernel sources. It consumes the paired kernel
   worktree's export with
   `xmake f --kernel_sdk=../kernel-<topic>/build/sdk/<arch>/<mode>`.
3. Fast lane: x86_64, arm32, ppc with `kernel-sdk-check`, `distro_image`,
   `rootfs-ext4` and `qemu-distro --fs=ext4 --require-native`. Before merge: all
   ten profiles (`xmake arch-matrix`) and the four primary Release profiles.
4. Receipts go to ObfuscationEvidence under `receipts/ObfuscationOS@<sha>/<branch>/`;
   per-slice notes to `docs/qualification/`; `docs/plans/STATUS.md` is regenerated,
   never edited.
5. Decisions in `docs/decisions/` bind this plan: musl is the primary userland
   (0001), the kernel-space desktop is frozen (0002), evidence lives outside the
   product tree (0003).

## P0 (done on `chore/land-2026-10`)

- Landed five weeks of uncommitted work as eight area commits; tag
  `sdk-abi74-uapi0.16`.
- F1 repaired without changing the SimpleFS format: `rootfs-simplefs` omits the
  eight ext4-only service programs (`tools/mksimplefs.py --omit`), the unfiltered
  38-entry root is still rejected.
- CI: three-architecture fast lane (x86_64, arm32, ppc) consuming the
  SysToolchain release archives (installed package cached per architecture,
  QEMU runtime libraries installed, 60/90-minute job timeouts), SDK artifact per
  architecture.
- `xmake/README.md` documents which Lua files are included and which are
  standalone fixture projects; the two fixture projects carry header comments.
- `qemu-distro --require-native` re-passes the saved `systoolchain_dir` and
  `kernel_sdk` options when it reconfigures; the previous partial `xmake f`
  dropped them and resolved (and built from source) the systoolchain package.
- 46 per-slice notes moved to `docs/qualification/`; `IMPLEMENTATION_PROGRESS.md`
  trimmed to the current continuation, history frozen in ObfuscationEvidence;
  `STATUS.md` generated from the ledger; decision records 0001–0003.

## P1

### WT1.5 `feat/musl-primary` (L)

Scope
- Static musl 1.2.5 sysroot for all ten profiles through the Linux personality,
  built by an xmake task from the pinned archive (needs the `<arch>-linux-musl`
  toolchain family from SysToolchain 0.2.0; until then the documented
  freestanding-GCC recipe in `docs/qualification/SHARED_MUSL_BUILD.md` is the
  fallback).
- Port a POSIX shell and a utility set (toybox or busybox; licence review
  recorded in a decision record) and make them the default `/bin` contents.
- okcrt keeps `init`, `login`, `posix-check`, `sync` and the rescue utilities;
  no new okcrt wrappers beyond what those need.
- Rootfs profiles: `ext4` (full), `simplefs` (rescue subset), `release`.

Exit gate: on ten profiles a musl `sh` runs scripts with expansion, pipelines,
redirection and command lists; the utility set passes its own test suite in the
guest. Depends on kernel WT1.1 (quotas); job control arrives with WT2.2.

Scaffold (merged to main from `feat/musl-primary`):
- `ports/README.md`, `ports/{musl,dash,toybox}/port.json`: pinned-source descriptors
  (archive hash, licence, dependencies, qualified profiles, state). musl 1.2.5 is
  pinned from `tools/musl_source.py`; dash and toybox stay `planned` until the
  licence decision record selects the shell and utility set.
- `tools/ports.py` (validate, order) and `tests/tools/test_ports.py`.
Next: `xmake port-build --name=musl --arch=...` driving the descriptor with the
`<arch>-linux-musl` toolchain family; rootfs profiles `ext4`, `simplefs`, `release`.

### WT1.6 `chore/sdk75-consumer` (S)

Consume the ABI 75 SDK from kernel WT1.1/WT1.2: `tools/kernel_sdk.py` admission,
`check_uapi.py`, SDK header lists, `tests/tools/test_kernel_sdk.py`. Exit: all
twenty architecture/mode SDKs pass admission; `distro_image` links on ten profiles.

## P2

### WT2.2 `feat/getty-login` (M)

`login` and a getty run on a PTY with termios from kernel WT2.2; console login
stops being opt-in once ten profiles pass. Session, foreground group and
SIGHUP-on-hangup tests move from hosted fixtures to guest execution.

### WT2.3 `feat/net-services` (L)

IRQ-driven virtio-net path, `netd` with a DHCP client, DNS resolver replacing the
hosts-only `resolved`, `sntp`, an `ip`-style configuration tool. Exit:
guest-to-host HTTP fetch under loss/reordering on ten profiles.

### WT2.4 `fix/mkfs-e2fsprogs` (M)

Replace `tools/mkext4_journalled.py`'s pinned Linux kernel image with e2fsprogs
1.47.2 (`mke2fs`, `tune2fs`, `e2fsck`) and make the journalled image the default
`rootfs-ext4` output once kernel WT2.4 lands. Keep the non-journalled image as
`rootfs-ext4-legacy` for the retained qualification lanes.

### WT2.5 `feat/drivers-as-modules` (M)

Build `drivers/virtio/*` and `drivers/net/*` as relocatable `.okmod` modules
against the module loader from kernel WT2.5; `distro_image` stops linking them
statically. Exit: load / unload / unload-refusal tests on ten profiles.

### WT2.6 `feat/display-input-drivers` (L)

virtio-gpu, virtio-input, ramfb, PS/2 and USB HID drivers move here from the
kernel and are exposed through the display/input UAPI from kernel WT2.6; `seatd`
hands leases to the compositor. Exit: a user-space program allocates a buffer and
presents it; input events reach user space.

Scaffold (merged to main from `feat/display-input-drivers`): `drivers/display/README.md` and
`drivers/input/README.md` record which kernel backends migrate (ramfb, virtio-gpu,
virtio-input, PS/2, USB HID), the contract against the draft `ok/uapi/display.h`
and `input.h`, and the exit gate. Code follows the kernel display mechanism.

## P3

### WT3.1 `feat/shared-musl-loader` (L)

`ld.so`, TLS, `dlopen`, pthread cancellation on ten profiles; fix the MIPS PIC
runtime (`DT_TEXTREL`) and PPC secure-PLT blockers; hosted libstdc++ for
applications.

### WT3.2 `feat/compositor` (XL)

Wayland compositor (libwayland, xdg-shell, wl_shm, pixman software renderer),
seat/session manager, greeter, panel. `modules/system-gui` rendering is disabled
once the compositor reaches the completion marker; renderer tests stay as visual
fixtures. Depends on WT2.6, WT3.1, WT2.2.

### WT3.3 `feat/desktop-apps` (L)

Terminal (PTY), Files, Editor, Settings, Tasks, Logs as separate processes;
toolkit; FreeType + HarfBuzz with UTF-8/CJK text. Exit: the novice workflow
(login, network, copy, save, reopen, lock, shut down) passes scripted.

### WT3.4 `feat/packages-installer` (L)

Package format and repository, installer and recovery image, update rollback.

### WT3.5 `feat/services-complete` (M)

`devd`, `seatd`, `sessiond`, `netd` integration; log rotation; generic shutdown
backends (ACPI, PSCI, SBI, board) on ten profiles replacing the x86_64-only
PC/8042 and PIIX4 backends.

## P4

M10 ext4 feature matrix, M11 physical reference machines, M12 ledger closure and
release media. Each opens its own worktree; none closes a milestone gate without
the evidence described in `plans/README.md` section 8.
