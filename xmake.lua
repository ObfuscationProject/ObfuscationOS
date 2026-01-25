set_project("ObfuscationOS")
set_version("0.0.1")
set_languages("c++23")

add_rules("mode.debug", "mode.release")

option("disable_exceptions")
    set_default(true)
    set_showmenu(true)
option("disable_rtti")
    set_default(true)
    set_showmenu(true)
option("disable_stack_protector")
    set_default(true)
    set_showmenu(true)
option("disable_unwind")
    set_default(true)
    set_showmenu(true)
option("disable_pie")
    set_default(true)
    set_showmenu(true)
option("disable_redzone")
    set_default(true)
    set_showmenu(true)
option("disable_simd")
    set_default(true)
    set_showmenu(true)
option("target_arch")
    set_default("x86_64")
    set_values("x86_64", "i386")
    set_showmenu(true)
option("toolchain")
    set_default("auto")
    set_values("auto", "gcc", "clang", "llvm", "cross")
    set_showmenu(true)
option("cross_prefix")
    set_default("")
    set_showmenu(true)
local function resolve_arch()
    local arch = get_config("target_arch")
    if not arch or arch == "" then
        arch = get_config("arch")
    end
    if not arch or arch == "" then
        arch = os.arch()
    end
    return arch
end

target("kernel")
    set_kind("binary")
    set_filename("kernel.elf")

    add_includedirs("kernel/include", {public = true})

    add_files("kernel/src/**.cpp")

    local arch = resolve_arch()
    if arch == "x86_64" then
        add_includedirs("hal/x86_64/include", {public = true})
        add_includedirs("kernel/arch/x86_64/include", {public = true})
        add_files("kernel/arch/x86_64/boot.S")
        add_files("kernel/arch/x86_64/ap_trampoline.S")
        add_files("hal/x86_64/src/**.cpp")
        add_files("kernel/arch/x86_64/src/**.cpp")
        add_files("kernel/arch/x86_64/src/**.S")
        add_defines("ARCH_X86_64")
    elseif arch == "x86" or arch == "i386" then
        add_includedirs("hal/i386/include", {public = true})
        add_includedirs("kernel/arch/i386/include", {public = true})
        add_files("kernel/arch/i386/boot.S")
        add_files("hal/i386/src/**.cpp")
        add_files("kernel/arch/i386/src/**.cpp")
        add_files("kernel/arch/i386/src/**.S")
        add_defines("ARCH_I386")
    else
        raise("Unsupported arch: " .. arch)
    end

    -- C++ freestanding kernel flags
    add_cxflags(
        "-ffreestanding",
        "-Wall", "-Wextra",
        {force = true}
    )
    if arch == "x86_64" then
        add_cxflags("-m64", "-mcmodel=kernel", {force = true})
    else
        add_cxflags("-m32", {force = true})
    end

    if has_config("disable_exceptions") then
        add_cxflags("-fno-exceptions", {force = true})
    end
    if has_config("disable_rtti") then
        add_cxflags("-fno-rtti", {force = true})
    end
    if has_config("disable_stack_protector") then
        add_cxflags("-fno-stack-protector", {force = true})
    end
    if has_config("disable_unwind") then
        add_cxflags("-fno-asynchronous-unwind-tables", "-fno-unwind-tables", {force = true})
    end
    if has_config("disable_pie") then
        add_cxflags("-fno-pic", "-fno-pie", {force = true})
    end
    if has_config("disable_redzone") then
        if arch == "x86_64" then
            add_cxflags("-mno-red-zone", {force = true})
        end
    end
    if has_config("disable_simd") then
        add_cxflags("-mno-sse", "-mno-sse2", "-mno-mmx", "-mno-80387", {force = true})
    end

    if arch == "x86_64" then
        add_asflags("-m64", {force = true})
    else
        add_asflags("-m32", {force = true})
    end

    -- ELF + Multiboot2: keep max page size 4KiB so the header stays in range
    local linker = "kernel/arch/x86_64/linker.ld"
    if arch == "x86" or arch == "i386" then
        linker = "kernel/arch/i386/linker.ld"
        add_ldflags("-m32", {force = true})
    end
    add_ldflags(
        "-nostdlib",
        "-no-pie",
        "-T", linker,
        "-z", "max-page-size=0x1000",
        {force = true}
    )

    local toolchain = get_config("toolchain")
    if toolchain and toolchain ~= "auto" then
        if toolchain == "cross" then
            local prefix = get_config("cross_prefix")
            if not prefix or prefix == "" then
                if arch == "x86_64" then
                    prefix = "x86_64-elf-"
                else
                    prefix = "i686-elf-"
                end
            end
            set_toolset("cc", prefix .. "gcc")
            set_toolset("cxx", prefix .. "g++")
            set_toolset("ld", prefix .. "ld")
            set_toolset("as", prefix .. "as")
            set_toolset("ar", prefix .. "ar")
        else
            set_toolchains(toolchain)
        end
    end

-- ---------------- Tasks: iso & qemu ----------------
task("iso")
    set_menu({
        usage = "xmake iso",
        description = "Build a GRUB2 bootable ISO image",
        options = {}
    })
    on_run(function ()
        -- `os` and `path` are builtin modules in xmake scripts.
        -- We avoid importing core.* modules to keep compatibility.
        os.exec("xmake build kernel")

        local builddir = "build"
        local isodir   = path.join(builddir, "iso_root")
        local grubdir  = path.join(isodir, "boot", "grub")

        os.rm(isodir)
        os.mkdir(grubdir)

        -- Copy kernel.elf: find it from build outputs
        local kernels = os.files(path.join(builddir, "**", "kernel.elf"))
        assert(#kernels > 0, "kernel.elf not found. Run `xmake build kernel -vD` to inspect output paths.")
        os.cp(kernels[1], path.join(isodir, "boot", "kernel.elf"))

        -- Copy grub.cfg
        os.cp("boot/grub/grub.cfg", grubdir)

        -- Build ISO
        local isofile = path.join(builddir, "ObfuscationOS.iso")
        os.rm(isofile)
        os.exec("grub-mkrescue -o %s %s", isofile, isodir)

        print("ISO generated: %s", isofile)
    end)

task("qemu")
    set_menu({
        usage = "xmake qemu",
        description = "Run the ISO in QEMU",
        options = {}
    })
    on_run(function ()

        local isofile = path.join("build", "ObfuscationOS.iso")
        local arch = resolve_arch()
        local qemu = "qemu-system-x86_64"
        if arch == "x86" or arch == "i386" then
            qemu = "qemu-system-i386"
        end
        os.exec("%s -m 256M -smp 4 -cdrom %s -no-reboot -no-shutdown -d int,cpu_reset -D qemu.log -debugcon stdio -global isa-debugcon.iobase=0xe9", qemu, isofile)
    end)
