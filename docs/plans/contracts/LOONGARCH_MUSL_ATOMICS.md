# LoongArch64 musl optimization requirement

The ABI 6 `run-v2` Debug musl lane timed out after the native runner started.
The native Kernel and OS regression gates for the same architecture passed.
The original v4 ELF remains at
`build/musl-bootstrap-v4/loongarch64/bootstrap.elf`, SHA-256
`0332b8c5125973ffec8aba0704a14767a74914fb8f8896fa0afe088fde1e5b1e`.

Paused QEMU system CPU samples found PC `0x40000d78` and `0x40000d94` inside
musl `a_cas_p`, called by first-clock `cgt_init`. TLS r2 was `0x400031e0`, and
the earlier `close(-1)` errno check had completed. The loop repeatedly failed
SC on the `vdso_func` pointer at `0x40003008`. This static binary has no VDSO;
musl must atomically publish the null lookup before using its syscall fallback.

The original libc used `-O0 -g`. Its inline LL/SC helpers became separate
functions: LL at `0x40000cd8`, then intervening stack stores and calls, and SC
at `0x40000d10`. The exact binary also times out under `qemu-loongarch64 -strace`
on Linux, after `set_tid_address` and `close`. Therefore this failure reproduces
outside ObfuscationKernel. An unmodified musl build using `-O2` eliminates that
loop failure: the comparison ELF
`cee91137b72c4e099d7e59bcda765523e5333c168289261ec0cc55eed8d81af0`
passes in Linux user emulation and in the OS QEMU ext4 guest.

`tools/musl_source.py` now keeps optimization enabled for all musl profiles:
Release uses `-O2`, Debug uses `-O2 -g`. Debug mode still selects Debug Kernel,
SDK and native programs. The libc optimization choice is part of its manifest;
it is not a kernel trap workaround or an architecture-matrix exemption.

Evidence lives under `build/musl-loong-diagnosis/`:

- `linux-user-results.json` records both ELF hashes, exit/timeout and syscall
  traces. This is Linux user emulation, not execution of ObfuscationKernel.
- `ok-loong-musl-registers.log` and `loong-musl.dis` preserve paused CPU samples
  and the original binary's disassembly.
- `native-release-probe/result.json` and `serial.log` record two actual musl
  runs, native parent exec/wait/exit and the following native pipeline.
- `diagnosis-artifacts.json` hashes those records.

The initial comparison used a Release libc probe on a Debug OS. The corrected
`debug-optimized-v1` libc also passes the native guest, with its record under
`native-debug-optimized-probe/`. These pilots do not replace the pending all-ten
Debug/Release qualification with new optimized Debug libc artifacts. These tests do not qualify SMP atomics,
threads, physical LoongArch hardware, or the rest of musl.
