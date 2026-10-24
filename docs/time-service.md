# Native time service

`timed` is an ObfuscationOS service consuming the exported Kernel SDK. It does
not change the kernel clock ABI or reduce the ten native architecture profiles.
The console login profile starts it with notification readiness; maintenance
continues to use its independent shell profile. `timed` requires an argument-free
launch by PID 1 with effective UID and GID zero and an exact
`OK_SERVICE_READY_FD` descriptor in the range 3 through 31. Readiness means the
checked local socket is listening. An unavailable realtime clock does not
prevent readiness.

`timectl status` prints a raw realtime sample, its errno when unavailable, a
separately sampled monotonic clock, the daemon PID, and `manual_updates`.
`timectl set SECONDS [NANOSECONDS]` calls the kernel realtime setter. Seconds
must be canonical decimal in `[0,8277292036)` and nanoseconds in `[0,1000000000)`;
omitted nanoseconds are zero. Kernel validation, including its current elapsed
monotonic lower bound, still applies. A kernel error is returned unchanged when
it is a valid errno.

`/run/timed.sock` is a root-owned mode 0666 UNIX stream socket in checked,
root-owned directories without group or other write permission. STATUS is
public. SET requires effective UID zero captured by `SO_PEERCRED`; a client
claim in a payload never supplies authority. Clients check the endpoint metadata
and root server credentials, and bind every non-error reply PID to that peer.
A stale socket is reclaimed only after ECONNREFUSED and unchanged checked
metadata. Live, full-backlog, unsafe or replaced endpoints are refused.

The versioned protocol accepts exactly `OKT1 STATUS\n` or
`OKT1 SET <seconds> <nanoseconds>\n`. LF is mandatory. Embedded controls,
noncanonical numbers, extra frames, and buffered suffixes visible before
dispatch are refused. One connection carries one request. Replies end in
`\nEND\n`, and clients require EOF with no suffix. Both sides use one fixed
1000 ms monotonic deadline, covering fragments, dispatch and responses; progress
never renews it. Later arriving bytes cannot revoke an already completed setter.

`manual_updates` counts successful setter syscalls in this daemon process only.
It increments before preparing the response, so a lost response can leave a
successful clock change. Retrying is another request. Restart resets the count;
direct clock setters bypass it. The value is not a kernel generation, UTC
provenance, RTC state or persistent history. The service provides no NTP,
accuracy guarantee, RTC writes, time persistence or power-loss guarantee.
Counter exhaustion is rejected before calling the setter. A transport failure
does not prove that SET failed; clients should query current status before
deciding to retry. Successful replies do not wait for logd or persistent I/O.
Manual epochs are not saved and reapplied on the next boot, when they would be
stale. A boot without an admitted hardware source may again report realtime
unavailable. This bounded manual service does not close M7.

Hosted actual-source tests in `tests/time_service_tests.c` inject syscall faults,
check descriptor cleanup, strict framing, peer authorization, raw clock errors,
lost responses and fixed deadline boundaries under ASan/UBSan. They are separate
from native guest execution and physical reference-machine qualification.
