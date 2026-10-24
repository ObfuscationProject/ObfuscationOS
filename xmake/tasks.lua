local task_arches = {"i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc"}

local task_arch_specs = {
    i386 = {qemu_system = "qemu-system-i386"},
    arm32 = {qemu_system = "qemu-system-arm"},
    rv32 = {qemu_system = "qemu-system-riscv32"},
    mips = {qemu_system = "qemu-system-mips"},
    mips64 = {qemu_system = "qemu-system-mips64"},
    ppc = {qemu_system = "qemu-system-ppc"},
    x86_64 = {qemu_system = "qemu-system-x86_64"},
    aarch64 = {qemu_system = "qemu-system-aarch64"},
    rv64 = {qemu_system = "qemu-system-riscv64"},
    loongarch64 = {qemu_system = "qemu-system-loongarch64"},
}

local function task_normalize_arch(arch)
    if arch == nil or arch == "" then
        return "x86_64"
    end
    if arch == "x64" or arch == "amd64" then
        return "x86_64"
    end
    if arch == "arm64" then
        return "aarch64"
    end
    if arch == "riscv64" then
        return "rv64"
    end
    if arch == "loong64" or arch == "loongarch" then
        return "loongarch64"
    end
    return arch
end

local function task_require_arch(arch)
    local normalized = task_normalize_arch(arch)
    local spec = task_arch_specs[normalized]
    if spec == nil then
        raise("unsupported first-stage userland arch '%s'; use one of: %s",
              tostring(normalized), table.concat(task_arches, ", "))
    end
    return normalized, spec
end

local function task_builddir(config, arch, mode)
    return path.join(os.projectdir(), "build", arch or task_normalize_arch(config.get("arch")), mode or config.get("mode") or "release")
end

local function task_configure_args(config, mode, arch)
    local args = {"f", "-y", "-m", mode, "-a", arch}
    for _, name in ipairs({"systoolchain_dir", "kernel_sdk"}) do
        if config.get(name) then
            table.insert(args, "--" .. name .. "=" .. path.absolute(config.get(name)))
        end
    end
    for _, name in ipairs({"native_init_acceptance", "native_vm_acceptance", "native_udp_probe"}) do
        table.insert(args, "--" .. name .. "=" .. (config.get(name) and "y" or "n"))
    end
    return args
end

task("arch-matrix")
    set_menu {
        usage = "xmake arch-matrix [-m MODE]",
        description = "Build sysroot and apps for every first-stage userland architecture",
        options = {
            {"m", "check-mode", "kv", nil, "Build mode used for the matrix"}
        }
    }
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()

        if config.get("kernel_sdk") then
            raise("arch-matrix requires the default per-architecture SDK layout; a single --kernel_sdk override cannot represent ten architectures")
        end
        if config.get("systoolchain_dir") then
            local bindir = path.join(path.absolute(config.get("systoolchain_dir")), "bin")
            for _, triple in ipairs({"i386-elf", "x86_64-elf", "aarch64-elf", "arm-none-eabi", "riscv64-elf", "riscv32-elf", "loongarch64-elf", "mips-elf", "mips64-elf", "powerpc-eabi"}) do
                assert(os.isfile(path.join(bindir, triple .. "-gcc")),
                    "arch-matrix local toolchain must contain all ten compilers; missing %s-gcc", triple)
            end
        end

        local current_arch = task_normalize_arch(config.get("arch") or "x86_64")
        local current_mode = config.get("mode") or "release"
        local mode = option.get("check-mode") or current_mode
        local failed = {}

        for _, arch in ipairs(task_arches) do
            task_require_arch(arch)
            print(string.format("[arch-matrix] %s (%s)", arch, mode))
            local config_code = os.execv("xmake", task_configure_args(config, mode, arch), {try = true})
            local sysroot_code = config_code == 0 and os.execv("xmake", {"-y", "-b", "sysroot"}, {try = true}) or config_code
            local apps_code = sysroot_code == 0 and os.execv("xmake", {"-y", "-b", "apps"}, {try = true}) or sysroot_code
            if config_code ~= 0 or sysroot_code ~= 0 or apps_code ~= 0 then
                table.insert(failed, arch)
            end
        end

        os.execv("xmake", task_configure_args(config, current_mode, current_arch))
        if #failed > 0 then
            raise("arch matrix failed for: %s", table.concat(failed, ", "))
        end
    end)
task_end()

