# Kernel SDK32 designated init contract

This records the historical SDK32 boundary. Current builds require the
[SDK33 init contract](KERNEL_SDK33_INIT.md); this page does not authorize
mixing SDK32 artifacts into an SDK33 consumer.

This isolated successor requires `abi_version=32` and
`native_init_profile=designated-pid1-adoption-v1` in each architecture- and
mode-specific Kernel SDK manifest. The Kernel module ABI constant is 32. The
producer checks its exported scheduler and module declarations before publishing
the SDK, and the OS validator rejects old, missing or conflicting contracts.
Artifact checksums, compiler version, architecture, mode and ordinary signal
profile are independently validated. ObfuscationOS builds only against the
exported SDK; it does not compile Kernel source.

The contract reserves common task ID 1 for the initial user program. A live
Linux-personality init adopts a departing Linux user's children. An unpublished,
completed or absent init leaves parent-zero reaping in force. The native signal
lifecycle rebinds live children's parent generation and thread, while completed
children remain waitable. This version changes public scheduler and process
layouts, so SDK31 libraries and headers cannot be mixed with SDK32.

`tests/musl/native_init_adoption.c` is an executable guest, installed as `/init`
by `tools/qualify_native_init.py`. It validates PID 1, a live grandchild's
observed parent, wait-any wakeup and statuses, SIGCHLD delivery, and adoption of
an already completed grandchild. `tools/native_init_adoption_evidence.py` checks
the exact guest transcript and frame/entry-stack resource return. The runner
freezes OS source, hashes explicit SDK and musl artifacts, builds an SDK-only
consumer and a fresh ext4 image, boots QEMU, retains failures and rechecks inputs.

This is a bounded M7 process-lifetime slice. It does not implement subreapers,
service supervision, durable restart policy, init-death recovery, SMP-safe
lifetime transitions, a production account/login stack or a completed desktop.
Host-model evidence, QEMU native execution, physical hardware and human desktop
acceptance remain separate claims.
