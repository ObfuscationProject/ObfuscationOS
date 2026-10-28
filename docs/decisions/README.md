# Decision records

Short, numbered records of architecture decisions that are not derivable from the
code. Each record states the decision, why, and what it supersedes. A record is
changed only by a later record that supersedes it.

| ID | Decision |
| --- | --- |
| [0001](0001-musl-primary-userland.md) | musl over the Linux personality is the primary userland; okcrt shrinks to init/rescue |
| [0002](0002-desktop-moves-to-user-space.md) | The prelinked kernel-space desktop is frozen; the desktop moves to user-space Wayland |
| [0003](0003-evidence-repository.md) | Qualification evidence lives in ObfuscationEvidence, never in product working trees |
| [0004](0004-busybox-shell-and-utilities.md) | BusyBox 1.37.0 supplies the musl `sh` and utility set; dash and toybox are not ported |
