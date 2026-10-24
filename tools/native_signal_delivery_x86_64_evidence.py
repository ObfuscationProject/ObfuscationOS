"""Private architecture-specific signal evidence; parsers do not execute handlers."""
import re
from native_child_events import normalize_transcript, WAIT as CHILD_WAIT
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline
from object_pressure_evidence import decode_frames, failure_line as general_failure, admit_sdk as admit_common_sdk
from entry_stack_evidence import decode_stacks, COUNTERS

MARKER = b'SIGNAL_DELIVERY_PASS x86_64 handler=7 nested=1 coalesced=1 nodefer=1 reset=1 registers=1 fp=1 corrupt_return=2'
PTHREAD_MARKER = b'PTHREAD_SIGNALS_PASS x86_64 raise=1 peer=1 siginfo=1 masks=1 tls=1 join=1'
ALTSTACK_MARKER = b'ALTSTACK_PASS x86_64 handlers=5 nested=2 onstack=1 autodisarm=2 restore_ignored=2 fork=1 pthread_reset=1 failed_exec=1 fault_children=2'
ALTSTACK_EXEC = b'ALTSTACK_EXEC_CHILD_PASS x86_64 flags=autodisarm_disabled'
CONTAINED_FAULT = b'OK_NATIVE scope=hardware fault=contained'
BAD_SP_MARKER = b'SIGNAL_BAD_SP_PASS x86_64 repaired=3 saved_sp=3 alt_local=3 stack_cookies=3 fault_children=2'
PROBES = {
    'raw': (MARKER, b'SIGNAL_DELIVERY_PASS', b'native-signal-delivery-x86-64', 3),
    'pthread': (PTHREAD_MARKER, b'PTHREAD_SIGNALS_PASS', b'native-pthread-signals-x86-64', 2),
    'altstack': (ALTSTACK_MARKER, b'ALTSTACK_PASS', b'/bin/native-signal-altstack-x86-64', 5),
    'altstack-exec': (ALTSTACK_MARKER, b'ALTSTACK_PASS', b'/bin/native-signal-altstack-x86-64 --exec', 6),
    'bad-sp': (BAD_SP_MARKER, b'SIGNAL_BAD_SP_PASS', b'/bin/native-signal-bad-sp-x86-64', 3),
}
# Private PPC32 BE e500v2 scalar-soft-float ABI with eager full64 SPE state.
PPC_RAW_MARKER = b'SIGNAL_PPC_PASS ppc legacy=1 rt=1 handlers=22 nested=2 nodefer_nested=2 states=10 relocated=2 full_spe=1 masks=10 fatal=24 restorer_ignored=1'
PPC_MAP_MARKER = b'SIGNAL_MAP_PASS ppc handlers=4 protected=8 hint=1 adjacent=1 fork=1 exec=1 write_fault=1 rt_only=0 plain=1 siginfo=1 restorer_ignored=1'
PPC_PROBES = {
    'ppc-raw': (PPC_RAW_MARKER, b'SIGNAL_PPC_PASS', b'/bin/native-signal-delivery-ppc', 25),
    'ppc-map': (PPC_MAP_MARKER, b'SIGNAL_MAP_PASS', b'/bin/native-signal-mapping-ppc', 3),
    'pthread': (PTHREAD_MARKER.replace(b'x86_64', b'ppc'), b'PTHREAD_SIGNALS_PASS', b'native-pthread-signals-ppc', 2),
    'altstack': (ALTSTACK_MARKER.replace(b'x86_64', b'ppc'), b'ALTSTACK_PASS', b'/bin/native-signal-altstack-ppc', 5),
    'altstack-exec': (ALTSTACK_MARKER.replace(b'x86_64', b'ppc'), b'ALTSTACK_PASS', b'/bin/native-signal-altstack-ppc --exec', 6),
    'bad-sp': (BAD_SP_MARKER.replace(b'x86_64', b'ppc'), b'SIGNAL_BAD_SP_PASS', b'/bin/native-signal-bad-sp-ppc', 3),
}
PPC_CHECK_COUNTS = {'altstack': b'35', 'altstack-exec': b'37', 'bad-sp': b'18', 'ppc-map': b'26'}
PPC_IMAGE_COUNTS = {'pthread': 1, 'altstack': 1, 'altstack-exec': 2, 'bad-sp': 1, 'ppc-raw': 1, 'ppc-map': 2}

