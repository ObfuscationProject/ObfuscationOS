# Native signal-mask probe

`tests/musl/native_signal_masks.c` exercises raw `rt_sigprocmask` through the
existing target assembly syscall trampoline. The kernel wire structure uses
native `unsigned long` words: 16 bytes for MIPS O32/N64 and 8 for all other
profiles. Public libc `sigset_t` is deliberately not used as the wire structure.

The probe checks block, unblock and replacement; SIGKILL/SIGSTOP removal; high
bits and word boundaries; null input ignoring `how`; size-before-input and
input-before-how error ordering; unchanged state on invalid input/how; committed
state after an old-mask output fault; and aliased input/output buffers.
On invalid input/how, the output buffer starts with a mask distinct from the
current mask and must remain unchanged. Invalid how must precede an invalid
output pointer. These assertions reject premature old-mask output writes.

A raw clone peer inherits mask A, replaces it with B, and forks from that actual
caller. The fork child observes B and changes independently. The original leader
checks A after both descendants exit. Clone children use raw syscalls and avoid
libc/TLS operations. They do not fabricate pthread structures.

The same ELF has `after-leader-exec` and `after-peer-exec` observer modes. Two
separate fork children perform leader and nonleader exec, respectively. The
nonleader installs mask D while the waiting leader retains A. Both callers
first attempt a missing image and require their mask to remain unchanged, then
exec the probe's exact path. The observer checks the expected C/D mask and
leader identity before producing a unique caller-specific marker. The original
parent waits for zero exit and emits final success only after both observers.
There is no `/proc` dependency, installed helper binary, or signal delivery.

`tools/qualify_native_signal_masks.py` requires exact SDK28 and retains all ten
architecture choices and Debug/Release modes. It consumes exported SDK artifacts
and never opens a Kernel checkout or builds Kernel source. It packages a private
ext4 root, runs the probe twice between native pipelines, retains source/compiler/
sysroot/ELF/transitive dependency/serial/disk/fsck evidence, and rechecks inputs.

The evidence parser requires exact complete boot/storage/output lines, one final
prompt per contiguous command, optional exact echoes, no foreign command output,
ordered unique leader/nonleader observer markers preceding final success, and
frame/entry-stack retirement after success. Each run requires at least six new
lease reservations and releases: probe launch, inheritance clone/fork, the two
exec processes, and the nonleader exec peer. Image replacement reuses its leader
lease. Final accounting must return to the live shell baseline.

```sh
python3 -B tests/tools/test_native_signal_masks.py
python3 -B tools/qualify_native_signal_masks.py freeze --output /absolute/new/source-inventory.json
python3 -B tools/qualify_native_signal_masks.py run --help
```

The `run` command uses explicit architecture, mode, SDK, GCC toolchain, QEMU and
musl build paths and their checksums, plus the exact frozen source inventory.
PowerPC also needs `--ppc-clang`. The packaged binary is
`/bin/native-signal-masks`; its main invocation has no arguments. A reference
host can invoke the ELF by its absolute path for self-exec.

Hosted parser tests, cross-compilation, Linux reference execution and SDK28
system execution are separate evidence. This bounded feature does not establish
handlers, delivery, pending signals, sigreturn frames, pthread support, SMP,
physical hardware or M3 completion. Masks do not make a process isolated.
