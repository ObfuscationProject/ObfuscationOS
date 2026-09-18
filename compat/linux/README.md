# Linux driver compatibility

Linux driver adaptation belongs to ObfuscationOS. It consumes the native driver
interfaces from an exported ObfuscationKernel SDK; the kernel does not depend on
this directory or on Linux headers.

`pci_model.hpp` and `pci_model.cpp` preserve the existing PCI adapter behavior as
a model. They use bounded buffers and native test primitives. They do not expose
the Linux C API, map hardware MMIO, deliver interrupts, or load Linux `.ko` code.
The regression test moved here with the adapter.

`abi_snapshot.hpp` and `abi_snapshot.cpp` own `LinuxAbiSnapshot`,
`LinuxStructLayout` and the bounded layout table in `obos::linux_compat`. They
record a selected Linux baseline, required/implemented symbol names and structure
layout notes. `coverage_x100()` counts only that manually recorded requirement
set; it is not a Linux release compatibility score. Snapshot creation, coverage,
duplicate handling and baseline reset are tested in
`tests/compat/linux_abi_snapshot_tests.cpp`, independently of the PCI model.

On an x86_64 Linux host, run both model suites against a matching exported SDK:

```sh
python3 tests/run_compat_tests.py --kernel-sdk=../ObfuscationKernel/build/sdk/x86_64/debug
```

A real compatibility backend must implement the scheduling, allocation,
IRQ/MMIO/DMA and memory-ordering semantics required by a selected Linux driver.
Keep the Linux-facing C adapter separate from native C++ implementation headers.
Choose one Linux source version and one device driver for the first port; do not
infer binary module compatibility from metadata parsing or model tests.
