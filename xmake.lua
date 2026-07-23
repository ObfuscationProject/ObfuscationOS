set_project("ObfuscationOS")
set_version("0.1.0")
set_languages("c11")

add_rules("mode.debug", "mode.release")

add_repositories("obfuscation-repo https://github.com/ObfuscationProject/ObfuscationRepo.git")
add_requires("systoolchain 0.1.0", {
    system = false,
    configs = {build_from_source = true}
})

includes("xmake/arch.lua")
includes("xmake/targets.lua")
includes("xmake/tasks.lua")
