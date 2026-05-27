local app_names = {"init", "oksh", "hello", "cat", "ls", "stat", "mkdir", "rm", "kmodload"}

local arch, arch_spec = ok_user_require_arch(ok_user_current_arch())
local project = os.projectdir()
local kernel_uapi_include = ok_user_kernel_uapi_include()
local run_python = ok_user_run_python

target("okcrt")
    set_kind("static")
    set_filename("libokcrt.a")
    set_targetdir(path.join(os.projectdir(), "build", "lib"))
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    add_files(path.join(project, "lib", "okcrt", "src", "*.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "syscall.S"))
    add_ok_user_cflags()
target_end()

for _, name in ipairs(app_names) do
    target("app-" .. name)
        set_kind("binary")
        set_default(false)
        set_filename(name .. ".elf")
        set_targetdir(path.join(os.projectdir(), "build", "apps"))
        add_deps("okcrt")
        add_ok_user_toolchain()
        add_ok_user_include_dirs()
        add_includedirs(path.join(project, "apps", "lib"))
        add_files(path.join(project, "apps", name, "main.c"))
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
            "--sysroot", path.join(project, "sysroot"),
            "--lib", path.join(project, "build", "lib", "libokcrt.a"),
            "--arch", arch,
        })
    end)
target_end()

target("kernel-submodule-check")
    set_kind("phony")
    set_default(false)
    on_buildcmd(function (target, batchcmds)
        run_python(batchcmds, "kernel_submodule_check.py", {"--project", os.projectdir()})
    end)
target_end()

target("uapi-test")
    set_kind("phony")
    set_default(false)
    add_deps("sysroot")
    on_buildcmd(function (target, batchcmds)
        run_python(batchcmds, "check_uapi.py", {"--include", path.join(os.projectdir(), "sysroot", "include")})
    end)
target_end()

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
        local root = path.join(project, "build", "rootfs")
        local image = path.join(project, "build", "rootfs.simplefs.img")
        stage_rootfs(batchcmds)
        run_python(batchcmds, "mksimplefs.py", {"pack", "--root", root, "--out", image})
        run_python(batchcmds, "mksimplefs.py", {"verify", image, "--root", root})
    end)
target_end()

target("rootfs-ext4")
    set_kind("phony")
    set_default(false)
    add_deps("apps")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        stage_rootfs(batchcmds)
        run_python(batchcmds, "mkext4.py", {
            "--root", path.join(project, "build", "rootfs"),
            "--out", path.join(project, "build", "rootfs.ext4.img"),
        })
    end)
target_end()