RISCV_MARKER = b'SIGNAL_RISCV_PASS x86_64 handler=8 nested=1 coalesced=1 nodefer=1 reset=1 registers=1 fp=1 fcsr=1 tp=1 restorer=9 corrupt_return=2'
MAP_MARKER = b'SIGNAL_MAP_PASS x86_64 handlers=4 protected=8 hint=1 adjacent=1 fork=1 exec=1 write_fault=1'
MAP_EXEC = b'SIGNAL_MAP_EXEC_CHILD_PASS x86_64 fresh=1 restorer=1'
ENTRY_MARKER = b'SIGNAL_ENTRY_PASS x86_64 handler_nx=1 return_nx=1 return_sp=1 frame_boundary=1 fault_children=4'
RISCV_PROBES = {
    'riscv-entry': (ENTRY_MARKER, b'SIGNAL_ENTRY_PASS', b'native-signal-entry-x86-64', 5),
    'riscv-raw': (RISCV_MARKER, b'SIGNAL_RISCV_PASS', b'native-signal-delivery-x86-64', 3),
    'riscv-map': (MAP_MARKER, b'SIGNAL_MAP_PASS', b'/bin/native-signal-mapping-x86-64', 3),
}


MIPS_MARKER = b'SIGNAL_MIPS_PASS mips legacy=1 rt=1 handlers=20 nested=2 nodefer_nested=2 coalesced=2 reset=2 gpr=4 fpr16=4 edited_fp=2 hilo=4 fcsr=4 tls=4 restorers=26 high_mask=2 corrupt_return=6 pending_fcsr=4 fcsr_writeback=4 sigfpe_before_resume=4 si_kernel=2 forced_default=4 preserved_payload=2 highest_fatal=1'

MIPS64_MARKER = b'SIGNAL_MIPS64_PASS mips64 plain_rt=1 siginfo_rt=1 handlers=20 nested=2 nodefer_nested=2 coalesced=2 reset=2 gpr=4 fpr32=4 edited_fp=2 hilo=4 fcsr=4 tls=4 restorers=26 high_mask=2 corrupt_return=16 pending_fcsr=4 fcsr_writeback=4 sigfpe_before_resume=4 si_kernel=2 forced_default=4 preserved_payload=2 highest_fatal=1'
MIPS64_MAP_MARKER = b'SIGNAL_MAP_PASS mips64 handlers=4 protected=8 hint=1 adjacent=1 fork=1 exec=1 write_fault=1 rt_only=1 plain=1 siginfo=1'

LOONGARCH64_MARKER = b'SIGNAL_LOONGARCH64_PASS loongarch64 handlers=20 nested=2 coalesced=2 nodefer=2 reset=2 registers=4 fp=4 edited_fp=2 f32=1 fcc8=1 fcsr=1 tp=2 restorers=24 high_mask=2 corrupt_return=4 pending_fcsr=2 fcsr_writeback=2 sigfpe_before_resume=2 si_kernel=1 forced_default=2 preserved_payload=1'

ARM32_MARKER = b'SIGNAL_ARM32_PASS arm32 legacy=4 rt=4 combinations=8 handlers=88 nested=8 coalesced=8 nodefer=8 reset=8 registers=16 fp=16 edited_fp=16 d32=1 fpscr=1 arm_thumb=1 restorers=96 high_mask=8 corrupt_return=4'

