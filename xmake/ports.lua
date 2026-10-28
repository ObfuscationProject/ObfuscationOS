-- Third-party ports for the static musl userland (ports/README.md). The task
-- drives tools/ports.py with explicit inputs; it never resolves an archive,
-- toolchain or dependency build by search and never executes target code.
task("port-build")
    set_menu {usage = "xmake port-build --name=PORT --arch=ARCH --mode=MODE --archive=FILE --toolchain=DIR --out=DIR",
        description = "Build one pinned port (musl, busybox) for one profile without executing it",
        options = {
            {nil, "name", "kv", nil, "Port directory under ports/"},
            {nil, "arch", "kv", nil, "Architecture profile"},
            {nil, "mode", "kv", nil, "debug or release"},
            {nil, "archive", "kv", nil, "Pinned upstream source archive (checksum enforced)"},
            {nil, "toolchain", "kv", nil, "Explicit cross toolchain directory"},
            {nil, "out", "kv", nil, "New build output directory"},
            {nil, "musl-build", "kv", nil, "Admitted static musl build (ports depending on musl)"},
            {nil, "ppc-clang", "kv", nil, "Pinned Linux-targeted Clang frontend (ppc)"},
            {nil, "softfp-build", "kv", nil, "Pinned MIPS64 binary128 runtime build (mips64)"},
            {nil, "softfp-manifest-sha256", "kv", nil, "Exact soft-fp manifest hash"},
            {nil, "jobs", "kv", "8", "Parallel make jobs"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {"-B", path.join(os.projectdir(), "tools/ports.py"), "build"}
        for _, name in ipairs({"name", "arch", "mode", "archive", "toolchain", "out"}) do
            assert(option.get(name), "port-build requires --%s", name)
        end
        for _, name in ipairs({"name", "arch", "mode", "archive", "toolchain", "out", "musl-build",
                               "ppc-clang", "softfp-build", "softfp-manifest-sha256", "jobs"}) do
            local value = option.get(name)
            if value then
                if name ~= "name" and name ~= "arch" and name ~= "mode" and name ~= "jobs" and
                        name ~= "softfp-manifest-sha256" then
                    value = path.absolute(value)
                end
                table.insert(args, "--" .. name)
                table.insert(args, value)
            end
        end
        os.execv("python3", args)
    end)
task_end()
