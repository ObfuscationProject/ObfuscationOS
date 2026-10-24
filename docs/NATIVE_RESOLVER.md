# Native local resolver

This OS-only candidate supplies ordinary `resolved` and `resolvectl` programs
using an explicitly selected installed Kernel SDK, ABI69/UAPI0.11.0. All ten
native architecture profiles remain selected by the existing xmake toolchain
configuration. Kernel source is not an OS build input.

The selected native console-login service manifest retains console, logd and
timed and adds `service resolved notify /bin/resolved - 0 0`. Ordinary PID1
starts the root service and receives its readiness byte only after the complete
hosts snapshot and checked AF_UNIX listener are ready. `resolvectl` is an
ordinary client, without a service record. `mountctl` remains independent.

## Commands and configuration

```text
resolvectl status
resolvectl lookup localhost
resolvectl lookup example.test
resolvectl lookup 192.0.2.1
```

`status` describes the daemon PID and loaded alias/byte counts. A lookup returns
a normalized name, dotted-decimal IPv4 address and numeric/hosts source, or an
explicit error. The initial `/etc/hosts` seed is:

```text
127.0.0.1 localhost
```

An administrator can edit `/etc/hosts` and run `service-ctl restart resolved`
to load the new snapshot. The daemon does not reload during a query. The hosts
file is mutable configuration, so its content hash is excluded from executable
product admission. A valid bounded edit does not require executable rehashing
or account reenrollment. Old console product profiles are refused without
modifying their images, sidecars or account state.

The hosts parser accepts at most 4096 bytes and 64 distinct normalized aliases.
Input names are ASCII, at most 253 bytes including an optional trailing dot,
with labels of 1–63 alphanumeric/hyphen characters and alphanumeric label edges.
ASCII case folds to lowercase; one
trailing dot is normalized away. Repeated aliases with the same address are
idempotent; conflicting addresses reject the whole startup snapshot. Each line
ends in LF; spaces, tabs and `#` comments are allowed. CR, NUL, other controls
and non-ASCII bytes are rejected. IPv4 literals use exactly four decimal octets,
0–255, with no leading zero except the single digit `0`. Malformed all-digit
or dotted-digit inputs fail rather than becoming hostname queries. All aliases
consisting only of digits and dots are refused in hosts records, including
canonical IPv4 literals; numeric lookups use their separate literal path.

An empty hosts file is valid and permits numeric-only lookups. A missing,
malformed or unsafe hosts file rejects daemon readiness. No partial table is
published after an invalid record, capacity overflow or conflict. The daemon
owns the bounded table and parsing workspace in static storage. The snapshot
detects descriptor metadata/size changes while reading and checks the final
named `/etc/hosts` inode against that descriptor before publication. Observable
replacement, unlink and symlink changes are refused. It makes no atomicity
claim for concurrent same-size administrator edits.

## File and transport admission

Packaging snapshots a bounded regular non-symlink `config/hosts` before changing
an existing staged root. Input ownership must be root or the packaging user;
world/group writable input and multiple hard links are rejected. Guest owners
are normalized separately. Staging writes `/etc/hosts` as 0644 under root-owned
0755 `/etc`, independent of host umask or source special bits. Archive and ext4
ownership policy remain distinct from the host staging directory owner.

The selected console product binds both resolver executable hashes and the
exact notify service configuration. Offline ext4 admission checks `/etc/hosts`
as a root:root regular 0644 inode with one link and at most 4096 bytes. It admits
protected metadata and size; the actual daemon owns full hosts syntax checks
and refuses readiness for invalid data. Administrator-edited content is not
compared with the original seed or included in immutable executable hashes.
Existing accounts, enrollment policy and mutable log recovery remain unchanged.

Public queries use the versioned bounded protocol on `/run/resolved.sock`,
with checked endpoint and peer identities. The root service uses the existing
root-owned `/run` directory policy and a public 0666 socket. Nonblocking I/O
uses one absolute monotonic 1000 ms deadline per request/reply, including partial
send/receive handling and checked EOF. Startup failure precedes readiness.

## Evidence and scope

Hosted parser/transport controls, actual offline ext4 admission, native
architecture compilation and later native guest execution are separate evidence
lanes. Packaging tests use powerless binary fixtures; they do not execute a
native resolver or perform Linux journal activation. No DNS fallback, NTP,
new networking/Kernel interfaces or libc-wide `getaddrinfo` behavior is added.
All full M0–M12 gates remain open; physical M11 and manual desktop M12 acceptance
remain deferred. Production ext4 stays `<1,9>` without paired I/O.

The legacy flat SimpleFS format retains its 32-entry limit. The complete staged
root already exceeded that bound before this resolver slice. Full native
products use the boot archive/ext4 lanes; the flat-format archive control uses
an explicit bounded subset and checks overflow refusal without a format change.
