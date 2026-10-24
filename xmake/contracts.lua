-- Contract tooling is independent of kernel sources and does not claim guest execution.
task("musl-shared-build")
    set_menu {usage = "xmake musl-shared-build --arch=ARCH --mode=MODE --archive=FILE --toolchain=DIR --out=DIR",
        description = "Build pinned shared musl artifacts without executing target code",
        options = {
            {nil, "arch", "kv", nil, "Explicit architecture profile"},
            {nil, "mode", "kv", nil, "debug or release"},
            {nil, "archive", "kv", nil, "Pinned musl 1.2.5 archive"},
            {nil, "toolchain", "kv", nil, "Explicit cross-toolchain installation"},
            {nil, "out", "kv", nil, "New isolated output directory"},
            {nil, "jobs", "kv", "4", "Build jobs, from 1 through 64"},
            {nil, "linker-build", "kv", nil, "Explicit isolated dynamic linker build"},
            {nil, "linker-manifest-sha256", "kv", nil, "Exact dynamic linker manifest hash"},
            {nil, "pic-runtime-build", "kv", nil, "Explicit MIPS PIC runtime build"},
            {nil, "pic-runtime-manifest-sha256", "kv", nil, "Exact PIC runtime manifest hash"},
            {nil, "softfp-build", "kv", nil, "Explicit MIPS64 binary128 build"},
            {nil, "softfp-manifest-sha256", "kv", nil, "Exact binary128 manifest hash"},
            {nil, "gcc-pic-runtime-build", "kv", nil, "Explicit RISC-V/LoongArch PIC runtime"},
            {nil, "gcc-pic-runtime-manifest-sha256", "kv", nil, "Exact RISC-V/LoongArch runtime manifest hash"},
            {nil, "ppc-pic-runtime-build", "kv", nil, "Explicit PPC secure-PLT PIC runtime"},
            {nil, "ppc-pic-runtime-manifest-sha256", "kv", nil, "Exact PPC runtime manifest hash"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {"-B", path.join(os.projectdir(), "tools/build_shared_musl.py")}
        for _, name in ipairs({"arch", "mode", "archive", "toolchain", "out", "jobs"}) do
            assert(option.get(name), "musl-shared-build requires --%s", name)
            table.insert(args, "--" .. name)
            table.insert(args, option.get(name))
        end
        for _, name in ipairs({"linker-build", "linker-manifest-sha256", "pic-runtime-build",
                              "pic-runtime-manifest-sha256", "softfp-build", "softfp-manifest-sha256",
                              "gcc-pic-runtime-build", "gcc-pic-runtime-manifest-sha256",
                              "ppc-pic-runtime-build", "ppc-pic-runtime-manifest-sha256"}) do
            if option.get(name) then
                table.insert(args, "--" .. name)
                table.insert(args, option.get(name))
            end
        end
        os.execv("python3", args, {envs = {PYTHONDONTWRITEBYTECODE = "1"}})
    end)

task("static-udp-test")
    set_menu {usage = "xmake static-udp-test --arch=ARCH --kernel-sdk=DIR --toolchain=DIR --mode=MODE --output=DIR",
        description = "SDK34 native static ARP/IPv4/UDP peer qualifier",
        options = {
            {nil, "arch", "kv", nil, "Retained architecture profile"},
            {nil, "kernel-sdk", "kv", nil, "Explicit architecture/mode Kernel SDK34"},
            {nil, "toolchain", "kv", nil, "Explicit cross compiler installation"},
            {nil, "mode", "kv", nil, "debug or release"},
            {nil, "output", "kv", nil, "New isolated output directory"},
            {nil, "compile-only", "k", nil, "Freestanding compile without execution"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {"-B", path.join(os.projectdir(), "scripts/test_static_udp.py")}
        for _, name in ipairs({"arch", "kernel-sdk", "toolchain", "mode", "output"}) do
            assert(option.get(name), "static-udp-test requires --%s", name)
            table.insert(args, "--" .. name); table.insert(args, option.get(name))
        end
        if option.get("compile-only") then table.insert(args, "--compile-only") end
        os.execv("python3", args, {envs = {PYTHONDONTWRITEBYTECODE = "1"}})
    end)

task("virtio-net-test")
    set_menu {usage = "xmake virtio-net-test --arch=ARCH --kernel-sdk=DIR --toolchain=DIR --mode=MODE --output=DIR",
        description = "SDK-only modern MMIO/PCI polling NIC probe with an external Ethernet peer",
        options = {
            {nil, "arch", "kv", nil, "Retained architecture profile"},
            {nil, "kernel-sdk", "kv", nil, "Explicit architecture/mode SDK"},
            {nil, "toolchain", "kv", nil, "Explicit cross compiler installation"},
            {nil, "mode", "kv", nil, "debug or release"},
            {nil, "output", "kv", nil, "New isolated output directory"},
            {nil, "compile-only", "k", nil, "Freestanding compile without execution"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {"-B", path.join(os.projectdir(), "scripts/test_virtio_net.py")}
        for _, name in ipairs({"arch", "kernel-sdk", "toolchain", "mode", "output"}) do
            assert(option.get(name), "virtio-net-test requires --%s", name)
            table.insert(args, "--" .. name); table.insert(args, option.get(name))
        end
        if option.get("compile-only") then table.insert(args, "--compile-only") end
        os.execv("python3", args, {envs = {PYTHONDONTWRITEBYTECODE = "1"}})
    end)

task("virtio-net-mmio-test")
    set_menu {usage = "xmake virtio-net-mmio-test --arch=ARCH --kernel-sdk=DIR --toolchain=DIR --mode=MODE --output=DIR",
        description = "SDK-only polling NIC probe with an independent raw Ethernet peer; no IP/socket/IRQ claim",
        options = {
            {nil, "arch", "kv", nil, "Retained architecture profile"},
            {nil, "kernel-sdk", "kv", nil, "Explicit architecture/mode SDK"},
            {nil, "toolchain", "kv", nil, "Explicit cross compiler installation"},
            {nil, "mode", "kv", nil, "debug or release"},
            {nil, "output", "kv", nil, "New isolated output directory"},
            {nil, "compile-only", "k", nil, "Freestanding compile without execution"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {"-B", path.join(os.projectdir(), "scripts/test_virtio_net_mmio.py")}
        for _, name in ipairs({"arch", "kernel-sdk", "toolchain", "mode", "output"}) do
            assert(option.get(name), "virtio-net-mmio-test requires --%s", name)
            table.insert(args, "--" .. name); table.insert(args, option.get(name))
        end
        if option.get("compile-only") then table.insert(args, "--compile-only") end
        os.execv("python3", args, {envs = {PYTHONDONTWRITEBYTECODE = "1"}})
    end)

task("plan-check")
    set_menu {usage = "xmake plan-check --evidence-root=DIR", description = "Validate the workstation seed ledger and its regression tests",
        options = {{nil, "evidence-root", "kv", nil, "Explicit root containing retained execution-evidence artifacts"}}}
    on_run(function ()
        import("core.base.option")
        local args = {path.join(os.projectdir(), "tools/plan_ledger.py"), "validate"}
        if option.get("evidence-root") then
            table.insert(args, "--evidence-root")
            table.insert(args, option.get("evidence-root"))
        end
        os.execv("python3", args)
        os.execv("python3", {"-m", "unittest", "discover", "-s", path.join(os.projectdir(), "tests/tools"), "-p", "test_console_receipt_admission.py"})
        os.execv("python3", {"-m", "unittest", "discover", "-s", path.join(os.projectdir(), "tests/tools"), "-p", "test_plan_ledger.py"})
        os.execv("python3", {"-m", "unittest", "discover", "-s", path.join(os.projectdir(), "tests/tools"), "-p", "test_linux_abi_draft.py"})
        os.execv("python3", {"-m", "unittest", "discover", "-s", path.join(os.projectdir(), "tests/tools"), "-p", "test_rfc_sources.py"})
        os.execv("python3", {"-m", "unittest", "discover", "-s", path.join(os.projectdir(), "tests/tools"), "-p", "test_musl_source.py"})
    end)

task("plan-report")
    set_menu {usage = "xmake plan-report --evidence-root=DIR [--output=FILE]", description = "Generate the source-backed workstation capability matrix",
        options = {{nil, "output", "kv", nil, "Output Markdown path; defaults to stdout"},
                   {nil, "evidence-root", "kv", nil, "Explicit root containing retained execution-evidence artifacts"}}}
    on_run(function ()
        import("core.base.option")
        local args = {path.join(os.projectdir(), "tools/plan_ledger.py"), "report"}
        if option.get("evidence-root") then
            table.insert(args, "--evidence-root")
            table.insert(args, option.get("evidence-root"))
        end
        if option.get("output") then
            table.insert(args, "--output")
            table.insert(args, option.get("output"))
        end
        os.execv("python3", args)
    end)

task("musl-static-spike")
    set_menu {usage = "xmake musl-static-spike --archive=FILE --arch=ARCH --toolchain=DIR [--out=DIR]",
        description = "Build pinned musl with an explicit cross compiler; does not execute target binaries",
        options = {
            {nil, "archive", "kv", nil, "Explicit musl release archive (checksum enforced)"},
            {nil, "arch", "kv", nil, "One retained OS architecture"},
            {nil, "toolchain", "kv", nil, "Cross compiler installation directory"},
            {nil, "ppc-clang", "kv", nil, "Explicit pinned Linux Clang frontend for the PowerPC ordinary probe"},
            {nil, "mode", "kv", "debug", "debug or release"},
            {nil, "out", "kv", nil, "New isolated output directory"},
            {nil, "jobs", "kv", "4", "GNU make parallel jobs"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {path.join(os.projectdir(), "tools/musl_source.py"), "build-static"}
        for _, name in ipairs({"archive", "arch", "toolchain"}) do
            assert(option.get(name), "musl-static-spike requires --%s", name)
        end
        for _, name in ipairs({"archive", "arch", "toolchain", "ppc-clang", "mode", "out", "jobs"}) do
            if option.get(name) then
                table.insert(args, "--" .. name)
                table.insert(args, option.get(name))
            end
        end
        os.execv("python3", args)
    end)


task("musl-source-check")
    set_menu {usage = "xmake musl-source-check --archive=FILE", description = "Verify pinned musl archive and all ten source ports",
        options = {{nil, "archive", "kv", nil, "Explicit musl release archive (checksum enforced)"}}}
    on_run(function ()
        import("core.base.option")
        assert(option.get("archive"), "musl-source-check requires --archive")
        os.execv("python3", {path.join(os.projectdir(), "tools/musl_source.py"), "inspect", "--archive", option.get("archive")})
    end)

-- C userland probe compilation stays separate from the native C++ Kernel SDK.
task("musl-bootstrap-probe")
    set_menu {usage = "xmake musl-bootstrap-probe --arch=ARCH --musl-build=DIR --toolchain=DIR --out=DIR",
        description = "Build a pinned static-musl startup/TLS/errno/clock probe; does not execute it",
        options = {
            {nil, "arch", "kv", nil, "Retained architecture profile"},
            {nil, "musl-build", "kv", nil, "Explicit audited musl build directory"},
            {nil, "toolchain", "kv", nil, "Explicit cross toolchain directory"},
            {nil, "out", "kv", nil, "New output directory"},
            {nil, "ppc-clang", "kv", nil, "Explicit Linux-targeted Clang frontend for PowerPC"},
            {nil, "softfp-build", "kv", nil, "Explicit MIPS64 binary128 runtime build"},
            {nil, "softfp-manifest-sha256", "kv", nil, "Exact runtime manifest hash"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {path.join(os.projectdir(), "tools/build_musl_probe.py")}
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out"}) do
            assert(option.get(name), "musl-bootstrap-probe requires --%s", name)
        end
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out", "ppc-clang", "softfp-build", "softfp-manifest-sha256"}) do
            if option.get(name) then
                table.insert(args, "--" .. name)
                table.insert(args, option.get(name))
            end
        end
        os.execv("python3", args)
    end)

task("mips64-softfp")
    set_menu {usage = "xmake mips64-softfp --archive=FILE --toolchain=DIR --mode=MODE --out=DIR",
        description = "Build the pinned MIPS64 binary128 user compiler runtime; does not execute it",
        options = {
            {nil, "archive", "kv", nil, "Pinned GCC 14.3.0 source archive"},
            {nil, "toolchain", "kv", nil, "Explicit MIPS64 compiler directory"},
            {nil, "mode", "kv", nil, "debug or release"},
            {nil, "out", "kv", nil, "New isolated build output directory"}
        }}
    on_run(function ()
        import("core.base.option")
        local args = {path.join(os.projectdir(), "tools/mips64_softfp.py")}
        for _, name in ipairs({"archive", "toolchain", "mode", "out"}) do
            assert(option.get(name), "mips64-softfp requires --%s", name)
            table.insert(args, "--" .. name)
            table.insert(args, option.get(name))
        end
        os.execv("python3", args)
    end)

task("musl-service-graph-guests")
    set_menu {usage = "xmake musl-service-graph-guests --arch=ARCH --musl-build=DIR --toolchain=DIR --out=DIR",
        description = "Build bounded persistent-manifest service graph artifacts; no target execution",
        options = {
            {nil, "arch", "kv", nil, "Retained architecture profile"},
            {nil, "musl-build", "kv", nil, "Explicit admitted static musl build"},
            {nil, "toolchain", "kv", nil, "Explicit cross toolchain"},
            {nil, "out", "kv", nil, "New output directory"},
            {nil, "ppc-clang", "kv", nil, "Explicit PowerPC Linux Clang frontend"},
            {nil, "softfp-build", "kv", nil, "Explicit MIPS64 binary128 runtime"},
            {nil, "softfp-manifest-sha256", "kv", nil, "Exact binary128 runtime manifest hash"}
        }}
    on_run(function ()
        import("core.base.option")
        local project = os.projectdir()
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out"}) do
            assert(option.get(name), "musl-service-graph-guests requires --%s", name)
        end
        local out = path.absolute(option.get("out"))
        assert(not os.isdir(out) and not os.isfile(out), "service graph output already exists")
        os.mkdir(out)
        local common = {"-B", path.join(project, "tools/build_musl_probe.py"),
            "--arch", option.get("arch"), "--musl-build", path.absolute(option.get("musl-build")),
            "--toolchain", path.absolute(option.get("toolchain")),
            "--linker-script", path.join(project, "tests/musl/bootstrap.ld")}
        for _, name in ipairs({"ppc-clang", "softfp-build", "softfp-manifest-sha256"}) do
            if option.get(name) then
                table.insert(common, "--" .. name)
                table.insert(common, name == "softfp-manifest-sha256" and option.get(name) or path.absolute(option.get(name)))
            end
        end
        for _, guest in ipairs({{"production-manager", "apps/init/service_manager.c"},
                                {"test-manager", "tests/musl/service_graph_init.c"},
                                {"test-child", "tests/musl/service_graph_child.c"}}) do
            local args = table.copy(common)
            table.insert(args, "--source"); table.insert(args, path.join(project, guest[2]))
            table.insert(args, "--out"); table.insert(args, path.join(out, guest[1]))
            os.execv("python3", args)
            os.execv("python3", {"-B", path.join(project, "tools/seal_service_graph_build.py"),
                "--project", project, "--build", path.join(out, guest[1]), "--source", path.join(project, guest[2])})
        end
    end)

task("musl-pid1-guests")
    set_menu {usage = "xmake musl-pid1-guests --arch=ARCH --musl-build=DIR --toolchain=DIR --out=DIR",
        description = "Build pinned static-musl production init and deterministic PID 1 acceptance guests; does not execute them",
        options = {
            {nil, "arch", "kv", nil, "Retained architecture profile"},
            {nil, "musl-build", "kv", nil, "Explicit audited musl build directory"},
            {nil, "toolchain", "kv", nil, "Explicit cross toolchain directory"},
            {nil, "out", "kv", nil, "New isolated output directory"},
            {nil, "ppc-clang", "kv", nil, "Explicit Linux-targeted Clang frontend for PowerPC"},
            {nil, "softfp-build", "kv", nil, "Explicit MIPS64 binary128 runtime build"},
            {nil, "softfp-manifest-sha256", "kv", nil, "Exact runtime manifest hash"}
        }}
    on_run(function ()
        import("core.base.option")
        local project = os.projectdir()
        for _, name in ipairs({"arch", "musl-build", "toolchain", "out"}) do
            assert(option.get(name), "musl-pid1-guests requires --%s", name)
        end
        local out = path.absolute(option.get("out"))
        assert(not os.isdir(out) and not os.isfile(out), "musl-pid1-guests output already exists")
        os.mkdir(out)
        local common = {"-B", path.join(project, "tools/build_musl_probe.py"),
            "--arch", option.get("arch"), "--musl-build", path.absolute(option.get("musl-build")),
            "--toolchain", path.absolute(option.get("toolchain")),
            "--linker-script", path.join(project, "tests/musl/bootstrap.ld")}
        for _, name in ipairs({"ppc-clang", "softfp-build", "softfp-manifest-sha256"}) do
            if option.get(name) then
                table.insert(common, "--" .. name)
                table.insert(common, name == "softfp-manifest-sha256" and option.get(name) or path.absolute(option.get(name)))
            end
        end
        for _, guest in ipairs({
            {"production-init", "apps/init/pid1.c"},
            {"test-init", "tests/musl/pid1_init.c"},
            {"test-service", "tests/musl/pid1_service.c"}
        }) do
            local args = table.copy(common)
            table.insert(args, "--source")
            table.insert(args, path.join(project, guest[2]))
            table.insert(args, "--out")
            table.insert(args, path.join(out, guest[1]))
            os.execv("python3", args)
            os.execv("python3", {"-B", path.join(project, "tools/seal_pid1_build.py"),
                "--build", path.join(out, guest[1]), "--project", project,
                "--source", path.join(project, guest[2])})
        end
    end)

task("pid1-policy-model-test")
    set_menu {usage = "xmake pid1-policy-model-test --out=DIR",
        description = "Run hosted PID 1 policy assertions; does not execute an OS guest",
        options = {{nil, "out", "kv", nil, "New isolated output directory"}}}
    on_run(function ()
        import("core.base.option")
        assert(option.get("out"), "pid1-policy-model-test requires --out")
        local out = path.absolute(option.get("out"))
        assert(not os.isdir(out) and not os.isfile(out), "PID 1 model output already exists")
        os.mkdir(out)
        local binary = path.join(out, "pid1-policy-tests")
        os.execv("cc", {"-std=c11", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", path.join(os.projectdir(), "tests/pid1_policy_tests.c"),
            "-o", binary})
        os.execv(binary, {}, {envs = {ASAN_OPTIONS = "detect_leaks=0"}})
    end)

task("native-init-model-test")
    set_menu {usage = "xmake native-init-model-test --out=DIR --host-cc=PATH",
        description = "Hosted native PID1 actor and config fault controls; no guest execution",
        options = {
            {nil, "out", "kv", nil, "New isolated output directory"},
            {nil, "host-cc", "kv", nil, "Explicit host C compiler"}
        }}
    on_run(function ()
        import("core.base.option")
        assert(option.get("out") and option.get("host-cc"), "native-init-model-test requires --out and --host-cc")
        local out = path.absolute(option.get("out"))
        assert(not os.isdir(out) and not os.isfile(out), "native init model output already exists")
        os.mkdir(out)
        for _, name in ipairs({"native_supervisor_tests", "native_manifest_load_tests", "pid1_policy_tests"}) do
            local binary = path.join(out, name)
            os.execv(path.absolute(option.get("host-cc")), {"-std=c11", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=undefined", "-fno-omit-frame-pointer",
                path.join(os.projectdir(), "tests", name .. ".c"), "-o", binary})
            os.execv(binary, {})
        end
    end)

task("service-manifest-model-test")
    set_menu {usage = "xmake service-manifest-model-test --out=DIR --host-cc=PATH",
        description = "Hosted service parser, loader and actor models; no guest execution",
        options = {
            {nil, "out", "kv", nil, "Fresh hosted output directory"},
            {nil, "host-cc", "kv", nil, "Explicit host C compiler"}
        }}
    on_run(function ()
        import("core.base.option")
        for _, name in ipairs({"out", "host-cc"}) do
            assert(option.get(name), "service-manifest-model-test requires --%s", name)
        end
        local out = path.absolute(option.get("out"))
        local compiler = path.absolute(option.get("host-cc"))
        assert(os.isfile(compiler), "explicit host C compiler is missing")
        assert(not os.isdir(out) and not os.isfile(out), "hosted output already exists")
        os.mkdir(out)
        for _, name in ipairs({"service_manifest_tests", "service_manifest_load_tests",
                              "service_graph_tests", "service_manager_clock_tests",
                              "service_generation_tests"}) do
            local binary = path.join(out, name)
            os.execv(compiler, {"-std=c11", "-D_GNU_SOURCE=1", "-Wall", "-Wextra", "-Werror",
                path.join(os.projectdir(), "tests", name .. ".c"), "-o", binary})
            os.execv(binary, {})
        end
    end)

task("notes-save-check")
    set_menu {usage = "xmake notes-save-check --output=DIR [--cc=CC] [--sanitize]",
        description = "Verify bounded Notes saves on scratch host files; does not execute a guest",
        options = {
            {nil, "output", "kv", nil, "New output directory; existing evidence is retained"},
            {nil, "cc", "kv", "cc", "Host C compiler"},
            {nil, "sanitize", "k", nil, "Enable ASan/UBSan; leak checking is disabled"}
        }}
    on_run(function ()
        import("core.base.option")
        assert(option.get("output"), "notes-save-check requires --output")
        local args = {"-B", path.join(os.projectdir(), "tools/test_notes_save.py"),
            "--output", option.get("output"), "--cc", option.get("cc")}
        if option.get("sanitize") then
            table.insert(args, "--sanitize")
        end
        os.execv("python3", args, {envs = {PYTHONDONTWRITEBYTECODE = "1"}})
    end)

