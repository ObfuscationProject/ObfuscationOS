# ObfuscationOS
An experimental OS inspired by HarmonyOS, built from scratch with a focus on openness and independent development

## 技术架构

### 混合内核设计
ObfuscationOS采用混合内核架构，结合了宏内核和微内核的优点，提供高性能和模块化特性。

### 分层架构
系统采用清晰的分层架构：

- **HAL层 (Hardware Abstraction Layer)**: 处理不同硬件架构的差异，目前支持x86_64，未来计划支持ARM64和RISC-V
- **Kernel层**: 核心操作系统功能，包括进程管理、内存管理、调度器等
- **Driver层**: 可动态加载的设备驱动程序
- **User层**: 用户空间应用程序接口

### 技术特性
- **编程语言**: C++23
- **构建系统**: XMake
- **POSIX兼容**: 提供POSIX标准API接口
- **硬件支持**: 初始支持x86_64架构
- **虚拟化测试**: 基于QEMU的测试环境

### 项目结构
```
ObfuscationOS/
├── src/                   # 源代码
│   ├── hal/              # 硬件抽象层
│   ├── kernel/           # 内核层
│   ├── drivers/          # 驱动层
│   ├── user/             # 用户层
│   └── posix/            # POSIX兼容层
├── build/                # 构建输出
├── tools/                # 工具脚本
│   └── qemu/             # QEMU测试脚本
├── xmake.lua             # XMake构建配置
├── linker.ld             # 链接器脚本
└── Makefile              # 简化构建命令
```

### 构建和运行
```bash
# 安装依赖 (需要xmake和QEMU)
# Ubuntu/Debian: sudo apt install xmake qemu-system-x86

# 构建内核
xmake build

# 创建ISO镜像
xmake build iso

# 在QEMU中运行 (需要先安装QEMU)
xmake run

# 清理构建文件
xmake clean

# 查看可用目标
xmake show -l targets
```

### 开发状态
- [x] 项目基础结构
- [x] XMake构建系统
- [x] HAL层架构
- [x] Kernel层基础
- [x] Driver层框架
- [x] User层基础
- [x] POSIX接口兼容
- [x] QEMU测试系统
- [ ] 完整功能实现

## 贡献
欢迎对本项目进行贡献！请遵循以下步骤：
1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request