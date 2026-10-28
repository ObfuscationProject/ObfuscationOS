# Static musl userland: BusyBox /bin, rootfs profiles and the guest gate

Slice of `feat/musl-primary` (plan WT1.5). BusyBox 1.37.0 (decision 0004)
built against the pinned static musl 1.2.5 sysroot is the default `/bin` of
images built with `--userland_build`; its `ash` runs scripts from the console
shell on eight profiles; on mips and mips64 the kernel stops the guest when
ash's first signal handler is due. The WT1.5 exit gate is not closed: kernel
limits listed below keep the complete BusyBox test suite from running.

## Scope

- `xmake port-build` (`tools/ports.py build`) builds one pinned port for one
  profile. The `musl` recipe is the audited `tools/musl_source.py build-static`.
  The `kconfig` recipe merges `ports/busybox/busybox.config` over `allnoconfig`
  and runs `oldconfig` until every unrequested boolean stays off unless a
  requested symbol selects it, applies the descriptor's patches and stages the
  program, its install list, test suite and licence with a hashed manifest.
- `tools/musl_cc.py` is the freestanding-GCC fallback driver: musl and builtin
  headers only, static ET_EXEC from `ports/musl/static-exec.ld`, `EI_OSABI`
  marked Linux, relocatable links passed through, shared and PIE refused.
- Rootfs profiles in `tools/stage_rootfs.py`: `full` (`rootfs-ext4`), `rescue`
  (`rootfs-simplefs` and the embedded boot archive, okcrt only) and `release`
  (`rootfs-release`, no acceptance programs; refuses startup acceptance). With
  `--userland_build` BusyBox is the default `/bin`; displaced okcrt tools move
  to `/rescue`; init, oksh, login, posix-check and sync stay.
- Root timestamps: the kernel answers Linux `stat` only for ext4 metadata with
  maintained timestamps, so `distro_image` built with the userland mounts the
  root with `Ext4TimestampPolicy::maintained`. Profiles without a kernel RTC
  source (i386, x86_64, loongarch64, mips, mips64, ppc) use the root's last
  write time as the provisional clock the journalled root already uses
  (`OK_STORAGE_CLOCK source=ext4-last-write provisional=1`); it carries no
  accuracy claim. The boot reports `OK_ROOT_TIMESTAMPS policy=maintained`.
  okcrt-only images keep the unqualified root and print nothing new.
- Guest gate: `scripts/test_musl_shell.py` boots the full image, runs
  `tests/userland/sh-acceptance.sh` (35 checks: parameter, arithmetic,
  command and field expansion, globbing, pipelines and their status,
  redirection, here-documents, command lists, compound commands, functions,
  traps) with `sh` from the console shell, checks that native programs still
  run, then BusyBox `testsuite/runtest` for the applets in
  `ports/busybox/testsuite-gate.txt` against its reviewed failures. A failure
  missing from the plan, or a listed failure that passes, fails the gate.

## Kernel limits found by the guest runs

| Limit | Effect | Handled here |
| --- | --- | --- |
| Linux `stat` needs maintained ext4 timestamps | PATH search, `ls`, `test -f`, `find` fail with EOPNOTSUPP on the default root | Maintained root for userland images (above) |
| `execve` copies at most 16 argv and 16 envp strings, each under 256 bytes | `xargs` with long input and any long environment variable fail | Patch 0002 keeps the test harness within it |
| `execve` of a non-ELF file returns EINVAL, not ENOEXEC; no `#!` | `./script` fails; ash's ENOEXEC fallback never runs | Scripts start as `sh script`; patch 0001 |
| The ext4 writer caches at most 128 inodes per mount and never evicts | After about 110 new files every lookup, create and exec returns ENOMEM | Patch 0003; the gate runs 13 applets per boot |
| Path components of 32 bytes or more return ENAMETOOLONG | Old-style test output files and two test directories fail | Reviewed failures in the gate plan |
| No device nodes (`/dev/zero`, `/dev/null`) | Tests reading `/dev/zero` fail; `>/dev/null` creates a file | Reviewed failure |
| `CLONE_VM\|CLONE_VFORK` returns ENOSYS | `vfork`, `posix_spawn`, `system`, `popen` fail | Ports build with `-Dvfork=fork` |
| MIPS o32/n64 signal delivery stops the guest when it cannot verify resuming a user handler | ash's SIGCHLD handler halts mips and mips64 guests | None in the OS; kernel work |
| `link`, `symlink`, `utimensat`, `uname`, `sysinfo`, `statfs`, `mknodat`, `fchownat`, `/proc` not routed | `ln`, `touch`, `uname`, `uptime`, `df`, `mkfifo`, `chown`, `ps` | Held back in `busybox.config`; okcrt keeps them |
| MIPS ELF admission reads the ABI flags record from the first 128 KiB | A program whose `.MIPS.abiflags` follows its text fails to exec | `static-exec.ld` places the record first; the recipe checks it |
| ppc ELF admission reads at most a 512 KiB file prefix and needs the section table (with the `.gnu.attributes` soft-float record) inside it | A larger ppc program fails to exec with ENOSYS | Compressed usage text; `bc`, `dc` and the `bzip2` compressor held back on every profile; the recipe refuses an oversized ppc program |

