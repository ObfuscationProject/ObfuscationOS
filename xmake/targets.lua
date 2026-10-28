local app_names = {"init", "oksh", "posix-check", "udp-probe", "hello", "cat", "ls", "stat", "mkdir", "rm", "mv", "ln", "pwd", "whoami", "uname", "uptime", "touch", "settings", "tasks", "notes", "about", "sync", "kmodload", "service-ctl", "logd", "logger", "timed", "timectl", "mountctl", "resolved", "resolvectl"}

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

-- Pure account policy is built separately until durable login is admitted.
target("account-policy")
    set_kind("static")
    set_default(false)
    set_filename("libokaccounts.a")
    set_targetdir(path.join(build, "lib"))
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_deps("kernel-sdk-check")
    add_files(path.join(project, "apps", "login", "password.c"))
    add_files(path.join(project, "apps", "login", "accounts.c"))
    add_ok_user_cflags()
target_end()

-- Selected by the explicit persistent console profile; maintenance stays separate.
target("app-login")
    set_kind("binary")
    set_default(false)
    set_filename("login.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "apps", "login", "*.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
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
        if name == "logd" or name == "logger" then
            add_files(path.join(project, "apps", "logging", "*.c"))
        end
        if name == "timed" or name == "timectl" then
            add_files(path.join(project, "apps", "time", "*.c"))
        end
        if name == "resolved" or name == "resolvectl" then
            add_files(path.join(project, "apps", "resolver", "*.c"))
        end
        if name == "notes" then
            add_files(path.join(project, "apps", "notes", "save.c"))
        end
        if name == "posix-check" then
            add_files(path.join(project, "apps", "posix-check", "fat.c"))
        end
        if name == "init" then
            add_defines("OK_NATIVE_CONSOLE_LEASE=1")
            if get_config("native_console_login") then add_defines("OK_NATIVE_CONSOLE_LOGIN=1") end
            add_files(path.join(project, "apps", "init", "native_supervisor.c"))
            if get_config("native_init_control") then
                add_defines("OK_NATIVE_INIT_CONTROL=1")
                add_files(path.join(project, "apps", "init", "native_control.c"))
            end
        end
        if name == "service-ctl" then
            add_files(path.join(project, "apps", "init", "native_control_client.c"))
        end
        if name == "init" and (get_config("native_init_acceptance") or get_config("native_udp_probe") or get_config("native_vm_acceptance")) then
            add_defines("OK_USERLAND_SELFTEST=1")
            if get_config("native_udp_probe") then add_defines("OK_NATIVE_UDP_PROBE=1") end
        end
        if name == "udp-probe" then
            add_defines(is_mode("debug") and "OK_NATIVE_UDP_TEST_DEBUG" or "OK_NATIVE_UDP_TEST_RELEASE")
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

target("app-musl-test-runner")
    set_kind("binary")
    set_default(false)
    set_filename("musl-test-runner.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "tests", "musl", "runner.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

target("app-dynamic-startup-runner")
    set_kind("binary")
    set_default(false)
    set_filename("dynamic-startup-runner.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "tests", "native", "dynamic_startup_runner.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

target("app-static-entropy-runner")
    set_kind("binary")
    set_default(false)
    set_filename("static-entropy-runner.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "tests", "native", "static_entropy_runner.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

target("app-unix-socketpair-runner")
    set_kind("binary")
    set_default(false)
    set_filename("unix-socketpair-runner.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "tests", "native", "unix_socketpair_runner.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

target("app-unix-rights-runner")
    set_kind("binary")
    set_default(false)
    set_filename("unix-rights-runner.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "tests", "native", "unix_rights_runner.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

target("app-unix-pathname-runner")
    set_kind("binary")
    set_default(false)
    set_filename("unix-pathname-runner.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "tests", "native", "unix_pathname_runner.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

target("app-clock-set-runner")
    set_kind("binary")
    set_default(false)
    set_filename("clock-set-runner.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "tests", "musl", "clock_set_runner.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

target("app-ext4-timestamps-runner")
    set_kind("binary")
    set_default(false)
    set_filename("ext4-timestamps-runner.elf")
    set_targetdir(path.join(build, "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(add_sdk_identity)
    add_files(path.join(project, "tests", "musl", "ext4_timestamps_runner.c"))
    add_files(path.join(project, "lib", "okcrt", "arch", arch_spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

target("apps")
    set_kind("phony")
    set_default(false)
    for _, name in ipairs(app_names) do
        add_deps("app-" .. name)
    end
    if get_config("native_console_login") then add_deps("app-login") end
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

target("virtio-net-queue-test")
    set_kind("phony")
    set_default(false)
    add_deps("kernel-sdk-check")
    on_buildcmd(function (target, batchcmds)
        local out = path.join(build, "tests", "virtio-net-queue")
        batchcmds:mkdir(path.directory(out))
        batchcmds:vrunv("c++", {"-std=c++23", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-I" .. path.join(sdk, "include"), "-I" .. project,
            path.join(project, "tests/drivers/virtio_net_queue_tests.cpp"), "-o", out})
        batchcmds:vrunv(out, {})
    end)
target_end()

target("virtio-net-tx-queue-test")
    set_kind("phony")
    set_default(false)
    add_deps("kernel-sdk-check")
    on_buildcmd(function (target, batchcmds)
        local out = path.join(build, "tests", "virtio-net-tx-queue")
        batchcmds:mkdir(path.directory(out))
        batchcmds:vrunv("c++", {"-std=c++23", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-I" .. path.join(sdk, "include"), "-I" .. project,
            path.join(project, "tests/drivers/virtio_net_tx_queue_tests.cpp"), "-o", out})
        batchcmds:vrunv(out, {})
    end)
target_end()

target("virtio-net-inactive-test")
    set_kind("phony")
    set_default(false)
    add_deps("kernel-sdk-check")
    on_buildcmd(function (target, batchcmds)
        local out = path.join(build, "tests", "virtio-net-inactive")
        batchcmds:mkdir(path.directory(out))
        batchcmds:vrunv("c++", {"-std=c++23", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-I" .. path.join(sdk, "include"), "-I" .. project,
            path.join(project, "tests/drivers/virtio_net_inactive_tests.cpp"),
            path.join(project, "drivers/virtio/net.cpp"), "-o", out})
        batchcmds:vrunv(out, {})
    end)
target_end()

target("virtio-net-receive-test")
    set_kind("phony")
    set_default(false)
    on_buildcmd(function (target, batchcmds)
        local out = path.join(build, "tests", "virtio-net-receive")
        batchcmds:mkdir(path.directory(out))
        batchcmds:vrunv("c++", {"-std=c++23", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", "-I" .. project, "-I" .. path.join(sdk, "include"),
            path.join(project, "tests/drivers/virtio_net_receive_tests.cpp"), "-o", out})
        batchcmds:vrunv(out, {})
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

-- Rootfs profiles: full (build/rootfs: every program, the musl userland and its
-- tests), rescue (build/rootfs-rescue: okcrt only, packed into SimpleFS) and
-- release (build/rootfs-release: no acceptance programs or test suites).
local function stage_rootfs(batchcmds, profile, out)
    local project = os.projectdir()
    local args = {
        "--apps-dir", path.join(build, "apps"),
        "--out", path.join(build, out),
        "--profile", profile,
    }
    if get_config("native_console_login") then table.insert(args, "--console-login") end
    if get_config("native_init_acceptance") or get_config("native_vm_acceptance") or get_config("native_udp_probe") then
        table.insert(args, "--acceptance")
    end
    local userland = get_config("userland_build")
    local userland_pin = get_config("userland_manifest_sha256")
    if (userland ~= nil) ~= (userland_pin ~= nil) then
        raise("userland_build and userland_manifest_sha256 must be supplied together")
    end
    if userland and profile ~= "rescue" then
        table.insert(args, "--userland-build")
        table.insert(args, path.absolute(userland))
        table.insert(args, "--userland-manifest-sha256")
        table.insert(args, userland_pin)
        table.insert(args, "--arch")
        table.insert(args, arch)
    end
    local managed = get_config("managed_init_build")
    local pin = get_config("managed_init_manifest_sha256")
    if (managed ~= nil) ~= (pin ~= nil) then
        raise("managed_init_build and managed_init_manifest_sha256 must be supplied together")
    end
    if managed then
        table.insert(args, "--managed-init-build")
        table.insert(args, path.absolute(managed))
        table.insert(args, "--managed-init-manifest-sha256")
        table.insert(args, pin)
        table.insert(args, "--arch")
        table.insert(args, arch)
    end
    local graph = get_config("service_graph_build")
    local graph_pin = get_config("service_graph_manifest_sha256")
    if (graph ~= nil) ~= (graph_pin ~= nil) then
        raise("service_graph_build and service_graph_manifest_sha256 must be supplied together")
    end
    if graph and managed then raise("only one explicit production init profile may be installed") end
    if graph then
        table.insert(args, "--service-graph-build")
        table.insert(args, path.absolute(graph))
        table.insert(args, "--service-graph-manifest-sha256")
        table.insert(args, graph_pin)
        table.insert(args, "--arch")
        table.insert(args, arch)
    end
    run_python(batchcmds, "stage_rootfs.py", args)
end

target("rootfs-stage")
    set_kind("phony")
    set_default(false)
    set_policy("build.fence", true)
    add_deps("apps")
    on_buildcmd(function (target, batchcmds)
        stage_rootfs(batchcmds, "full", "rootfs")
    end)
target_end()

target("rootfs-rescue-stage")
    set_kind("phony")
    set_default(false)
    set_policy("build.fence", true)
    add_deps("apps")
    on_buildcmd(function (target, batchcmds)
        stage_rootfs(batchcmds, "rescue", "rootfs-rescue")
    end)
target_end()

target("rootfs-release-stage")
    set_kind("phony")
    set_default(false)
    set_policy("build.fence", true)
    add_deps("apps")
    on_buildcmd(function (target, batchcmds)
        stage_rootfs(batchcmds, "release", "rootfs-release")
    end)
target_end()

-- SimpleFS is the fixed 32-entry rescue/test image; its on-disk format is kept
-- unchanged. It packs the okcrt-only rescue tree, which still exceeds that cap,
-- so the supervised service programs (started only from ext4 roots through
-- services*.conf) are omitted here. The archive unit tests still require an unfiltered 33+-entry root to
-- be rejected.
local simplefs_omit = "logd,logger,timed,timectl,resolved,resolvectl,mountctl,service-ctl"

target("rootfs-simplefs")
    set_kind("phony")
    set_default(false)
    add_deps("rootfs-rescue-stage")
    on_buildcmd(function (target, batchcmds)
        local project = os.projectdir()
        local root = path.join(build, "rootfs-rescue")
        local image = path.join(build, "rootfs.simplefs.img")
        run_python(batchcmds, "mksimplefs.py", {"pack", "--root", root, "--out", image, "--omit", simplefs_omit})
        run_python(batchcmds, "mksimplefs.py", {"verify", image, "--root", root, "--omit", simplefs_omit})
    end)
target_end()

-- The embedded fallback root is the okcrt rescue tree: the archive format holds
-- regular files and directories only, never the musl userland's links.
target("boot-archive")
    set_policy("build.fence", true)
    set_kind("phony")
    set_default(false)
    add_deps("rootfs-rescue-stage")
    on_buildcmd(function (target, batchcmds)
        run_python(batchcmds, "mkarchive.py", {
            "--root", path.join(build, "rootfs-rescue"),
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

target("rootfs-release")
    set_kind("phony")
    set_default(false)
    add_deps("rootfs-release-stage")
    on_buildcmd(function (target, batchcmds)
        run_python(batchcmds, "mkext4.py", {
            "--root", path.join(build, "rootfs-release"),
            "--out", path.join(build, "rootfs.release.img"),
        })
    end)
target_end()

target("rootfs-ext4-journalled")
    set_kind("phony")
    set_default(false)
    add_deps("rootfs-stage")
    on_buildcmd(function (target, batchcmds)
        assert(get_config("linux_journal_image") and get_config("linux_journal_image_sha256"),
            "journalled root requires explicit pinned Linux activation image")
        local args = {
            "--root", path.join(build, "rootfs"),
            "--out", path.join(build, get_config("native_console_login") and
                "rootfs.login.ext4-journalled.img" or "rootfs.ext4-journalled.img"),
            "--linux-image", get_config("linux_journal_image"),
            "--linux-image-sha256", get_config("linux_journal_image_sha256"),
        }
        if get_config("native_console_login") then table.insert(args, "--console-login") end
        run_python(batchcmds, "mkext4_journalled.py", args)
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
    target:add("asflags", manifest.asflags, {force = true})
    target:add("defines", manifest.defines)
    target:add("ldflags", manifest.ldflags, {force = true})
end

-- Compile the production driver against one validated SDK without constructing
-- a distribution image or executing device I/O. Full integration is separate.
target("virtio-net-driver")
    set_kind("static")
    set_default(false)
    set_languages("c++23")
    set_targetdir(path.join(build, "lib"))
    add_ok_user_toolchain()
    add_files(path.join(project, "drivers/virtio/net.cpp"))
    add_includedirs(project)
    on_load(add_kernel_sdk_flags)
    before_build(function (target)
        os.execv("python3", {path.join(project, "tools", "kernel_sdk.py"), "validate",
            "--sdk", sdk, "--arch", arch, "--mode", mode, "--compiler", (target:tool("cxx"))})
    end)
target_end()

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
    add_files(path.join(project, "modules/boot/archive.cpp"), path.join(project, "modules/boot/archive.S"),
              path.join(project, "modules/boot/storage.cpp"), path.join(project, "drivers/virtio/block.cpp"),
              path.join(project, "modules/boot/entropy.cpp"), path.join(project, "drivers/virtio/rng.cpp"))
    add_defines('OK_BOOT_ARCHIVE_INCLUDE="' .. path.join(build, "boot.okar.inc") .. '"')
    -- musl programs need Linux stat, which the kernel answers only for a root
    -- with maintained timestamps (modules/boot/storage.cpp).
    if get_config("userland_build") then add_defines("OK_MAINTAINED_ROOT=1") end
    set_kind("binary")
    set_default(false)
    set_languages("c++23")
    set_filename("kernel.elf")
    set_targetdir(path.join(build, "distro"))
    add_ok_user_toolchain()
    add_files(path.join(project, "modules/system-gui/external_module.cpp"), path.join(project, "modules/system-gui/system_gui_runtime.cpp"),
              path.join(project, "drivers/virtio/net.cpp"))
    if is_mode("debug") then
        add_files(path.join(project, "modules/system-gui/system_gui_tests.cpp"))
    end
    add_includedirs(project, path.join(project, "modules/system-gui"))
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
            "--sdk", sdk, "--arch", arch, "--mode", mode, "--compiler", (target:tool("cxx")),
            "--require-fat-filesystem"})
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
        -- Fifteen tool suites compile fixtures against the configured SDK and
        -- require OK_TEST_KERNEL_SDK; run the whole discovery with it, and the
        -- architecture and mode it was exported for, set.
        batchcmds:vrunv("python3", {"-B", "-m", "unittest", "discover", "-s", path.join(project, "tests", "tools"), "-p", "test_*.py"},
            {envs = {OK_TEST_KERNEL_SDK = sdk, OK_TEST_KERNEL_ARCH = arch, OK_TEST_KERNEL_MODE = mode,
                     PYTHONDONTWRITEBYTECODE = "1"}})
    end)
target_end()

task("notes-boundary-test")
    set_category("action")
    set_menu {
        usage = "xmake notes-boundary-test [options]",
        description = "Check staged Notes writes at qualified file-block boundaries",
        options = {
            {nil, "output", "kv", nil, "Fresh hosted evidence directory"},
            {nil, "cc", "kv", "cc", "Host C compiler"},
            {nil, "sanitize", "k", nil, "Enable ASan and UBSan"},
            {nil, "predecessor-root", "kv", nil, "Explicit unchanged OS source for counterexample"}
        }
    }
    on_run(function ()
        import("core.base.option")
        local output = option.get("output")
        assert(output, "--output is required")
        local argv = {"-B", "tools/test_notes_boundaries.py", "--output", output,
                      "--cc", option.get("cc")}
        if option.get("sanitize") then table.insert(argv, "--sanitize") end
        if option.get("predecessor-root") then
            table.insert(argv, "--predecessor-root")
            table.insert(argv, option.get("predecessor-root"))
        end
        os.execv("python3", argv, {envs = {PYTHONDONTWRITEBYTECODE = "1"}})
    end)
