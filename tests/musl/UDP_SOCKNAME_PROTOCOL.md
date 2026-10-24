# Explicit public-libc UDP name fixture

The nondefault `musl-udp-sockname` fixture uses public musl calls in
`udp_sockname.c` and a native fork/exec/wait parent. The original UDP fixture,
default applications and normal rootfs remain available unchanged.

The six ordered phases are unbound, fixed, capacity, duplicate, bind-zero and
implicit. Full queries verify AF_INET, actual length 16, exact endpoint, zero
sockaddr padding and poisoned storage guards. Capacity checks cover 0, 1, 2, 3,
7, 15, 16, 17 and INT_MAX, plus a null address at capacity zero. Duplication is
mandatory: the alias retains the endpoint after original close and actual I/O;
last-close permits rebind of the fixed port. Closed queries require EBADF and
unchanged output before any descriptor reuse.

Nine strictly ordered `MUSL_UDP_NAME stage=name` reports identify the queried
address and port. Wildcard and implicit sockets report address ANY, while their
packets use the configured local IPv4 address. No ephemeral allocator value is
prescribed. The observer compares each reported nonzero dynamic port with the
complete, checksum-validated actual guest wire frame before sending its ACK.
Serial and network arrival order are independent. Failed gates publish no
accepted dynamic port and send no ACK bytes.

The exact guest wire events are one ARP reply, fixed and duplicate UDP, two
bind-zero UDP and two implicit UDP. UDP identifiers are 0x9000 through 0x9005.
Missing/extra/malformed/partial records or frames, unstable ports, false reports,
wrong wildcard addresses and predecessor pass logs refuse completion. Parsed
reports retained in receipts carry their exact complete serial line indexes.

Build the explicit child with `xmake musl-udp-sockname-probe`, supplying an
audited musl build and toolchain plus a fresh output directory and actual
`--capture-compile-dependencies`. All four supplied musl profiles remain
supported. Configure the OS with an explicit matching Kernel SDK and the four
pins `musl_udp_sockname_child_build`, `musl_udp_sockname_child_manifest_sha256`,
`musl_udp_sockname_musl_build` and `musl_udp_sockname_musl_manifest_sha256`.
`musl-udp-sockname-fixture-image` packages the child and native parent into
`fixtures/musl-udp-sockname`, validates the exported SDK and links only OS code
against its artifacts. The shared packager's closed `--fixture=udp-sockname`
selector requires the new source/dependency manifest and exact archive path
`/bin/musl-udp-sockname-probe`; omitted or explicit `udp` retains the predecessor.

`musl-udp-sockname-nic-test` requires explicit architecture, mode, fresh SDK,
image, staged child and new output directory. Initial execution qualification
is x86_64 using actual QEMU guest instructions, Linux-personality traps and the
external polling modern Virtio PCI driver. Normal Kernel diagnostics and a
working explicit Virtio RNG device precede Linux exec. The receipt retains raw
serial and every transport byte on failure and success, bounded quiet/drain
intervals and actual QEMU cleanup. Endpoint equality is distinct from the
separately admitted image/SDK producing command chain.

The observer and packaging Python tests are hosted synthetic controls. The
separate Linux/glibc reference of the C child is not target musl or guest
execution. Source composition and ELF/archive inspection do not qualify that
execution. Fresh SDK selection, actual guest admission, other architecture
execution, IRQ/SMP, physical hardware, general networking, manual desktop and
full M0-M12 remain separate gates.
