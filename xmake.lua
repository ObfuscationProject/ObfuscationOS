set_project("ObfuscationOS")
set_version("0.1.0")
set_languages("c11")

add_rules("mode.debug", "mode.release")
includes("toolchains/*.lua")

option("cross_prefix")
    set_default("")
    set_showmenu(true)
option("auto_bootstrap_toolchain")
    set_default(true)
    set_showmenu(true)

local app_names = {"init", "oksh", "hello", "cat", "ls", "stat", "mkdir", "rm"}

local function normalize_arch(arch)
    if arch == "x64" or arch == "amd64" then
        return "x86_64"
    elseif arch == "arm64" then
        return "aarch64"
    elseif arch == "riscv64" then
        return "rv64"
    elseif arch == "loong64" then
        return "loongarch64"
    end
    return arch
end

local function resolve_arch()
    local arch = get_config("arch")
    if not arch or arch == "" then
        arch = os.arch()
    end
    return normalize_arch(arch)
end

local function assert_supported_arch(arch)
    local supported = {
        x86_64 = true,
        aarch64 = true,
        rv64 = true,
        loongarch64 = true,
    }
    if not supported[arch] then
        raise("Unsupported first-stage userland arch: " .. tostring(arch))
    end
end

local function resolve_elf_target(arch)
    arch = normalize_arch(arch)
    if arch == "x86_64" then
        return "x86_64-elf"
    elseif arch == "aarch64" then
        return "aarch64-none-elf"
    elseif arch == "rv64" then
        return "riscv64-unknown-elf"
    elseif arch == "loongarch64" then
        return "loongarch64-unknown-elf"
    end
    raise("Unsupported arch for ELF toolchain: " .. tostring(arch))
end

local function add_user_cflags(arch)
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
    if arch == "x86_64" then
        add_cflags("-m64", "-mno-red-zone", {force = true})
        add_asflags("-m64", {force = true})
    elseif arch == "rv64" then
        add_cflags("-march=rv64gc", "-mabi=lp64", {force = true})
        add_asflags("-march=rv64gc", "-mabi=lp64", {force = true})
    end
end

local function add_user_linkflags(arch)
    add_ldflags(
        "-nostdlib",
        "-static",
        "-Wl,-e,_start",
        "-Wl,--gc-sections",
        {force = true}
    )
    if arch == "x86_64" then
        add_ldflags("-no-pie", "-Wl,-z,max-page-size=0x1000", {force = true})
    end
end

local function py(batchcmds, project, script, args)
    local argv = {path.join(project, "tools", script)}
    for _, arg in ipairs(args) do
        table.insert(argv, arg)
    end
    batchcmds:vrunv("python3", argv)
end

local arch = resolve_arch()
assert_supported_arch(arch)

target("okcrt")
    set_kind("static")
    set_filename("libokcrt.a")
    set_targetdir(path.join(os.projectdir(), "build", "lib"))
    set_toolchains("elf")
    add_includedirs("sdk/include", "uapi/include", "lib/okcrt/include", {public = true})
    add_files("lib/okcrt/src/*.c")
    add_files(path.join("lib", "okcrt", "arch", arch, "syscall.S"))
    add_user_cflags(arch)

for _, name in ipairs(app_names) do
    target("app-" .. name)
        set_kind("binary")
        set_default(false)
        set_filename(name .. ".elf")
        set_targetdir(path.join(os.projectdir(), "build", "apps"))
        set_toolchains("elf")
        add_deps("okcrt")
        add_includedirs("sdk/include", "uapi/include", "lib/okcrt/include", "apps/lib")
        add_files(path.join("apps", name, "main.c"))
        if name ~= "init" then
            add_files("apps/lib/commands.c")
        end
        add_files(path.join("lib", "okcrt", "arch", arch, "crt0.S"))
        add_user_cflags(arch)
        add_user_linkflags(arch)
        add_links("gcc")
end

target("apps")
    set_kind("phony")
    set_default(false)
    for _, name in ipairs(app_names) do
        add_deps("app-" .. name)
    end

target("sysroot")
    set_kind("phony")
    set_default(false)
    add_deps("okcrt")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        py(batchcmds, project, "install_sysroot.py", {
            "--project", project,
            "--sysroot", path.join(project, "sysroot"),
            "--lib", path.join(project, "build", "lib", "libokcrt.a"),
            "--arch", arch,
        })
    end)

