#pragma once
// Hosted boundary doubles for the actual OS storage callback tests. Kernel VFS,
// journal and Virtio implementations have separate native/provider coverage.
#include <ok/core/shutdown_storage.hpp>
#include <array>
#include <span>
#include <string_view>
#include <vector>

namespace ok::driver {
struct BlockGeometry { u64 block_count{}; u32 block_size{512}; bool writable{}; };
class BlockDevice {
  public:
    virtual ~BlockDevice() = default;
    virtual BlockGeometry geometry() const = 0;
    virtual Status read_blocks(u64, std::span<std::byte>) = 0;
    virtual Status write_blocks(u64, std::span<const std::byte>) = 0;
};
}
namespace storage_seam {
inline std::vector<unsigned> calls;
inline unsigned fail_call{}, preflights{}, freezes{}, stops{}, reference_checks{};
inline bool bad_seal{}, active_reader{}, bad_policy{}, published{true};
inline ok::Status failure = ok::Status::io_error("injected original storage failure");
inline ok::Status step(unsigned kind) {
    calls.push_back(kind);
    return fail_call == calls.size() ? failure : ok::Status{};
}
}
namespace ok::block { enum class DeviceState { owned, failed }; }
namespace ok::fs {
enum class FileSystemMode { archive, ext4_journaled, ext4_read_write };
enum class NodeType { directory, symlink };
inline constexpr unsigned mode_permission_mask = 07777;
struct Metadata { NodeType type{NodeType::directory}; unsigned uid{}, gid{}, mode{0755}, link_count{1}; };
struct Credentials { unsigned uid{}, gid{}; };
struct ResolveContext { Credentials credentials{}; bool check_search{}; };
enum class FinalComponent { no_follow };
struct VfsMountHandle { unsigned id{}; bool valid() const { return id != 0; } bool operator==(const VfsMountHandle &) const = default; };
enum class OwnedMountKind { provider, ram };
struct OwnedMountExpectation { VfsMountHandle handle; const char *path; OwnedMountKind kind; VfsMountHandle parent; };
struct StatResult { Result<Metadata> result; };
class VirtualFileSystem {
  public:
    FileSystemMode selected_mode{FileSystemMode::ext4_journaled};
    Status owned_status{}, reference_status{};
    FileSystemMode mode() const { return selected_mode; }
    void set_mode(FileSystemMode mode) { selected_mode = mode; }
    Status preflight_owned_mounts(std::span<const OwnedMountExpectation> expected) const {
        ++storage_seam::preflights;
        if (expected.size() != 2 || expected[0].handle.id != 1 || expected[1].handle.id != 2 ||
            std::string_view(expected[0].path) != "/" || std::string_view(expected[1].path) != "/run" ||
            expected[0].kind != OwnedMountKind::provider || expected[1].kind != OwnedMountKind::ram ||
            expected[0].parent.valid() || expected[1].parent != expected[0].handle)
            return Status::denied("unexpected original owned attachments");
        return owned_status;
    }
    Status shutdown_reference_status() const {
        ++storage_seam::reference_checks;
        if (auto status = storage_seam::step(1); !status) return status;
        return reference_status;
    }
    Status detach(VfsMountHandle handle) { return storage_seam::step(handle.id == 2 ? 2 : 3); }
    StatResult try_stat_absolute(const char *, Credentials, FinalComponent) { return {Metadata{}}; }
    Status create(const ResolveContext &, const char *, NodeType, unsigned, unsigned, unsigned) { return {}; }
    Result<VfsMountHandle> mount_ram_owned(const char *, unsigned, unsigned, unsigned) { return VfsMountHandle{2}; }
    Result<VfsMountHandle> mount_owned(const char *, int) { return VfsMountHandle{1}; }
    Status mount(const char *, int &) { return {}; }
};
enum class Ext4TimestampPolicy : u8 { unqualified, maintained };
struct Ext4MountOptions
{
    bool writable{true};
    Ext4TimestampPolicy timestamps{Ext4TimestampPolicy::unqualified};
};
class Ext4FileSystem {
  public:
    Status mount(driver::BlockDevice &, bool) { return {}; }
    Status mount(driver::BlockDevice &, Ext4MountOptions) { return {}; }
    int *root() { return &root_; }
  private:
    int root_{};
};
enum class FatVariant { fat32, exfat };
struct FatMountInfo { FatVariant variant{FatVariant::fat32}; };
class FatVolume {
  public:
    Status mount(driver::BlockDevice &) { return Status::unsupported("not FAT in this storage seam"); }
};
class FatFileSystem {
  public:
    Status mount(driver::BlockDevice &, bool) { return {}; }
    int *root() { return &root_; }
    const FatMountInfo &info() const { return info_; }
  private:
    int root_{};
    FatMountInfo info_{};
};
enum class Ext4MountedPolicy { ordered_data_dirty_noatime, other };
enum class Ext4MountPhase { readable, clean_sealed, failed };
enum class MetadataOwnerState { ready, failed };
struct StorageOwner {
    block::DeviceState state{block::DeviceState::owned}; StatusCode first_error{StatusCode::ok};
    unsigned identity{4}, registration_generation{5}, session_serial{6};
    unsigned in_flight{}, pending_writes{};
};
struct StorageBuffers {
    MetadataOwnerState state{MetadataOwnerState::ready}; StatusCode first_error{StatusCode::ok};
    unsigned device_identity{4}, registration_generation{5}, session_serial{6};
    u64 first_sector{}, sectors{2048};
    unsigned read_pins{}, in_flight{}; bool transaction_active{};
};
struct StorageReport {
    Ext4MountPhase phase{Ext4MountPhase::readable}; Status status{};
    bool published{true}; unsigned epoch{1}; bool reading{};
};
template <unsigned> class Ext4MountedMetadata {
  public:
    struct CommonStorage {};
    class Registry {
      public:
        struct Registration { unsigned id{1}; };
        StorageOwner owner{}; Status inspect_status{};
        Result<Registration> register_device(driver::BlockDevice &, unsigned, unsigned) { return Registration{}; }
        Result<StorageOwner> inspect(Registration) const { return inspect_status ? Result<StorageOwner>{owner} : Result<StorageOwner>{inspect_status}; }
    };
    explicit Ext4MountedMetadata(CommonStorage &) {}
    StorageReport state{}; StorageBuffers buffer_state{};
    Ext4MountedPolicy policy() const { return storage_seam::bad_policy ? Ext4MountedPolicy::other : Ext4MountedPolicy::ordered_data_dirty_noatime; }
    StorageReport report() const {
        auto result = state; result.reading = storage_seam::active_reader;
        result.published = storage_seam::published; return result;
    }
    StorageBuffers buffers() const { return buffer_state; }
    Status mount(Registry &, typename Registry::Registration, std::array<u64, 2>) { return {}; }
    Result<int> retain_root() { return 1; }
    Status freeze_clean() {
        ++storage_seam::freezes;
        auto status = storage_seam::step(4);
        if (status && !storage_seam::bad_seal) state.phase = Ext4MountPhase::clean_sealed;
        return status;
    }
};
}
