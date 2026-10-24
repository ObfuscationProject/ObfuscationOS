# Distribution development contract

- ObfuscationOS owns userland, rootfs, system desktop/session policy, external
  kernel modules, external drivers and Linux driver compatibility code.
- Consume a validated Kernel SDK with matching architecture, mode and compiler
  ABI. Do not embed a kernel checkout, use source-header fallbacks or build the
  kernel sources from this repository.
- Preserve all ten userland/kernel profiles: i386, x86_64, aarch64, arm32, rv64,
  rv32, loongarch64, mips, mips64 and ppc. Do not silently narrow that matrix.
- Use xmake. Kernel extensions use freestanding C++23. Use templates/static
  dispatch for hot algorithms; runtime module/device boundaries may use OOP.
- Statically composing an OS extension is not runtime ELF module loading.
  ELF metadata/process records are not proof that user-mode code executed.
- Keep desktop and compatibility tests with the OS implementation. Verify SDK
  mismatch handling, distribution image linkage, rootfs packaging and QEMU
  desktop integration after boundary changes.
- Documentation, source comments and identifiers are English.
- New applications and services target musl over the Linux personality; okcrt
  is for init, login, rescue and native acceptance only (docs/decisions/0001).
- `modules/system-gui` is frozen to regression fixes; desktop work goes to the
  user-space compositor and applications (docs/decisions/0002).
- Qualification receipts and prototype trees go to the ObfuscationEvidence
  repository, never into this working tree (docs/decisions/0003). Per-slice
  notes live under docs/qualification/; docs/plans/STATUS.md is generated.
- Work is organised as paired worktrees described in docs/PLAN.md; a worktree
  that changes the SDK contract has a paired Kernel worktree.
