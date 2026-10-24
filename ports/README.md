# Ports framework

`ports/<name>/port.json` describes one pinned third-party source that the
distribution builds for the ten userland profiles with the musl toolchain family
(decision 0001). `tools/ports.py` validates the descriptors, prints the build
order from `depends`, and will drive the per-port xmake build task once the
`<arch>-linux-musl` toolchains exist (SysToolchain plan, item 2).

Descriptor fields:

| Field | Meaning |
| --- | --- |
| `name`, `version` | Upstream identity |
| `archive`, `sha256` | Pinned source archive and its SHA-256; a port without a hash is `planned` only |
| `license` | SPDX identifier; `review` means the licence decision record is still pending |
| `depends` | Ports that must be built first |
| `profiles` | Architecture profiles the port is qualified for; `[]` until the first guest run |
| `state` | `planned`, `builds`, `executes` (hosted vs guest execution are recorded separately in the ledger) |
| `build` | `{"system": "configure"|"make"|"xmake", "configure_args": [...]}` |

A port's `state` is never advanced by a successful build alone; `executes` needs
guest execution evidence in ObfuscationEvidence.
