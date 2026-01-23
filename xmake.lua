set_project("ObfuscationOS")
set_version("0.0.1")
set_languages("c++23")

add_rules("mode.debug", "mode.release")

target("kernel")
    set_kind("binary")
    set_filename("kernel.elf")

    add_includedirs("hal/x86_64/include", "kernel/include", {public = true})

    add_files("kernel/x86_64/boot.S")
    add_files("kernel/x86_64/ap_trampoline.S")
    add_files("kernel/x86_64/src/**.cpp")
    add_files("kernel/x86_64/src/**.S")

    -- C++ freestanding kernel flags
    add_cxflags(
        "-ffreestanding",
        "-fno-exceptions",
        "-fno-rtti",
        "-fno-stack-protector",
        "-fno-pic",
        "-fno-pie",
        "-fno-asynchronous-unwind-tables",
        "-fno-unwind-tables",
        "-m64",
        "-mno-red-zone",
        "-mno-sse",
        "-mno-sse2",
        "-mno-mmx",
        "-mno-80387",
        "-mcmodel=kernel",
        "-Wall", "-Wextra",
        {force = true}
    )

    add_asflags("-m64", {force = true})

    -- ELF64 + Multiboot2: keep max page size 4KiB so the header stays in range
    add_ldflags(
        "-nostdlib",
        "-no-pie",
        "-T", "kernel/x86_64/linker.ld",
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
