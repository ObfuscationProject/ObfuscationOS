import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from test_musl_userland import validate_execution, validate_file_private, failure_line

BOOT = b"OK_MUSL_NATIVE scope=hardware libc=musl-1.2.5 startup=pass tls=pass errno=pass clock=pass\n"
PARENT = b"OK_MUSL_PARENT scope=hardware native=pass exec=pass wait=pass exit=pass repeat=pass\n"
FILES = b"OK_MUSL_FILES scope=hardware openat=pass flags=pass append=pass vector_io=pass symlink=pass limits=pass sync=pass\n"
HEAP = b"OK_MUSL_HEAP malloc=pass calloc=pass realloc=pass alignment=pass reuse=pass\n"
VM = b"OK_MUSL_HEAP_VM brk=pass fixed=pass pressure=pass reclaim=pass\n"
PRIVATE = (b"OK_MUSL_FILE_PRIVATE scope=hardware offset=pass short_length=pass "
           b"tail_zero=pass errno=pass close=pass unlink=pass private_write=pass fork=pass syscall=")

class MuslEvidenceTests(unittest.TestCase):
    def test_file_private_requires_one_exact_record_per_native_execution(self):
        mmap2 = {"i386", "arm32", "rv32", "mips", "ppc"}
        for arch in ("x86_64", "i386", "aarch64", "arm32", "rv64", "rv32",
                     "loongarch64", "mips", "mips64", "ppc"):
            record = PRIVATE + (b"mmap2" if arch in mmap2 else b"mmap") + b"\r\n"
            with self.subTest(arch=arch):
                validate_file_private((BOOT + record) * 2 + PARENT, arch)

    def test_file_private_rejects_wrapped_unknown_duplicate_and_unterminated(self):
        record = PRIVATE + b"mmap\n"
        good = (BOOT + record) * 2 + PARENT
        bad = (
            good.replace(record, b"console: " + record, 1),
            good.replace(record, PRIVATE + b"mmap3\n", 1),
            good + record,
            BOOT + record * 2 + BOOT + PARENT,
            BOOT + record + BOOT + PRIVATE + b"mmap",
            good.replace(record, PRIVATE + b"mmap\n" + PRIVATE + b"mmap\n", 1),
        )
        for serial in bad:
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_file_private(serial, "x86_64")
        with self.assertRaises(ValueError):
            validate_file_private(good, "unknown")
        with self.assertRaises(RuntimeError):
            validate_file_private(good, "i386")

    def test_files_do_not_qualify_heap_or_mapped_vm(self):
        for extra in (b"", HEAP * 2, VM * 2, HEAP + VM, HEAP * 2 + VM):
            with self.subTest(extra=extra), self.assertRaisesRegex(RuntimeError, "heap and VM"):
                validate_execution((BOOT + FILES) * 2 + extra + PARENT, True, True)
        validate_execution((BOOT + FILES + HEAP + VM) * 2 + PARENT, True, True)

    def test_startup_does_not_qualify_files(self):
        validate_execution(BOOT * 2 + PARENT)
        with self.assertRaisesRegex(RuntimeError, "file and sync"):
            validate_execution(BOOT * 2 + PARENT, True)
    def test_each_run_needs_file_and_sync_checks(self):
        for segment in (BOOT * 2 + FILES + PARENT, BOOT * 2 + FILES.replace(b" sync=pass", b"") * 2 + PARENT):
            with self.subTest(segment=segment), self.assertRaises(RuntimeError):
                validate_execution(segment, True)
        validate_execution((BOOT + FILES) * 2 + PARENT, True)
    def test_file_markers_do_not_replace_parent_status(self):
        with self.assertRaisesRegex(RuntimeError, "native-parent"):
            validate_execution((BOOT + FILES) * 2, True)

    def test_failure_waits_for_complete_diagnostic(self):
        self.assertIsNone(failure_line(b"MUSL_CHECK failed:"))
        self.assertEqual(failure_line(b"MUSL_CHECK failed: child status=9472\r\n"),
                         "MUSL_CHECK failed: child status=9472")

