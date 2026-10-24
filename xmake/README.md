# Build definition layout

Files included from the repository `xmake.lua`, in order:

| File | Content |
| --- | --- |
| `arch.lua` | Ten userland architecture specs, SDK path resolution, shared toolchain/flag helpers |
| `targets.lua` | Product targets: `okcrt`, `apps`, `sysroot`, `kernel-sdk-check`, rootfs images, `distro_image`, drivers, compat, tests |
| `tasks.lua` | `arch-matrix`, `distro-test`, `qemu-distro`, `qemu-distro-window` |
| `contracts.lua` | Ledger, musl and qualification tasks that do not claim guest execution |
| `zero_truncate_fixture.lua`, `musl_udp*_fixture.lua`, `native_tcp_fixture.lua` | Fixture targets/tasks for specific qualification campaigns |

Standalone fixture projects, **not** included from `xmake.lua`. Tools copy or pin
them as the `xmake.lua` of a private build directory, which is why they define
their own `okcrt`/`kernel-sdk-check` targets:

| File | Owner |
| --- | --- |
| `linux_stat_runner.lua` | `tools/build_linux_stat_runner.py`, `tools/test_linux_stat_user.py` |
| `shared_files_fixture.lua` | `tools/write_seal_recipe_inputs.py` |

Keep new included files in the first table and new standalone projects in the
second; a file must not appear in both roles.
