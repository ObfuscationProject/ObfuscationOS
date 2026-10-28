# Ports framework

`ports/<name>/port.json` describes one pinned third-party source that the
distribution builds for the ten userland profiles with the musl toolchain family
(decision 0001). `tools/ports.py` validates the descriptors, prints the build
order from `depends` and builds one port for one profile (`xmake port-build`).
BusyBox supplies the shell and the utility set (decision 0004).

Descriptor fields:

| Field | Meaning |
| --- | --- |
| `name`, `version` | Upstream identity |
| `archive`, `sha256`, `url` | Pinned source archive, its SHA-256 and upstream location; a port without a hash is `planned` only |
| `license` | SPDX identifier; `review` means the licence decision record is still pending |
| `depends` | Ports that must be built first |
| `profiles` | Architecture profiles the port is qualified for; `[]` until the first guest run |
| `state` | `planned`, `builds`, `executes` (hosted vs guest execution are recorded separately in the ledger) |
| `build` | `system` selects the recipe; `kconfig` ports also name `config`, `program`, `testsuite`, optional `patches` (applied in order) and `clang_cflags` (added only when the ppc clang frontend compiles) |

A port's `state` is never advanced by a successful build alone; `executes` needs
guest execution evidence in ObfuscationEvidence.

## Building

```sh
xmake port-build --name=musl --arch=x86_64 --mode=debug \
    --archive=/path/to/musl-1.2.5.tar.gz --toolchain=/path/to/x86_64-elf --out=/new/musl-x86_64-debug
xmake port-build --name=busybox --arch=x86_64 --mode=debug \
    --archive=/path/to/busybox-1.37.0.tar.bz2 --toolchain=/path/to/x86_64-elf \
    --musl-build=/new/musl-x86_64-debug --out=/new/busybox-x86_64-debug
```

Every input is explicit and checked: the archive bytes must match the descriptor
pin (musl's must also equal the ledger reference), a dependent port names its
admitted musl build, the port compiler must be the one that built that musl
sysroot, and `--out` must not exist. A failed build keeps its logs and partial
output, labelled `build-failed` in its manifest. Nothing executes target code.

| `system` | Recipe |
| --- | --- |
| `musl` | `tools/musl_source.py build-static`: static libc, startup objects and headers |
| `kconfig` | `make allnoconfig`, merge `<config>`, then `make oldconfig` with default answers, switching every unrequested boolean back off until nothing changes (symbols forced by `select` stay on); every requested symbol must survive into `.config`; then the program and its install list are built through `tools/musl_cc.py` |

`configure`, `make` and `xmake` are accepted descriptor values with no recipe yet.

## Toolchain: freestanding-GCC fallback

Until SysToolchain 0.2.0 ships the `<arch>-linux-musl` family, ports build with
the `*-elf` compilers and `tools/musl_cc.py`. The driver compiles against the
admitted musl headers plus the compiler's builtin headers only, links a static
ET_EXEC with `ports/musl/static-exec.ld` (the probe layout from
`tests/musl/bootstrap.ld`, `USER_BASE` 0x10000000 on Arm, 0x40000000 elsewhere),
and marks `EI_OSABI` as Linux. It refuses shared, PIE and relocatable links.
`<arch>-linux-musl-gcc` in the toolchain directory is refused until the recipe
selects it. Ports compile with `-Dvfork=fork`: the Linux personality returns
ENOSYS for `CLONE_VM|CLONE_VFORK`.

Per-profile inputs:

| Profile | Extra input | Why |
| --- | --- | --- |
| ppc | `--ppc-clang` (the pinned clang 18.1.3) and a `powerpc-eabi` GCC whose `-msoft-float` multilib is `nof` | EABI GCC calls `__eabi` from `main`; the SysToolchain 0.1.0 `powerpc-eabi` archive is `--disable-multilib`, so its only libgcc is hard-float and cannot link soft-float code that uses `double` |
| mips64 | `--softfp-build` and `--softfp-manifest-sha256` (`xmake mips64-softfp`) | binary128 `long double` routines missing from the `mips64-elf` libgcc |

## Outputs and image staging

A `kconfig` build directory holds `manifest.json` (inputs, commands, `.config`
hash, applet list, ELF identity, every staged file's hash) and `stage/`:
`bin/<program>`, `share/<name>/{testsuite,.config,applets}` and
`share/licenses/<name>/`. Image staging rechecks all of it (`ports.admit`).

`xmake f --userland_build=DIR --userland_manifest_sha256=HEX` makes the
admitted build the default `/bin` of the `full` and `release` rootfs profiles
(`tools/stage_rootfs.py`): `/bin/<program>` plus one symbolic link per applet.
An okcrt program whose name an applet takes moves to `/rescue/<name>`; init,
oksh, login, posix-check and sync are never displaced (decision 0001). The full
profile also carries the upstream test suite under `/usr/share/<name>` and the
guest scripts under `/usr/share/userland-tests`; `scripts/test_musl_shell.py`
runs them. The `rescue` profile (SimpleFS) stays okcrt-only.
