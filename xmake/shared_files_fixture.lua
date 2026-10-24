set_project("shared-files-native-acceptance")
set_languages("c11")
add_rules("mode.debug", "mode.release")

option("systoolchain_dir")
    set_showmenu(true)
option_end()
option("kernel_sdk")
    set_showmenu(true)
option_end()
includes("xmake/arch.lua")
local arch, spec = ok_user_require_arch(ok_user_current_arch())
local project = os.projectdir()
local sdk = ok_user_kernel_sdk()
local build = ok_user_builddir()
local mode = get_config("mode") or "debug"

local function bind_sdk(target)
    assert(get_config("systoolchain_dir"), "explicit cross toolchain required")
    assert(get_config("kernel_sdk"), "explicit exported Kernel SDK required")
    target:add("defines", "OK_KERNEL_SDK_FINGERPRINT_" .. hash.sha256(path.join(sdk, "manifest.json")))
end

target("kernel-sdk-check")
    set_kind("phony")
    set_default(false)
    on_build(function ()
        local compiler = path.join(get_config("systoolchain_dir"), "bin", spec.triple .. "-g++")
        os.vrunv("python3", {path.join(project, "tools/kernel_sdk.py"), "validate",
            "--sdk", sdk, "--arch", arch, "--mode", mode, "--compiler", compiler})
    end)
target_end()

target("okcrt")
    set_kind("static")
    set_default(false)
    set_filename("libokcrt.a")
    set_targetdir(path.join(build, "lib"))
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(bind_sdk)
    add_deps("kernel-sdk-check")
    add_files("lib/okcrt/src/abi.c", "lib/okcrt/src/errno.c", "lib/okcrt/src/stdio.c",
              "lib/okcrt/src/stdlib.c", "lib/okcrt/src/string.c", "lib/okcrt/src/syscalls.c")
    add_files(path.join("lib/okcrt/arch", spec.source, "syscall.S"))
    add_ok_user_cflags()
target_end()

local probes = {
    {name = "shared-files-native", source = "shared_files_probe.c", define = "OK_NATIVE_SHARED_FILE_PROBE"},
    {name = "shared-rights-native", source = "shared_rights_probe.c", define = "OK_SHARED_RIGHTS_NATIVE"},
    {name = "shared-write-seal-native", source = "shared_write_seal_probe.c", define = "OK_NATIVE_SHARED_WRITE_SEAL_PROBE"},
    {name = "shared-files-suite", source = "shared_files_suite_runner.c"},
    {name = "shared-write-seal-suite", source = "shared_write_seal_suite_runner.c"}
}
for _, probe in ipairs(probes) do
    target("app-" .. probe.name)
        set_kind("binary")
        set_default(false)
        set_filename(probe.name .. ".elf")
        set_strip("none")
        set_targetdir(path.join(build, "apps"))
        add_deps("okcrt")
        add_ok_user_toolchain()
        add_ok_user_include_dirs()
        on_load(bind_sdk)
        add_files(path.join("tests/native", probe.source))
        if probe.define then add_defines(probe.define) end
        add_files(path.join("lib/okcrt/arch", spec.source, "crt0.S"))
        add_ok_user_cflags()
        add_ok_user_linkflags()
        add_syslinks("gcc")
    target_end()
end
