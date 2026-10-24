set_project("desktop-files-actions")
set_languages("c++23")
add_rules("mode.debug", "mode.release")
toolchain("files-explicit")
    set_kind("standalone")
    on_check(function (toolchain)
        assert(os.isfile(os.getenv("DESKTOP_FILES_CC")) and os.isfile(os.getenv("DESKTOP_FILES_CXX")), "explicit compiler required")
        assert(os.isdir(os.getenv("DESKTOP_FILES_SDK")), "explicit SDK required")
        return true
    end)
    on_load(function (toolchain)
        toolchain:set("toolset", "cc", os.getenv("DESKTOP_FILES_CC"))
        toolchain:set("toolset", "cxx", os.getenv("DESKTOP_FILES_CXX"))
        toolchain:set("toolset", "ld", os.getenv("DESKTOP_FILES_CXX"))
    end)
toolchain_end()
target("desktop-files")
    set_toolchains("files-explicit")
    set_kind(os.getenv("DESKTOP_FILES_KIND") == "object" and "object" or "binary")
    add_includedirs(os.getenv("DESKTOP_FILES_SDK") .. "/include", os.getenv("DESKTOP_FILES_OS"))
    add_cxxflags("-Wall", "-Wextra", "-Werror", "-fno-exceptions", {force=true})
    if os.getenv("DESKTOP_FILES_KIND") == "object" then
        add_files(os.getenv("DESKTOP_FILES_OS") .. "/tests/hosted/desktop_files_object.cpp")
        add_cxxflags("-ffreestanding", "-fno-stack-protector", "-fno-threadsafe-statics", {force=true})
        for flag in (os.getenv("DESKTOP_FILES_ARCH_FLAGS") or ""):gmatch("%S+") do add_cxxflags(flag, {force=true}) end
    else
        add_files(os.getenv("DESKTOP_FILES_OS") .. "/tests/hosted/desktop_files_actions.cpp")
        if os.getenv("DESKTOP_FILES_KIND") == "sanitized" then
            add_cxxflags("-fsanitize=address,undefined", "-fno-omit-frame-pointer", {force=true})
            add_ldflags("-fsanitize=address,undefined", {force=true})
        end
    end
target_end()
