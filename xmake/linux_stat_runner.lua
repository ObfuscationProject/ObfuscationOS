set_project("sdk23-linux-stat-native-runner")
set_languages("c11")
add_rules("mode.debug", "mode.release")

option("systoolchain_dir")
    set_showmenu(true)
option_end()
option("kernel_sdk")
    set_showmenu(true)
option_end()

option("stat_policy")
    set_default("maintained")
    set_showmenu(true)
option_end()
option("stat_epoch")
    set_default("post2038")
    set_showmenu(true)
option_end()
includes("xmake/arch.lua")
local arch, spec = ok_user_require_arch(ok_user_current_arch())
local project = os.projectdir()
local sdk = ok_user_kernel_sdk()
local build = ok_user_builddir()
local mode = get_config("mode") or "debug"
local policy = get_config("stat_policy") or "maintained"
local epoch = get_config("stat_epoch") or "post2038"

local function bind_sdk(target)
    assert(get_config("systoolchain_dir"), "explicit cross toolchain required")
    assert(get_config("kernel_sdk"), "explicit exported SDK23 required")
    assert(policy == "maintained" or policy == "readonly" or policy == "unqualified", "invalid stat policy")
    assert(epoch == "negative" or epoch == "post2038", "invalid stat epoch")
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
    set_objectdir(path.join(build, "objects", "okcrt"))
    set_dependir(path.join(build, "dependencies", "okcrt"))
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(bind_sdk)
    add_deps("kernel-sdk-check")
    add_files("lib/okcrt/src/abi.c", "lib/okcrt/src/errno.c", "lib/okcrt/src/stdio.c",
              "lib/okcrt/src/stdlib.c", "lib/okcrt/src/string.c", "lib/okcrt/src/syscalls.c")
    add_files(path.join("lib/okcrt/arch", spec.source, "syscall.S"))
    add_ok_user_cflags()
target_end()

target("app-linux-stat-runner")
    set_kind("binary")
    set_default(false)
    set_filename("linux-stat-runner.elf")
    -- Retain symbols so the builder can audit unresolved references in every mode.
    set_strip("none")
    set_targetdir(path.join(build, "apps"))
    set_objectdir(path.join(build, "objects", "app-linux-stat-runner"))
    set_dependir(path.join(build, "dependencies", "app-linux-stat-runner"))
    add_deps("okcrt")
    add_ok_user_toolchain()
    add_ok_user_include_dirs()
    on_load(bind_sdk)
    if policy == "maintained" then
        add_files("tests/native/linux_stat_runner.c")
    else
        add_files("tests/native/linux_stat_controls_runner.c")
    end
    add_defines("LINUX_STAT_READONLY=" .. (policy == "readonly" and "1" or "0"),
                "LINUX_STAT_NEGATIVE=" .. (epoch == "negative" and "1" or "0"))
    add_files(path.join("lib/okcrt/arch", spec.source, "crt0.S"))
    add_ok_user_cflags()
    add_ok_user_linkflags()
    add_syslinks("gcc")
target_end()