I386_MARKER = b'SIGNAL_I386_PASS i386 legacy=1 rt=1 handler=16 nested=2 coalesced=2 nodefer=2 reset=2 registers=2 x87=2 xmm=2 mxcsr=2 edited_fp=2 high_mask=2 corrupt_return=4'

I386_ENTRY_MARKER = b'SIGNAL_I386_ENTRY_PASS i386 legacy=1 rt=1 handler_nx=2 return_nx=2 return_sp=2 segmented_sp=2 segmented_delivery=2 segmented_readonly=2 fault_children=8'

def probe_spec(arch, kind):
    if arch == 'ppc' and kind in PPC_PROBES:
        return PPC_PROBES[kind]
    if arch == 'mips64':
        if kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'): return PROBES[kind]
        if kind == 'mips64-raw': return (MIPS64_MARKER, b'SIGNAL_MIPS64_PASS', b'/bin/native-signal-mips64', 22)
        if kind == 'mips64-map': return (MIPS64_MAP_MARKER, b'SIGNAL_MAP_PASS', b'/bin/native-signal-mapping-mips64', 3)
    if arch == 'mips':
        if kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'): return PROBES[kind]
        if kind == 'mips-raw': return (MIPS_MARKER, b'SIGNAL_MIPS_PASS', b'native-signal-mips', 12)
        if kind == 'mips-map': return RISCV_PROBES['riscv-map']
    if arch == 'loongarch64':
        if kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'): return PROBES[kind]
        if kind == 'loongarch-map': return RISCV_PROBES['riscv-map']
        if kind == 'loongarch-raw': return (LOONGARCH64_MARKER, b'SIGNAL_LOONGARCH64_PASS', b'native-signal-delivery-x86-64', 7)
    if arch == 'arm32':
        if kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'):
            return PROBES[kind]
        if kind == 'arm32-raw':
            return (ARM32_MARKER, b'SIGNAL_ARM32_PASS', b'native-signal-delivery-arm32', 5)
    if arch == 'i386':
        if kind == 'i386-entry':
            return (I386_ENTRY_MARKER, b'SIGNAL_I386_ENTRY_PASS', b'native-signal-entry-i386', 9)
        if kind == 'i386-raw':
            return (I386_MARKER, b'SIGNAL_I386_PASS', b'native-signal-delivery-i386', 5)
        if kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'):
            return PROBES[kind]
    if arch in ('x86_64', 'aarch64') and kind in PROBES:
        return PROBES[kind]
    if arch in ('rv32', 'rv64'):
        if kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'):
            return PROBES[kind]
        if kind in RISCV_PROBES:
            return RISCV_PROBES[kind]
    raise ValueError('probe is not supported for this private delivery profile')


IMAGE = re.compile(rb'OK_NATIVE_IMAGE personality=linux source=(firmware|linker) pages=[1-9][0-9]* physical_first=0x[0-9a-f]{16} physical_last=0x[0-9a-f]{16} owner=retained')


def incidental_events(span, arch, baseline):
    # Import lazily: the pipe codecs share this module's IMAGE wire grammar.
    from native_pipe_io_events import native_events as pipe_events
    from native_futex_events import native_events as futex_events
    from native_poll_events import native_events as poll_events
    return (pipe_events(span, arch) + futex_events(span, arch, allow_signal=False) +
            poll_events(span, arch, allow_signal=False) + child_events(span, arch, baseline=baseline))


def validate_command(span, command, success, extra=()):
    if span.count(b'oksh> ') != 1:
        raise ValueError('dedicated command must contain exactly one final shell prompt')
    output, _, _ = span.rpartition(b'oksh> ')
    first = True
    for raw in output.splitlines(keepends=True):
        if not raw.endswith(b'\n'):
            raise ValueError('incomplete command output line')
        line = raw[:-1].removesuffix(b'\r')
        if not line:
            continue
        if first and line == command:
            first = False
            continue
        first = False
        if (line == success or line in extra or line.startswith(b'OK_NATIVE_FRAMES ') or
                line.startswith(b'OK_ENTRY_STACKS ') or IMAGE.fullmatch(line)):
            continue
        raise ValueError('unexpected output or command inside dedicated command span')


