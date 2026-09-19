#include "../../drivers/virtio/block.hpp"
#include <ok/fs/ext4_fs.hpp>

extern "C" void ok_platform_console_write_char(char);
namespace
{
void report(const char *text)
{
    while (*text) ok_platform_console_write_char(*text++);
}
ok::fs::Ext4FileSystem root_filesystem;
}

// Distribution policy: a clean supported ext4 disk replaces the archive root.
// Missing disks and non-ext4 media keep the embedded rescue root. An ext4 disk
// that fails validation never gets formatted or silently mounted read/write.
extern "C" ok::Status ok_boot_filesystem(ok::fs::VirtualFileSystem &vfs)
{
    auto disk = os::drivers::probe_virtio_block();
    if (!disk)
    {
        if (disk.status().code() != ok::StatusCode::not_found && disk.status().code() != ok::StatusCode::unsupported)
            return disk.status();
        report("OK_STORAGE source=archive reason=no-supported-device\n");
        return ok::Status::success();
    }
    std::array<std::byte, 1024> super{};
    if (auto status = disk.value()->read_blocks(2, super); !status.ok()) return status;
    if (super[56] != std::byte{0x53} || super[57] != std::byte{0xef})
    {
        report("OK_STORAGE source=archive reason=non-ext4-media\n");
        return ok::Status::success();
    }
    if (auto status = root_filesystem.mount(*disk.value(), true); !status.ok()) return status;
    if (auto status = vfs.mount("/", *root_filesystem.root()); !status.ok()) return status;
    vfs.set_mode(ok::fs::FileSystemMode::ext4_read_write);
    report("OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\n");
    return ok::Status::success();
}
