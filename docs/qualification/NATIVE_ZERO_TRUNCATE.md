# Linked-file zero-truncate user fixture

`tests/musl/zero_truncate.c` is a prepared userspace acceptance fixture. Its host
reference run passes; execution against the new Kernel mechanism is pending.
It does not enable mounted mutation or supply a recovery implementation.

The native first role uses argv[0] `/init`, creates the previously absent
`/home/zero-truncate.txt` as uid/gid 1000, and leaves the final document for
inspection and a later boot. Creation is exclusive. A failed run preserves its
file and must not be resumed as a fresh first role.

The first role exercises descriptor ftruncate, O_TRUNC open and pathname truncate.
It checks that each empties the live inode without changing its inode/device,
permissions, owner or link identity. Independent offsets remain independent;
dup descriptions retain their shared offset. Existing descriptors observe EOF
and remain usable. A readonly descriptor and a negative length are rejected
without changing file size. Each empty-file rewrite checks a different write
route, including a positioned write and a normal write from a retained offset,
with exact zero-filled gaps and exact content after close/reopen.

The native restart role uses argv[0] `/./init` and performs only read/reopen checks
against the retained final document. It validates its 137-byte zero prefix,
English payload, permissions, owner, links, size and EOF. It does not claim
descriptor identity or offset continuity across boots. Both roles use bounded
transfer attempts and explicit completion/failure markers.

Build the static-musl fixture through xmake with exact supplied arguments:

```sh
xmake musl-zero-truncate-probe --arch=ARCH --musl-build=DIR \
  --toolchain=DIR --out=NEW_DIR
```

The task uses the explicit source and bootstrap linker script, validates the musl
sysroot and architecture, and records compiler/linker/ELF provenance through the
existing probe builder. It does not execute or package the ELF. Preserve all ten
architecture profiles; a built ELF is not a qualified user ABI port. The actual
guest lane must additionally bind the architecture/mode-specific exported Kernel
SDK, installed probe ELF, rootfs and mounted provider. The OS never builds Kernel
sources.

A separate host reference task checks the C fixture against the host filesystem:

```sh
xmake zero-truncate-fixture-reference --out=NEW_DIR --host-cc=/usr/bin/cc
```

It creates a new isolated directory, compiles a retained source copy with warnings
as errors, and runs first/restart roles with an explicit scratch pathname. Its
result is host filesystem execution, not Kernel, hardware, journal or desktop
acceptance. Artifact hashes and the extra exclusive-create/invalid-role refusals
are retained in
`build/prototypes/sdk53-zero-truncate-fixture-reference-v1/root-readback-attempt-01`.

Before the native gate, require the distinct transaction witness and replay,
allocated-empty first-data rewrite, both typed startup recovery routes, strict
final admission and the lifetime/counter/checksum controls. Native fault campaigns
must verify full-volume effects, inode allocation/generation/version and birth/
access timestamps from independently inspected media, peer files, every whole-home
mixture and interrupted recovery. The C fixture cannot inspect those private
on-disk facts or attest FLUSH durability. File-backed VM coherence, general shrink,
large/deep/multi-group files and full POSIX/ext4 remain separate required work.
