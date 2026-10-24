-- Explicit build-only Linux-personality probe; ordinary images omit this task.
task("musl-console-control-probe")
    set_menu {usage = "xmake musl-console-control-probe --arch=ARCH --musl-build=DIR --toolchain=DIR --out=DIR",
        description = "Build a bounded controlling-console musl probe without target execution",
        options = {
            {nil, "arch", "kv", nil, "Supplied musl architecture"},
            {nil, "musl-build", "kv", nil, "Exact admitted musl artifact directory"},
            {nil, "toolchain", "kv", nil, "Exact architecture compiler directory"},
            {nil, "out", "kv", nil, "New build output directory"}
        }}
    on_run(function ()
        import("core.base.option")
        local supplied = {x86_64 = true, aarch64 = true, rv64 = true, loongarch64 = true}
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out"}) do
            assert(option.get(name), "musl-console-control-probe requires --%s", name)
        end
        assert(supplied[option.get("arch")], "a supplied musl profile is required")
        local args = {"-B", path.join(os.projectdir(), "tools/build_musl_probe.py"),
            "--source", path.join(os.projectdir(), "tests/musl/native_console_control.c"),
            "--linker-script", path.join(os.projectdir(), "tests/musl/bootstrap.ld"),
            "--capture-compile-dependencies"}
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out"}) do
            table.insert(args, "--" .. name)
            table.insert(args, option.get(name))
        end
        os.execv("python3", args)
    end)
task_end()
