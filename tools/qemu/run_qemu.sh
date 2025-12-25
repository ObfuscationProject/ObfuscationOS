#!/bin/bash
# run_qemu.sh - 在QEMU中运行ObfuscationOS

# 检查是否安装了QEMU
if ! command -v qemu-system-x86_64 &> /dev/null; then
    echo "错误: 未找到qemu-system-x86_64，请先安装QEMU"
    exit 1
fi

# 检查ISO文件是否存在
if [ ! -f "build/obfuscationos.iso" ]; then
    echo "错误: 未找到ISO文件 build/obfuscationos.iso，请先构建项目并创建ISO"
    exit 1
fi

# 运行QEMU
qemu-system-x86_64 \
    -cdrom build/obfuscationos.iso \
    -nographic \
    -serial stdio \
    -m 128M \
    -smp 1 \
    -no-shutdown \
    -no-reboot \
    -monitor none \
    -netdev user,id=net0 -device e1000,netdev=net0