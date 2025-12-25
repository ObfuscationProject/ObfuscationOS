-- xmake.lua
set_project("ObfuscationOS")
set_version("0.1.0")
set_xmakever("2.5.1")

-- 设置C++标准为C++23
set_languages("c++23", "c17")

-- 设置架构
set_arch("x86_64")

-- 设置编译模式
add_rules("mode.debug", "mode.release")

-- 设置编译选项
add_cxflags("-ffreestanding")      -- 不依赖标准库
add_cxflags("-fno-exceptions")     -- 禁用异常
add_cxflags("-fno-rtti")           -- 禁用运行时类型信息
add_cxflags("-fno-stack-protector") -- 禁用栈保护
add_cxflags("-fno-builtin")        -- 禁用内置函数
add_cxflags("-nostdlib")           -- 不链接标准库
add_cxflags("-Wall")               -- 启用所有警告
add_cxflags("-Wextra")             -- 启用额外警告
add_ldflags("-nostdlib")           -- 链接时也不使用标准库
add_ldflags("-static")             -- 静态链接
add_ldflags("-T $(projectdir)/linker.ld") -- 使用链接脚本

-- 添加内联汇编支持
add_cxflags("-mgeneral-regs-only")

-- 定义内核入口点
add_ldflags("-Wl,-e,_start")

-- 包含路径
add_includedirs("src/include")

-- 添加libc源文件
target("libc")
    set_kind("object")
    add_files("src/libc/*.cpp")
    add_headerfiles("src/libc/*.hpp", "src/libc/*.h")

-- 添加HAL层源文件
target("hal")
    set_kind("object")
    add_files("src/hal/*.cpp")
    add_headerfiles("src/hal/*.hpp", "src/hal/*.h")

-- 添加Kernel层源文件
target("kernel")
    set_kind("object")
    add_files("src/kernel/*.cpp", "src/kernel/*.S")
    add_headerfiles("src/kernel/*.hpp", "src/kernel/*.h")

-- 添加Driver层源文件
target("drivers")
    set_kind("object")
    add_files("src/drivers/*.cpp")
    add_headerfiles("src/drivers/*.hpp", "src/drivers/*.h")

-- 添加User层源文件
target("user")
    set_kind("object")
    add_files("src/user/*.cpp")
    add_headerfiles("src/user/*.hpp", "src/user/*.h")

-- 添加POSIX层源文件
target("posix")
    set_kind("object")
    add_files("src/posix/*.cpp")
    add_headerfiles("src/posix/*.hpp", "src/posix/*.h")

-- 主目标 - 内核
target("kernel.elf")
    set_kind("binary")
    add_deps("libc", "hal", "kernel", "drivers", "user", "posix")
    set_targetdir("build/")
    
    -- 链接脚本
    add_ldflags("-T $(projectdir)/linker.ld", {force = true})
    
    -- 禁用默认运行
    set_default(false)

-- 创建ISO镜像目标
target("iso")
    set_kind("phony")
    add_deps("kernel.elf")
    after_build(function (target)
        -- 创建ISO镜像的命令
        os.exec("mkdir -p build/isodir/boot/grub")
        os.exec("cp build/kernel.elf build/isodir/boot/kernel.elf")
        os.exec("echo 'set timeout=0' > build/isodir/boot/grub/grub.cfg")
        os.exec("echo 'set default=0' >> build/isodir/boot/grub/grub.cfg")
        os.exec("echo 'menuentry \"ObfuscationOS\" { multiboot2 /boot/kernel.elf; boot }' >> build/isodir/boot/grub/grub.cfg")
        os.exec("grub-mkrescue -o build/obfuscationos.iso build/isodir")
    end)

-- 运行QEMU目标
target("qemu")
    set_kind("phony")
    add_deps("iso")
    on_run(function (target)
        import("lib.detect.find_tool")
        local qemu = find_tool("qemu-system-x86_64")
        if not qemu then
            print("错误: 未找到qemu-system-x86_64，请先安装QEMU")
            return
        end
        
        -- 检查ISO文件是否存在
        if not os.isfile("build/obfuscationos.iso") then
            print("错误: 未找到ISO文件 build/obfuscationos.iso，请先构建项目并创建ISO")
            return
        end
        
        -- 运行QEMU
        os.exec("qemu-system-x86_64 -cdrom build/obfuscationos.iso -nographic -serial stdio -m 128M -smp 1 -no-shutdown -no-reboot -monitor none")
    end)

-- 创建运行目标（构建并运行）
target("run")
    set_kind("phony")
    add_deps("qemu")
    


