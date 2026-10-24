// Compile actual storage.cpp against real exported SDK status/ticket/barrier
// types and hosted VFS/provider/transport boundaries; no target code executes.
#include "hosted/native_shutdown_storage_seams.hpp"
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <cassert>
#include <iostream>
#include <string>

namespace ok::user {
// Exercise the real private barrier constructor at its existing friend seam.
class NativeShutdownServices {
  public:
    static ShutdownStorageBarrier barrier(ShutdownTicket ticket) { return ShutdownStorageBarrier{ticket}; }
};
}
#include "../modules/boot/storage.cpp"

namespace {
class Disk final : public ok::driver::BlockDevice {
  public:
    ok::driver::BlockGeometry geometry_value{2048, 512, true};
    ok::driver::BlockGeometry geometry() const override { return geometry_value; }
    ok::Status read_blocks(ok::u64, std::span<std::byte>) override { return {}; }
    ok::Status write_blocks(ok::u64, std::span<const std::byte>) override { return {}; }
} disk;
ok::fs::VirtualFileSystem vfs;
std::string console;
ok::Status transport_status{}, stop_status{};
unsigned transport_preflights{};
bool terminal_supported{true};
ok::Status terminal_status{};
unsigned terminal_fail_preflight{};
std::vector<ok::SystemPowerAction> terminal_support_actions, terminal_preflight_actions;

void reset()
{
    storage_seam::calls.clear(); storage_seam::fail_call = 0;
    storage_seam::preflights = storage_seam::freezes = storage_seam::stops = storage_seam::reference_checks = 0;
    storage_seam::bad_seal = storage_seam::active_reader = storage_seam::bad_policy = false;
    storage_seam::published = true; console.clear(); transport_status = stop_status = {}; transport_preflights = 0;
    terminal_supported = true; terminal_status = {}; terminal_fail_preflight = 0;
    terminal_support_actions.clear(); terminal_preflight_actions.clear();
    disk.geometry_value = {2048, 512, true}; vfs = {};
    journal_registry = {}; journal_attachment = {1}; run_attachment = {2};
    journal_vfs = &vfs; journal_device = &disk; journal_geometry = disk.geometry(); journal_registration = {};
    journal_constructed = journal_boot_complete = true;
    auto *common = ::new (journal_common_storage.data()) JournalRoot::CommonStorage{};
    ::new (journal_storage.data()) JournalRoot{*common};
    storage_shutdown_phase = StorageShutdownPhase::idle; storage_shutdown_ticket = {}; storage_shutdown_failure = {};
}
ok::ShutdownTicket ticket(ok::SystemPowerAction action)
{
    return {&vfs, {&disk, 7, 1, 3}, 9, action};
}
ok::Status seal(ok::ShutdownTicket value)
{
    auto barrier = ok::user::NativeShutdownServices::barrier(value);
    return ok_shutdown_storage_seal(vfs, barrier);
}
void untouched()
{
    assert(storage_seam::calls.empty() && !storage_seam::freezes && !storage_seam::stops);
    assert(storage_shutdown_phase == StorageShutdownPhase::idle && storage_shutdown_ticket == ok::ShutdownTicket{});
}
void action_policy()
{
    using Action = ok::SystemPowerAction; using Code = ok::StatusCode;
    for (auto action : {Action::none, static_cast<Action>(255)}) {
        reset();
        assert(ok_shutdown_storage_preflight(vfs, action).code() == Code::invalid_argument); untouched();
        assert(seal(ticket(action)).code() == Code::invalid_argument); untouched();
        assert(!transport_preflights && !storage_seam::preflights);
        assert(terminal_support_actions.empty() && terminal_preflight_actions.empty());
    }
}
void terminal_controls(ok::SystemPowerAction action)
{
    using Action = ok::SystemPowerAction; using Code = ok::StatusCode;
    reset(); terminal_supported = false;
    assert(ok_shutdown_storage_preflight(vfs, action).code() == Code::unsupported); untouched();
    assert((terminal_support_actions == std::vector<Action>{action}));
    assert(terminal_preflight_actions.empty() && !transport_preflights && !storage_seam::preflights);
    assert(seal(ticket(action)).code() == Code::unsupported); untouched();
    assert((terminal_support_actions == std::vector<Action>{action, action}));
    assert(terminal_preflight_actions.empty() && !transport_preflights && !storage_seam::preflights);

    // Selected-backend refusal preserves the original status before any owner is latched.
    for (auto failure : {ok::Status::unsupported("selected terminal unavailable"),
                         ok::Status::denied("selected terminal denied"),
                         ok::Status::busy("selected terminal not ready")}) {
        reset(); terminal_status = failure;
        auto preflight = ok_shutdown_storage_preflight(vfs, action);
        assert(preflight.code() == failure.code() && preflight.message() == failure.message()); untouched();
        auto refused = seal(ticket(action));
        assert(refused.code() == failure.code() && refused.message() == failure.message()); untouched();
        assert((terminal_support_actions == std::vector<Action>{action, action}));
        assert(terminal_preflight_actions == terminal_support_actions);
        assert(!transport_preflights && !storage_seam::preflights);
        terminal_status = {};
        assert(seal(ticket(action)) && storage_shutdown_phase == StorageShutdownPhase::sealed);
    }

    // A changed second preflight after the latch fails sticky before detach or freeze.
    reset(); terminal_fail_preflight = 2;
    const auto selected = ticket(action);
    auto first = seal(selected);
    assert(first.code() == Code::busy && first.message() == std::string_view("selected terminal preflight changed"));
    assert(storage_shutdown_phase == StorageShutdownPhase::failed && storage_shutdown_ticket == selected);
    assert((terminal_support_actions == std::vector<Action>{action, action}));
    assert(terminal_preflight_actions == terminal_support_actions);
    assert(storage_seam::calls.empty() && !storage_seam::preflights && !transport_preflights);
    assert(!storage_seam::freezes && !storage_seam::stops && console.empty());
    terminal_fail_preflight = 0;
    for (auto retry_action : {Action::halt, Action::reboot, Action::poweroff}) {
        auto retry = seal(ticket(retry_action));
        assert(retry.code() == first.code() && retry.message() == first.message());
        auto preflight = ok_shutdown_storage_preflight(vfs, retry_action);
        assert(preflight.code() == first.code() && preflight.message() == first.message());
        assert((terminal_support_actions == std::vector<Action>{action, action}));
        assert(terminal_preflight_actions == terminal_support_actions);
        assert(storage_seam::calls.empty() && !storage_seam::preflights && !transport_preflights);
    }
}
void preflight_controls(ok::SystemPowerAction action)
{
    using Code = ok::StatusCode;
    reset(); assert(ok_shutdown_storage_preflight(vfs, action)); untouched();
    assert(transport_preflights == 1 && storage_seam::preflights == 1);
    assert((terminal_support_actions == std::vector<ok::SystemPowerAction>{action}));
    assert(terminal_preflight_actions == terminal_support_actions);
    for (unsigned fault = 0; fault < 31; ++fault) {
        reset(); auto expected = Code::unsupported;
        if (fault == 0) journal_constructed = false;
        if (fault == 1) journal_boot_complete = false;
        if (fault == 2) journal_vfs = nullptr;
        if (fault == 3) journal_device = nullptr;
        if (fault == 4) journal_attachment = {};
        if (fault == 5) run_attachment = {};
        if (fault == 6) vfs.selected_mode = ok::fs::FileSystemMode::archive;
        if (fault == 7) { vfs.owned_status = ok::Status::denied("changed attachment"); expected = Code::denied; }
        if (fault == 8) storage_seam::bad_policy = true;
        if (fault == 9) storage_seam::published = false;
        if (fault == 10) original_journal_root().state.epoch = 0;
        if (fault == 11) { storage_seam::active_reader = true; expected = Code::busy; }
        if (fault == 12) { journal_registry.inspect_status = ok::Status::denied("changed registration"); expected = Code::denied; }
        if (fault == 13) journal_registry.owner.identity++;
        if (fault == 14) journal_registry.owner.registration_generation++;
        if (fault == 15) journal_registry.owner.session_serial++;
        if (fault == 16) original_journal_root().buffer_state.first_sector = 1;
        if (fault == 17) original_journal_root().buffer_state.sectors--;
        if (fault == 18) { journal_registry.owner.in_flight = 1; expected = Code::busy; }
        if (fault == 19) { original_journal_root().buffer_state.read_pins = 1; expected = Code::busy; }
        if (fault == 20) { original_journal_root().buffer_state.transaction_active = true; expected = Code::busy; }
        if (fault == 21) disk.geometry_value.writable = false;
        if (fault == 22) disk.geometry_value.block_count--;
        if (fault == 23) transport_status = ok::Status::unsupported("unqualified transport or no FLUSH");
        if (fault == 24) vfs.selected_mode = ok::fs::FileSystemMode::ext4_read_write;
        if (fault == 25) journal_registry.owner.state = ok::block::DeviceState::failed;
        if (fault == 26) original_journal_root().buffer_state.state = ok::fs::MetadataOwnerState::failed;
        if (fault == 27) { journal_registry.owner.pending_writes = 1; expected = Code::busy; }
        if (fault == 28) { original_journal_root().buffer_state.in_flight = 1; expected = Code::busy; }
        if (fault == 29) disk.geometry_value.block_size = 4096;
        if (fault == 30) original_journal_root().state.status = storage_seam::failure;
        assert(ok_shutdown_storage_preflight(vfs, action).code() == expected); untouched();
    }
}
void seal_controls(ok::SystemPowerAction action)
{
    using Code = ok::StatusCode;
    for (unsigned fault = 0; fault < 7; ++fault) {
        reset(); auto invalid = ticket(action);
        if (fault == 0) invalid.coordinator = nullptr;
        if (fault == 1) invalid.owner.runtime = nullptr;
        if (fault == 2) invalid.owner.incarnation = 0;
        if (fault == 3) invalid.owner.process = 2;
        if (fault == 4) invalid.owner.leader = 0;
        if (fault == 5) invalid.generation = 0;
        if (fault == 6) invalid.owner.process = 0;
        assert(seal(invalid).code() == Code::denied); untouched();
        assert(terminal_support_actions.empty() && terminal_preflight_actions.empty());
    }
    reset(); storage_shutdown_phase = StorageShutdownPhase::detaching_run;
    assert(seal(ticket(action)).code() == Code::busy && storage_seam::calls.empty());
    assert(ok_shutdown_storage_preflight(vfs, action).code() == Code::busy);
    reset(); const auto selected = ticket(action); assert(seal(selected));
    assert((storage_seam::calls == std::vector<unsigned>{1, 2, 3, 1, 4, 5}));
    assert(storage_seam::freezes == 1 && storage_seam::stops == 1);
    assert((terminal_support_actions == std::vector<ok::SystemPowerAction>{action, action}));
    assert(terminal_preflight_actions == terminal_support_actions);
    assert(storage_shutdown_phase == StorageShutdownPhase::sealed && storage_shutdown_ticket == selected);
    assert(console == "OK_STORAGE_SHUTDOWN scope=provider state=clean_sealed platform=0\n");
    const auto calls = storage_seam::calls;
    assert(seal(selected) && calls == storage_seam::calls);
    assert((terminal_support_actions == std::vector<ok::SystemPowerAction>{action, action}));
    assert(terminal_preflight_actions == terminal_support_actions);
    for (unsigned field = 0; field < 7; ++field) {
        auto changed = selected;
        if (field == 0) changed.action = action == ok::SystemPowerAction::halt ? ok::SystemPowerAction::reboot : ok::SystemPowerAction::halt;
        if (field == 1) changed.coordinator = &disk;
        if (field == 2) changed.owner.runtime = &vfs;
        if (field == 3) changed.owner.incarnation++;
        if (field == 4) changed.owner.process++;
        if (field == 5) changed.owner.leader++;
        if (field == 6) changed.generation++;
        assert(seal(changed).code() == Code::denied && calls == storage_seam::calls);
    }
    assert(ok_shutdown_storage_preflight(vfs, action).code() == Code::busy);
    for (unsigned fault = 1; fault <= 9; ++fault) {
        reset();
        if (fault <= 6) storage_seam::fail_call = fault;
        if (fault == 7) storage_seam::bad_seal = true;
        if (fault == 8) vfs.owned_status = storage_seam::failure;
        if (fault == 9) vfs.reference_status = ok::Status::busy("retained original reference");
        auto first = seal(ticket(action)); assert(!first && storage_shutdown_phase == StorageShutdownPhase::failed);
        assert(storage_shutdown_ticket == ticket(action) && console.empty());
        auto consumed = storage_seam::calls;
        storage_seam::fail_call = 0; storage_seam::bad_seal = false; vfs.owned_status = {}; vfs.reference_status = {};
        auto second = seal(ticket(action));
        assert(second.code() == first.code() && second.message() == first.message() && storage_seam::calls == consumed);
        auto changed = ticket(action);
        changed.action = action == ok::SystemPowerAction::halt ? ok::SystemPowerAction::reboot : ok::SystemPowerAction::halt;
        auto cross = seal(changed);
        assert(cross.code() == first.code() && cross.message() == first.message() && storage_seam::calls == consumed);
        auto preflight = ok_shutdown_storage_preflight(vfs, action);
        assert(preflight.code() == first.code() && preflight.message() == first.message() && storage_seam::calls == consumed);
    }
}
}
extern "C" void ok_platform_console_write_char(char value) { console += value; }
namespace os::drivers {
ok::Result<ok::driver::BlockDevice *> probe_virtio_block() { return &disk; }
ok::Status preflight_virtio_block_shutdown(const ok::driver::BlockDevice &device)
{
    assert(&device == &disk); ++transport_preflights; return transport_status;
}
ok::Status stop_virtio_block_shutdown(const ok::driver::BlockDevice &device)
{
    assert(&device == &disk); ++storage_seam::stops;
    if (auto status = storage_seam::step(5); !status) return status;
    return stop_status;
}
}
namespace ok::arch {
bool terminal_power_action_supported(SystemPowerAction action) noexcept
{
    terminal_support_actions.push_back(action);
    return terminal_supported;
}
Status preflight_terminal_power_action(SystemPowerAction action) noexcept
{
    terminal_preflight_actions.push_back(action);
    if (terminal_fail_preflight && terminal_preflight_actions.size() == terminal_fail_preflight)
        return Status::busy("selected terminal preflight changed");
    return terminal_status;
}
Status initialize_clock() { return Status::unsupported("hosted no clock"); }
Status initialize_realtime() { return Status::unsupported("hosted no realtime"); }
Result<time::RealtimeSample> realtime_sample() { return Status::unsupported("hosted no realtime"); }
Result<time::MonotonicPoint> monotonic_sample() { return Status::unsupported("hosted no clock"); }
Status set_realtime(time::EpochTime, time::MonotonicPoint) { return Status::unsupported("hosted no realtime"); }
}
int main()
{
    action_policy();
    for (auto action : {ok::SystemPowerAction::halt, ok::SystemPowerAction::reboot, ok::SystemPowerAction::poweroff}) {
        terminal_controls(action); preflight_controls(action); seal_controls(action);
    }
    std::cout << "actual OS storage HALT/REBOOT/POWEROFF selected-terminal action, ownership, exact barrier, ordering and sticky failure controls passed\n";
}
