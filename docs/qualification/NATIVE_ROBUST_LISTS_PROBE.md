# Native robust-list probe

`tests/musl/native_robust_lists.c` uses the pinned musl raw clone trampoline and
`thread_syscall4` for child syscalls. It tests registration and ordered getter
copies, clone and raw fork registration reset, four ordinary owner-death wakes,
four pending-owner-zero wakes, malformed head registration/exit, and unregister.
The child uses no libc TLS operations. These are raw Linux ABI checks, not a
pthread or priority-inheritance implementation claim.

Each owner waits 20 ms on a private futex after the parent's release handshake.
The parent requires its distinct shared-operation wait to return zero. Ordinary
owner death must leave exactly `FUTEX_WAITERS | FUTEX_OWNER_DIED`; pending-owner-zero
must leave zero. No other code wakes that word. The delay provides scheduling
margin, while the successful wait proves a queued waiter was woken. Premature
exit fails with EAGAIN or an outer timeout; it is never accepted as a wake.

`tools/qualify_native_robust_lists.py` retains source/SDK/compiler/sysroot/probe
hashes, builds a fresh SDK-only distribution consumer, creates a private ext4
image, and runs the probe twice between independent native pipelines. It requires
SDK27 and accepts all ten architecture profiles and both Debug/Release modes.
Each probe command must return to the shell's frame and entry-stack baselines,
with fresh privileged entries/syscalls and at least ten lease reservations and
releases: probe launch, eight clone peers and one fork child. The exact complete
success marker must occur once per probe command; final accounting must follow
the marker. This is serialized CPU0 coverage, with mapped stack canaries, no SMP
or physical-hardware claim.

Use an explicit output path outside the mutable source tree. Freeze after all
source changes are complete; a changed, missing or extra input invalidates it.

```sh
python3 -B tools/qualify_native_robust_lists.py freeze --output /tmp/robust-sources.json
python3 -B tools/qualify_native_robust_lists.py run \
  --arch x86_64 --mode debug --kernel-sdk /explicit/sdk/x86_64/debug \
  --sdk-manifest-sha256 EXACT_SHA256 --toolchain /explicit/toolchain/x86_64-elf \
  --compiler-sha256 EXACT_SHA256 --qemu /explicit/qemu-system-x86_64 \
  --qemu-sha256 EXACT_SHA256 --musl-build /explicit/musl/x86_64/debug \
  --musl-manifest-sha256 EXACT_SHA256 --source-inventory /tmp/robust-sources.json \
  --source-inventory-sha256 EXACT_SHA256 --output /tmp/robust-x86-debug
```

PowerPC additionally requires `--ppc-clang` with the explicit Linux-targeted
frontend. The other profiles are i386, aarch64, arm32, rv64, rv32, loongarch64,
mips, mips64 and ppc; the qualifier never chooses a target from a wildcard.

`tests/tools/test_native_robust_lists.py` tests synthetic corruptions only.
Cross-compiling the probe and running it on a Linux reference host are separate
checks. A guest is qualified only by a completed SDK27 run receipt with retained
serial, identity, disk, filesystem and accounting evidence.
