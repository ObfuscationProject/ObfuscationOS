# Bounded ordinary-account registry

This candidate supplies ordinary-account metadata persistence for the serialized
native console-login leader. It preserves the existing first-administrator
`accounts.db` version 1 bytes, enrollment and password-rotation policy. It does
not itself authenticate, create home directories, change process credentials or
start a session. Hosted controls are separate from native execution and disk
durability evidence.

The independent `/etc/users.db` version 1 registry contains at most sixteen
ordinary users in at most 4096 file bytes. Each record has a canonical existing
account name, equal UID/GID in `[1000, 4294967294]`, sixteen salt bytes and
thirty-two PBKDF2-HMAC-SHA256 verifier bytes. The shared work factor is exactly
600000. Records are strictly ordered by UID; names and IDs are unique. The
actual administrator name is excluded by operation admission. Home paths are
always derived as `/home/NAME`; database bytes cannot select another home.

The canonical wire format uses lowercase hexadecimal, decimal integers without
leading zeros and exact ASCII separators and line endings:

```text
OKUSERS 1
kdf pbkdf2-hmac-sha256
rounds 600000
count 1
user alice 1000 1000 SALT_HEX_32_CHARACTERS VERIFIER_HEX_64_CHARACTERS
```

The placeholders above describe the two hexadecimal fields, not accepted
literal database content. `count 0` followed by a newline is an explicitly
empty database. Only absence of both database and staging also means empty;
empty, truncated, malformed or unsupported existing files fail closed.

`ok_users_store_open(store, administrator)` retains the observed database and
selects a complete `.users.next` only if it adds exactly one user or rotates
exactly one existing principal's credentials. All unrelated records must be
identical. Deletions, identity changes, multiple additions/rotations and identical
staging fail. `recovery_kind` and `change_index` identify the pending operation.
Opening never publishes or removes staging. Before `recover`, the caller must
authenticate the administrator for an addition, or the selected staged user with
the new credentials for a rotation. Before `add`/`stage_add`/`rotate`, the caller
must authenticate the administrator/administrator/current selected user respectively.

The console workflow uses `stage_add`, which synchronizes the complete successor
and selects it in memory without renaming `users.db`. The caller checks that the
home name is absent before staging. After staging, it prepares and synchronizes
that exact principal's home, then calls `recover` to publish. On restart, an ADD
requires administrator authentication and completion of the matching home before
publication. A root-owned 0700 directory or an already exact-owned 0700 directory
can resume this step; unrelated objects fail closed. The convenience `add` API
requires the caller to have already prepared and persisted the home.

Both files must be root:root, mode 0600, regular, single-link files beneath
checked root-owned directories. Symlinks, FIFOs, wrong metadata and unsupported
persistent synchronization fail. Mutation checks the retained predecessor,
creates staging exclusively, writes the full canonical successor, synchronizes
the file, closes it and synchronizes the containing directory. Publication
rechecks staging and predecessor, renames staging, synchronizes the directory
and verifies the resulting database. A possible post-creation failure returns
`OK_USERS_STORE_UNCERTAIN`; every failed transaction poisons that store so the
caller must close/reopen and inspect, never retry blindly. A partial file remains
for refusal; this API does not delete or reseed it. These ordering rules do not
claim arbitrary power-loss durability.

Keep `struct ok_users_store` in static storage: its explicit registry/read
workspace is 8392 bytes on the checked x86_64 ABI. Parsing uses one temporary
record and name spans instead of nested registry copies. Close clears the
workspace and salts/verifiers. The caller owns hidden password input, trusted
entropy, plaintext clearing, home publication and final credential readback.
Only one console-login leader may write; other root writers and concurrent
changes are outside this API's contract.

Run `python3 tools/test_native_users.py` for actual-source hosted parser and
store controls, including independent wire fixtures, sixteen-user preservation,
strict recovery successors and syscall-failure boundaries. The test namespace
and ownership/sync seams are substitutes and establish no guest execution.

The login interface exposes `:useradd` for administrator-authenticated creation
and `:passwd` for the selected account's password rotation. Ordinary sessions
remain unavailable during administrator activation/recovery or a staged ADD.
A staged ROTATE can be published only by authenticating its selected new
credentials; unrelated successful logins leave it pending. The UID allocator
starts at 1000 and skips all registry and configured service UID/GID values.
The home helper keeps `/home` root-owned, upgrades a legacy 0700 parent to 0755,
and creates private 0700 children. Session entry closes private stores and parent
directory descriptors before setting all three GIDs, then all three UIDs. It
verifies all six values, enters the retained checked home descriptor, sets umask
0077 and executes `/bin/oksh` with fixed HOME/PATH/USER/LOGNAME and console epoch.
These are implementation contracts; native campaign evidence remains a separate
gate.

Journalled packaging imports bootstrap regular files densely so zero ELF
alignment padding does not grow an external extent tree beyond the native
checked bootstrap reader's supported profile. Only the private packaging copy
receives temporary filler bytes before `mke2fs -d`; `debugfs zap_block -f`
restores exactly the original zero blocks before metadata normalization,
byte-for-byte dump admission, Linux journal activation and read-only fsck.
Before publication, every regular file must have complete initialized inline
extents, exact size and sector accounting, and bounded nonoverlapping physical
ranges. The final read-only fsck checks filesystem checksums and allocation.
The manifest records both the explicit dense-file plan and the final inline
admission facts. Packaging also exclusively creates the private activation marker
and refuses existing files, directories and symlinks at that name. This does
not add external extent-tree support or change executable bytes.

`whoami` reads the effective UID. It prints `root` for UID 0 and an explicit
`uidN` value for other identities; it does not invent a fixed name for UID 1000
or trust USER/LOGNAME as an account authority. Public name lookup is not
provided by the protected password registry.
