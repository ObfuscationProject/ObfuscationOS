# ObfuscationOS
An experimental OS inspired by HarmonyOS, built from scratch with a focus on openness and independent development

## Toolchain Bootstrap
- Build bare-metal ELF toolchain for current `target_arch`:
  - `xmake toolchain`
- `target_arch=x86_64` builds `x86_64-elf`, `target_arch=i386` builds `i686-elf`.
- Toolchain binaries are installed to `build-toolchain/opt/<target>/bin`.
- Auto bootstrap is enabled by default when `elf` toolchain is missing.
  - Disable with: `xmake f --auto_bootstrap_toolchain=n`
