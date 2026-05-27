local task_arches = {"x86_64", "aarch64", "rv64", "loongarch64"}

local task_arch_specs = {
    x86_64 = {triple = "x86_64-elf"},
    aarch64 = {triple = "aarch64-elf"},
    rv64 = {triple = "riscv64-elf"},
    loongarch64 = {triple = "loongarch64-elf"},
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

local function task_toolchain_sdkdir(spec)
    local project = os.projectdir()
    local candidates = {
        path.join(project, "toolchains", spec.triple),
        path.join(project, "build-toolchain", "opt", spec.triple),
    }
    for _, candidate in ipairs(candidates) do
        if os.isfile(path.join(candidate, "bin", spec.triple .. "-gcc")) then
            return candidate
        end
    end
    return candidates[1]
end

local function task_toolchain_binary(spec, tool)
    return path.join(task_toolchain_sdkdir(spec), "bin", spec.triple .. "-" .. tool)
end

task("toolchains")
    set_menu {
        usage = "xmake toolchains -a ARCH",
        description = "Build GCC/binutils cross toolchains into ./toolchains",
        options = {
            {"a", "target-arch", "kv", "all", "Architecture: x86_64/aarch64/rv64/loongarch64/all"},
            {"j", "jobs", "kv", nil, "Parallel build jobs"}
        }
    }
    on_run(function ()
        import("core.base.option")
        local arch = task_normalize_arch(option.get("target-arch") or "all")
        if arch ~= "all" then
            task_require_arch(arch)
        end
        local argv = {path.join(os.projectdir(), "scripts", "build-toolchain.sh"), "--arch", arch}
        if option.get("jobs") then
            table.insert(argv, "--jobs")
            table.insert(argv, option.get("jobs"))
        end
        os.execv("bash", argv)
    end)
task_end()

task("toolchain")
    set_menu {
        usage = "xmake toolchain",
        description = "Build the toolchain for the configured userland architecture",
        options = {
            {"j", "jobs", "kv", nil, "Parallel build jobs"}
        }
    }
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        local arch = task_normalize_arch(config.get("arch") or "x86_64")
        task_require_arch(arch)
        local argv = {path.join(os.projectdir(), "scripts", "build-toolchain.sh"), "--arch", arch}
        if option.get("jobs") then
            table.insert(argv, "--jobs")
            table.insert(argv, option.get("jobs"))
        end
        os.execv("bash", argv)
    end)
task_end()

task("toolchain-check")
    set_menu {
        usage = "xmake toolchain-check [-a ARCH] [--all]",
        description = "Check whether required userland toolchains are installed",
        options = {
            {"a", "profile", "kv", nil, "Architecture to check"},
            {nil, "all", "k", nil, "Check every first-stage architecture"}
        }
    }
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()

        local arches = {}
        if option.get("all") then
            arches = task_arches
        else
            table.insert(arches, task_normalize_arch(option.get("profile") or config.get("arch") or "x86_64"))
        end

        local missing = {}
        for _, arch in ipairs(arches) do
            local normalized, spec = task_require_arch(arch)
            local compiler = task_toolchain_binary(spec, "gcc")
            if os.isfile(compiler) then
                print(string.format("[ok] %s: %s", normalized, compiler))
            else
                print(string.format("[missing] %s: %s", normalized, compiler))
                table.insert(missing, normalized)
            end
        end

        if #missing > 0 then
            raise("missing toolchain(s): %s. Run: xmake toolchains -a %s",
                  table.concat(missing, ", "), #missing == 1 and missing[1] or "all")
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
            {nil, "timeout", "kv", "20", "QEMU timeout in seconds"}
        }
    }
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        local fs = option.get("fs") or "simplefs"
        if fs ~= "simplefs" and fs ~= "ext4" then
            raise("unsupported fs: %s", fs)
        end

        local image_target = fs == "simplefs" and "rootfs-simplefs" or "rootfs-ext4"
        os.execv("xmake", {"-y", "-b", image_target})

        local project = os.projectdir()
        local kernel = option.get("kernel")
        if not kernel then
            local kernel_dir = path.join(project, "external", "ObfuscationKernel")
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
            and path.join(project, "build", "rootfs.simplefs.img")
            or path.join(project, "build", "rootfs.ext4.img")

        os.execv("python3", {
            path.join(project, "scripts", "qemu_distro.py"),
            "--arch", task_normalize_arch(config.get("arch") or "x86_64"),
            "--kernel", kernel,
            "--rootfs", image,
            "--fs", fs,
            "--timeout", option.get("timeout") or "20",
        })
    end)
task_end()
