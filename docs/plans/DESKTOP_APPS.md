# Desktop, graphics and system applications

Status: proposed implementation design. Parent: [workstation plan](README.md).
The selected visual direction is a restrained light desktop, cool gray and blue,
with clear typography. The goal is a usable system, not another privileged demo.

## G00. Current implementation and migration boundary

Current sources:

- [`modules/system-gui`](../../modules/system-gui): greeter/session, dock,
  application views and prelinked `KernelExtension` callbacks.
- [Current GUI contract](../GUI.md) and [renderer screenshots](../gui/README.md):
  ASCII bitmap text, 480x270 logical framebuffer, hosted renderer verification.
- Kernel [`GuiDesktopService`](../../../ObfuscationKernel/include/ok/gui/desktop.hpp):
  eight 4096-byte in-kernel buffer slots and a 256-byte clipboard; these are not
  shared mappings between isolated clients.
- Kernel [driver abstractions](../../../ObfuscationKernel/include/ok/driver/driver.hpp)
  and [visual tokens](../../../ObfuscationKernel/include/ok/gui/theme.hpp).

Native `/init` and shell execution do not make the current GUI views native
applications. Replace the OS extension's ordinary desktop path with userspace
services and real app executables. Preserve renderer tests as visual regression
fixtures and preserve the Kernel compositor for bootstrap/rescue diagnostics.
Do not migrate user desktop policy into Kernel while doing this.

## G01. Process and privilege architecture

```text
Kernel: display/input objects, VM/shared memory, UNIX sockets, clocks, credentials
    | device descriptors / validated ioctls / poll / mmap
OS external drivers: virtio-gpu or framebuffer, virtio-input/USB/HID
    | only descriptors granted to the active seat
OS system services: session and seat manager, authentication, device broker
    | credential-checked session socket and revocable device leases
User session: compositor -> desktop shell / panels / notifications
    | Wayland over AF_UNIX with descriptor passing
Independent processes: Terminal, Files, Editor, Settings, Tasks, other apps
```

The compositor is a dedicated user process, not a kernel module. A greeter runs
in a separate restricted session; the session manager controls the transition
to the user's compositor and revokes the old seat. Ordinary clients cannot
obtain global input, arbitrary scanout access or another user's display socket.
Only a small broker performs privileged display/session/account operations.

The desktop shell and notification process may initially share one userspace
process to limit complexity. Apps remain separate from it from their first
graphical milestone. A shell crash must not terminate the compositor or apps.
Sessions are supervised by the service manager described in
[network and services](NETWORK_SERVICES.md).

## G02. Kernel device and buffer contracts

Proposed interfaces live under Kernel `include/ok/uapi/display.h`, `input.h` and
OS `drivers/display`, `drivers/input`. Use fixed-width records with size/version,
reserved fields, checked offsets and explicit pixel/event formats; never export
native pointers, `std::span` or C++ vtables to userspace.

### Display

Provide enumeration, connector/mode query, buffer allocation/import, CPU mapping,
atomic present, completion events and lease revocation. A present describes
output ID, mode generation, buffer handle, pitch, pixel format and damage;
Kernel validates overflow, range, ownership and mode compatibility before
queueing it. Begin with one XRGB8888 output, then ARGB8888, multi-output and
hotplug. Advertise real capabilities; do not claim a vblank/page-flip when the
backend performs a synchronous framebuffer copy.

Buffers hold page references until the last mapping, pending presentation and
device reference are released. A completion fence makes reuse explicit. Final
open-description release or explicit lease revocation cancels future submissions
and drains/cancels queued work before freeing pages; closing one duplicated or
passed FD does not invalidate the remaining holders. Device reset fails pending
requests with a defined error and invalidates
the relevant generation. Kernel controls physical mappings; applications cannot
map arbitrary RAM or device MMIO.

The CPU renderer is available on all ten profiles. Virtio-gpu 2D is an OS driver
target; ramfb/simple framebuffer remains a bootstrap fallback. Accelerated
rendering requires a separately scoped GPU memory/synchronization/command
validation interface and a Mesa port. Do not expose unrestricted DMA submission
to ordinary clients to get acceleration quickly.

### Input

Provide timestamped key/scancode, pointer, wheel and touch events with device ID,
sequence and hotplug state. Separate physical key events from composed text.
Use monotonic timestamps; record keymap/layout in the session, not in raw driver
events. Bounded queues coalesce motion but preserve key/button transitions;
overflow sends a resynchronization event and key-state snapshot to prevent
stuck keys. Removal synthesizes/releases state through a defined reset path.

Start with a native event record and a small OS backend. Add an evdev-compatible
subset and qualify libinput/libxkbcommon integration without claiming complete
Linux input ioctl compatibility. Seat access is revocable on lock/logout/VT
switch. Input never broadcasts to unfocused app or background serial shell.

