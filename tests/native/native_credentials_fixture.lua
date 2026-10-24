-- Included only by an explicit SDK-only native credentials qualifier.
for _, name in ipairs({"native-credentials-probe", "native-control-drop"}) do
    target(name)
        set_kind("binary")
        set_default(false)
        set_filename(name .. ".elf")
        set_targetdir(path.join(ok_user_builddir(), "fixtures"))
        add_deps("okcrt")
        add_ok_user_toolchain()
        add_ok_user_include_dirs()
        add_files(path.join(os.projectdir(), "tests/native", name:gsub("-", "_") .. ".c"))
        local _, spec = ok_user_require_arch(ok_user_current_arch())
        add_files(path.join(os.projectdir(), "lib/okcrt/arch", spec.source, "crt0.S"))
        add_ok_user_cflags()
        add_ok_user_linkflags()
        add_syslinks("gcc")
    target_end()
end
