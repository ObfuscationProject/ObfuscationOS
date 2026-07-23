local task_arches = {"x86_64", "aarch64", "rv64", "loongarch64"}

local task_arch_specs = {
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

local function task_find_kernel_image()
    local kernel_dir = path.join(os.projectdir(), "external", "ObfuscationKernel")
    local kernels = os.files(path.join(kernel_dir, "build", "**", "kernel.bin"))
    table.sort(kernels)
    if #kernels == 0 then
        kernels = os.files(path.join(kernel_dir, "build", "**", "kernel.elf"))
        table.sort(kernels)
    end
    return kernels[1]
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

        local current_arch = task_normalize_arch(config.get("arch") or "x86_64")
        local current_mode = config.get("mode") or "release"
        local mode = option.get("check-mode") or current_mode
        local failed = {}

        for _, arch in ipairs(task_arches) do
            task_require_arch(arch)
            print(string.format("[arch-matrix] %s (%s)", arch, mode))
            local config_code = os.execv("xmake", {"f", "-c", "-y", "-m", mode, "-a", arch}, {try = true})
            local sysroot_code = config_code == 0 and os.execv("xmake", {"-y", "-b", "sysroot"}, {try = true}) or config_code
            local apps_code = sysroot_code == 0 and os.execv("xmake", {"-y", "-b", "apps"}, {try = true}) or sysroot_code
            if config_code ~= 0 or sysroot_code ~= 0 or apps_code ~= 0 then
                table.insert(failed, arch)
            end
        end

        os.execv("xmake", {"f", "-c", "-y", "-m", current_mode, "-a", current_arch})
        if #failed > 0 then
            raise("arch matrix failed for: %s", table.concat(failed, ", "))
        end
    end)
task_end()

task("distro-test")
    set_menu {
        usage = "xmake distro-test [-k KERNEL] [--no-qemu]",
        description = "Run userland, image, UAPI, submodule, and QEMU distro smoke tests",
        options = {
            {"k", "kernel", "kv", nil, "Path to kernel.bin/kernel.elf from external/ObfuscationKernel"},
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

        os.execv("xmake", {"f", "-c", "-y", "-m", mode, "-a", "x86_64"}, {try = true})
        checked("kernel-submodule-check", {"-y", "-b", "kernel-submodule-check"})
        checked("uapi-test", {"-y", "-b", "uapi-test"})
        checked("libc-test", {"-y", "-b", "libc-test"})
        checked("rootfs-simplefs", {"-y", "-b", "rootfs-simplefs"})
        checked("rootfs-ext4", {"-y", "-b", "rootfs-ext4"})

        if not option.get("no-qemu") then
            local kernel = option.get("kernel") or task_find_kernel_image()
            if kernel == nil then
                table.insert(failed, "qemu-distro")
                print("[distro-test] qemu-distro skipped: kernel image not found")
            else
                checked("qemu-distro simplefs", {
                    "qemu-distro", "--fs=simplefs", "-k", kernel, "--timeout=" .. (option.get("timeout") or "20")
                })
                checked("qemu-distro ext4", {
                    "qemu-distro", "--fs=ext4", "-k", kernel, "--timeout=" .. (option.get("timeout") or "20")
                })
            end
        end

        os.execv("xmake", {"f", "-c", "-y", "-m", current_mode, "-a", current_arch})
        if #failed > 0 then
            raise("distro test failed for: %s", table.concat(failed, ", "))
        end
    end)
task_end()

task("qemu-distro")
    set_menu {
        usage = "xmake qemu-distro --fs=<simplefs|ext4>",
        description = "Run the external kernel with an ObfuscationOS rootfs image",
        options = {
            {"f", "fs", "kv", "simplefs", "Root filesystem image to run: simplefs or ext4"},
            {"k", "kernel", "kv", nil, "Path to kernel.bin/kernel.elf from external/ObfuscationKernel"},
            {nil, "timeout", "kv", "20", "QEMU timeout in seconds"},
            {nil, "display", "kv", "none", "QEMU display backend: none or sdl"},
            {nil, "interactive", "k", nil, "Keep QEMU running until the window/process exits"}
        }
    }
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        import("core.project.project")
        config.load()
        local fs = option.get("fs") or "simplefs"
        if fs ~= "simplefs" and fs ~= "ext4" then
            raise("unsupported fs: %s", fs)
        end

        local image_target = fs == "simplefs" and "rootfs-simplefs" or "rootfs-ext4"
        os.execv("xmake", {"-y", "-b", image_target})

        local arch, spec = task_require_arch(config.get("arch") or "x86_64")
        local systoolchain = project.required_package("systoolchain")
        if systoolchain == nil then
            raise("the systoolchain package is not resolved; rerun xmake f -c -y -a %s", arch)
        end
        local qemu = path.absolute(path.join(systoolchain:installdir(), "bin", spec.qemu_system))
        assert(os.isfile(qemu), "systoolchain is missing packaged QEMU: %s", qemu)

        local project_dir = os.projectdir()
        local kernel = option.get("kernel")
        if not kernel then
            local kernel_dir = path.join(project_dir, "external", "ObfuscationKernel")
            local kernels = os.files(path.join(kernel_dir, "build", "**", "kernel.bin"))
            if #kernels == 0 then
                kernels = os.files(path.join(kernel_dir, "build", "**", "kernel.elf"))
            end
            if #kernels == 0 then
                raise("kernel image not found under external/ObfuscationKernel/build; build the kernel submodule first")
            end
            kernel = kernels[1]
        end

        local image = fs == "simplefs"
            and path.join(project_dir, "build", "rootfs.simplefs.img")
            or path.join(project_dir, "build", "rootfs.ext4.img")

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
        os.execv("python3", args)
    end)
task_end()

task("qemu-distro-window")
    set_menu {
        usage = "xmake qemu-distro-window --fs=simplefs",
        description = "Build/run the system GUI distro path with a graphical display and keep the window open",
        options = {
            {"f", "fs", "kv", "simplefs", "Root filesystem image to run: simplefs"},
            {"k", "kernel", "kv", nil, "Path to kernel.bin/kernel.elf from external/ObfuscationKernel"},
            {nil, "kernel-mode", "kv", "release", "Kernel mode to build when --kernel is omitted"},
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
        local kernel = option.get("kernel")
        if not kernel then
            local arch = task_normalize_arch(config.get("arch") or "x86_64")
            local mode = option.get("kernel-mode") or "release"
            local kernel_dir = path.join(project, "external", "ObfuscationKernel")
            os.execv("xmake", {"f", "-P", ".", "-y", "-m", mode, "-a", arch, "--kernel_gui=y"}, {curdir = kernel_dir})
            os.execv("xmake", {"-P", ".", "-y", "-b", "okernel_image"}, {curdir = kernel_dir})
            local candidates = {
                path.join(kernel_dir, "build", "linux", arch, mode, "kernel.bin"),
                path.join(project, "build", "linux", arch, mode, "kernel.bin"),
            }
            for _, candidate in ipairs(candidates) do
                if os.isfile(candidate) then
                    kernel = candidate
                    break
                end
            end
            if not kernel then
                raise("built kernel image not found for %s/%s", arch, mode)
            end
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
