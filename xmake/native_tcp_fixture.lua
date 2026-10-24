option("native_tcp_peer_port")
    set_showmenu(true)
    set_description("Explicit owned host port for the non-default native TCP fixture")
option_end()

-- Explicit fixtures are excluded from default applications and rootfs policy.
local native_tcp_sdk = ok_user_kernel_sdk()
local native_tcp_arch = ok_user_current_arch()
local native_tcp_project = path.absolute(os.projectdir())
target("app-native-tcp-probe")
    set_kind("binary")
    set_default(false)
    set_filename("native-tcp-probe.elf")
    set_strip("none")
    set_targetdir(path.join(ok_user_builddir(), "apps"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    add_files(path.join(native_tcp_project, "tests/native/native_tcp_probe.c"))
    local _, spec = ok_user_require_arch(native_tcp_arch)
    add_files(path.join(native_tcp_project, "lib/okcrt/arch", spec.source, "crt0.S"))
    on_load(function (target)
        target:add("defines", "OK_KERNEL_SDK_FINGERPRINT_" .. hash.sha256(path.join(native_tcp_sdk, "manifest.json")))
        local port = get_config("native_tcp_peer_port")
        if port then
            assert(tostring(port):match("^[0-9]+$") and tonumber(port) > 1024 and tonumber(port) < 65535,
                   "native TCP fixture requires a decimal host port in 1025..65534")
            target:add("defines", "OK_NATIVE_TCP_PEER_PORT=" .. tostring(port))
        end
    end)
    before_build(function ()
        assert(native_tcp_arch == "x86_64" and get_config("native_tcp_peer_port"),
               "native TCP immediate fixture currently requires x86_64 and an explicit host peer port")
    end)
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()

local fixture_arch, fixture_spec = ok_user_require_arch(native_tcp_arch)
local fixture_mode = get_config("mode") or "release"
local fixture_build = ok_user_builddir()
local fixture_run_python = ok_user_run_python
local fixture_package = path.join(fixture_build, "fixtures/native-tcp/package")

target("native-tcp-fixture-archive")
    set_kind("phony")
    set_default(false)
    set_policy("build.fence", true)
    add_deps("rootfs-stage", "app-native-tcp-probe", {inherit = false})
    on_buildcmd(function (target, batchcmds)
        assert(fixture_arch == "x86_64", "native TCP immediate fixture currently requires x86_64")
        fixture_run_python(batchcmds, "package_native_tcp_fixture.py", {
            "--arch", fixture_arch, "--mode", fixture_mode,
            "--normal-root", path.join(fixture_build, "rootfs"),
            "--probe", path.join(fixture_build, "apps/native-tcp-probe.elf"),
            "--out", fixture_package})
    end)
target_end()

target("native-tcp-fixture-image")
    set_kind("binary")
    set_default(false)
    set_languages("c++23")
    set_filename("kernel.elf")
    set_targetdir(path.join(fixture_build, "fixtures/native-tcp/distro"))
    add_deps("native-tcp-fixture-archive", {inherit = false})
    add_ok_user_toolchain()
    add_files(path.join(native_tcp_project, "modules/boot/archive.cpp"),
              path.join(native_tcp_project, "modules/boot/archive.S"),
              path.join(native_tcp_project, "modules/boot/storage.cpp"),
              path.join(native_tcp_project, "drivers/virtio/block.cpp"),
              path.join(native_tcp_project, "modules/boot/entropy.cpp"),
              path.join(native_tcp_project, "drivers/virtio/rng.cpp"),
              path.join(native_tcp_project, "modules/system-gui/external_module.cpp"),
              path.join(native_tcp_project, "modules/system-gui/system_gui_runtime.cpp"),
              path.join(native_tcp_project, "drivers/virtio/net.cpp"))
    if is_mode("debug") then
        add_files(path.join(native_tcp_project, "modules/system-gui/system_gui_tests.cpp"))
    end
    add_defines('OK_BOOT_ARCHIVE_INCLUDE="' .. path.join(fixture_package, "boot.okar.inc") .. '"')
    add_defines("OK_PRIVATE_NATIVE_TCP_SLIRP_FIXTURE")
    add_includedirs(native_tcp_project, path.join(native_tcp_project, "modules/system-gui"))
    on_load(function (target)
        import("core.base.json")
        os.execv("python3", {"-B", path.join(native_tcp_project, "tools/kernel_sdk.py"), "validate",
            "--sdk", native_tcp_sdk, "--arch", fixture_arch, "--mode", fixture_mode})
        local manifest = json.loadfile(path.join(native_tcp_sdk, "manifest.json"))
        target:add("defines", "OK_KERNEL_SDK_FINGERPRINT_" .. hash.sha256(path.join(native_tcp_sdk, "manifest.json")))
        target:add("includedirs", path.join(native_tcp_sdk, "include"))
        target:add("cxxflags", manifest.cxxflags, {force = true})
        target:add("asflags", manifest.asflags, {force = true})
        target:add("defines", manifest.defines)
        target:add("ldflags", manifest.ldflags, {force = true})
        target:add("ldflags", "-nostdlib", "-static", "-no-pie", "-Wl,--build-id=none",
            "-Wl,-z,max-page-size=0x1000", "-Wl,-T," .. path.join(native_tcp_sdk, "boot/linker.ld"),
            "-Wl,--start-group", "-Wl,--whole-archive", path.join(native_tcp_sdk, "lib/libokernel_boot.a"),
            "-Wl,--no-whole-archive", path.join(native_tcp_sdk, "lib/libokernel.a"),
            "-lgcc", "-Wl,--end-group", {force = true})
        for _, artifact in ipairs({path.join(fixture_package, "boot.okar"), path.join(native_tcp_sdk, "manifest.json"),
                path.join(native_tcp_sdk, "boot/linker.ld"), path.join(native_tcp_sdk, "lib/libokernel_boot.a"),
                path.join(native_tcp_sdk, "lib/libokernel.a")}) do
            target:data_add("linkdepfiles", artifact)
        end
    end)
    before_build(function (target)
        os.execv("python3", {"-B", path.join(native_tcp_project, "tools/kernel_sdk.py"), "validate",
            "--sdk", native_tcp_sdk, "--arch", fixture_arch, "--mode", fixture_mode,
            "--compiler", (target:tool("cxx"))})
    end)
    after_build(function (target)
        os.execv("python3", {"-B", path.join(native_tcp_project, "tools/kernel_sdk.py"), "assemble",
            "--sdk", native_tcp_sdk, "--arch", fixture_arch, "--mode", fixture_mode,
            "--elf", target:targetfile(), "--out", path.join(target:targetdir(), "kernel.bin"),
            "--objcopy", path.join(path.directory((target:tool("cxx"))), fixture_spec.triple .. "-objcopy")})
    end)
target_end()

