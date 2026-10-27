#include "drivers/virtio/block.hpp"
#include <ok/fs/ext4/layout.hpp>
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <new>
#include "timestamp_fixture.hpp"
using namespace ok;
namespace {
void emit(const char *text)
{
    while (*text)
    {
#if defined(__x86_64__) || defined(__i386__)
        u8 ready;
        do { asm volatile("inb %1, %0" : "=a"(ready) : "Nd"(u16{0x3fd})); } while (!(ready & 32));
        asm volatile("outb %0, %1" :: "a"(static_cast<u8>(*text++)), "Nd"(u16{0x3f8}));
#elif defined(__aarch64__) || defined(__arm__)
        while (*reinterpret_cast<volatile u32 *>(0x09000018) & 32) {}
        *reinterpret_cast<volatile u32 *>(0x09000000) = static_cast<u8>(*text++);
#elif defined(__riscv)
        *reinterpret_cast<volatile u8 *>(0x10000000) = static_cast<u8>(*text++);
#elif defined(__loongarch__)
        while (!(*reinterpret_cast<volatile u8 *>(0x1fe001e5) & 32)) {}
        *reinterpret_cast<volatile u8 *>(0x1fe001e0) = static_cast<u8>(*text++);
#elif defined(__mips__)
#if __SIZEOF_POINTER__ == 8
        constexpr uptr uart = 0xffffffffb80003f8ull;
#else
        constexpr uptr uart = 0xb80003f8;
#endif
        while (!(*reinterpret_cast<volatile u8 *>(uart + 5) & 32)) {}
        *reinterpret_cast<volatile u8 *>(uart) = static_cast<u8>(*text++);
#elif defined(__powerpc__) || defined(__PPC__)
        while (!(*reinterpret_cast<volatile u8 *>(0xe0004505) & 32)) {}
        *reinterpret_cast<volatile u8 *>(0xe0004500) = static_cast<u8>(*text++);
#else
#error "Every supported probe profile requires its explicit serial backend"
#endif
    }
}

[[noreturn]] void stop(bool success = false)
{
#if defined(__x86_64__) || defined(__i386__)
    asm volatile("outl %0, %1" :: "a"(success ? 16U : 17U), "Nd"(u16{0xf4}));
#else
    static_cast<void>(success);
#endif
    for (;;) asm volatile("" ::: "memory");
}

void check(bool value, const char *reason)
{
    if (value) return;
    emit("EXT4_TIMESTAMPS_FAIL "); emit(reason); emit("\n"); stop();
}

} // namespace
// Minimal freestanding probe runtime; RTTI remains enabled as in the SDK.
extern "C" void *memcpy(void *to, const void *from, usize size)
{
    auto *out = static_cast<volatile std::byte *>(to);
    const auto *in = static_cast<const std::byte *>(from);
    for (usize index = 0; index < size; ++index) out[index] = in[index];
    return to;
}
extern "C" void *memset(void *to, int value, usize size)
{
    auto *out = static_cast<volatile u8 *>(to);
    for (usize index = 0; index < size; ++index) out[index] = static_cast<u8>(value);
    return to;
}
extern "C" int memcmp(const void *one, const void *two, usize size)
{
    const auto *a = static_cast<const u8 *>(one);
    const auto *b = static_cast<const u8 *>(two);
    for (usize index = 0; index < size; ++index)
        if (a[index] != b[index]) return a[index] < b[index] ? -1 : 1;
    return 0;
}
extern "C" void *memchr(const void *source, int value, usize size)
{
    const auto *bytes = static_cast<const u8 *>(source);
    for (usize index = 0; index < size; ++index)
        if (bytes[index] == static_cast<u8>(value))
            return const_cast<u8 *>(bytes + index);
    return nullptr;
}
extern "C" usize strlen(const char *text)
{
    usize count = 0;
    while (text[count]) ++count;
    return count;
}
extern "C" int atexit(void (*)()) { return 0; }
extern "C" void __cxa_pure_virtual() { stop(); }
namespace std { [[noreturn]] void terminate() noexcept { stop(); } }
void operator delete(void *) noexcept { stop(); }
void operator delete(void *, usize) noexcept { stop(); }
namespace __cxxabiv1
{
class __class_type_info { public: virtual ~__class_type_info(); };
class __si_class_type_info : public __class_type_info { public: ~__si_class_type_info() override; };
class __vmi_class_type_info : public __class_type_info { public: ~__vmi_class_type_info() override; };
__class_type_info::~__class_type_info() = default;
__si_class_type_info::~__si_class_type_info() = default;
__vmi_class_type_info::~__vmi_class_type_info() = default;
} // namespace __cxxabiv1