### Ownership of fallback graphics

Use a single display-owner state machine:
`boot-diagnostics -> greeter -> user-session -> rescue`, with explicit acquire,
release, revoke and failed-owner recovery. Kernel rescue cannot race the user
compositor writing the same scanout. A panic path may force ownership after
stopping normal presentation; it must use preallocated memory and avoid locks
that could be held by the failed path. Basic diagnostics retain serial output.

## G03. Client protocol and event loop

Use **Wayland**, initially `wl_compositor`, `wl_shm`, `wl_seat`, `wl_output`,
`wl_data_device_manager`, `wl_subcompositor` and `xdg-shell`, plus the stable
protocols actually needed by the desktop. Pin protocol/library versions and
generate bindings as part of the OS build. Use libwayland with an OS event-loop
backend; qualify its actual `poll`/`epoll`, timer and ancillary-message needs.
AF_UNIX, `sendmsg`/`recvmsg`, `SCM_RIGHTS`, peer credentials, close-on-exec,
shared `mmap` and functional wakeup semantics are prerequisites.

Reasons: a maintained wire protocol, existing clients and explicit buffer
lifetime semantics reduce future toolkit lock-in. Wayland does not provide a
window manager, rendering library, login, permissions, full accessibility or
application toolkit; those still need the components below. XWayland is a later
compatibility port, not a dependency for this native desktop.

Implementation requirements:

- Negotiate protocol versions, reject malformed lengths/object IDs and bound
  client objects, pending messages, FDs, mapped memory and queued commits.
- Verify peer identity and session socket permissions. Never trust a PID/UID
  embedded in an app message as an authorization credential.
- `wl_shm` uses real file-backed shared memory, not Kernel GUI buffer slots.
  Support the required backing-file lifecycle; use sealed buffers where
  available and libwayland-compatible SIGBUS-safe access for untrusted,
  truncatable pools. Validate offset/stride/height arithmetic before touching
  pixels. Revalidate resized pools and track mapping generations.
- Treat pixel bytes as untrusted mutable data even after a commit. Keep all
  control metadata in compositor-owned memory; snapshot/copy or use protected
  access as needed. A malicious client's concurrent writes must not corrupt
  the compositor's object graph.
- Follow configure/ack/commit ordering, surface role restrictions, frame
  callbacks and buffer release. A displayed buffer cannot be recycled before
  its release/completion conditions hold.
- Limit work per client per event-loop turn; disconnect abusive clients without
  starving input or presentation. A slow reader must not block the server.
- On client death, detach surfaces, selection offers and buffers; release
  resources only after outstanding compositor/device references expire.
- Clipboard and drag-and-drop transfer MIME-typed data through pipes/FDs with
  limits, cancellation and negotiated action. There is no global Kernel string
  clipboard for ordinary application contents. Clear sensitive state on logout.
- Screenshots, global shortcuts, input injection, screen capture and remote
  control require explicit session policy via a broker/portal.

## G04. Compositor and rendering design

Proposed OS layout:

```text
services/compositor/       outputs, seats, surfaces, scene, event loop, rendering
services/session/          login/session/seat ownership (service-plan integration)
desktop/shell/             launcher, task switcher, panels, workspace policy
desktop/notifications/     bounded notification history and user actions
lib/gui/                   widgets, layout, text, styling, Wayland client binding
lib/graphics/              images, paths, pixel backend and caches
protocols/                 pinned Wayland XML and approved private extensions
apps/gui/<application>/    isolated graphical applications
drivers/display/           external display/GPU device modules
drivers/input/             external input drivers
tests/gui/                 visual fixtures plus native interaction tests
```

Keep protocol objects, scene nodes and output rendering separate. Scene nodes
hold geometry, clipping, opacity, transforms and surface generation, not app
business state. Maintain per-output damage rectangles/tiles. Repaint damaged
areas and schedule presentation from frame deadlines/completion, not a busy
loop. Bound damage list growth by merging or falling back to full-output repaint.

Use a proven software pixel library such as pixman for initial composition;
qualify endian/word-size/SIMD configuration per architecture. Use templates for
in-house pixel-format/blend/span kernels only when profiling justifies them.
Runtime polymorphism is appropriate for software/GPU output backends, not for
each pixel or widget property lookup. Keep a generic scalar renderer for rare
architectures and reference-image comparisons.

Perform rendering from a coherent scene snapshot. Device completion and client
request handlers cannot free buffers referenced by that snapshot. Initially use
one compositor event/render thread; scale with immutable render jobs and bounded
worker queues after correctness and SMP support. Avoid a global lock held across
socket I/O or driver submission.

Support true output sizes from 800x600 upward, multiple monitors, 1x/1.25x/1.5x/2x
scaling and rotation in staged gates. Use logical coordinates consistently;
round device pixel boundaries deterministically. Begin with sRGB composition
and document color behavior; advanced color/HDR requires a separate capability.

