local function resolve_sdkdir(triple)
    local project = os.projectdir()
    local primary = path.join(project, "toolchains", triple)
    local legacy = path.join(project, "build-toolchain", "opt", triple)
    if os.isfile(path.join(primary, "bin", triple .. "-gcc")) then
        return primary
    end
    if os.isfile(path.join(legacy, "bin", triple .. "-gcc")) then
        return legacy
    end
    return primary
end

local function define_user_toolchain(name, triple, arch)
    toolchain(name)
        set_kind("standalone")
        set_sdkdir(resolve_sdkdir(triple))
        set_toolset("cc", triple .. "-gcc")
        set_toolset("cxx", triple .. "-g++")
        set_toolset("as", triple .. "-gcc")
        set_toolset("ld", triple .. "-gcc")
        set_toolset("ar", triple .. "-ar")
        set_toolset("ranlib", triple .. "-ranlib")
        set_toolset("strip", triple .. "-strip")
        set_toolset("objcopy", triple .. "-objcopy")
        set_toolset("objdump", triple .. "-objdump")
        on_check(function ()
            if os.isfile(path.join(resolve_sdkdir(triple), "bin", triple .. "-gcc")) then
                return true
            end
            if get_config("auto_bootstrap_toolchain") == false then
                raise("missing userland toolchain (%s). Run: xmake toolchains -a %s", triple, arch)
            end
            cprint("${yellow}warning: userland toolchain missing (%s). Configure continues; build will fail until it is installed.${clear}", triple)
            return true
        end)
    toolchain_end()
end

define_user_toolchain("ok-user-x86_64-elf", "x86_64-elf", "x86_64")
define_user_toolchain("ok-user-aarch64-elf", "aarch64-elf", "aarch64")
define_user_toolchain("ok-user-rv64-elf", "riscv64-elf", "rv64")
define_user_toolchain("ok-user-loongarch64-elf", "loongarch64-elf", "loongarch64")