## Results on this branch

Commit `213d2e4`, SysToolchain 0.1.0 release archives (GCC 14.2.0, QEMU
10.2.0), debug Kernel SDKs from ObfuscationKernel `3418bec` (ABI 76). Receipts:
ObfuscationEvidence `receipts/ObfuscationOS@213d2e4/feat/musl-primary/`
(`port-builds`, `userland-gate`, `release-check`).

| Check | Profiles | Result |
| --- | --- | --- |
| `xmake port-build` musl 1.2.5 and BusyBox 1.37.0 (97 applets), debug | all ten | `built-not-executed`; BusyBox 357–590 KB |
| `kernel-sdk-check`, `distro_image`, `rootfs-simplefs`, `rootfs-ext4` and `qemu-distro --fs=ext4 --require-native` with BusyBox as `/bin` (init's `hello \| cat` runs the BusyBox `cat`) | all ten | pass |
| Root mount of userland images | all ten | `policy=maintained`; provisional last-write clock on i386, x86_64, loongarch64, mips, mips64, ppc |
| `sh-acceptance.sh`, 35 checks | i386, x86_64, aarch64, arm32, rv64, rv32, loongarch64, ppc | pass |
| BusyBox `testsuite/runtest`, 13 applets, 151 cases in one boot | same eight | 133 pass, the 9 reviewed failures, 9 untested (options not configured) |
| `sh-acceptance.sh` | mips, mips64 | stops after 4–5 checks: the kernel prints `OK_TEST_FAIL native-runtime=private MIPS handler resume unverified` (`n64` on mips64) when ash's SIGCHLD handler is due, and the guest halts |
| Release mode, okcrt images: build, `qemu-distro --fs=simplefs`, `qemu-distro --fs=release` | x86_64, aarch64, rv64, loongarch64 | pass |
| `tests/tools` with `OK_TEST_KERNEL_SDK` | host | 1323 run; 1 failure that also fails on the unchanged tree (`test_oksh` console pipeline exceeds the oksh line limit under a long `TMPDIR`) |

mips and mips64 ran at `213d2e4`; the other eight ran at `006bb09`, whose
BusyBox programs are byte-identical to `213d2e4`'s (`213d2e4` only moves
`.MIPS.abiflags`).

ppc builds with a `powerpc-eabi` GCC that has the `nof` soft-float multilib
and the pinned clang 18.1.3 frontend: the SysToolchain 0.1.0 `powerpc-eabi`
archive is `--disable-multilib`, so its only libgcc is hard-float. Under clang
BusyBox needs `-DBB_GLOBAL_CONST=` (descriptor `clang_cflags`): clang caches its
`const` global pointers across their initialization. mips64 links the pinned
binary128 supplement (`xmake mips64-softfp`).

## Reproduce

```sh
xmake port-build --name=musl --arch=x86_64 --mode=debug --archive=musl-1.2.5.tar.gz \
    --toolchain=TC/x86_64-elf --out=OUT/musl-x86_64-debug
xmake port-build --name=busybox --arch=x86_64 --mode=debug --archive=busybox-1.37.0.tar.bz2 \
    --toolchain=TC/x86_64-elf --musl-build=OUT/musl-x86_64-debug --out=OUT/busybox-x86_64-debug
xmake f -m debug -a x86_64 --kernel_sdk=SDK --systoolchain_dir=TC/x86_64-elf \
    --userland_build=OUT/busybox-x86_64-debug \
    --userland_manifest_sha256=$(sha256sum OUT/busybox-x86_64-debug/manifest.json | cut -d' ' -f1)
xmake -b distro_image && xmake -b rootfs-ext4
xmake qemu-distro --fs=ext4 --require-native
python3 scripts/test_musl_shell.py --arch x86_64 --qemu TC/x86_64-elf/bin/qemu-system-x86_64 \
    --kernel build/x86_64/debug/distro/kernel.bin --rootfs build/x86_64/debug/rootfs.ext4.img \
    --suite-plan ports/busybox/testsuite-gate.txt --out RECEIPTS/x86_64
```