namespace {
alignas(fs::Ext4FileSystem) std::array<std::byte, sizeof(fs::Ext4FileSystem)> volume_storage{}, reopen_storage{};
class ObservedDisk final : public driver::BlockDevice {
    driver::BlockDevice &device_;
  public:
    u64 reads{}, writes{}, flushes{};
    explicit ObservedDisk(driver::BlockDevice &device) : device_(device) {}
    driver::BlockGeometry geometry() const override { return device_.geometry(); }
    Status read_blocks(u64 first, std::span<std::byte> out) override { ++reads; return device_.read_blocks(first, out); }
    Status write_blocks(u64 first, std::span<const std::byte> in) override { ++writes; return device_.write_blocks(first, in); }
    Status flush() override { ++flushes; return device_.flush(); }
};
ObservedDisk *disk;
u64 sequence{};
i64 base_epoch = 946684800;
void number(u64 value)
{
    char text[24]{}; usize length = 0;
    do { text[length++] = static_cast<char>('0' + value % 10); value /= 10; } while (value);
    while (length) { const char part[]{text[--length], 0}; emit(part); }
}
void field(const char *name, u64 value) { emit(" "); emit(name); emit("="); number(value); }
bool equal(fs::EpochTimestamp a, fs::EpochTimestamp b)
{ return a.seconds == b.seconds && a.nanoseconds == b.nanoseconds && a.source == b.source; }
fs::FileAttributes attributes(fs::Node &node)
{
    auto result = node.query_metadata(); check(result.ok(), "checked metadata");
    auto value = result.value().attributes;
    check(value.has(fs::Attribute::inode) && value.has(fs::Attribute::access_time) &&
          value.has(fs::Attribute::modification_time) && value.has(fs::Attribute::change_time), "complete stored times");
    return value;
}
void times(const char *prefix, const fs::FileAttributes &value)
{
    const fs::EpochTimestamp values[]{value.access, value.modification, value.change};
    const char *names[]{"a", "m", "c"};
    for (usize i = 0; i < 3; ++i) {
        check(values[i].seconds >= 0, "native fixture uses nonnegative epochs");
        emit(" "); emit(prefix); emit(names[i]); emit("_sec="); number(static_cast<u64>(values[i].seconds));
        emit(" "); emit(prefix); emit(names[i]); emit("_ns="); number(values[i].nanoseconds);
        emit(" "); emit(prefix); emit(names[i]); emit("_source="); number(static_cast<u64>(values[i].source));
    }
}
time::RealtimeSample sample()
{
    auto value = arch::realtime_sample(); check(value.ok(), "actual active realtime sample");
    check(value.value().origin == time::RealtimeOrigin::administrator_software && value.value().wall_generation &&
          value.value().monotonic.generation, "explicit software origin");
    return value.value();
}
void select_time(i64 seconds)
{
    auto mono = arch::monotonic_sample(); check(mono.ok(), "actual monotonic sample");
    check(arch::set_realtime({seconds, 123456789}, mono.value()).ok(), "trusted software clock selection");
}
struct Event {
    struct Item { const char *role{}; fs::Node *node{}; u32 mask{}; bool created{}; fs::FileAttributes before{}; };
    const char *name;
    time::RealtimeSample before;
    u64 writes;
    std::array<Item, 4> items{};
    usize count{};
    explicit Event(const char *label) : name(label), writes(disk->writes)
    { select_time(base_epoch + static_cast<i64>(++sequence * 2)); before = sample(); }
    void watch(const char *role, fs::Node &node, u32 mask)
    { check(count < items.size(), "bounded participants"); items[count++] = {role, &node, mask, false, attributes(node)}; }
    void created(const char *role, fs::Node &node)
    { check(count < items.size(), "bounded new participant"); items[count++] = {role, &node, 7, true, {}}; }
    void finish(Status result = {}, StatusCode expected = StatusCode::ok, bool no_writes = false)
    {
        const auto after = sample();
        check(result.code() == expected, "operation status");
        check(after.wall_generation == before.wall_generation && after.monotonic.generation == before.monotonic.generation &&
              after.monotonic.nanoseconds >= before.monotonic.nanoseconds, "operation clock continuity");
        if (no_writes) check(disk->writes == writes, "no-event or preflight operation wrote disk");
        emit("EXT4_TIME_EVENT name="); emit(name); emit(" status=");
        emit(expected == StatusCode::ok ? "ok" : expected == StatusCode::overflow ? "overflow" : "busy");
        field("writes", disk->writes - writes); field("no_writes", no_writes);
        field("before_sec", static_cast<u64>(before.value.seconds)); field("before_ns", before.value.nanoseconds);
        field("after_sec", static_cast<u64>(after.value.seconds)); field("after_ns", after.value.nanoseconds);
        field("before_mono", before.monotonic.nanoseconds); field("after_mono", after.monotonic.nanoseconds);
        field("wall_generation", before.wall_generation); field("mono_generation", before.monotonic.generation);
        emit(" origin=administrator-software\n");
        bool selected = false; fs::EpochTimestamp common{};
        for (usize i = 0; i < count; ++i) {
            const auto &item = items[i]; const auto now = attributes(*item.node);
            if (!item.created) check(now.inode == item.before.inode, "participant inode identity");
            const fs::EpochTimestamp old[]{item.before.access, item.before.modification, item.before.change};
            const fs::EpochTimestamp current[]{now.access, now.modification, now.change};
            for (usize f = 0; f < 3; ++f) {
                check(current[f].source == fs::TimestampSource::maintained_ext4, "maintained provenance");
                if (item.mask & (1u << f)) {
                    const u64 actual = static_cast<u64>(current[f].seconds) * 1000000000 + current[f].nanoseconds;
                    const u64 lower = static_cast<u64>(before.value.seconds) * 1000000000 +
                                      (timestamp_fixture::inode_size == 128 ? 0 : before.value.nanoseconds);
                    const u64 upper = static_cast<u64>(after.value.seconds) * 1000000000 +
                                      (timestamp_fixture::inode_size == 128 ? 0 : after.value.nanoseconds);
                    check(actual >= lower && actual <= upper, "selected timestamp real clock bracket");
                    if (timestamp_fixture::inode_size == 128) check(current[f].nanoseconds == 0, "seconds-only precision");
                    if (selected) check(equal(common, current[f]), "multi-field single-sample consistency");
                    common = current[f]; selected = true;
                } else check(equal(old[f], current[f]), "unselected field changed");
            }
            emit("EXT4_TIME_INODE event="); emit(name); emit(" role="); emit(item.role);
            field("inode", now.inode); field("mask", item.mask); field("created", item.created);
            times("before_", item.before); times("after_", now); emit("\n");
        }
    }
};
std::span<const std::byte> bytes(std::string_view value)
{ return {reinterpret_cast<const std::byte *>(value.data()), value.size()}; }
fs::Node &create(fs::Node &parent, const char *name, fs::NodeType type)
{
    auto value = parent.create_child(name, {type, type == fs::NodeType::directory ? 0755u : 0640u, 0, 0});
    check(value.ok() && value.value(), "create child"); return *value.value();
}
fs::Node &lookup(fs::Node &parent, const char *name)
{ auto value = parent.lookup_child(name); check(value.ok() && value.value(), "child lookup"); return *value.value(); }
void final_node(const char *path, fs::Node &node, fs::Ext4FileSystem &readonly)
{
    const auto maintained = attributes(node);
    fs::Node *current = readonly.root();
    std::string_view remaining(path);
    while (!remaining.empty() && remaining.front() == '/') remaining.remove_prefix(1);
    while (!remaining.empty()) {
        const auto slash = remaining.find('/'); const auto name = remaining.substr(0, slash);
        auto next = current->lookup_child(name); check(next.ok() && next.value(), "readonly reopen lookup"); current = next.value();
        if (slash == std::string_view::npos) break;
        remaining.remove_prefix(slash + 1);
    }
    const auto reopened = attributes(*current);
    check(maintained.inode == reopened.inode, "reopen inode");
    const fs::EpochTimestamp a[]{maintained.access, maintained.modification, maintained.change};
    const fs::EpochTimestamp b[]{reopened.access, reopened.modification, reopened.change};
    for (usize i = 0; i < 3; ++i)
        check(a[i].seconds == b[i].seconds && a[i].nanoseconds == b[i].nanoseconds &&
              b[i].source == fs::TimestampSource::readonly_ext4, "readonly stored times preserved");
    emit("EXT4_TIME_FINAL path="); emit(path); field("inode", maintained.inode); times("", maintained);
    field("reopened", 1); emit("\n");
}
} // namespace
extern "C" [[noreturn]] void kernel_main()
{
    emit("EXT4_TIMESTAMPS_BEGIN scope=privileged-device-provider\n");
    check(arch::initialize_clock().ok(), "actual clock initialization");
    static_cast<void>(arch::initialize_realtime());
    select_time(base_epoch);
    const auto boot = arch::realtime_info();
    auto found = os::drivers::probe_virtio_block(); check(found.ok(), "actual Virtio device");
    ObservedDisk observed(*found.value()); disk = &observed;
    auto &volume = *::new(volume_storage.data()) fs::Ext4FileSystem;
    check(volume.mount(observed, fs::Ext4MountOptions{true, fs::Ext4TimestampPolicy::maintained}).ok(), "maintained admission");
    check(!observed.writes, "mount admission wrote timestamp");
    auto &root = *volume.root();
    fs::Node *left{}, *right{}, *file{}, *shortlink{}, *longlink{}, *sub{}, *victim{}, *dirvictim{}, *orphan{};
    { Event e("create-left"); e.watch("parent", root, 6); left = &create(root, "left", fs::NodeType::directory); e.created("child", *left); e.finish(); }
    { Event e("create-right"); e.watch("parent", root, 6); right = &create(root, "right", fs::NodeType::directory); e.created("child", *right); e.finish(); }
    { Event e("create-file"); e.watch("parent", *left, 6); file = &create(*left, "file", fs::NodeType::regular); e.created("child", *file); e.finish(); }
    { Event e("create-inline"); e.watch("parent", *left, 6); check(left->create_symlink("short", "file", 0, 0).ok(), "inline symlink"); shortlink = &lookup(*left, "short"); e.created("child", *shortlink); e.finish(); }
    static constexpr std::string_view long_target = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-long-target";
    { Event e("create-block-link"); e.watch("parent", *left, 6); check(left->create_symlink("long", long_target, 0, 0).ok(), "block symlink"); longlink = &lookup(*left, "long"); e.created("child", *longlink); e.finish(); }
    { Event e("write"); e.watch("target", *file, 6); e.finish(file->write(0, bytes("abcdef"))); }
    { Event e("write-identical"); e.watch("target", *file, 6); e.finish(file->write(0, bytes("abcdef"))); }
    { Event e("write-sparse"); e.watch("target", *file, 6); e.finish(file->write(timestamp_fixture::block_size + 3, bytes("XYZ"))); }
    { Event e("write-empty"); e.watch("target", *file, 0); e.finish(file->write(0, {}), StatusCode::ok, true); }
    { Event e("truncate-same"); e.watch("target", *file, 6); e.finish(file->truncate(timestamp_fixture::block_size + 6)); }
    { Event e("truncate-grow"); e.watch("target", *file, 6); e.finish(file->truncate(timestamp_fixture::block_size * 2 + 5)); }
    { Event e("truncate-shrink"); e.watch("target", *file, 6); e.finish(file->truncate(6)); }
    { Event e("truncate-zero"); e.watch("target", *file, 6); e.finish(file->truncate(0)); }
    { Event e("truncate-zero-again"); e.watch("target", *file, 6); e.finish(file->truncate(0)); }
    { Event e("write-restore"); e.watch("target", *file, 6); e.finish(file->write(0, bytes("abcdef"))); }
    { Event e("chmod-equal"); e.watch("target", *file, 4); e.finish(file->chmod(0640)); }
    { Event e("chmod"); e.watch("target", *file, 4); e.finish(file->chmod(0600)); }
    { Event e("chown-equal"); e.watch("target", *file, 4); e.finish(file->chown(0, 0)); }
    { Event e("chown"); e.watch("target", *file, 4); e.finish(file->chown(0x12345678, 0x87654321)); }
    check(file->retain().ok(), "retain file");
    { Event e("link"); e.watch("parent", *right, 6); e.watch("source", *file, 4); e.finish(right->link("hard", *file)); }
    { Event e("rename-hardlink-noop"); e.watch("old", *left, 0); e.watch("new", *right, 0); e.watch("source", *file, 0); e.finish(left->rename("file", *right, "hard"), StatusCode::ok, true); }
    { Event e("unlink-retained"); e.watch("parent", *right, 6); e.watch("victim", *file, 4); e.finish(right->remove("hard", false)); }
    { Event e("rename-same-inode"); e.watch("parent", *left, 0); e.watch("source", *file, 0); e.finish(left->rename("file", *left, "file"), StatusCode::ok, true); }
    { Event e("rename-same-parent"); e.watch("parent", *left, 6); e.watch("source", *file, 4); e.finish(left->rename("file", *left, "same")); }
    { Event e("rename-cross-parent"); e.watch("old", *left, 6); e.watch("new", *right, 6); e.watch("source", *file, 4); e.finish(left->rename("same", *right, "moved")); }
    { Event e("create-victim"); e.watch("parent", *right, 6); victim = &create(*right, "victim", fs::NodeType::regular); e.created("child", *victim); e.finish(); }
    check(victim->retain().ok(), "retain replacement");
    { Event e("rename-replace"); e.watch("parent", *right, 6); e.watch("source", *file, 4); e.watch("victim", *victim, 4); e.finish(right->rename("moved", *right, "victim")); }
    { Event e("release-replaced"); e.watch("parent", *right, 0); e.watch("source", *file, 0); e.finish(victim->release()); }
    { Event e("create-sub"); e.watch("parent", *left, 6); sub = &create(*left, "sub", fs::NodeType::directory); e.created("child", *sub); e.finish(); }
    { Event e("create-dir-victim"); e.watch("parent", *right, 6); dirvictim = &create(*right, "dst", fs::NodeType::directory); e.created("child", *dirvictim); e.finish(); }
    check(dirvictim->retain().ok(), "retain directory replacement");
    { Event e("move-directory"); e.watch("old", *left, 6); e.watch("new", *right, 6); e.watch("source", *sub, 4); e.finish(left->rename("sub", *right, "sub")); }
    { Event e("replace-directory"); e.watch("parent", *right, 6); e.watch("source", *sub, 4); e.watch("victim", *dirvictim, 4); e.finish(right->rename("sub", *right, "dst")); }
    { Event e("release-directory"); e.watch("parent", *right, 0); e.watch("source", *sub, 0); e.finish(dirvictim->release()); }
    { Event e("read"); e.watch("target", *file, 1); auto value = file->read(0, 6); check(value.ok() && value.value().size == 6 && !memcmp(value.value().data.data(), "abcdef", 6), "file data"); e.finish(); }
    { Event e("read-eof"); e.watch("target", *file, 1); auto value = file->read(6, 1); check(value.ok() && !value.value().size, "nonzero EOF"); e.finish(); }
    { Event e("read-zero"); e.watch("target", *file, 0); auto value = file->read(0, 0); check(value.ok() && !value.value().size, "zero read"); e.finish({}, StatusCode::ok, true); }
    { Event e("read-inline"); e.watch("target", *shortlink, 1); auto value = shortlink->read(0, 4); check(value.ok() && value.value().size == 4 && !memcmp(value.value().data.data(), "file", 4), "inline bytes"); e.finish(); }
    { Event e("read-block-link"); e.watch("target", *longlink, 1); auto value = longlink->read(0, long_target.size()); check(value.ok() && value.value().size == long_target.size() && !memcmp(value.value().data.data(), long_target.data(), long_target.size()), "block link bytes"); e.finish(); }
    { Event e("list-access"); e.watch("directory", *left, 1); e.watch("child", *shortlink, 0); auto value = left->list(); check(value.ok() && value.value().count == 2, "public listing"); e.finish(); }
    { Event e("list-inspection"); e.watch("directory", *left, 0); auto value = left->list(fs::DirectoryReadIntent::inspection); check(value.ok() && value.value().count == 2, "inspection listing"); e.finish({}, StatusCode::ok, true); }
    { Event e("list-empty"); e.watch("directory", *sub, 1); auto value = sub->list(); check(value.ok() && !value.value().count, "empty access"); e.finish(); }
    { Event e("rmdir-nonempty"); e.watch("parent", root, 0); e.watch("victim", *left, 0); e.finish(root.remove("left", true), StatusCode::busy, true); }
    { Event e("metadata-lookup"); e.watch("parent", *right, 0); e.watch("target", *file, 0); check(&lookup(*right, "victim") == file, "retained lookup identity"); check(file->query_metadata().ok(), "metadata only"); e.finish({}, StatusCode::ok, true); }
    base_epoch = 2208988800;
    { Event e("post2038"); e.watch("target", *file, timestamp_fixture::inode_size == 128 ? 0 : 6); e.finish(file->write(0, bytes("abcdef")), timestamp_fixture::inode_size == 128 ? StatusCode::overflow : StatusCode::ok, timestamp_fixture::inode_size == 128); }
    base_epoch = 946684800;
    { Event e("backward"); e.watch("target", *file, 4); e.finish(file->chmod(0600)); }
    { Event e("create-orphan"); e.watch("parent", root, 6); orphan = &create(root, "orphan", fs::NodeType::regular); e.created("child", *orphan); e.finish(); }
    check(orphan->retain().ok(), "retain orphan");
    { Event e("remove-orphan"); e.watch("parent", root, 6); e.watch("victim", *orphan, 4); e.finish(root.remove("orphan", false)); }
    { Event e("close-orphan"); e.watch("parent", root, 0); e.watch("file", *file, 0); e.finish(orphan->release()); }
    fs::Node *removed_directory{};
    { Event e("create-rmdir"); e.watch("parent", root, 6); removed_directory = &create(root, "removed-directory", fs::NodeType::directory); e.created("child", *removed_directory); e.finish(); }
    check(removed_directory->retain().ok(), "retain removed directory");
    { Event e("rmdir-retained"); e.watch("parent", root, 6); e.watch("victim", *removed_directory, 4); e.finish(root.remove("removed-directory", true)); }
    { Event e("close-removed-directory"); e.watch("parent", root, 0); e.finish(removed_directory->release()); }
    { Event e("close-linked"); e.watch("target", *file, 0); e.finish(file->release(), StatusCode::ok, true); }
    { Event e("sync"); e.watch("root", root, 0); e.watch("file", *file, 0); e.finish(volume.sync()); }
    auto &readonly = *::new(reopen_storage.data()) fs::Ext4FileSystem;
    const auto writes = observed.writes;
    check(readonly.mount(observed, false).ok(), "readonly reopen");
    final_node("/", root, readonly); final_node("/left", *left, readonly); final_node("/right", *right, readonly);
    final_node("/right/victim", *file, readonly); final_node("/left/short", *shortlink, readonly);
    final_node("/left/long", *longlink, readonly); final_node("/right/dst", *sub, readonly);
    check(observed.writes == writes, "readonly reopen wrote disk");
    const auto after_boot = arch::realtime_info();
    check(boot.state == after_boot.state && boot.source == after_boot.source &&
          boot.monotonic_generation == after_boot.monotonic_generation, "software selections changed boot provenance");
    emit("EXT4_TIME_SCOPE origin=administrator-software public-user=0 clock-loss=hosted-only physical=0 smp=0");
    field("events", sequence); field("reads", observed.reads); field("writes", observed.writes); field("flushes", observed.flushes); emit("\n");
    emit("EXT4_TIMESTAMPS_PASS scope=privileged-device-provider\n"); stop(true);
}
