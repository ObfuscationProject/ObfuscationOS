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

option("linux_journal_image")
    set_showmenu(true)
    set_description("Explicit Linux x86_64 kernel image for ext4 journal activation")
option_end()

option("linux_journal_image_sha256")
    set_showmenu(true)
    set_description("SHA-256 pin for the Linux journal activation image")
option_end()

option("managed_init_build")
    set_showmenu(true)
    set_description("Explicit pinned static-musl production init build directory")
option_end()

option("managed_init_manifest_sha256")
    set_showmenu(true)
    set_description("Exact SHA-256 of the managed init build manifest")
option_end()

option("native_udp_probe")
    set_default(false)
    set_showmenu(true)
    set_description("Run the native UDP user socket probe from init")
option_end()

option("service_graph_build")
    set_showmenu(true)
    set_description("Explicit sealed static-musl production service graph build directory")
option_end()

option("service_graph_manifest_sha256")
    set_showmenu(true)
    set_description("Exact SHA-256 of the production service graph manifest")
option_end()

option("native_vm_acceptance")
    set_default(false)
    set_showmenu(true)
    set_description("Run native userland acceptance from init in an explicit Release qualifier")
option_end()

option("native_init_acceptance")
    set_default(false)
    set_showmenu(true)
    set_description("Explicitly run native init acceptance before production supervision")
option_end()

option("native_init_control")
    set_default(true)
    set_showmenu(true)
    set_description("Bounded native PID1 status and authenticated restart control")
option_end()

option("native_console_login")
    set_default(false)
    set_showmenu(true)
    set_description("Native console account login on a persistent journalled root")
    after_check(function ()
        import("core.project.config")
        if not config.get("native_console_login") then return end
        if config.get("managed_init_build") or config.get("service_graph_build") then
            raise("native_console_login requires the ordinary native PID1")
        end
        if config.get("native_init_acceptance") or config.get("native_vm_acceptance") or config.get("native_udp_probe") then
            raise("native_console_login cannot run startup acceptance before authentication")
        end
    end)
option_end()


includes("xmake/arch.lua")
includes("xmake/targets.lua")
includes("xmake/tasks.lua")
includes("xmake/contracts.lua")
includes("xmake/zero_truncate_fixture.lua")
includes("xmake/musl_udp_fixture.lua")
includes("xmake/musl_udp_sockname_fixture.lua")
includes("xmake/musl_udp_connected_fixture.lua")

includes("xmake/native_tcp_fixture.lua")