HEAP = b"OK_MUSL_HEAP malloc=pass calloc=pass realloc=pass alignment=pass reuse=pass\n"
HEAP_VM = b"OK_MUSL_HEAP_VM brk=pass fixed=pass pressure=pass reclaim=pass\n"
PROCESS = b"OK_MUSL_PROCESS identity=pass fork=pass isolation=pass exec=pass wait=pass shared_fd=pass\n"
CAPACITY = b"OK_MUSL_PROCESS_CAPACITY bounded=pass reap=pass retry=pass\n"
LIMIT = b"OK_MUSL_PROCESS_LIMIT errno=EAGAIN children=16\n"

class MuslProcessEvidenceTests(unittest.TestCase):
    def test_combined_process_evidence(self):
        run = BOOT + FILES + HEAP + HEAP_VM + PROCESS + CAPACITY + LIMIT
        validate_execution(run * 2 + PARENT, require_process=True)
        validate_execution(run.replace(b"errno=EAGAIN", b"errno=ENOMEM") * 2 + PARENT, require_process=True)
        for marker in (HEAP, HEAP_VM, PROCESS, CAPACITY, LIMIT):
            with self.subTest(marker=marker), self.assertRaises(RuntimeError):
                validate_execution(run + run.replace(marker, b"") + PARENT, require_process=True)
    def test_process_limits_are_bounded_and_explicit(self):
        run = BOOT + FILES + HEAP + HEAP_VM + PROCESS + CAPACITY + LIMIT
        for invalid in (b"children=0", b"children=64", b"children=-1", b"children=abc"):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                validate_execution(run.replace(b"children=16", invalid) * 2 + PARENT, require_process=True)
        with self.assertRaises(RuntimeError):
            validate_execution(run.replace(b"errno=EAGAIN", b"errno=EOVERFLOW") * 2 + PARENT, require_process=True)


class MuslPathEvidenceTests(unittest.TestCase):
    def test_two_complete_path_runs_and_prior_gates(self):
        paths = b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n"
        run = BOOT + FILES + HEAP + HEAP_VM + PROCESS + CAPACITY + LIMIT + paths
        validate_execution(run * 2 + PARENT, require_paths=True)
        validate_execution((run * 2 + PARENT).replace(b"\n", b"\r\n"), require_paths=True)
        for damaged in (run + run.replace(paths, b"") + PARENT,
                        run * 2 + PARENT + paths,
                        run + run.replace(paths, paths.replace(b" boundaries=pass", b"")) + PARENT,
                        run * 2 + PARENT + paths[:-1],
                        run.replace(PROCESS, b"") * 2 + PARENT):
            with self.subTest(damaged=damaged), self.assertRaises(RuntimeError):
                validate_execution(damaged, require_paths=True)

class MuslDescriptorEvidenceTests(unittest.TestCase):
    def test_two_complete_descriptor_runs_and_prior_gates(self):
        paths = b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n"
        fds = b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n"
        run = BOOT + FILES + HEAP + HEAP_VM + PROCESS + CAPACITY + LIMIT + paths + fds
        validate_execution(run * 2 + PARENT, require_fds=True)
        validate_execution((run * 2 + PARENT).replace(b"\n", b"\r\n"), require_fds=True)
        for damaged in (run + run.replace(fds, b"") + PARENT,
                        run * 2 + PARENT + fds,
                        run + run.replace(fds, fds.replace(b" exec=pass", b"")) + PARENT,
                        run * 2 + PARENT + fds[:-1],
                        run.replace(paths, b"") * 2 + PARENT,
                        run.replace(PROCESS, b"") * 2 + PARENT):
            with self.subTest(damaged=damaged), self.assertRaises(RuntimeError):
                validate_execution(damaged, require_fds=True)

class MuslSeekEvidenceTests(unittest.TestCase):
    def test_two_complete_seek_runs_and_prior_gates(self):
        paths = b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n"
        fds = b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n"
        seek = b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n"
        run = BOOT + FILES + HEAP + HEAP_VM + PROCESS + CAPACITY + LIMIT + paths + fds + seek
        validate_execution(run * 2 + PARENT, require_seek=True)
        validate_execution((run * 2 + PARENT).replace(b"\n", b"\r\n"), require_seek=True)
        for damaged in (run + run.replace(seek, b"") + PARENT,
                        run * 2 + PARENT + seek,
                        run + run.replace(seek, seek.replace(b" bounded=pass", b"")) + PARENT,
                        run * 2 + PARENT + seek[:-1],
                        run.replace(fds, b"") * 2 + PARENT,
                        run.replace(PROCESS, b"") * 2 + PARENT):
            with self.subTest(damaged=damaged), self.assertRaises(RuntimeError):
                validate_execution(damaged, require_seek=True)