target("kernel-submodule-check")
    set_kind("phony")
    set_default(false)
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        py(batchcmds, project, "kernel_submodule_check.py", {"--project", project})
    end)

target("uapi-test")
    set_kind("phony")
    set_default(false)
    add_deps("sysroot")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        py(batchcmds, project, "check_uapi.py", {"--include", path.join(project, "sysroot", "include")})
    end)

target("libc-test")
    set_kind("phony")
    set_default(false)
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        local out = path.join(project, "build", "tests", "mock_libc")
        batchcmds:mkdir(path.directory(out))
        batchcmds:vrunv("cc", {
            "-Wall",
            "-Wextra",
            "-Isdk/include",
            "-Iuapi/include",
            "-Ilib/okcrt/include",
            "tests/mock_libc.c",
            "lib/okcrt/src/errno.c",
            "lib/okcrt/src/string.c",
            "lib/okcrt/src/syscalls.c",
            "-o",
            out,
        })
        batchcmds:vrunv(out, {})
    end)

local function stage_rootfs(batchcmds, project)
    py(batchcmds, project, "stage_rootfs.py", {
        "--apps-dir", path.join(project, "build", "apps"),
        "--out", path.join(project, "build", "rootfs"),
    })
end

target("rootfs-simplefs")
    set_kind("phony")
    set_default(false)
    add_deps("apps")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        stage_rootfs(batchcmds, project)
        local image = path.join(project, "build", "rootfs.simplefs.img")
        local root = path.join(project, "build", "rootfs")
        py(batchcmds, project, "mksimplefs.py", {
            "pack",
            "--root", root,
            "--out", image,
        })
        py(batchcmds, project, "mksimplefs.py", {
            "verify",
            image,
            "--root", root,
        })
    end)

target("rootfs-ext4")
    set_kind("phony")
    set_default(false)
    add_deps("apps")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        stage_rootfs(batchcmds, project)
        py(batchcmds, project, "mkext4.py", {
            "--root", path.join(project, "build", "rootfs"),
            "--out", path.join(project, "build", "rootfs.ext4.img"),
        })
    end)

task("toolchain")
    set_menu({
        usage = "xmake toolchain",
        description = "Download and build a bare-metal ELF toolchain for the configured 64-bit arch",
        options = {}
    })
    on_run(function ()
        local target = resolve_elf_target(resolve_arch())
        local script = path.join(os.projectdir(), "build-toolchain", "build-elf-toolchain.sh")
        if not os.isfile(script) then
            raise("toolchain bootstrap script not found: " .. script)
        end
        os.exec("bash %s --target %s", script, target)
    end)

task("qemu-distro")
    set_menu({
        usage = "xmake qemu-distro --fs=<simplefs|ext4>",
        description = "Run the external kernel with an ObfuscationOS rootfs image",
        options = {
            {"f", "fs", "kv", "simplefs", "Root filesystem image to run: simplefs or ext4"},
        }
    })
    on_run(function ()
        local option = import("core.base.option")
        local fs = option.get("fs") or "simplefs"
        if fs ~= "simplefs" and fs ~= "ext4" then
            raise("unsupported fs: " .. tostring(fs))
        end

        local target = fs == "simplefs" and "rootfs-simplefs" or "rootfs-ext4"
        os.exec("xmake build %s", target)

        local project = os.projectdir()
        local kernel_dir = path.join(project, "external", "ObfuscationKernel")
        local kernels = os.files(path.join(kernel_dir, "build", "**", "kernel.elf"))
        if #kernels == 0 then
            raise("kernel.elf not found under external/ObfuscationKernel/build; build the kernel submodule first")
        end

        local image = fs == "simplefs"
            and path.join(project, "build", "rootfs.simplefs.img")
            or path.join(project, "build", "rootfs.ext4.img")

        local qemu_map = {
            x86_64 = "qemu-system-x86_64",
            aarch64 = "qemu-system-aarch64",
            rv64 = "qemu-system-riscv64",
            loongarch64 = "qemu-system-loongarch64",
        }
        local qemu = qemu_map[arch]
        if not qemu then
            raise("no qemu binary mapping for arch: " .. tostring(arch))
        end

        os.exec("%s -m 512M -kernel %s -drive file=%s,format=raw,media=disk -serial stdio -no-reboot -no-shutdown",
            qemu, kernels[1], image)
    end)