task("distro-test")
    set_menu {
        usage = "xmake distro-test [-k KERNEL] [--no-qemu]",
        description = "Run userland, image, UAPI, SDK, and QEMU distro smoke tests",
        options = {
            {"k", "kernel", "kv", nil, "Explicit kernel image override (otherwise build distro_image from the selected SDK)"},
            {"m", "check-mode", "kv", nil, "Build mode used for userland images"},
            {nil, "timeout", "kv", "20", "QEMU timeout in seconds"},
            {nil, "no-qemu", "k", nil, "Skip QEMU distro smoke tests"}
        }
    }
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()

        local current_arch = task_normalize_arch(config.get("arch") or "x86_64")
        local current_mode = config.get("mode") or "release"
        local mode = option.get("check-mode") or current_mode
        local failed = {}

        local function checked(label, args)
            print("[distro-test] " .. label)
            local code = os.execv("xmake", args, {try = true})
            if code ~= 0 then
                table.insert(failed, label)
            end
            return code
        end

        local restore_args = task_configure_args(config, current_mode, current_arch)
        local acceptance_args = task_configure_args(config, mode, current_arch)
        if mode == "debug" then
            for i, arg in ipairs(acceptance_args) do
                if arg:find("--native_init_acceptance=", 1, true) == 1 then
                    acceptance_args[i] = "--native_init_acceptance=y"
                end
            end
        end
        local configured = checked("configure", acceptance_args)
        if configured ~= 0 then
            os.execv("xmake", restore_args)
            raise("distro-test configuration failed")
        end
        checked("distro_image", {"-y", "-b", "distro_image"})
        checked("kernel-sdk-check", {"-y", "-b", "kernel-sdk-check"})
        checked("uapi-test", {"-y", "-b", "uapi-test"})
        checked("libc-test", {"-y", "-b", "libc-test"})
        checked("rootfs-simplefs", {"-y", "-b", "rootfs-simplefs"})
        checked("rootfs-ext4", {"-y", "-b", "rootfs-ext4"})

        if not option.get("no-qemu") then
            local kernel = option.get("kernel") or path.join(task_builddir(config, current_arch, mode), "distro", "kernel.bin")
            if not os.isfile(kernel) then
                table.insert(failed, "qemu-distro")
                print("[distro-test] qemu-distro skipped: kernel image not found")
            else
                local simplefs_args = {
                    "qemu-distro", "--fs=simplefs", "-k", kernel, "--timeout=" .. (option.get("timeout") or "20")
                }
                local ext4_args = {
                    "qemu-distro", "--fs=ext4", "-k", kernel, "--timeout=" .. (option.get("timeout") or "20")
                }
                if mode == "debug" then
                    table.insert(simplefs_args, "--require-native")
                    table.insert(ext4_args, "--require-native")
                end
                checked("qemu-distro simplefs", simplefs_args)
                checked("qemu-distro ext4", ext4_args)
            end
        end

        os.execv("xmake", restore_args)
        if #failed > 0 then
            raise("distro test failed for: %s", table.concat(failed, ", "))
        end
    end)
task_end()

