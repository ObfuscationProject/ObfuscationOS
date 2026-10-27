#include <ok/fs/ext4/journal.hpp>
#include "linux_fixture.hpp"
#include <cstdio>

using namespace ok;
using namespace ok::fs::jbd2;
struct Reader
{
    std::FILE *file;
    Status read_block(u32 index, std::span<u8> bytes)
    {
        if (index >= fixture::layout.journal_blocks || bytes.size() != fixture::layout.block_size)
            return Status::invalid_argument("fixture journal bounds");
        const u64 offset = (fixture::layout.journal_first_block + index) * fixture::layout.block_size;
        if (std::fseek(file, static_cast<long>(offset), SEEK_SET) != 0 ||
            std::fread(bytes.data(), 1, bytes.size(), file) != bytes.size())
            return Status::io_error("fixture read");
        return Status::success();
    }
};
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    auto *file = std::fopen(argv[1], "rb");
    if (!file) return 2;
    Reader reader{file};
    std::array<u8, 1024> record{}, payload{};
    std::array<ReplayAction, 64> actions{};
    std::array<Revocation, 64> revokes{};
    if (!reader.read_block(0, record)) return 3;
#ifdef OS_JBD2_AUDIT_STRICT
    const auto codec = Codec::open(record, fixture::layout.journal_blocks, fixture::uuid);
#else
    const auto codec = Codec::open(record, fixture::layout.journal_blocks, fixture::uuid,
                                   DescriptorUuidPolicy::linux_internal_zero);
#endif
    if (!codec) { std::fprintf(stderr, "%.*s\n", int(codec.status().message().size()), codec.status().message().data()); return 4; }
    const auto plan = build_replay_plan(codec.value(), reader, {fixture::layout.filesystem_blocks, fixture::ranges},
                                      {record, payload, actions, revokes});
    if (!plan) { std::fprintf(stderr, "%.*s\n", int(plan.status().message().size()), plan.status().message().data()); return 5; }
    std::printf("{\"transactions\":%u,\"next_sequence\":%u,\"scanned\":%u,\"revoked\":%zu,\"incomplete\":%s,\"actions\":[",
                plan.value().committed_transactions, plan.value().next_sequence, plan.value().scanned_blocks,
                plan.value().revoked_actions, plan.value().incomplete_tail ? "true" : "false");
    bool comma = false;
    for (const auto &action : plan.value().actions)
    {
        std::printf("%s{\"target\":%llu,\"source\":%u,\"sequence\":%u,\"order\":%u,\"checksum\":%u,\"escape\":%s}",
                    comma ? "," : "", static_cast<unsigned long long>(action.target_block), action.journal_block,
                    action.sequence, action.transaction_order, action.checksum, action.restore_magic ? "true" : "false");
        comma = true;
    }
    std::puts("]}");
    return std::fclose(file) == 0 ? 0 : 6;
}
