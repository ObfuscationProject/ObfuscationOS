local function normalize_arch(arch)
    if arch == "x86" or arch == "i686" then
        return "i386"
    elseif arch == "x64" or arch == "amd64" then
        return "x86_64"
    end
    return arch
end

local function resolve_arch()
    local arch = get_config("arch")
    if not arch or arch == "" then
        arch = os.arch()
    end
    arch = normalize_arch(arch)
    return arch or ""
end

local function resolve_target()
    local arch = resolve_arch()
    if arch == "x86_64" then
        return "x86_64-elf"
    elseif arch == "i386" then
        return "i686-elf"
    end
    assert(false, "Unsupported arch for elf toolchain: " .. tostring(arch))
end

local function resolve_location(target)
    local prefix = get_config("cross_prefix")
    if prefix and prefix ~= "" then
        return prefix, nil
    end
    local bindir = path.join(os.projectdir(), "build-toolchain", "opt", target, "bin")
    if os.isfile(path.join(bindir, target .. "-gcc")) then
        return target .. "-", bindir
    end
    return target .. "-", nil
end

local function apply_toolset(toolchain, prefix, bindir)
    if bindir and bindir ~= "" then
        toolchain:set("bindir", bindir)
    end
    toolchain:set("toolset", "cc", prefix .. "gcc")
    toolchain:set("toolset", "cxx", prefix .. "g++")
    toolchain:set("toolset", "as", prefix .. "gcc")
    toolchain:set("toolset", "ld", prefix .. "ld")
    toolchain:set("toolset", "ar", prefix .. "ar")
    toolchain:set("toolset", "ranlib", prefix .. "ranlib")
    toolchain:set("toolset", "strip", prefix .. "strip")
    toolchain:set("toolset", "objcopy", prefix .. "objcopy")
    toolchain:set("toolset", "objdump", prefix .. "objdump")
end

local function program_exists(program, bindir)
    if not program or program == "" then
        return false
    end
    if bindir and bindir ~= "" and not path.is_absolute(program) and not program:find("/", 1, true) then
        if os.isfile(path.join(bindir, program)) then
            return true
        end
    end
    if path.is_absolute(program) or program:find("/", 1, true) then
        return os.isfile(program)
    end

    local env_path = os.getenv("PATH") or ""
    if bindir and bindir ~= "" then
        env_path = bindir .. ":" .. env_path
    end
    for dir in env_path:gmatch("([^:]+)") do
        if os.isfile(path.join(dir, program)) then
            return true
        end
    end
    return false
end

toolchain("elf")
    set_kind("standalone")
    set_description("Bare-metal ELF toolchain using GCC + GNU Binutils")

    on_load(function (toolchain)
        local target = resolve_target()
        local prefix, bindir = resolve_location(target)
        apply_toolset(toolchain, prefix, bindir)
    end)

    on_check(function (toolchain)
        local target = resolve_target()
        local prefix, bindir = resolve_location(target)
        apply_toolset(toolchain, prefix, bindir)
        local cc_program = prefix .. "gcc"

        if program_exists(cc_program, bindir) then
            return true
        end

        if get_config("auto_bootstrap_toolchain") == false then
            assert(false, string.format("ELF toolchain not found (%s). Run `xmake toolchain` or set `--cross_prefix=...`.", target))
        end
        cprint("${yellow}warning: ELF toolchain missing (%s). Configure continues, run `xmake toolchain` to bootstrap it.${clear}", target)
        return true
    end)