class MuslPipeEvidenceTests(unittest.TestCase):
    def test_two_complete_pipe_runs_and_all_prior_gates(self):
        paths = b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n"
        fds = b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n"
        pipes = b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n"
        run = BOOT + FILES + HEAP + HEAP_VM + PROCESS + CAPACITY + LIMIT + paths + fds + pipes
        validate_execution(run * 2 + PARENT, require_pipes=True)
        validate_execution((run * 2 + PARENT).replace(b"\n", b"\r\n"), require_pipes=True)
        damaged = [run + run.replace(pipes,b"") + PARENT, run * 2 + PARENT + pipes,
                   run * 2 + PARENT + pipes[:-1],
                   run.replace(b"epipe=errno-only",b"signals=pass") * 2 + PARENT]
        damaged += [run.replace(marker,b"") * 2 + PARENT for marker in (BOOT,FILES,HEAP,HEAP_VM,PROCESS,CAPACITY,LIMIT,paths,fds)]
        for serial in damaged:
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_execution(serial, require_pipes=True)

class MuslSleepEvidenceTests(unittest.TestCase):
    def test_deadline_receipts_preserve_all_prior_gates(self):
        paths = b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n"
        fds = b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n"
        pipes = b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n"
        seek = b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n"
        sleep = b"OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass\n"
        run = BOOT + FILES + HEAP + HEAP_VM + PROCESS + CAPACITY + LIMIT + paths + fds + pipes + seek + sleep
        validate_execution(run * 2 + PARENT, require_sleep=True)
        validate_execution((run * 2 + PARENT).replace(b"\n", b"\r\n"), require_sleep=True)
        for serial in (run + run.replace(sleep, b"") + PARENT,
                       run * 2 + PARENT + sleep,
                       run + run.replace(sleep, sleep[:-1]) + PARENT,
                       run.replace(seek, b"") * 2 + PARENT,
                       run.replace(pipes, b"") * 2 + PARENT,
                       run.replace(sleep, sleep.replace(b"peer=pass", b"peer=fail")) * 2 + PARENT):
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_execution(serial, require_sleep=True)

class MuslPollEvidenceTests(unittest.TestCase):
    def test_poll_receipts_require_both_complete_runs_and_prior_suites(self):
        paths = b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n"
        fds = b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n"
        pipes = b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n"
        seek = b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n"
        sleep = b"OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass\n"
        poll = b"OK_MUSL_POLL poll=pass ppoll=pass layouts=pass timeout=pass wake=pass eof=pass errors=pass mask=unsupported\n"
        run = BOOT + FILES + HEAP + HEAP_VM + PROCESS + CAPACITY + LIMIT + paths + fds + pipes + seek + sleep + poll
        validate_execution(run * 2 + PARENT, require_poll=True)
        validate_execution((run * 2 + PARENT).replace(b"\n", b"\r\n"), require_poll=True)
        damaged = [run + run.replace(poll, b"") + PARENT, run * 2 + PARENT + poll,
                   run + run.replace(poll, poll[:-1]) + PARENT,
                   run.replace(b"mask=unsupported", b"signals=pass") * 2 + PARENT]
        damaged += [run.replace(marker, b"") * 2 + PARENT for marker in
                    (BOOT, FILES, HEAP, HEAP_VM, PROCESS, CAPACITY, LIMIT, paths, fds, pipes, seek, sleep)]
        for serial in damaged:
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_execution(serial, require_poll=True)