task("qemu-distro")
    set_menu {
        usage = "xmake qemu-distro --fs=<simplefs|ext4|ext4-journalled>",
        description = "Run the external kernel with an ObfuscationOS rootfs image",
        options = {
            {"f", "fs", "kv", "simplefs", "Root filesystem image: simplefs, ext4 or ext4-journalled"},
            {"k", "kernel", "kv", nil, "Explicit kernel image override (otherwise build distro_image from the selected SDK)"},
            {nil, "qemu", "kv", nil, "Explicit QEMU executable override"},
            {nil, "timeout", "kv", "20", "QEMU timeout in seconds"},
            {nil, "display", "kv", "none", "QEMU display backend: none or sdl"},
            {nil, "persist", "k", nil, "Reuse the ext4 disk and preserve guest writes"},
            {nil, "require-native", "k", nil, "Select and require explicit native init/timer acceptance"},
            {nil, "interactive", "k", nil, "Keep QEMU running until the window/process exits"}
        }
    }
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        import("core.project.project")
        config.load()
        local login = config.get("native_console_login")
        if login and option.get("require-native") then
            raise("native_console_login cannot run startup acceptance before authentication")
        end
        if option.get("require-native") and not (config.get("native_init_acceptance") or
                config.get("native_vm_acceptance") or config.get("native_udp_probe")) then
            os.execv("xmake", {"f", "-y", "--native_init_acceptance=y"})
            config.load()
        end
        local fs = option.get("fs") or "simplefs"
        if fs ~= "simplefs" and fs ~= "ext4" and fs ~= "ext4-journalled" then
            raise("unsupported fs: %s", fs)
        end
        if login and (fs ~= "ext4-journalled" or not option.get("interactive")) then
            raise("native_console_login requires --fs=ext4-journalled --interactive")
        end
        local images = {
            simplefs = {"rootfs-simplefs", "rootfs.simplefs.img"},
            ext4 = {"rootfs-ext4", "rootfs.ext4.img"},
            ["ext4-journalled"] = {"rootfs-ext4-journalled", "rootfs.ext4-journalled.img"},
        }
        local image_target = images[fs][1]
        if login then images[fs][2] = "rootfs.login.ext4-journalled.img" end
        local image = path.join(task_builddir(config), images[fs][2])
        local persist = option.get("persist") or login
        if persist and fs == "simplefs" then raise("--persist requires an ext4 filesystem") end
        if not persist or not os.isfile(image) then
            os.execv("xmake", {"-y", "-b", image_target})
        end

        local arch, spec = task_require_arch(config.get("arch") or "x86_64")
        local qemu = option.get("qemu")
        if qemu then
            qemu = path.absolute(qemu)
        else
            local prefix = config.get("systoolchain_dir")
            if not prefix then
                local systoolchain = project.required_package("systoolchain")
                assert(systoolchain, "the systoolchain package is not resolved")
                prefix = systoolchain:installdir()
            end
            qemu = path.absolute(path.join(prefix, "bin", spec.qemu_system))
        end
        assert(os.isfile(qemu), "QEMU executable is missing: %s", qemu)
        local project_dir = os.projectdir()
        local kernel = option.get("kernel")
        if not kernel then
            os.execv("xmake", {"-y", "-b", "distro_image"})
            kernel = path.join(task_builddir(config), "distro", "kernel.bin")
        end
        if login then
            os.execv("python3", {"-B", path.join(project_dir, "tools", "console_login_disk.py"),
                "--image", image, "--root", path.join(task_builddir(config), "rootfs")})
        end

        local args = {
            path.join(project_dir, "scripts", "qemu_distro.py"),
            "--qemu", qemu,
            "--arch", arch,
            "--kernel", kernel,
            "--rootfs", image,
            "--fs", fs,
            "--timeout", option.get("timeout") or "20",
            "--display", option.get("display") or "none",
        }
        if option.get("interactive") then
            table.insert(args, "--interactive")
        end
        if persist then
            table.insert(args, "--persist")
        end
        if option.get("require-native") then
            table.insert(args, "--require-native")
        end
        os.execv("python3", args)
    end)
task_end()

task("qemu-distro-window")
    set_menu {
        usage = "xmake qemu-distro-window --fs=simplefs",
        description = "Build/run the system GUI distro path with a graphical display and keep the window open",
        options = {
            {"f", "fs", "kv", "simplefs", "Root filesystem image to run: simplefs"},
            {"k", "kernel", "kv", nil, "Explicit kernel image override (otherwise build distro_image from the selected SDK)"},
            {nil, "display", "kv", "sdl", "QEMU display backend: sdl or none"},
            {nil, "timeout", "kv", nil, "Run headless marker validation instead of keeping the window open"}
        }
    }
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        local project = os.projectdir()
        local fs = option.get("fs") or "simplefs"
        if fs ~= "simplefs" then
            raise("qemu-distro-window currently requires simplefs so the early System GUI module loader can read /boot/modules")
        end
        -- Build the OS extension against the configured SDK; never enter a
        -- kernel source checkout or select a globbed architecture artifact.
        local kernel = option.get("kernel")
        if not kernel then
            os.execv("xmake", {"-y", "-b", "distro_image"})
            kernel = path.join(task_builddir(config), "distro", "kernel.bin")
        end
        local args = {
            "qemu-distro",
            "--fs=" .. fs,
            "--display=" .. (option.get("display") or "sdl"),
        }
        if option.get("timeout") then
            table.insert(args, "--timeout=" .. option.get("timeout"))
        else
            table.insert(args, "--interactive")
        end
        table.insert(args, "-k")
        table.insert(args, kernel)
        os.execv("xmake", args)
    end)
task_end()
