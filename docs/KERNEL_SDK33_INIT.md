# Kernel SDK33 designated init contract

The current distribution requires `abi_version=33` and
`native_init_profile=designated-pid1-adoption-v1` in each architecture- and
mode-specific Kernel SDK manifest. The Kernel module ABI constant is 33. The
producer checks its exported scheduler and module declarations before publishing
the SDK, and the OS validator rejects old, missing or conflicting contracts.
Artifact checksums, compiler version, architecture, mode and signal profile are
independently validated. ObfuscationOS builds only against the exported SDK.

The contract reserves common task ID 1 for the initial user program. A live
Linux-personality init adopts a departing Linux user's children. An unpublished,
completed or absent init leaves parent-zero reaping in force. The native signal
lifecycle rebinds live children's parent generation and thread, while completed
children remain waitable. SDK32 libraries and headers cannot be mixed with SDK33.

`tests/musl/native_init_adoption.c` is an executable guest, installed as `/init`
by `tools/qualify_native_init.py`. It validates PID 1, a live grandchild's
observed parent, wait-any wakeup and statuses, SIGCHLD delivery, and adoption of
an already completed grandchild. `tools/native_init_adoption_evidence.py` checks
the exact guest transcript and frame/entry-stack resource return. The runner
freezes OS source, hashes explicit SDK and musl artifacts, builds an SDK-only
consumer and a fresh ext4 image, boots QEMU, retains failures and rechecks inputs.

This is a bounded process-lifetime slice. It does not implement subreapers,
service supervision, durable restart policy, init-death recovery, SMP-safe
lifetime transitions, a production account/login stack or a completed desktop.
Host-model evidence, QEMU native execution, physical hardware and human desktop
acceptance remain separate claims.
