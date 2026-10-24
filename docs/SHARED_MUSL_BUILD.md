# Shared musl build artifacts

`xmake musl-shared-build` builds the pinned musl 1.2.5 archive with shared libc
enabled, using an explicit cross-toolchain, architecture, mode and new output
directory. It leaves the upstream source unchanged and keeps failed builds,
command logs and partial artifacts. It does not compile Kernel sources, install
files on the host, run a target binary or modify an existing static musl sysroot.

The recipe forwards `-shared` directly to ld because some retained bare-metal
GCC specs accept the compiler option but omit it from their linker invocation.
An ET_EXEC mislabeled as `libc.so` is rejected. The standalone ET_DYN must match
the requested class, byte order, machine and explicit architecture ABI flags, have bounded load/dynamic tables,
a file-backed loader entry, an internal `libc.so` SONAME and no dependency on
another shared library. Writable executable loads and text relocation tags are
rejected. The linker receives `-z defs -z text -z noexecstack`, and one nonexecutable
read/write GNU stack declaration is required. These are artifact checks, not dynamic code loading or a complete
relocation/TLS audit.
The package records its exact configured loader path and makes its symlink
relative to the packaged libc, without following a host `/usr/lib/libc.so`.
The output directory is reserved exclusively after input preflight. Existing
outputs and output symlinks are rejected. Source, generated objects, logs,
installed files, recipe inputs and actual compiler programs are bound in the
receipt; a failed build keeps its complete output directory.

RISC-V, LoongArch and MIPS may use an explicit isolated Linux-capable GNU
binutils artifact through `--linker-build` and its exact
`--linker-manifest-sha256`. The compiler must select its admitted `ld` and,
when supplied by that artifact, `as`. This never replaces the native toolchain.

MIPS shared builds require `--pic-runtime-build` and
`--pic-runtime-manifest-sha256`; MIPS64 also requires `--softfp-build` and
`--softfp-manifest-sha256` for its binary128 supplement. Runtime architecture,
compiler, mode, source and archive members are admitted explicitly. The recipe
retains these inputs, passes only their admitted archives as upstream `LIBCC`,
and rechecks admission after the build. MIPS assembly is compiled with
`-Wa,-KPIC`; MIPS32 uses the explicitly admitted Linux assembler to preserve
valid ELF local-symbol ordering.

RISC-V and LoongArch require `--gcc-pic-runtime-build` and
`--gcc-pic-runtime-manifest-sha256`. PPC requires `--ppc-pic-runtime-build`
and `--ppc-pic-runtime-manifest-sha256`, and its compiler and linker use secure
PLT flags. Native non-PIC archives cannot replace these selected inputs.
Each runtime selector is rejected for other architecture profiles. Profiles
without a runtime override retain the selected default libgcc archive and pass
its explicit path as `LIBCC`; configure cannot silently select an empty runtime.

```sh
PYTHONDONTWRITEBYTECODE=1 xmake musl-shared-build --arch=x86_64 --mode=debug --archive=/path/to/musl-1.2.5.tar.gz --toolchain=/path/to/x86_64-elf --out=/tmp/musl-shared-new
```

All ten architecture selectors remain present. Each requires its own successful
artifact receipt; a failed profile remains incomplete. Matching installed
static/shared headers, compiler-runtime ABI, symbol/TLS relocation behavior,
dynamic application startup, dlopen, pthread cancellation and OS syscall
semantics need separate qualification. This build task alone does not satisfy
M5 or prove POSIX conformance.
