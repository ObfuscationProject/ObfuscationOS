# Actual userland object-pressure qualification

`tools/qualify_object_pressure.py` freezes OS sources, admits explicit SDK33,
compiler, QEMU and musl manifests, and builds a fresh SDK-only consumer. It does
not read or build a Kernel checkout. It preserves inputs, compiler-emitted probe
headers, outputs, exact commands, serial and scratch ext4 images. A failed guest
or offline check cannot become an executed pass. Images are never host-mounted.

The real static-musl workload starts eight children, exercises shared page
quota pressure while poll waits use Kernel objects, checks page contents, unmaps
and reaps children, then checks mmap/poll reuse. The native pipeline runs before
and after pressure. Their actual final frame records establish a comparable
baseline: both the pressure exit and subsequent pipeline must return to the
same user-page and object-page counts, with zero pinned/pending pages. A
resident shell or supervisor object may remain allocated at that baseline; the
test requires a temporary increase during pressure and its full reclamation.
A boot-time frame record alone is not a comparable shell baseline after exec.
The shell may create one resident object after an early boot diagnostic; its
pre-pressure record then becomes the baseline for temporary object growth.

The command requires explicit paths and SHA256 values (see `run --help`). Use
`freeze --output PATH` first. Output directories must be new and outside the
mutable OS sources. All ten architectures and both SDK modes are admitted; each
row still needs the matching exported producer SDK and static musl mode. A
historical SDK23 result does not qualify an SDK33 row; each row needs its own
bounded guest and offline filesystem receipt.
The PPC guest uses the admitted `e500v2_v22` reference CPU with one serialized
TCG thread; the default ppce500 CPU does not establish the private CPU contract.

The serial decoder validates dynamic quotas and lifetime counters rather than
assuming a fixed total. Hosted admission/corruption tests are separate from the
actual userland result. This is bounded allocation/poll evidence, not pthread,
physical hardware, SMP, general isolation or full M1/M0-M12 completion.
