# Toolchains

ObfuscationOS no longer installs compilers in this directory. Freestanding
GCC/binutils comes from the `systoolchain` xmake package and is stored in xmake's
package cache.

Supported first-stage userland architectures:

- `x86_64` -> `x86_64-elf`
- `aarch64` -> `aarch64-elf`
- `rv64` -> `riscv64-elf`
- `loongarch64` -> `loongarch64-elf`

Run `xmake f -c -y -a <arch>` to build and resolve the package from its pinned
sources. Package installation validates the target compiler and corresponding
QEMU executable before either is exposed to ObfuscationOS.
