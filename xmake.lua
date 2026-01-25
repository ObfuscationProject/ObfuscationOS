set_project("ObfuscationOS")
set_version("0.0.1")
set_languages("c++23")
set_arch("x86_64")

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

target("kernel")
    set_kind("binary")
    set_filename("kernel.elf")

    add_includedirs("kernel/include", {public = true})

    add_files("kernel/src/**.cpp")

    local arch = os.arch()
    if arch == "x86_64" then
        add_includedirs("hal/x86_64/include", {public = true})
        add_includedirs("kernel/arch/x86_64/include", {public = true})
        add_files("kernel/arch/x86_64/boot.S")
        add_files("kernel/arch/x86_64/ap_trampoline.S")
        add_files("hal/x86_64/src/**.cpp")
        add_files("kernel/arch/x86_64/src/**.cpp")
        add_files("kernel/arch/x86_64/src/**.S")
    else
        raise("Unsupported arch: " .. arch)
    end

    -- C++ freestanding kernel flags
    add_cxflags(
        "-ffreestanding",
        "-m64",
        "-mcmodel=kernel",
        "-Wall", "-Wextra",
        {force = true}
    )

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
        add_cxflags("-mno-red-zone", {force = true})
    end
    if has_config("disable_simd") then
        add_cxflags("-mno-sse", "-mno-sse2", "-mno-mmx", "-mno-80387", {force = true})
    end

    add_asflags("-m64", {force = true})

    -- ELF64 + Multiboot2: keep max page size 4KiB so the header stays in range
    add_ldflags(
        "-nostdlib",
        "-no-pie",
        "-T", "kernel/arch/x86_64/linker.ld",
        "-z", "max-page-size=0x1000",
        {force = true}
    )

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
        description = "Run the ISO in QEMU (x86_64)",
        options = {}
    })
    on_run(function ()

        local isofile = path.join("build", "ObfuscationOS.iso")
        os.exec("qemu-system-x86_64 -m 256M -smp 4 -cdrom %s -no-reboot -no-shutdown -d int,cpu_reset -D qemu.log -debugcon stdio -global isa-debugcon.iobase=0xe9", isofile)
    end)
