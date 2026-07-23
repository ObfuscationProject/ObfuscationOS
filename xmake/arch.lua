OK_USER_ARCHES = {"x86_64", "aarch64", "rv64", "loongarch64"}

OK_USER_ARCH_SPECS = {
    x86_64 = {
        define = "OK_USER_ARCH_X86_64",
        source = "x86_64",
        triple = "x86_64-elf",
        qemu_system = "qemu-system-x86_64",
        cflags = {"-m64", "-mno-red-zone"},
        asflags = {"-m64"},
        ldflags = {"-no-pie", "-Wl,-z,max-page-size=0x1000"},
    },
    aarch64 = {
        define = "OK_USER_ARCH_AARCH64",
        source = "aarch64",
        triple = "aarch64-elf",
        qemu_system = "qemu-system-aarch64",
        cflags = {"-mno-outline-atomics", "-mgeneral-regs-only"},
        asflags = {},
        ldflags = {},
    },
    rv64 = {
        define = "OK_USER_ARCH_RV64",
        source = "rv64",
        triple = "riscv64-elf",
        qemu_system = "qemu-system-riscv64",
        cflags = {"-mcmodel=medany"},
        asflags = {"-mcmodel=medany"},
        ldflags = {},
    },
    loongarch64 = {
        define = "OK_USER_ARCH_LOONGARCH64",
        source = "loongarch64",
        triple = "loongarch64-elf",
        qemu_system = "qemu-system-loongarch64",
        cflags = {"-msimd=none"},
        asflags = {"-msimd=none"},
        ldflags = {"-msimd=none"},
    },
}

function ok_user_normalize_arch(arch)
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

function ok_user_current_arch()
    return ok_user_normalize_arch(get_config("arch"))
end

function ok_user_arch_spec(arch)
    return OK_USER_ARCH_SPECS[ok_user_normalize_arch(arch)]
end

function ok_user_require_arch(arch)
    local normalized = ok_user_normalize_arch(arch)
    local spec = OK_USER_ARCH_SPECS[normalized]
    if spec == nil then
        raise("unsupported first-stage userland arch '%s'; use one of: %s",
              tostring(normalized), table.concat(OK_USER_ARCHES, ", "))
    end
    return normalized, spec
end

function ok_user_kernel_uapi_include()
    local kernel_include = path.join(os.projectdir(), "external", "ObfuscationKernel", "include")
    if os.isfile(path.join(kernel_include, "ok", "uapi", "syscall.h")) then
        return kernel_include
    end
    return path.join(os.projectdir(), "uapi", "include")
end

function add_ok_user_toolchain()
    local _, spec = ok_user_require_arch(ok_user_current_arch())
    set_toolchains("cross@systoolchain")
    add_packages("systoolchain")
    add_defines(spec.define)
end

function add_ok_user_include_dirs()
    local project = os.projectdir()
    add_includedirs(
        path.join(project, "sdk", "include"),
        ok_user_kernel_uapi_include(),
        path.join(project, "lib", "okcrt", "include"),
        {public = true}
    )
end

function add_ok_user_cflags()
    local _, spec = ok_user_require_arch(ok_user_current_arch())
    add_cflags(
        "-ffreestanding",
        "-fno-builtin",
        "-fno-stack-protector",
        "-fdata-sections",
        "-ffunction-sections",
        "-Wall",
        "-Wextra",
        {force = true}
    )
    add_asflags("-ffreestanding", {force = true})
    for _, flag in ipairs(spec.cflags or {}) do
        add_cflags(flag, {force = true})
    end
    for _, flag in ipairs(spec.asflags or {}) do
        add_asflags(flag, {force = true})
    end
end

function add_ok_user_linkflags()
    local _, spec = ok_user_require_arch(ok_user_current_arch())
    add_ldflags(
        "-nostdlib",
        "-static",
        "-Wl,-e,_start",
        "-Wl,--gc-sections",
        {force = true}
    )
    for _, flag in ipairs(spec.ldflags or {}) do
        add_ldflags(flag, {force = true})
    end
end

function ok_user_run_python(batchcmds, script, args)
    local project = os.projectdir()
    local argv = {path.join(project, "tools", script)}
    for _, arg in ipairs(args) do
        table.insert(argv, arg)
    end
    batchcmds:vrunv("python3", argv)
end
