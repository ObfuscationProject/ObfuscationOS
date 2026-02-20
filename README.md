# ObfuscationOS
An experimental OS inspired by HarmonyOS, built from scratch with a focus on openness and independent development

## Toolchain Bootstrap
- Build bare-metal ELF toolchain for current `arch`:
  - `xmake toolchain`
- `arch=x86_64` builds `x86_64-elf`, `arch=i386` builds `i686-elf`.
- Example:
  - `xmake f -a i386`
  - `xmake toolchain`
- Toolchain binaries are installed to `build-toolchain/opt/<target>/bin`.
- If `elf` toolchain is missing, run `xmake toolchain` manually to bootstrap it.
- Strict check mode:
  - `xmake f --auto_bootstrap_toolchain=n` (missing toolchain will fail fast)
