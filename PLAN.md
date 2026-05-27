# ObfuscationOS 用户态重构计划

## Summary
- 重建 `ObfuscationOS` 为 mini distro：用户态 SDK、tiny libc、应用、rootfs 镜像、QEMU 联调脚本。
- `ObfuscationKernel` 作为 git submodule 放在 `external/ObfuscationKernel`，默认锁到当前 `v0.1.0` / `104f2091`，构建时从 submodule 复制 UAPI。
- 第一阶段支持 64 位主线：`x86_64`、`aarch64`、`rv64`、`loongarch64`。`i386`、`arm32`、`rv32`、`mips`、`mips64`、`ppc` 留到后续。

## Key Changes
- 构建系统保留 xmake，新增 `kernel-submodule-check`、`sysroot`、`okcrt`、`apps`、`rootfs-simplefs`、`rootfs-ext4`、`qemu-distro` 目标；删除旧 kernel/HAL/GRUB ISO 框架。
- tiny libc 实现多架构目录：`arch/x86_64` 先完整实现 syscall ABI，`arch/aarch64`、`arch/rv64`、`arch/loongarch64` 建立 syscall/crt0 接口并按 kernel ABI 补齐。
- 用户程序 MVP：`init`、`oksh`、`hello`、`cat`、`ls`、`stat`、`mkdir`、`rm`。当前 kernel 对外 `fork/execve/wait/pipe/select/poll` 仍是 `ENOSYS`，所以 `oksh` 第一版使用内建命令。
- 默认生成两种 rootfs：SimpleFS 和 EXT4。SimpleFS 用于当前 kernel flat writable path；EXT4 使用标准层级 `/bin/init`、`/etc/os-release`，作为默认发行版镜像格式和后续真实挂载目标。
- SimpleFS 镜像受 kernel 限制：512-byte block、flat root、最多 32 entries；打包时将 `/bin/init` 映射成 `init` 这类根目录文件名。

## Public Interfaces
- `git submodule update --init --recursive external/ObfuscationKernel`
- `xmake f -a x86_64`
- `xmake -y -b sysroot`
- `xmake -y -b rootfs-simplefs`
- `xmake -y -b rootfs-ext4`
- `xmake qemu-distro --fs=simplefs`
- `xmake qemu-distro --fs=ext4`
- 输出布局：`sysroot/include`、`sysroot/lib/libokcrt.a`、`build/apps/*.elf`、`build/rootfs.simplefs.img`、`build/rootfs.ext4.img`。

## Kernel Dependencies
- Kernel 需要支持 submodule 版本的 UAPI 作为稳定输入。
- SimpleFS 启动路径需要改成“mount existing, format only if empty/invalid”，否则会覆盖 OS 生成的镜像。
- EXT4 目前是 read-only foundation；OS 先生成标准 ext4 镜像，真正作为 rootfs 启动依赖 kernel 完成目录遍历、inode data read 和 mount routing。
- 真实用户态运行仍依赖 kernel 完成 ELF loader handoff、trap-return、用户页表和 syscall return path。

## Test Plan
- 构建测试：四个首发 64 位架构至少完成 sysroot/app 编译；`x86_64` 作为完整 smoke baseline。
- UAPI 测试：校验 `ok/uapi/syscall.h` 版本、syscall numbers、errno、`ok_stat/ok_timespec/ok_iovec` 布局。
- libc 测试：mock syscall backend 验证 wrappers、负 errno、`errno`、基础 string/memory/stdio。
- 镜像测试：SimpleFS roundtrip；EXT4 使用 `debugfs`/`e2fsck -n` 校验目录和文件。
- 集成测试：先运行 kernel submodule 的 `xmake test` / `xmake qemu-test`；kernel dependencies 落地后，`qemu-distro` 挂载 rootfs 并要求 `init` 输出启动 marker。

## Assumptions
- “其他所有 64 位架构”指 `aarch64`、`rv64`、`loongarch64`，但明确不包含 `mips64` 第一阶段。
- EXT4 第一版由 OS 生成完整镜像，kernel 侧能启动前只做离线校验和后续挂载准备。
- 不引入 musl/glibc；第一版使用项目自有 tiny libc。
