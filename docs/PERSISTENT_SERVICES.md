# Bounded boot-time service configuration

The static-musl production service manager reads `/etc/services.conf` before
launching children. It retains the existing bounded graph lifecycle: simple
exec readiness, inherited notify-pipe acknowledgement, oneshot successful exit,
generation-bound dependency retirement, bounded restart and reverse-order stop.
This is an OS policy extension; no Kernel ABI change is required.

```text
OK_SERVICE_MANIFEST 1
service console simple /bin/oksh -
```

The first line is mandatory. Records have exactly five fields separated by one
ASCII space: `service`, a unique name, `simple|notify|oneshot`, an absolute
executable path, and a comma-separated list of dependency names or `-`.
Dependencies can refer forward to later records. Blank lines and full-line
comments starting with `#` are allowed. Every line ends in LF. Names use ASCII
letters, digits, dash and underscore, have at most31 bytes and cannot equal `-`;
executable paths have at most95 bytes. At most eight services and4096 total
bytes are accepted. There is no shell evaluation, quoting, argument syntax,
live reload or credential policy in this version.

Unknown directives/modes/dependencies, duplicate names/edges, cycles, NUL,
non-ASCII/control bytes, excess fields and limits refuse the whole graph.
The parser owns its strings; the running graph binds pointers only to committed
storage. Failure publishes neither a partial manifest nor a partial graph.

The manager pins and checks root-owned `/etc`, then opens the final file with
NOFOLLOW, CLOEXEC and NONBLOCK. Root-controlled `/` and mounted-root authority
are trusted boot prerequisites. The file must be a root-owned regular file
without group/other write bits. Metadata changes, inconsistent size/EOF, I/O
and close failures refuse before any launch. A missing final `services.conf`
retains the default console; missing `/etc` or any present invalid/insecure file
does not fall back. Invalid configuration produces a `config-invalid` event.

Rootfs staging validates one immutable snapshot of `config/services.conf` before
manager admission or output replacement. Admission binds those same parsed bytes
to the sealed configuration digest; staging writes them without rereading the
source path, with mode0644. The existing ext4
rootfs normalization establishes guest uid/gid0 and `/etc` mode0755, independently
of host ownership. The production static-musl dependency seal uses profile
`bounded-boot-manifest-noargs-v2`, pins the parser/loader headers and default
config bytes, and rejects legacy fixed-graph seals and test-manager artifacts.

Hosted parser, loader, actor and packaging controls do not qualify guest
execution. Fresh exact SDK-only production builds and config-driven QEMU
workflows are separate gates. No full M7, authenticated service IPC, durable
configuration update, Internet networking, desktop or physical claim follows.
