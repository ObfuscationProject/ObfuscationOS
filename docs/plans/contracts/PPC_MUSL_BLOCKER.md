# PowerPC musl compiler startup boundary

The retained `powerpc-eabi` GCC 14.2.0 compiler can build musl 1.2.5's PowerPC
soft-float libc, but it injects `bl __eabi` into an ordinary C `main`. The resulting
probe cannot link with musl's Linux startup objects. This is a compiler target
configuration boundary, not an absent musl PowerPC source port.

On 2026-09-20, an isolated assembly probe retained `-mcpu=8548 -msoft-float
-mlong-double-64 -msdata=none` and tested the following accepted configurations:

| Additional compiler options | Reported EABI mode | `bl __eabi` emitted |
| --- | --- | --- |
| None | Enabled | Yes |
| `-mcall-linux` | Disabled | Yes |
| `-mno-eabi` | Disabled | Yes |
| `-mcall-linux -mno-eabi` | Disabled | Yes |
| `-mcall-sysv -mno-eabi` | Disabled | Yes |
| `-mcall-linux -mno-eabi -ffreestanding -fno-builtin` | Disabled | Yes |
| `-mcall-linux -mno-eabi -O2` | Disabled | Yes |

The compiler's own `-Q --help=target` output confirms that the Linux/no-EABI
options take effect. Their failure to remove the call is explained by GCC's
version-pinned implementation:

- [GCC 14.2.0 `gcc/config/rs6000/eabi.h`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-14.2.0/gcc/config/rs6000/eabi.h#L26)
  defines `NAME__MAIN` as `__eabi` and defines `INVOKE__main` when the compiler is
  built for this target. SHA-256:
  `f38c61a695736b4cfe1bdebbbfa89845b810f8d41ce21b874c17f583acf37e8d`.
- [GCC 14.2.0 `gcc/cfgexpand.cc`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-14.2.0/gcc/cfgexpand.cc#L6545)
  implements `expand_main_function` using those compile-time definitions.
  The ordinary file-scope `main` path calls it at line 6842; it does not consult
  runtime `-meabi` state or the hosted/freestanding switch. SHA-256:
  `a704c60552661a27f377f3c9b352118a211adc7fecb8f4ed197286e396f88951`.

Changing driver specs to pass the tested ABI options cannot undefine a macro
compiled into `cc1`. A Linux-targeted frontend is required for ordinary applications. The bootstrap
probe now has a working Clang path described below; startup, TLS, atomics and
signal context still need native qualification. The native `powerpc-eabi` SDK compiler
remains unchanged for Kernel/native extensions.

No startup stub, application-symbol renaming, postprocessed assembly or CPU
substitution was used. These were compiler/assembly inspections; no target
instructions or musl application executed. Linux ABI qualification remains open.

## Explicit Linux Clang application frontend

A subsequent isolated probe compiled the ordinary C application with installed
Clang 18 (`--target=powerpc-linux-musl -mcpu=8548 -msoft-float
-mlong-double-64 -ftls-model=local-exec`). It links with the previously audited
musl PowerPC startup/static libc and the retained cross-linker/runtime. It does
not rename `main`, replace libc startup, postprocess assembly or supply a dummy
`__eabi`. The emitted ELF retains ELF32 big-endian PowerPC and has a PT_TLS segment.

`tools/build_musl_probe.py` requires the frontend through explicit `--ppc-clang`
and records compiler, source manifest and output hashes. The reproducible xmake
entry point is `musl-bootstrap-probe`. The new probe includes a volatile
thread-local initializer, errno and monotonic time checks for later guest use.
The frontend change is limited to C application compilation; native C++ Kernel
SDK builds continue to use the exact exported GCC compiler identity.

The initial artifact is `build/musl-bootstrap/ppc-pilot/manifest.json`, classified
`built-not-executed`. This resolves the ordinary-main link blocker for this probe;
it does not qualify a complete Linux compiler/sysroot, mixed-toolchain C ABI,
physical e500 processor or musl execution. The original failed GCC records remain
valid evidence of the retained bare-metal frontend's behavior.

## Source-build admission and tool identity

`tools/musl_source.py build-static --arch=ppc --ppc-clang=PATH` now uses the same
validated frontend for its ordinary C `main` probe, compiles an object separately,
then links it with the retained GCC driver and newly built musl startup/libc.
`xmake musl-static-spike` forwards this option. The musl source itself still uses
the explicit GCC compiler. All new musl builds use `-O2`, with additional `-g` in
debug mode; no optimization is removed to retain debug information.

The current local binary pin is Ubuntu Clang 18.1.3 (`1ubuntu1`), inspected at
`/usr/lib/llvm-18/bin/clang`, SHA-256
`8ef402d453d1ba4902e4ee0f0f847f6cfa01400c95aa43c24e97818b9c0e3f45`.
The path is supplied explicitly; the exact byte identity is enforced regardless
of its location. This is a local tool pin, not an authenticated upstream archive.
The recipe also requires effective target `powerpc-unknown-linux-musl` and checks
its pointer width, byte order, long-double width, Linux and PowerPC macros under
the actual flags. A different compiler requires an explicit reviewed pin update.
The build manifest records frontend version/target/flags/hash and retained
compiler, assembler, linker and readelf hashes.

New bootstrap builds accept only source manifests marked `built-not-executed`
with the pinned musl version, explicit debug/release mode and audited required
startup/libc/header files. Failed source builds are rejected before creating
probe outputs. The early PPC pilot/v4 probes used partial sysroots left by the
failed GCC ordinary-main experiment; those historical records are preserved, but
cannot be reused as newly admitted source builds. New probe manifests carry the
source version and mode without changing any earlier failure record.
