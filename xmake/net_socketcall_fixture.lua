-- Explicit fixture: the net_probe distribution with a Linux-personality
-- socketcall probe in its rescue root (scripts/test_net_socketcall.py).
-- Excluded from default applications, rootfs policy and images.
local socketcall_sdk = ok_user_kernel_sdk()
local socketcall_project = path.absolute(os.projectdir())
local socketcall_arch, socketcall_spec = ok_user_require_arch(ok_user_current_arch())
local socketcall_mode = get_config("mode") or "release"
local socketcall_build = ok_user_builddir()
local socketcall_package = path.join(socketcall_build, "fixtures/net-socketcall/package")
local socketcall_run_python = ok_user_run_python

target("net-socketcall-fixture-archive")
    set_kind("phony")
    set_default(false)
    set_policy("build.fence", true)
    add_deps("rootfs-rescue-stage", {inherit = false})
    on_buildcmd(function (target, batchcmds)
        assert(socketcall_arch == "i386" or socketcall_arch == "mips" or socketcall_arch == "ppc",
               "the socketcall fixture applies to i386, mips and ppc only")
        local toolchain = get_config("systoolchain_dir")
        assert(toolchain, "the socketcall fixture requires --systoolchain_dir")
        socketcall_run_python(batchcmds, "package_net_socketcall_fixture.py", {
            "--arch", socketcall_arch,
            "--compiler", path.join(toolchain, "bin", socketcall_spec.triple .. "-gcc"),
            "--rescue-root", path.join(socketcall_build, "rootfs-rescue"),
            "--out", socketcall_package})
    end)
target_end()

target("net-socketcall-fixture-image")
    set_kind("binary")
    set_default(false)
    set_languages("c++23")
    set_filename("kernel.elf")
    set_targetdir(path.join(socketcall_build, "fixtures/net-socketcall/distro"))
    add_deps("net-socketcall-fixture-archive", {inherit = false})
    add_ok_user_toolchain()
    add_files(path.join(socketcall_project, "modules/boot/archive.cpp"),
              path.join(socketcall_project, "modules/boot/archive.S"),
              path.join(socketcall_project, "modules/boot/storage.cpp"),
              path.join(socketcall_project, "drivers/virtio/block.cpp"),
              path.join(socketcall_project, "modules/boot/entropy.cpp"),
              path.join(socketcall_project, "drivers/virtio/rng.cpp"),
              path.join(socketcall_project, "modules/system-gui/external_module.cpp"),
              path.join(socketcall_project, "modules/system-gui/system_gui_runtime.cpp"),
              path.join(socketcall_project, "drivers/virtio/net.cpp"))
    if is_mode("debug") then
        add_files(path.join(socketcall_project, "modules/system-gui/system_gui_tests.cpp"))
    end
    -- The kernel link probe brings the interface up first (OS_NET_PROBE).
    add_defines('OK_BOOT_ARCHIVE_INCLUDE="' .. path.join(socketcall_package, "boot.okar.inc") .. '"', "OS_NET_PROBE=1")
    add_includedirs(socketcall_project, path.join(socketcall_project, "modules/system-gui"))
    on_load(function (target)
        import("core.base.json")
        os.execv("python3", {"-B", path.join(socketcall_project, "tools/kernel_sdk.py"), "validate",
            "--sdk", socketcall_sdk, "--arch", socketcall_arch, "--mode", socketcall_mode})
        local manifest = json.loadfile(path.join(socketcall_sdk, "manifest.json"))
        target:add("defines", "OK_KERNEL_SDK_FINGERPRINT_" .. hash.sha256(path.join(socketcall_sdk, "manifest.json")))
        target:add("includedirs", path.join(socketcall_sdk, "include"))
        target:add("cxxflags", manifest.cxxflags, {force = true})
        target:add("asflags", manifest.asflags, {force = true})
        target:add("defines", manifest.defines)
        target:add("ldflags", manifest.ldflags, {force = true})
        target:add("ldflags", "-nostdlib", "-static", "-no-pie", "-Wl,--build-id=none",
            "-Wl,-z,max-page-size=0x1000", "-Wl,-T," .. path.join(socketcall_sdk, "boot/linker.ld"),
            "-Wl,--start-group", "-Wl,--whole-archive", path.join(socketcall_sdk, "lib/libokernel_boot.a"),
            "-Wl,--no-whole-archive", path.join(socketcall_sdk, "lib/libokernel.a"),
            "-lgcc", "-Wl,--end-group", {force = true})
        for _, artifact in ipairs({path.join(socketcall_package, "boot.okar"), path.join(socketcall_sdk, "manifest.json"),
                path.join(socketcall_sdk, "boot/linker.ld"), path.join(socketcall_sdk, "lib/libokernel_boot.a"),
                path.join(socketcall_sdk, "lib/libokernel.a")}) do
            target:data_add("linkdepfiles", artifact)
        end
    end)
    before_build(function (target)
        os.execv("python3", {"-B", path.join(socketcall_project, "tools/kernel_sdk.py"), "validate",
            "--sdk", socketcall_sdk, "--arch", socketcall_arch, "--mode", socketcall_mode,
            "--compiler", (target:tool("cxx"))})
    end)
    after_build(function (target)
        os.execv("python3", {"-B", path.join(socketcall_project, "tools/kernel_sdk.py"), "assemble",
            "--sdk", socketcall_sdk, "--arch", socketcall_arch, "--mode", socketcall_mode,
            "--elf", target:targetfile(), "--out", path.join(target:targetdir(), "kernel.bin"),
            "--objcopy", path.join(path.directory((target:tool("cxx"))), socketcall_spec.triple .. "-objcopy")})
    end)
target_end()
