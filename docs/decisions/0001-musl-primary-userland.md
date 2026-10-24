# 0001: musl over the Linux personality is the primary userland

Date: 2026-10-24. Status: accepted.

## Decision

- Applications, services and the shell are built against the pinned musl 1.2.5
  sysroot and execute through the per-architecture Linux syscall personality.
  Static linking first (worktree `feat/musl-primary`), shared libc and loader
  later (`feat/shared-musl-loader`).
- `lib/okcrt` and the native UAPI remain for `/init` bootstrap, `login`, the
  rescue tools and the native acceptance programs. No new service or application
  is written against okcrt once a musl shell and utility set execute on all ten
  profiles.
- The native UAPI stays exported from the Kernel SDK as the init/rescue/diagnostic
  interface. It is not removed; it stops growing application-facing surface.

## Why

Two user-space stacks were being maintained in parallel with no end state: 36
okcrt programs, a 1.6k-line libc shim and a PID 1 on one side, musl probes and
qualification fixtures on the other. The workstation plan already selects a Linux
personality so that musl, a POSIX shell, coreutils and third-party ports can be
reused instead of reimplemented. Keeping the native path "during migration"
without a sunset rule meant every new service doubled the work.

## Consequences

- `apps/init`, `apps/login`, `apps/posix-check`, `apps/sync` and the rescue
  utilities stay on okcrt. Everything else migrates as the musl toolchain and
  job control (`feat/tty-jobctl`) land.
- okcrt gains no new wrappers except those `/init` and rescue need.
- The common UAPI numbering remains project-specific; this decision does not claim
  Linux binary compatibility.
