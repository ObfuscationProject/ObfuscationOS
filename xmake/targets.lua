local app_names = {"init", "oksh", "posix-check", "hello", "cat", "ls", "stat", "mkdir", "rm", "pwd", "whoami", "uname", "uptime", "touch", "settings", "tasks", "notes", "about", "kmodload"}

local arch, arch_spec = ok_user_require_arch(ok_user_current_arch())
local project = os.projectdir()
local kernel_uapi_include = ok_user_kernel_uapi_include()
local run_python = ok_user_run_python
local build = ok_user_builddir()
local sdk = ok_user_kernel_sdk()
local mode = get_config("mode") or "release"

local function add_sdk_identity(target)
    -- A downloaded/relocated SDK may preserve timestamps older than existing
    -- objects. Bind the compile signature to content, not file modification time.
    target:add("defines", "OK_KERNEL_SDK_FINGERPRINT_" .. hash.sha256(path.join(sdk, "manifest.json")))
end

target("okcrt")
    set_kind("static")
    set_filename("libokcrt.a")
    set_targetdir(path.join(build, "lib"))
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_deps("kernel-sdk-check")
    add_files(path.join(project, "lib", "okcrt", "src", "*.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "syscall.S"))
    add_ok_user_cflags()
target_end()

for _, name in ipairs(app_names) do
    target("app-" .. name)
        set_kind("binary")
        set_default(false)
        set_filename(name .. ".elf")
        set_targetdir(path.join(build, "apps"))
        add_deps("okcrt")
        add_ok_user_toolchain()
        add_ok_user_include_dirs()
        on_load(add_sdk_identity)
        add_includedirs(path.join(project, "apps", "lib"))
        add_files(path.join(project, "apps", name, "main.c"))
        if name == "init" and is_mode("debug") then
            add_defines("OK_USERLAND_SELFTEST=1")
        end
        if name ~= "init" then
            add_files(path.join(project, "apps", "lib", "commands.c"))
        end
        add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
        add_ok_user_cflags()
        add_ok_user_linkflags()
        add_syslinks("gcc")
    target_end()
end

target("apps")
    set_kind("phony")
    set_default(false)
    for _, name in ipairs(app_names) do
        add_deps("app-" .. name)
    end
target_end()

target("sysroot")
    set_kind("phony")
    set_default(false)
    add_deps("okcrt")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        run_python(batchcmds, "install_sysroot.py", {
            "--project", project,
            "--sysroot", path.join(build, "sysroot"),
            "--lib", path.join(build, "lib", "libokcrt.a"),
            "--arch", arch,
            "--mode", mode,
            "--kernel-sdk", sdk,
        })
    end)
target_end()

target("kernel-sdk-check")
    set_kind("phony")
    set_default(false)
    on_buildcmd(function (target, batchcmds)
        run_python(batchcmds, "kernel_sdk.py", {"validate", "--sdk", sdk, "--arch", arch, "--mode", mode})
    end)
target_end()

target("uapi-test")
    set_kind("phony")
    set_default(false)
    add_deps("sysroot")
    on_buildcmd(function (target, batchcmds)
        run_python(batchcmds, "check_uapi.py", {"--include", path.join(build, "sysroot", "include")})
    end)
target_end()

target("libc-test")
    set_kind("phony")
    add_deps("kernel-sdk-check")
    set_default(false)
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        local out = path.join(build, "tests", "mock_libc")
        batchcmds:mkdir(path.directory(out))
        batchcmds:vrunv("cc", {
            "-Wall",
            "-Wextra",
            "-Isdk/include",
            "-I" .. kernel_uapi_include,
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
target_end()

local function stage_rootfs(batchcmds)
    local project = os.projectdir()
    run_python(batchcmds, "stage_rootfs.py", {
        "--apps-dir", path.join(build, "apps"),
        "--out", path.join(build, "rootfs"),
    })
end

target("rootfs-stage")
    set_kind("phony")
    set_default(false)
    set_policy("build.fence", true)
    add_deps("apps")
    on_buildcmd(function (target, batchcmds)
        stage_rootfs(batchcmds)
    end)
target_end()

target("rootfs-simplefs")
    set_kind("phony")
    set_default(false)
    add_deps("rootfs-stage")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        local root = path.join(build, "rootfs")
        local image = path.join(build, "rootfs.simplefs.img")
        run_python(batchcmds, "mksimplefs.py", {"pack", "--root", root, "--out", image})
        run_python(batchcmds, "mksimplefs.py", {"verify", image, "--root", root})
    end)
target_end()

target("boot-archive")
    set_policy("build.fence", true)
    set_kind("phony")
    set_default(false)
    add_deps("rootfs-stage")
    on_buildcmd(function (target, batchcmds)
        run_python(batchcmds, "mkarchive.py", {
            "--root", path.join(build, "rootfs"),
            "--out", path.join(build, "boot.okar"),
        })
    end)
target_end()

target("rootfs-ext4")
    set_kind("phony")
    set_default(false)
    add_deps("rootfs-stage")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        run_python(batchcmds, "mkext4.py", {
            "--root", path.join(build, "rootfs"),
            "--out", path.join(build, "rootfs.ext4.img"),
        })
    end)
target_end()

-- Only distribution sources compile here. Boot/runtime objects and core kernel
-- are immutable inputs supplied by the selected kernel SDK.
local function add_kernel_sdk_flags(target)
    import("core.base.json")
    os.execv("python3", {path.join(project, "tools", "kernel_sdk.py"), "validate",
        "--sdk", sdk, "--arch", arch, "--mode", mode})
    local manifest = json.loadfile(path.join(sdk, "manifest.json"))
    add_sdk_identity(target)
    target:add("includedirs", path.join(sdk, "include"))
    target:add("cxxflags", manifest.cxxflags, {force = true})
    target:add("defines", manifest.defines)
    target:add("ldflags", manifest.ldflags, {force = true})
end

target("linux-driver-compat")
    set_kind("static")
    set_default(false)
    set_languages("c++23")
    set_targetdir(path.join(build, "lib"))
    add_ok_user_toolchain()
    add_files(path.join(project, "compat/linux/src/*.cpp"))
    add_includedirs(path.join(project, "compat/linux/include"), {public = true})
    on_load(add_kernel_sdk_flags)
    before_build(function (target)
        os.execv("python3", {path.join(project, "tools", "kernel_sdk.py"), "validate",
            "--sdk", sdk, "--arch", arch, "--mode", mode, "--compiler", (target:tool("cxx"))})
    end)
target_end()

target("distro_image")
    add_deps("boot-archive", {inherit = false})
    add_files(path.join(project, "modules/boot/archive.cpp"), path.join(project, "modules/boot/archive.S"))
    add_defines('OK_BOOT_ARCHIVE_INCLUDE="' .. path.join(build, "boot.okar.inc") .. '"')
    set_kind("binary")
    set_default(false)
    set_languages("c++23")
    set_filename("kernel.elf")
    set_targetdir(path.join(build, "distro"))
    add_ok_user_toolchain()
    add_files(path.join(project, "modules/system-gui/external_module.cpp"), path.join(project, "modules/system-gui/system_gui_runtime.cpp"))
    if is_mode("debug") then
        add_files(path.join(project, "modules/system-gui/system_gui_tests.cpp"))
    end
    add_includedirs(path.join(project, "modules/system-gui"))
    on_load(function (target)
        add_kernel_sdk_flags(target)
        target:add("ldflags", "-nostdlib", "-static", "-no-pie", "-Wl,--build-id=none",
            "-Wl,-z,max-page-size=0x1000", "-Wl,-T," .. path.join(sdk, "boot", "linker.ld"),
            "-Wl,--start-group", "-Wl,--whole-archive", path.join(sdk, "lib", "libokernel_boot.a"),
            "-Wl,--no-whole-archive", path.join(sdk, "lib", "libokernel.a"),
            "-lgcc", "-Wl,--end-group", {force = true})
        target:data_add("linkdepfiles", path.join(build, "boot.okar"))
        for _, artifact in ipairs({"manifest.json", "boot/linker.ld", "lib/libokernel_boot.a", "lib/libokernel.a"}) do
            target:data_add("linkdepfiles", path.join(sdk, artifact))
        end
    end)
    before_build(function (target)
        os.execv("python3", {path.join(project, "tools", "kernel_sdk.py"), "validate",
            "--sdk", sdk, "--arch", arch, "--mode", mode, "--compiler", (target:tool("cxx"))})
    end)
    after_build(function (target)
        os.execv("python3", {path.join(project, "tools", "kernel_sdk.py"), "assemble",
            "--sdk", sdk, "--arch", arch, "--mode", mode,
            "--elf", target:targetfile(), "--out", path.join(target:targetdir(), "kernel.bin"),
            "--objcopy", path.join(path.directory(target:tool("cxx")), arch_spec.triple .. "-objcopy")})
    end)
target_end()


target("compat-test")
    set_kind("phony")
    set_default(false)
    add_deps("kernel-sdk-check")
    on_buildcmd(function (target, batchcmds)
        batchcmds:vrunv("python3", {path.join(project, "tests", "run_compat_tests.py"), "--kernel-sdk", sdk})
    end)
target_end()

target("artifact-test")
    set_kind("phony")
    set_default(false)
    on_buildcmd(function (target, batchcmds)
        batchcmds:vrunv("python3", {"-B", "-m", "unittest", "discover", "-s", path.join(project, "tests", "tools"), "-p", "test_*.py"})
    end)
target_end()