class MuslOpenEvidenceTests(unittest.TestCase):
    def test_open_receipts_require_complete_cumulative_runs(self):
        markers = [BOOT, FILES, HEAP, HEAP_VM, PROCESS, CAPACITY, LIMIT,
            b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n",
            b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n",
            b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n",
            b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n",
            b"OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass\n",
            b"OK_MUSL_POLL poll=pass ppoll=pass layouts=pass timeout=pass wake=pass eof=pass errors=pass mask=unsupported\n",
            b"OK_MUSL_OPEN open=pass creat=pass flags=pass cwd=pass copies=pass pressure=pass legacy=where-present\n"]
        run=b"".join(markers);marker=markers[-1]
        validate_execution(run*2+PARENT,require_open=True)
        validate_execution((run*2+PARENT).replace(b"\n",b"\r\n"),require_open=True)
        damaged=[run*2+PARENT+marker,run+run.replace(marker,marker[:-1])+PARENT,
                 run.replace(b"legacy=where-present",b"legacy=universal")*2+PARENT]
        damaged += [run+run.replace(item,b"")+PARENT for item in markers]
        for serial in damaged:
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_execution(serial,require_open=True)

class MuslPositionalEvidenceTests(unittest.TestCase):
    def test_positional_receipts_require_complete_cumulative_runs(self):
        markers = [BOOT, FILES, HEAP, HEAP_VM, PROCESS, CAPACITY, LIMIT,
            b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n",
            b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n",
            b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n",
            b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n",
            b"OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass\n",
            b"OK_MUSL_POLL poll=pass ppoll=pass layouts=pass timeout=pass wake=pass eof=pass errors=pass mask=unsupported\n",
            b"OK_MUSL_OPEN open=pass creat=pass flags=pass cwd=pass copies=pass pressure=pass legacy=where-present\n",
            b"OK_MUSL_POSITIONAL pread=pass pwrite=pass offsets=pass shared=pass append=linux copies=pass bounded=pass\n"]
        run=b"".join(markers);marker=markers[-1]
        validate_execution(run*2+PARENT,require_positional=True)
        validate_execution((run*2+PARENT).replace(b"\n",b"\r\n"),require_positional=True)
        damaged=[run*2+PARENT+marker,run+run.replace(marker,marker[:-1])+PARENT,
                 run.replace(b"append=linux",b"append=native")*2+PARENT]
        damaged += [run+run.replace(item,b"")+PARENT for item in markers]
        for serial in damaged:
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_execution(serial,require_positional=True)
class MuslSelectEvidenceTests(unittest.TestCase):
    def test_select_receipts_require_complete_cumulative_runs(self):
        markers = [BOOT, FILES, HEAP, HEAP_VM, PROCESS, CAPACITY, LIMIT,
            b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n",
            b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n",
            b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n",
            b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n",
            b"OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass\n",
            b"OK_MUSL_POLL poll=pass ppoll=pass layouts=pass timeout=pass wake=pass eof=pass errors=pass mask=unsupported\n",
            b"OK_MUSL_OPEN open=pass creat=pass flags=pass cwd=pass copies=pass pressure=pass legacy=where-present\n",
            b"OK_MUSL_POSITIONAL pread=pass pwrite=pass offsets=pass shared=pass append=linux copies=pass bounded=pass\n",
            b"OK_MUSL_SELECT select=pass pselect=pass layouts=pass timeout=pass wake=pass sets=pass errors=pass mask=unsupported\n"]
        run=b"".join(markers);marker=markers[-1]
        validate_execution(run*2+PARENT,require_select=True)
        validate_execution((run*2+PARENT).replace(b"\n",b"\r\n"),require_select=True)
        damaged=[run*2+PARENT+marker,run+run.replace(marker,marker[:-1])+PARENT,
                 run.replace(b"mask=unsupported",b"mask=pass")*2+PARENT]
        damaged += [run+run.replace(item,b"")+PARENT for item in markers]
        for serial in damaged:
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_execution(serial,require_select=True)


