# Private Kernel SDK ABI65 source contract draft

This document describes an unqualified source proposal. No SDK65 artifacts or
execution receipts are supplied. Root retains SDK64 installation authority and
later exact source composition. Existing historical reports and global progress
do not change.

The proposed source combines the selected ABI64 runtime-mountpoint base with the
audited memfd write-seal overlay and the additional global ABI65 overlay. Its
source selection SHA256 is
`578c1f38dd26ee6cd30485bb9b0b712667a95cae31c63d9e5e227a21b8cf7efd`;
the write-seal overlay manifest SHA256 is
`7f2c2ab59282578af718a4a92df3f2133f272a3b64a13bfcc568054191ddfca2`;
the independent write-seal source audit SHA256 is
`e8ae673f5501325ede347060f356ef170b70e1d20d56df8c12c5cf43c22d3180`.
The draft lane's input, delta and path/hash reports define exact replacement
paths. A write-seal overlay alone still has global ABI64 and is not this contract.

The exported SDK manifest `abi_version`, compiled
`kernel_module_abi_version`, and all six feature markers must be 65:
`ext4_common_module_abi`, `ext4_directory_create_module_abi`,
`native_tcp_module_abi`, `native_udp_module_abi`, `unix_pathname_module_abi` and
`native_shared_file_module_abi`. Both producer and consumer require these exact
typed markers; positive fixtures use 65 and existing future refusal fixtures
use 66. Retired 64 and earlier-version refusals are retained. Dynamic compiled
module manifests inherit 65 from the module constant. Text `.okmod` `version=1`
is the module's metadata version, not the SDK ABI.

The native/Linux shared-file profile is
`bootcpu-volatile-sealed-size-write-eager-pages-v2`, with supported seal mask 15.
This inherits the bounded volatile write-seal proposal: first WRITE requires
zero aliases and independent frame pins; descriptor writes and writable shared
mapping admission are refused after sealing. FUTURE_WRITE remains unsupported.
The other feature profile strings and resource bounds are unchanged.

UAPI remains 0.7.0; manifest schema remains 1; Session counters remain 64 bits and
shared files remain bounded to 64 pages. Architecture names, ELF formats,
compiler flags, native syscall numbers and all unrelated 64/65 values are not
module-version fields. No process, scheduler, init/adoption, ownership or
teardown change is introduced by the global ABI overlay.

Kernel mechanisms and essential platform support remain Kernel-owned. OS
policy, desktop, applications, external extensions/drivers and Linux driver
adaptation remain OS-owned. Build Kernel separately and consume its exact
architecture/mode SDK artifacts with explicit named hashes and compiler checks.
There is no source-header fallback or Kernel source compilation from OS.
Freestanding C++23, xmake and static dispatch remain required. Metadata parsing
does not load code; process records do not establish isolation.

Preserve all ten Kernel profiles (i386, x86_64, aarch64, arm32, rv64, rv32,
loongarch64, mips, mips64, ppc), both debug/release modes, and the four supplied
musl profiles (x86_64, aarch64, rv64, loongarch64). Retain the wider OS profile
definitions without claiming ten supplied libc profiles.

The existing shared-files and pathname acceptance scripts require an explicit
`--expected-abi 65` in a future ABI65 recipe. Their stale exact 59/exact 63 gates
are migrated, including the pathname target receipt ABI. Socketpair and rights
scripts retain their caller-selected manifest equality check and must also be
given 65 for this SDK. Kernel target probes with `--flag-sdk-abi` retain explicit
caller selection. No command is invoked by this document or this draft lane.

The inherited shared-files runner/observer still describes the old paired
native/static suite. The separate write-seal probe is not wired into it.
New exact image inputs, runner/observer recipe, store-fault observations, cleanup
and per-row receipts require review before execution. Existing external ABI64
recipes and successful prefixes remain immutable. Their results cannot qualify
ABI65. Standalone Kernel, SDK producer, explicit OS consumer, generator, model,
twenty native rows and four supplied musl profile checks are all pending here.

Inherited control limits remain visible: SDK manifest ABI comparison is numeric
equality rather than a JSON integer-type rule, and the module-manager fixture
has no explicit prior 64 case (its dynamic future+1 becomes 66). Source marker
typing and the SDK/profile prior 64 controls remain separate. The Linux reference
does not establish mprotect EACCES, and proposal source/marker strings do not
establish actual protection faults. This draft claims neither hardware/manual
acceptance nor full M0-M12 completion.