## G05. Toolkit, text and visual specification

Port FreeType, HarfBuzz, a pinned Unicode data set and suitable licensed Latin/CJK
fonts. Add bidi and grapheme/word segmentation support using qualified libraries;
do not assume UTF-8 decoding alone handles international text. Use font fallback,
shaping, line breaking, selection, caret movement and IME preedit/commit. Keep
font parsing in user processes and bound glyph/image caches. Locale strings and
font packages belong in OS, while Kernel diagnostics retain a small embedded
font independent of user filesystem state.

The toolkit owns layout, focus, actions, menus, text editing, selection, scroll,
dialogs, accessibility nodes and application state. Start with box/grid layout,
labels/buttons/text fields/lists/tree/table/tab/splitter/scroll container. Lists
virtualize large directories and process tables. Rendering and application I/O
run independently so a slow disk/network cannot freeze input.

Reuse current colors as a seed, not current low-resolution geometry:

| Token | Initial value or rule |
| --- | --- |
| Canvas / surface | `#EDF1F7` / `#FFFFFF` |
| Text / secondary | `#24324A` / `#65748B`; verify contrast for actual size and background |
| Accent / selected background | `#326BD8` / `#E7EEFD` |
| Border | `#D6DEEB`, reinforced where contrast communicates state |
| Spacing | 4 px base, common 8/12/16/24 px gaps at logical 1x |
| Type | 14-16 px body, 12-13 px metadata, 20-28 px page titles; scalable user setting |
| Controls | 32-36 px compact pointer controls; 44 px touch targets where touch is supported |
| Focus | Visible high-contrast outline on every keyboard-reachable action |
| Shape | Small consistent corner radii, subtle shadows only for stacking/context |
| Motion | Brief optional transitions; respect reduced-motion and disable under pressure |
| Status | Text/icon alongside color; never color-only success/error |

Publish tokens as neutral OS theme data and a generated small Kernel subset;
do not make ordinary apps include private Kernel drawing headers. Kernel rescue
shares the visual vocabulary but exposes diagnostics only. OS desktop defaults
to an unprivileged user, with clear menus, a searchable launcher, visible running
apps, clock/network/volume/power status and a predictable task switcher. Offer
light/dark/high-contrast variants after the default is consistent.

## G06. Application specifications

Each app is a real ELF process with its own address space, credentials and
bounded resource use. All have keyboard navigation, localized labels, help,
loading/empty/error states, close handling and session-aware state persistence.

| App | Required useful behavior | Dependencies and acceptance |
| --- | --- | --- |
| Terminal | PTY-hosted real shell, UTF-8, ANSI/VT escape subset with documented coverage, resize, scrollback, copy/paste, tabs, search, font control | PTY/termios/job control/signals; run interactive editor, Ctrl-C/Ctrl-Z, fg/bg and resize without losing child state |
| Files | Home/volumes/sidebar, breadcrumbs, history, list/grid, sort/search, mkdir, copy/move/link/rename/trash/restore, permissions/properties, open-with | Async VFS operations; safe name handling, symlink policy and progress/cancel; copy beyond RAM size, disk-full recovery, open directory during rename |
| Text Editor / Notes | Real file open/save/save-as, UTF-8/CJK editing and IME, selection/search/undo/redo, line ending handling, autosave recovery | Save temporary file in destination directory, preserve intended metadata, fsync, rename and sync parent; do not report success on flush failure; files persist outside `/tmp` |
| Settings | Display/scaling, input/layout, accessibility, appearance, timezone/locale, network, accounts, sound/power where hardware supports them | Validate changes through dedicated service APIs; timed display rollback, privilege prompt for system changes, atomic config persistence |
| Tasks | Per-process CPU/RSS/I/O, service view, filter/sort, details, graceful terminate then force action | Kernel counters and permission-checked signals; distinguish totals/rates/capacity, no fabricated SMP utilization |
| Logs / Diagnostics | Structured service/boot/app logs, search/filter/export, disk health and network status, crash report review | Read-only authorized log API, bounded history, secret redaction and user-controlled export |
| Network panel | Link state, addresses/routes/DNS, Ethernet configuration, reconnect/test; Wi-Fi only when its service/driver gate passes | Network daemon API; accurate offline/error state; no blocking UI while DHCP/DNS times out |
| Software / Updates | Signed package metadata, search/details, dependency plan, download, install/remove, progress and rollback | Package service, durable transactions, verified repository keys and ABI/arch constraints; interrupted install leaves recoverable state |
| Disk utility / Installer | Enumerate disks, inspect/mount/unmount, guided install, safe format/partition confirmation, recovery and backup tools | Brokered storage privileges, pinned e2fsprogs/partition tools, exact device identity and busy checks; destructive UI operations require clear user confirmation |
| About / Help | Actual build/architecture, support status, license notices, keyboard guide, searchable offline help | Generated release manifest; never label preview features fully supported |
| Session UI | Greeter, authentication, lock, switch user, logout/reboot/shutdown with unsaved-work handling | Auth/session service, device lease revocation, lock protocol and clean service/storage shutdown |

