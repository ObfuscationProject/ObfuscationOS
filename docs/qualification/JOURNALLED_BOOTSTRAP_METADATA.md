# Journalled bootstrap metadata

The selected journalled production image uses
`journalled-root-owned-bootstrap-v1`. Host UID, GID and umask are
staging details; `mke2fs -d` must not turn them into guest bootstrap policy.

The image root, `/etc`, bootstrap service manifests and all ordinary paths
are owned by guest root. Directories use 0755, regular files use
0644 or 0755 according to their intended executable bit, and `/tmp` uses 01777.
`/lost+found` uses 0700. The `/home` directory and its descendants are owned by
guest root; `/home` uses 0700, matching the existing nonjournalled bootstrap
policy and the production default archive root credentials. An unprivileged
login session requires its own explicit distribution policy and remains
separate from this root bootstrap workflow. Literal symlink targets are retained
with symlink mode 0777. A symlink may
not replace trusted `/etc`. Names containing debugfs command delimiters are
refused before metadata commands run. The ordinary host work-directory path must
also fit the explicit safe debugfs operand alphabet; paths requiring quoting are
refused before backend use.

`journalled_rootfs_policy.py` inventories the explicit staged root, verifies
actual inode types and rejects aliases. It applies owner and permission fields
through debugfs/libext2fs, which writes metadata checksums for the 1 KiB
`metadata_csum` image. The packager checks the readback metadata and every regular
file's bytes, then runs `e2fsck -fn` before Linux journal activation. The existing
postactivation checks remain required. The packaging manifest records this
policy and its source hash.

The separate nonjournalled 4 KiB native bootstrap image retains its existing
root-only rescue policy. Its raw metadata normalizer cannot be applied to the
journalled checksum profile. Host packaging checks are separate from native
bootstrap, userland and power-loss execution evidence.

The normalizer also checks that each pathname retains its original inode number.
Before writing metadata it compares literal symlink target bytes against the host
staging link, then compares them again after normalization. This includes fast
inline links and one-block extent or direct-block links up to 1 KiB. It never
follows dangling, relative or absolute link targets. Other symlink storage is
rejected explicitly. The bounded raw reader verifies profile geometry and inode
allocation; the packaging caller still performs the mandatory full e2fsck check.
Host tests distinguish actual checksum-aware images from an injected namespace
replacement observation. These checks do not establish native symlink execution.
