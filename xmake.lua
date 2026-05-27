set_project("ObfuscationOS")
set_version("0.1.0")
set_languages("c11")

add_rules("mode.debug", "mode.release")

option("auto_bootstrap_toolchain")
    set_default(true)
    set_showmenu(true)
    set_description("Keep configure non-fatal when a first-stage toolchain is missing")
option_end()

includes("xmake/arch.lua")
includes("xmake/toolchains.lua")
includes("xmake/targets.lua")
includes("xmake/tasks.lua")