File manager and editor use UTF-8 for display but preserve arbitrary valid POSIX
filename bytes through an escaped presentation where decoding fails. Do not
round-trip a filename through lossy Unicode conversion. Clipboard/file transfer
uses descriptors or names with explicit directory context and access checks.
Trash is per-user and same-filesystem when possible; cross-filesystem move uses
copy, verified durability, then deletion, with honest non-atomic semantics.

Audio is a separate device/service path: Kernel stream/timing mechanisms, OS
external audio drivers and a user sound service with per-client volume/mixing.
Its absence cannot be hidden behind a decorative volume control. Printing,
browser/media suites and XWayland are additional ports; the base desktop target
does not claim to implement a browser engine or arbitrary GPU/Wi-Fi hardware.

## G07. Accessibility, security and lifecycle

- Expose semantic roles, labels, state, text ranges and actions to an
  accessibility service; qualify a screen-reader protocol/client rather than
  merely exporting a placeholder tree. Every app must be usable keyboard-only.
- Support high contrast, text scaling, reduced motion, sticky keys, adjustable
  repeat/pointer settings and IME candidate-window placement.
- Lock is a trusted compositor/session state. A client cannot paint over or
  dismiss it, retain a global input grab or take screenshots while locked.
  Killing the lock client must keep the display locked or terminate the session.
- Privilege prompts identify the requested operation and caller via a trusted
  service. An app's claim of identity is not sufficient. Avoid running the
  desktop as root for convenience.
- Store user settings under user-owned config/state/data directories with
  restrictive modes. Persist atomically; version schemas; ignore or quarantine
  malformed settings and start with usable defaults.
- Closing an app asks about unsaved work; force termination is explicit. A
  compositor crash may disconnect clients, but autosaved documents survive and
  the supervisor returns to a safe login/session state. Do not promise seamless
  Wayland reconnection unless the client toolkit implements and tests it.
- Session restart never restarts failed Kernel code as though it were an
  isolated userspace service. Recovery limitations remain explicit.

## G08. Delivery stages and test gates

| Stage | Deliverable | Required evidence |
| --- | --- | --- |
| G1 after M1/M2 | Display/input FDs, shared memory, revocable seat and real wakeups | Native mapping/permission/buffer-lifetime tests; invalid dimensions/overflow/close during scanout; no input leak |
| G2 after M3/M5 | Software Wayland compositor, two basic clients | Each client has distinct PID/address space; real descriptor transfer; client death/truncation/malformed protocol does not kill peers |
| G3 | Fonts, toolkit and Terminal | CJK/RTL/grapheme selection fixtures; actual PTY shell/editor; keyboard focus/resize/clipboard tests |
| G4 with M7 | Greeter/session/lock, desktop shell, persistent Files/Editor/Settings | Unprivileged login, permissions, durable save/reboot, disk-full and service-failure UX |
| G5 | Remaining system apps, accessibility, multiple outputs/scaling | Screen reader and keyboard task completion, hotplug, scale transitions, package/installer recovery |
| G6 with M11/M12 | Acceleration where supported, long-running desktop, ten-profile qualification | Stress/leak/latency reports and visual/manual workflow evidence, separated by emulator and physical device |

Keep hosted golden-image/layout tests for deterministic rendering. Add native
QEMU input automation, compositor/client PID tracing and screenshot checks;
screenshots alone cannot prove isolation. Test at least narrow/wide windows,
1x/2x scaling, long localized strings, missing fonts, empty/full storage and
disconnected services. Track memory after repeated open/close and hotplug cycles.

Human acceptance tasks: a new user logs in without instructions, finds a file,
creates a folder, edits/saves/reopens a document, configures a connection, finds
the failing service's log, changes text size, locks and logs out. Observe task
completion and confusion, then repair navigation and wording. No numeric
benchmark substitutes for these usability checks.

## References to qualify during implementation

- [Wayland architecture](https://wayland.freedesktop.org/architecture.html) and
  [protocol documentation](https://wayland.freedesktop.org/docs/html/).
- [wayland-protocols](https://gitlab.freedesktop.org/wayland/wayland-protocols).
- [FreeType](https://freetype.org/), [HarfBuzz](https://harfbuzz.github.io/),
  [Unicode specifications](https://www.unicode.org/versions/latest/).

These are upstream design references, not claims that those packages have been
ported or that their latest releases were qualified in this planning change.
