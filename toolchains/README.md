# Toolchains

`xmake toolchains -a ARCH` installs freestanding GCC/binutils toolchains here,
matching the layout used by `external/ObfuscationKernel`.

Supported first-stage userland architectures:

- `x86_64` -> `x86_64-elf`
- `aarch64` -> `aarch64-elf`
- `rv64` -> `riscv64-elf`
- `loongarch64` -> `loongarch64-elf`

The build still probes the legacy `build-toolchain/opt/<triple>` layout so
existing local x86_64 toolchains continue to work during the transition.
