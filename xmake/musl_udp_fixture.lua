-- Explicit fixtures are excluded from default applications and rootfs policy.
local musl_udp_sdk = ok_user_kernel_sdk()
local musl_udp_project = path.absolute(os.projectdir())
target("app-musl-udp-runner")
    set_kind("binary")
    set_default(false)
    set_filename("musl-udp-runner.elf")
    set_strip("none")
    set_targetdir(path.join(ok_user_builddir(), "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(function (target)
        target:add("defines", "OK_KERNEL_SDK_FINGERPRINT_" ..
            hash.sha256(path.join(musl_udp_sdk, "manifest.json")))
    end)
    add_files(path.join(musl_udp_project, "tests/native/musl_udp_runner.c"))
    local _, spec = ok_user_require_arch(ok_user_current_arch())
    add_files(path.join(musl_udp_project, "lib/okcrt/arch", spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

task("musl-udp-probe")
    set_menu {usage = "xmake musl-udp-probe --arch=ARCH --musl-build=DIR --toolchain=DIR --out=DIR",
        description = "Build the explicit musl UDP fixture; does not package or execute it",
        options = {
            {nil, "arch", "kv", nil, "Supplied musl profile: x86_64, aarch64, rv64, loongarch64"},
            {nil, "musl-build", "kv", nil, "Explicit audited musl build directory"},
            {nil, "toolchain", "kv", nil, "Explicit cross toolchain directory"},
            {nil, "out", "kv", nil, "New output directory"},
            {nil, "capture-compile-dependencies", "k", nil, "Record dependencies from the actual object compilation"}
        }}
    on_run(function ()
        import("core.base.option")
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out"}) do
            assert(option.get(name), "musl-udp-probe requires --%s", name)
        end
        local supplied = {x86_64 = true, aarch64 = true, rv64 = true, loongarch64 = true}
        assert(supplied[option.get("arch")], "musl-udp-probe requires a supplied four-profile musl architecture")
        local project = os.projectdir()
        local args = {"-B", path.join(project, "tools/build_musl_probe.py"),
            "--source", path.join(project, "tests/musl/udp.c"),
            "--linker-script", path.join(project, "tests/musl/bootstrap.ld")}
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out"}) do
            table.insert(args, "--" .. name)
            table.insert(args, option.get(name))
        end
        if option.get("capture-compile-dependencies") then
            table.insert(args, "--capture-compile-dependencies")
        end
        os.execv("python3", args)
    end)
task_end()

for _, fixture_option in ipairs({"musl_udp_child_build", "musl_udp_child_manifest_sha256",
                                 "musl_udp_musl_build", "musl_udp_musl_manifest_sha256"}) do
    option(fixture_option)
        set_showmenu(true)
        set_description("Explicit pinned musl UDP experimental fixture input: " .. fixture_option)
    option_end()
end

local fixture_arch, fixture_spec = ok_user_require_arch(ok_user_current_arch())
local fixture_mode = get_config("mode") or "release"
local fixture_build = ok_user_builddir()
local fixture_run_python = ok_user_run_python
local fixture_package = path.join(fixture_build, "fixtures/musl-udp/package")

target("musl-udp-fixture-archive")
    set_kind("phony")
    set_default(false)
    set_policy("build.fence", true)
    add_deps("rootfs-stage", "app-musl-udp-runner", {inherit = false})
    on_buildcmd(function (target, batchcmds)
        local args = {"--arch", fixture_arch, "--mode", fixture_mode,
            "--normal-root", path.join(fixture_build, "rootfs"),
            "--native-parent", path.join(fixture_build, "apps/musl-udp-runner.elf"),
            "--out", fixture_package}
        for _, pair in ipairs({{"musl_udp_child_build", "child-build"},
                               {"musl_udp_child_manifest_sha256", "child-manifest-sha256"},
                               {"musl_udp_musl_build", "musl-build"},
                               {"musl_udp_musl_manifest_sha256", "musl-manifest-sha256"}}) do
            assert(get_config(pair[1]), "musl-udp-fixture-archive requires explicit --%s", pair[1])
            table.insert(args, "--" .. pair[2])
            table.insert(args, get_config(pair[1]))
        end
        fixture_run_python(batchcmds, "package_musl_udp_fixture.py", args)
    end)
target_end()

target("musl-udp-fixture-image")
    set_kind("binary")
    set_default(false)
    set_languages("c++23")
    set_filename("kernel.elf")
    set_targetdir(path.join(fixture_build, "fixtures/musl-udp/distro"))
    add_deps("musl-udp-fixture-archive", {inherit = false})
    add_ok_user_toolchain()
    add_files(path.join(musl_udp_project, "modules/boot/archive.cpp"),
              path.join(musl_udp_project, "modules/boot/archive.S"),
              path.join(musl_udp_project, "modules/boot/storage.cpp"),
              path.join(musl_udp_project, "drivers/virtio/block.cpp"),
              path.join(musl_udp_project, "modules/boot/entropy.cpp"),
              path.join(musl_udp_project, "drivers/virtio/rng.cpp"),
              path.join(musl_udp_project, "modules/system-gui/external_module.cpp"),
              path.join(musl_udp_project, "modules/system-gui/system_gui_runtime.cpp"),
              path.join(musl_udp_project, "drivers/virtio/net.cpp"))
    if is_mode("debug") then
        add_files(path.join(musl_udp_project, "modules/system-gui/system_gui_tests.cpp"))
    end
    add_defines('OK_BOOT_ARCHIVE_INCLUDE="' .. path.join(fixture_package, "boot.okar.inc") .. '"')
    add_includedirs(musl_udp_project, path.join(musl_udp_project, "modules/system-gui"))
    on_load(function (target)
        import("core.base.json")
        os.execv("python3", {"-B", path.join(musl_udp_project, "tools/kernel_sdk.py"), "validate",
            "--sdk", musl_udp_sdk, "--arch", fixture_arch, "--mode", fixture_mode})
        local manifest = json.loadfile(path.join(musl_udp_sdk, "manifest.json"))
        target:add("defines", "OK_KERNEL_SDK_FINGERPRINT_" .. hash.sha256(path.join(musl_udp_sdk, "manifest.json")))
        target:add("includedirs", path.join(musl_udp_sdk, "include"))
        target:add("cxxflags", manifest.cxxflags, {force = true})
        target:add("asflags", manifest.asflags, {force = true})
        target:add("defines", manifest.defines)
        target:add("ldflags", manifest.ldflags, {force = true})
        target:add("ldflags", "-nostdlib", "-static", "-no-pie", "-Wl,--build-id=none",
            "-Wl,-z,max-page-size=0x1000", "-Wl,-T," .. path.join(musl_udp_sdk, "boot/linker.ld"),
            "-Wl,--start-group", "-Wl,--whole-archive", path.join(musl_udp_sdk, "lib/libokernel_boot.a"),
            "-Wl,--no-whole-archive", path.join(musl_udp_sdk, "lib/libokernel.a"),
            "-lgcc", "-Wl,--end-group", {force = true})
        for _, artifact in ipairs({path.join(fixture_package, "boot.okar"), path.join(musl_udp_sdk, "manifest.json"),
                path.join(musl_udp_sdk, "boot/linker.ld"), path.join(musl_udp_sdk, "lib/libokernel_boot.a"),
                path.join(musl_udp_sdk, "lib/libokernel.a")}) do
            target:data_add("linkdepfiles", artifact)
        end
    end)
    before_build(function (target)
        os.execv("python3", {"-B", path.join(musl_udp_project, "tools/kernel_sdk.py"), "validate",
            "--sdk", musl_udp_sdk, "--arch", fixture_arch, "--mode", fixture_mode,
            "--compiler", (target:tool("cxx"))})
    end)
    after_build(function (target)
        os.execv("python3", {"-B", path.join(musl_udp_project, "tools/kernel_sdk.py"), "assemble",
            "--sdk", musl_udp_sdk, "--arch", fixture_arch, "--mode", fixture_mode,
            "--elf", target:targetfile(), "--out", path.join(target:targetdir(), "kernel.bin"),
            "--objcopy", path.join(path.directory((target:tool("cxx"))), fixture_spec.triple .. "-objcopy")})
    end)
target_end()

task("musl-udp-nic-test")
    set_menu {usage = "xmake musl-udp-nic-test --arch=x86_64 --mode=MODE --kernel-sdk=DIR --image=FILE --packaged-child=FILE --output=NEW_DIR",
        description = "Execute an explicit packaged musl UDP fixture over actual QEMU Virtio PCI",
        options = {
            {nil, "arch", "kv", nil, "Actual NIC qualification profile: x86_64"},
            {nil, "mode", "kv", nil, "Explicit matching SDK mode: debug or release"},
            {nil, "kernel-sdk", "kv", nil, "Explicit architecture/mode-specific exported Kernel SDK"},
            {nil, "image", "kv", nil, "Explicit freshly packaged fixture image"},
            {nil, "packaged-child", "kv", nil, "Exact staged /bin/musl-udp-probe ELF"},
            {nil, "qemu", "kv", nil, "Explicit QEMU executable (optional)"},
            {nil, "output", "kv", nil, "New execution evidence directory"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {"-B", path.join(os.projectdir(), "scripts/test_musl_udp_socket.py")}
        for _, name in ipairs({"arch", "mode", "kernel-sdk", "image", "packaged-child", "output"}) do
            assert(option.get(name), "musl-udp-nic-test requires --%s", name)
            table.insert(args, "--" .. name)
            table.insert(args, option.get(name))
        end
        if option.get("qemu") then
            table.insert(args, "--qemu")
            table.insert(args, option.get("qemu"))
        end
        os.execv("python3", args, {envs = {PYTHONDONTWRITEBYTECODE = "1"}})
    end)
task_end()
