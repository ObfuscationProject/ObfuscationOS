#include "ok/fs/archive.hpp"
extern "C" const std::byte ok_archive_begin[], ok_archive_end[];
extern "C" ok::fs::BootArchive ok_boot_archive()
{
    return {ok_archive_begin, static_cast<ok::usize>(ok_archive_end - ok_archive_begin), "/init"};
}
