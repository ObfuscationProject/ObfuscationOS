set_project("ObfuscationOS")
set_version("0.1.0")
set_languages("c11")

add_rules("mode.debug", "mode.release")

option("systoolchain_dir")
    set_showmenu(true)
    set_description("Use an existing SysToolchain installation instead of resolving the package")
option_end()

if not get_config("systoolchain_dir") then
    add_repositories("obfuscation-repo https://github.com/ObfuscationProject/ObfuscationRepo.git")
    add_requires("systoolchain 0.1.0", {
        system = false,
        configs = {build_from_source = true}
    })
end


option("kernel_sdk")
    set_showmenu(true)
    set_description("Exported kernel SDK directory; default ../ObfuscationKernel/build/sdk/<arch>/<mode>")
option_end()

includes("xmake/arch.lua")
includes("xmake/targets.lua")
includes("xmake/tasks.lua")