# Keep the collector's complete-line guard aligned with all signal diagnostics.
SIGNAL_FAILURE_PREFIXES = (
    b'SIGNAL_PPC_FAIL',
    b'SIGNAL_MIPS64_FAIL', b'SIGNAL_MIPS_FAIL', b'SIGNAL_LOONGARCH64_FAIL', b'SIGNAL_ARM32_FAIL',
    b'SIGNAL_I386_ENTRY_FAIL', b'SIGNAL_I386_FAIL', b'SIGNAL_DELIVERY_FAIL',
    b'PTHREAD_SIGNALS_FAIL', b'ALTSTACK_FAIL', b'SIGNAL_BAD_SP_FAIL',
    b'SIGNAL_RISCV_FAIL', b'SIGNAL_ENTRY_FAIL', b'SIGNAL_MAP_FAIL',
)


def incomplete_failure_line(serial):
    failure = next((prefix for prefix in SIGNAL_FAILURE_PREFIXES if prefix in serial), None)
    return failure is not None and b'\n' not in serial[serial.index(failure):]


def failure_line(serial):
    if b'SIGNAL_PPC_FAIL' in serial:
        return 'PPC32 legacy/RT signal assertion failed: ' + serial[serial.index(b'SIGNAL_PPC_FAIL'):].split(b'\n', 1)[0].decode(errors='replace')
    if b'SIGNAL_MIPS64_FAIL' in serial:
        return 'MIPS64 n64 RT signal assertion failed'
    if b'SIGNAL_MIPS_FAIL' in serial:
        return 'MIPS o32 raw signal assertion failed'
    if b'SIGNAL_LOONGARCH64_FAIL' in serial:
        return 'LoongArch64 raw signal assertion failed'
    if b'SIGNAL_ARM32_FAIL' in serial:
        return 'ARM32 legacy/RT signal assertion failed'
    if b'SIGNAL_I386_ENTRY_FAIL' in serial:
        return 'i386 signal entry assertion failed'
    if b'SIGNAL_I386_FAIL' in serial:
        return 'i386 legacy/RT signal assertion failed'
    if b'SIGNAL_DELIVERY_FAIL' in serial:
        return 'signal-delivery assertion failed: ' + serial[serial.index(b'SIGNAL_DELIVERY_FAIL'):].split(b'\n', 1)[0].decode(errors='replace')
    if b'PTHREAD_SIGNALS_FAIL' in serial:
        return 'pthread signal assertion failed'
    if b'ALTSTACK_FAIL' in serial:
        return 'alternate-stack assertion failed'
    if b'SIGNAL_BAD_SP_FAIL' in serial:
        return 'bad-SP rescue assertion failed'
    if b'SIGNAL_RISCV_FAIL' in serial:
        return 'RISC-V raw signal assertion failed'
    if b'SIGNAL_ENTRY_FAIL' in serial:
        return 'RISC-V signal entry assertion failed'
    if b'SIGNAL_MAP_FAIL' in serial:
        return 'RISC-V signal mapping assertion failed'
    return general_failure(serial)


