-- Build the userspace fixture against an explicit musl sysroot. This task does
-- not package, boot, repair or modify a filesystem image.
task("musl-zero-truncate-probe")
    set_menu {usage = "xmake musl-zero-truncate-probe --arch=ARCH --musl-build=DIR --toolchain=DIR --out=DIR",
        description = "Build the linked-file zero-truncate/rewrite fixture; does not execute it",
        options = {
            {nil, "arch", "kv", nil, "Retained architecture profile"},
            {nil, "musl-build", "kv", nil, "Explicit audited musl build directory"},
            {nil, "toolchain", "kv", nil, "Explicit cross toolchain directory"},
            {nil, "out", "kv", nil, "New output directory"},
            {nil, "ppc-clang", "kv", nil, "Explicit Linux-targeted PowerPC frontend"},
            {nil, "softfp-build", "kv", nil, "Explicit MIPS64 binary128 runtime build"},
            {nil, "softfp-manifest-sha256", "kv", nil, "Exact runtime manifest hash"}
        }}
    on_run(function ()
        import("core.base.option")
        local project = os.projectdir()
        local args = {"-B", path.join(project, "tools/build_musl_probe.py"),
            "--source", path.join(project, "tests/musl/zero_truncate.c"),
            "--linker-script", path.join(project, "tests/musl/bootstrap.ld")}
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out"}) do
            assert(option.get(name), "musl-zero-truncate-probe requires --%s", name)
        end
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out", "ppc-clang", "softfp-build", "softfp-manifest-sha256"}) do
            if option.get(name) then
                table.insert(args, "--" .. name)
                table.insert(args, option.get(name))
            end
        end
        os.execv("python3", args)
    end)

task("zero-truncate-fixture-reference")
    set_menu {usage = "xmake zero-truncate-fixture-reference --out=DIR --host-cc=PATH",
        description = "Run the C fixture on the host filesystem; does not qualify Kernel behavior",
        options = {
            {nil, "out", "kv", nil, "Fresh isolated reference output directory"},
            {nil, "host-cc", "kv", nil, "Explicit host C compiler"}
        }}
    on_run(function ()
        import("core.base.option")
        for _, name in ipairs({"out", "host-cc"}) do
            assert(option.get(name), "zero-truncate-fixture-reference requires --%s", name)
        end
        local out = path.absolute(option.get("out"))
        local compiler = path.absolute(option.get("host-cc"))
        assert(os.isfile(compiler), "explicit host compiler is missing")
        assert(not os.isdir(out) and not os.isfile(out), "reference output already exists")
        os.mkdir(out)
        local source = path.join(out, "zero_truncate.c")
        local binary = path.join(out, "zero-truncate-reference")
        local file = path.join(out, "document.txt")
        os.cp(path.join(os.projectdir(), "tests/musl/zero_truncate.c"), source)
        os.execv(compiler, {"-std=c11", "-Wall", "-Wextra", "-Werror", "-fno-builtin", source, "-o", binary})
        os.execv(binary, {"first", file})
        os.execv(binary, {"restart", file})
    end)