class MuslDirectoryEvidenceTests(unittest.TestCase):
    def test_directory_receipts_require_complete_cumulative_runs(self):
        markers = [BOOT, FILES, HEAP, HEAP_VM, PROCESS, CAPACITY, LIMIT,
            b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n",
            b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n",
            b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n",
            b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n",
            b"OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass\n",
            b"OK_MUSL_POLL poll=pass ppoll=pass layouts=pass timeout=pass wake=pass eof=pass errors=pass mask=unsupported\n",
            b"OK_MUSL_OPEN open=pass creat=pass flags=pass cwd=pass copies=pass pressure=pass legacy=where-present\n",
            b"OK_MUSL_POSITIONAL pread=pass pwrite=pass offsets=pass shared=pass append=linux copies=pass bounded=pass\n",
            b"OK_MUSL_SELECT select=pass pselect=pass layouts=pass timeout=pass wake=pass sets=pass errors=pass mask=unsupported\n",
            b"OK_MUSL_DIRECTORY_INODE name=musl-positional inode=1234\n",
            b"OK_MUSL_DIRECTORY opendir=pass readdir=pass cookies=pass shared=pass inode=pass copies=pass bounded=pass\n"]
        run = b"".join(markers)
        validate_execution(run * 2 + PARENT, require_directory=True)
        validate_execution((run * 2 + PARENT).replace(b"\n", b"\r\n"), require_directory=True)
        damaged = [run * 2 + PARENT + markers[-1],
                   run + run.replace(markers[-1], markers[-1][:-1]) + PARENT,
                   run.replace(b"cookies=pass", b"cookies=fail") * 2 + PARENT,
                   run * 2]
        damaged += [run + run.replace(item, b"") + PARENT for item in markers]
        for serial in damaged:
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_execution(serial, require_directory=True)

    def test_inode_receipt_is_exact_complete_and_stable(self):
        from test_musl_userland import directory_inode_evidence
        marker=b"OK_MUSL_DIRECTORY_INODE name=musl-positional inode=1234\n"
        self.assertEqual(directory_inode_evidence(marker*2),1234)
        self.assertEqual(directory_inode_evidence((marker*2).replace(b"\n",b"\r\n")),1234)
        for serial in (marker,marker*3,marker+marker[:-1],marker+marker.replace(b"1234",b"1235"),
                       marker.replace(b"1234",b"0")*2,marker.replace(b"1234",b"18446744073709551616")*2,
                       marker.replace(b"musl-positional",b"other")*2):
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                directory_inode_evidence(serial)


class MuslUmaskEvidenceTests(unittest.TestCase):
    def test_cumulative_runs_require_distinct_creation_slots(self):
        markers = [BOOT, FILES, HEAP, HEAP_VM, PROCESS, CAPACITY, LIMIT,
            b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n",
            b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n",
            b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n",
            b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n",
            b"OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass\n",
            b"OK_MUSL_POLL poll=pass ppoll=pass layouts=pass timeout=pass wake=pass eof=pass errors=pass mask=unsupported\n",
            b"OK_MUSL_OPEN open=pass creat=pass flags=pass cwd=pass copies=pass pressure=pass legacy=where-present\n",
            b"OK_MUSL_POSITIONAL pread=pass pwrite=pass offsets=pass shared=pass append=linux copies=pass bounded=pass\n",
            b"OK_MUSL_SELECT select=pass pselect=pass layouts=pass timeout=pass wake=pass sets=pass errors=pass mask=unsupported\n",
            b"OK_MUSL_DIRECTORY_INODE name=musl-positional inode=1234\n",
            b"OK_MUSL_DIRECTORY opendir=pass readdir=pass cookies=pass shared=pass inode=pass copies=pass bounded=pass\n"]
        umask = b"OK_MUSL_UMASK scalar=pass creation=pass existing=pass fork=pass exec=pass isolation=pass\n"
        slot0 = b"OK_MUSL_UMASK_FILES slot=0 parent=0644 restricted=0600 child=0660 exec=0640\n"
        slot1 = slot0.replace(b"slot=0", b"slot=1")
        run = b"".join(markers) + umask
        valid = run + slot0 + run + slot1 + PARENT
        validate_execution(valid, require_umask=True)
        validate_execution(valid.replace(b"\n", b"\r\n"), require_umask=True)
        damaged = [valid.replace(slot1, slot0), valid.replace(slot1, slot1[:-1]),
                   valid.replace(b"parent=0644", b"parent=0600"), valid + umask,
                   valid.replace(b"exec=pass isolation=pass", b"exec=fail isolation=pass"),
                   valid.replace(slot1, slot1.replace(b"slot=1", b"slot=2"))]
        damaged += [valid.replace(marker, b"", 1) for marker in [*markers, umask, slot0, slot1, PARENT]]
        for serial in damaged:
            with self.subTest(serial=serial), self.assertRaises(RuntimeError):
                validate_execution(serial, require_umask=True)