def validate_probe(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='raw'):
    serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin) = normalize_transcript(
        serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin))
    marker, prefix, command, leases = probe_spec(arch, kind)
    marker = marker.replace(b'x86_64', arch.encode())
    command = command.replace(b'x86-64', b'la64' if arch == 'loongarch64' else arch.replace('_', '-').encode())
    boundaries = (baseline_begin, probe_begin, probe_mid, probe_end, native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('command boundary does not end at a complete shell prompt')
    if error := failure_line(serial):
        raise ValueError(error)
    if arch == 'ppc' and kind in ('ppc-raw', 'ppc-map') and b'SIGNAL_PPC_CASE_PASS' in serial:
        raise ValueError('PPC single-case diagnostics cannot qualify an aggregate collection')
    tail = serial.rsplit(b'oksh> ', 1)
    if len(tail) != 2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n', tail[1])):
        raise ValueError('unexpected bytes after the final shell prompt')
    boot = serial[:baseline_begin]
    child_baseline = boot_baseline(boot, arch)
    baseline = serial[baseline_begin:probe_begin]
    first, second = serial[probe_begin:probe_mid], serial[probe_mid:probe_end]
    native = serial[native_begin:]
    for span in (baseline, native):
        incidental = incidental_events(span, arch, child_baseline)
        validate_command(span, b'hello | cat', b'hello from ObfuscationOS userland', tuple(e['line'] for e in incidental))
    for span in (first, second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index, line in enumerate(lines) if IMAGE.fullmatch(line)]
        expected_images = 2 if kind in ('altstack-exec', 'riscv-map', 'loongarch-map', 'mips-map', 'mips64-map') else 1
        if arch == 'ppc':
            expected_images = PPC_IMAGE_COUNTS[kind]
        if len(images) != expected_images:
            raise ValueError('missing or duplicate Linux image admission within probe command')
        source = b'linker' if arch in ('loongarch64', 'mips', 'mips64') else b'firmware'
        if any(IMAGE.fullmatch(lines[index])[1] != source for index in images):
            raise ValueError('Linux image source differs from the selected architecture')
        if (any(line != command and not CHILD_WAIT.fullmatch(line) for line in lines[:images[0]]) or
                marker not in lines or images[-1] >= lines.index(marker)):
            raise ValueError('Linux image admission must precede probe execution and success')
        extra = ()
        if kind.startswith('altstack'):
            check_count = PPC_CHECK_COUNTS[kind] if arch == 'ppc' else (b'37' if kind == 'altstack-exec' else b'35')
            extra = (b'ALTSTACK_CHECKS count=' + check_count,)
            if kind == 'altstack-exec':
                extra += (ALTSTACK_EXEC.replace(b'x86_64', arch.encode()),)
            if any(lines.count(line) != 1 for line in extra):
                raise ValueError('missing or duplicate alternate-stack subtest completion')
            if marker not in lines or lines.index(extra[0]) <= lines.index(marker):
                raise ValueError('alternate-stack check count must follow success')
            if kind == 'altstack-exec' and lines.index(extra[1]) >= lines.index(marker):
                raise ValueError('exec child completion must precede parent success')
            if kind == 'altstack-exec' and images[1] >= lines.index(extra[1]):
                raise ValueError('successful exec image must precede exec child completion')
            # Either intentional fault child may trap in its exhausted handler
            # before delivery detects insufficient frame space. Tie these
            # bounded diagnostics to actual entry-fault counter deltas below.
            if lines.count(CONTAINED_FAULT) > 2:
                raise ValueError('too many contained faults for two intentional children')
            extra += (CONTAINED_FAULT,)
        if kind == 'bad-sp':
            count = b'SIGNAL_BAD_SP_CHECKS count=' + (PPC_CHECK_COUNTS[kind] if arch == 'ppc' else b'18')
            if lines.count(count) != 1 or marker not in lines or lines.index(count) <= lines.index(marker):
                raise ValueError('missing ordered bad-SP check count')
            if lines.count(CONTAINED_FAULT) > 2:
                raise ValueError('too many contained bad-SP child faults')
            extra = (count, CONTAINED_FAULT)
        if kind in ('riscv-map', 'loongarch-map', 'mips-map', 'mips64-map', 'ppc-map'):
            count = b'SIGNAL_MAP_CHECKS count=' + (b'26' if kind in ('mips64-map', 'ppc-map') else b'25')
            child = MAP_EXEC.replace(b'x86_64', arch.encode())
            if (lines.count(count) != 1 or lines.index(count) <= lines.index(marker) or
                    lines.count(child) != 1 or not images[1] < lines.index(child) < lines.index(marker)):
                raise ValueError('missing unique ordered signal mapping/exec completion')
            if lines.count(CONTAINED_FAULT) != 1 or lines.index(CONTAINED_FAULT) >= images[1]:
                raise ValueError('missing unique write-fault child before successful exec')
            extra = (count, child, CONTAINED_FAULT)
        if any(index >= lines.index(marker) for index, line in enumerate(lines) if line == CONTAINED_FAULT):
            raise ValueError('intentional child faults must precede parent success')
        incidental = incidental_events(span, arch, child_baseline)
        validate_command(span, command, marker, extra + tuple(e['line'] for e in incidental))
    for boot_prefix, expected in ((b'OK_SYSTEM_GUI boot=', b'OK_SYSTEM_GUI boot=complete'),
                             (b'OK_STORAGE ', b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        lines = [line for line in boot.splitlines(keepends=True) if boot_prefix in line]
        if len(lines) != 1 or lines[0] not in (expected + b'\n', expected + b'\r\n'):
            raise ValueError('missing unique complete distribution boot evidence')
    for span in (baseline, native):
        lines = [line for line in span.splitlines(keepends=True) if b'hello from ObfuscationOS userland' in line]
        if len(lines) != 1 or lines[0] not in (b'hello from ObfuscationOS userland\n', b'hello from ObfuscationOS userland\r\n'):
            raise ValueError('missing unique complete dedicated native pipeline')
    for span in (first, second):
        lines = [line for line in span.splitlines(keepends=True) if prefix in line]
        if len(lines) != 1 or lines[0] not in (marker+b'\n', marker+b'\r\n'):
            raise ValueError('missing unique complete probe success within each command')
    if any(prefix in span for span in (boot, baseline, serial[probe_end:])):
        raise ValueError('probe success outside execution boundaries')
    if kind.startswith('altstack') and any(word in span for word in (b'ALTSTACK_CHECKS', b'ALTSTACK_EXEC_CHILD_PASS')
                                         for span in (boot, baseline, serial[probe_end:])):
        raise ValueError('alternate-stack completion outside execution boundaries')
    if kind == 'bad-sp' and any(b'SIGNAL_BAD_SP_CHECKS' in span for span in (boot, baseline, serial[probe_end:])):
        raise ValueError('bad-SP completion outside execution boundaries')
    if kind in ('riscv-map', 'loongarch-map', 'mips-map', 'mips64-map', 'ppc-map') and any(word in span for word in (b'SIGNAL_MAP_CHECKS', b'SIGNAL_MAP_EXEC_CHILD_PASS')
                                  for span in (boot, baseline, serial[probe_end:])):
        raise ValueError('signal mapping completion outside execution boundaries')
    rows = decode_frames(serial, arch)
    base = decode_frames(baseline, arch)[-1]
    if base['allocations'] <= decode_frames(boot, arch)[-1]['allocations']:
        raise ValueError('baseline pipeline has no independent allocation evidence')
    endings = [decode_frames(span, arch)[-1] for span in (first, second, native)]
    for index, span in enumerate((baseline, first, second, native)):
        success = prefix if index in (1, 2) else b'hello from ObfuscationOS userland'
        if span.rfind(b'OK_NATIVE_FRAMES') <= span.rfind(success):
            raise ValueError('missing frame retirement after dedicated command output')
    if b'OK_NATIVE_FRAMES' in serial[probe_end:native_begin]:
        raise ValueError('frame activity outside dedicated command boundaries')
    if any(rows[0][key] for key in ('used', 'allocations', 'releases')):
        raise ValueError('missing empty boot baseline')
    for row in [base, *endings]:
        if row['objects'] != int(bool(child_baseline)) or row['user'] != base['user']:
            raise ValueError('probe did not retire object/user allocations')
    previous = base
    for row in endings:
        if row['allocations'] <= previous['allocations'] or row['releases'] <= previous['releases']:
            raise ValueError('missing allocation and retirement in dedicated command')
        previous = row
    checks = (dict(handler='passed', nesting='passed', coalescing='passed', nodefer='passed',
                   resethand='passed', registers='passed', fp='passed', corrupt_return='passed')
              if kind in ('raw', 'riscv-raw', 'i386-raw', 'arm32-raw', 'loongarch-raw', 'mips-raw', 'mips64-raw') else dict(raise_signal='passed', peer='passed', siginfo='passed', masks='passed', tls='passed', join='passed')
              if kind == 'pthread' else dict(handler_nx='passed', return_nx='passed', return_sp='passed',
                  frame_boundary='passed', fault_children='passed') if kind == 'riscv-entry' else dict(protected='passed', hint='passed', adjacent='passed', fork='passed',
                  successful_exec='passed', write_fault='passed') if kind in ('riscv-map', 'loongarch-map', 'mips-map', 'mips64-map', 'ppc-map') else dict(repaired='passed', saved_sp='passed', alt_local='passed',
                  stack_cookies='passed', fault_children='passed') if kind == 'bad-sp' else dict(alternate_stack='passed', nesting='passed', autodisarm='passed',
                  restore_ignored='passed', fork='passed', pthread_reset='passed', failed_exec='passed',
                  fault_children='passed', successful_exec='passed' if kind == 'altstack-exec' else 'not-run'))
    if kind == 'i386-entry':
        checks = dict(legacy='passed', realtime='passed', handler_nx='passed', return_nx='passed', return_sp='passed', segmented_sp='passed', segmented_delivery='passed', segmented_readonly='passed', fault_children='passed')
    if kind == 'i386-raw':
        checks.update(legacy='passed', realtime='passed', x87='passed', xmm='passed', mxcsr='passed', edited_fp='passed', high_mask='passed')
    if kind == 'arm32-raw':
        checks.update(legacy='passed', realtime='passed', arm_thumb='passed', d32='passed', fpscr='passed', edited_fp='passed', high_mask='passed', restorers='passed')
    if kind == 'loongarch-raw':
        checks.update(f32='passed', fcc8='passed', fcsr='passed', tp='passed', edited_fp='passed', restorers='passed', high_mask='passed', pending_fcsr='passed', fcsr_writeback='passed', sigfpe_before_resume='passed', si_kernel='passed', forced_default='passed', preserved_payload='passed')
    if kind == 'mips-raw':
        checks.update(legacy='passed', realtime='passed', gpr='passed', fpr16='passed', hilo='passed', fcsr='passed', tls='passed', edited_fp='passed', restorers='passed', high_mask='passed', pending_fcsr='passed', fcsr_writeback='passed', sigfpe_before_resume='passed', si_kernel='passed', forced_default='passed', preserved_payload='passed', highest_fatal='passed')
    if kind == 'mips64-raw':
        checks.update(rt_only=True, plain_rt='passed', siginfo_rt='passed', gpr='passed', fpr32='passed', hilo='passed', fcsr='passed', tls='passed', edited_fp='passed', restorers='passed', high_mask='passed', pending_fcsr='passed', fcsr_writeback='passed', sigfpe_before_resume='passed', si_kernel='passed', forced_default='passed', preserved_payload='passed', highest_fatal='passed', corrupt_return_children=16, forced_default_children=4, highest_signal_children=1, image_publications_per_run=1)
    if kind == 'mips64-map':
        checks.update(rt_only=True, plain='passed', siginfo='passed', check_count=26, image_publications_per_run=2)
    if kind == 'ppc-raw':
        # This exact PPC contract does not inherit generic raw FP/reset claims.
        checks = dict(legacy='passed', realtime='passed', handler='passed',
                      nesting='passed', nodefer_nesting='passed', states='passed',
                      relocated_context='passed', full_spe='passed', masks='passed',
                      fatal_return='passed', restorer_ignored='passed',
                      handlers=22, nested=2, nodefer_nested=2, state_cases=10,
                      relocated_contexts=2, mask_cases=10, fatal_children=24,
                      corrupt_return_children=23, highest_signal_children=1,
                      image_publications_per_run=1)
    if kind == 'ppc-map':
        checks.update(rt_only=False, plain='passed', siginfo='passed',
                      restorer_ignored='passed', check_count=26, image_publications_per_run=2)
    if kind == 'riscv-raw':
        checks.update(fcsr='passed', tp='passed', restorer='passed')
    return dict(runs=2, **checks, minimum_leases_per_run=leases, kind=kind,
                experimental=True, production_signal_support=False,
                baseline=base, final=endings[-1], records=len(rows), accounting_version=2,
                child_baseline={str(k):{n:v for n,v in r.items() if n!='line'} for k,r in child_baseline.items()})



def admit_sdk(sdk, expected, arch, mode, compiler, compiler_hash):
    if arch not in ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc') or mode != 'debug':
        raise ValueError('private delivery requires i386/x86_64/AArch64/ARM32/RV32/RV64/LoongArch64/MIPS o32/MIPS64 n64/PPC32 e500v2 Debug')
    manifest = admit_common_sdk(sdk, expected, arch, mode, compiler, compiler_hash)
    if manifest.get("abi_version") != 31 or manifest.get("compiler", {}).get("family") != "gcc":
        raise ValueError("private delivery fixture requires SDK31 GCC ABI")
    return manifest


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='raw'):
    serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin) = normalize_transcript(
        serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin))
    _, prefix, _, _ = probe_spec(arch, kind)
    result = validate_probe(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind)
    rows = decode_stacks(serial)
    if any(rows[0].values()):
        raise ValueError('missing empty entry-stack boot baseline')
    boot = decode_stacks(serial[:baseline_begin])
    spans = (serial[baseline_begin:probe_begin], serial[probe_begin:probe_mid],
             serial[probe_mid:probe_end], serial[native_begin:])
    if b'OK_ENTRY_STACKS' in serial[probe_end:native_begin]:
        raise ValueError('entry-stack activity outside dedicated command boundaries')
    endings = [decode_stacks(span)[-1] for span in spans]
    for index, span in enumerate(spans):
        success = prefix if index in (1, 2) else b'hello from ObfuscationOS userland'
        if span.rfind(b'OK_ENTRY_STACKS') <= span.rfind(success):
            raise ValueError('missing entry-stack retirement after dedicated command output')
    baseline = endings[0]
    if baseline['leased'] == 0 or any(row['leased'] != baseline['leased'] for row in endings):
        raise ValueError('dedicated command did not return to live shell lease baseline')
    previous = boot[-1]
    commands = []
    for index, row in enumerate(endings):
        delta = {key: row[key] - previous[key] for key in COUNTERS}
        # Raw probe forks two children; the libc probe creates one peer.
        minimum = result['minimum_leases_per_run'] if index in (1, 2) else 1
        if (delta['reservations'] < minimum or delta['releases'] < minimum or
                delta['activations'] <= 0 or delta['syscalls'] <= 0):
            raise ValueError('dedicated command lacks fresh owned entries, syscalls or lease reuse')
        # Every captured fault requires an admitted diagnostic in that same
        # command. Kinds without fault children admit no diagnostic, hence zero.
        fault_lines = spans[index].splitlines().count(CONTAINED_FAULT)
        if delta['faults'] != fault_lines:
            raise ValueError('contained fault diagnostics differ from captured entry faults')
        commands.append(delta)
        previous = row
    result['entry_stacks'] = dict(version=1, scope='actual-user', cpu=0, smp=False,
        guards='mapped-canaries', capacity=128, usable_bytes=65536, backing_bytes=9437184,
        boot=rows[0], baseline=baseline, first=endings[1], second=endings[2], final=endings[3],
        commands=commands, minimum_probe_reservations=result['minimum_leases_per_run'], records=len(rows))
    return result
