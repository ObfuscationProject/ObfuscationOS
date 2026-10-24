"""Ordinary SDK31 signal user observations; journal replay is not execution.

General resource/image records and Debug wait records are strictly decoded.
Private signal/lifetime ledgers are absent. The SDK-only runner separately
establishes provenance and actual QEMU execution.
"""
import re
import shlex

from kernel_sdk import ARCH_TRIPLES
from object_pressure_evidence import admit_sdk as admit_common_sdk, failure_line as general_failure
from object_pressure_evidence import decode_frames
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE
from native_child_events import normalize_transcript, boot_baseline, native_events as child_events
from native_pipe_io_events import native_events as pipe_events
import native_child_exit_guest as policy
import native_child_exit_pressure_guest as pressure

KINDS = ('child-exit-policy', 'child-exit-pressure')
PROMPT = b'oksh> '
TERMINATION = re.compile(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n')
REJECTED_PLATFORM_PREFIXES = (b'N64_SIGNAL_PLATFORM_REJECT', b'N64_PRIVATE_EARLY_')
PLATFORM_PASS = b'N64_SIGNAL_PLATFORM_PASS before-cxx=1 fp=fr1'


def probe_spec(arch, kind):
    if kind not in KINDS:
        raise ValueError('unsupported ordinary signal probe')
    return (policy if kind == KINDS[0] else pressure).probe_spec(arch, kind)


def macro_options(flags):
    words = []
    for flag in flags:
        words.extend(flag[4:].split(',') if flag.startswith('-Wp,') else shlex.split(flag))
    options = []
    index = 0
    while index < len(words):
        word = words[index]
        if word in ('-D', '-U'):
            index += 1
            if index == len(words):
                raise ValueError('incomplete SDK macro option')
            options.append((word[1], words[index]))
        elif word.startswith(('-D', '-U')):
            options.append((word[1], word[2:]))
        index += 1
    return options


def admit_profile(manifest, arch, mode):
    """Additional ordinary-service admission, independent of private collectors."""
    if arch not in ARCH_TRIPLES or mode not in ('debug', 'release'):
        raise ValueError('unsupported ordinary architecture or mode')
    for key, expected in (('abi_version', 31), ('arch', arch), ('mode', mode),
                          ('native_signal_profile', 'bounded-bootcpu-v1')):
        if manifest.get(key) != expected:
            raise ValueError('ordinary SDK capability mismatch: ' + key)
    for field in ('defines', 'cxxflags', 'asflags'):
        if not isinstance(manifest.get(field), list) or any(not isinstance(x, str) for x in manifest[field]):
            raise ValueError('invalid ordinary SDK macro inventory')
    runtime = 'OK_NATIVE_SIGNAL_RUNTIME'
    private = 'OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE'
    controls = {runtime, private, 'OK_ENABLE_TEST_POINTS'}
    defines = manifest['defines']
    cpp, asm = macro_options(manifest['cxxflags']), macro_options(manifest['asflags'])
    if [x for x in defines if x.split('=', 1)[0] == runtime] != [runtime]:
        raise ValueError('ordinary SDK requires canonical runtime definition')
    if any(action == 'U' and name.split('=', 1)[0] in controls for action, name in cpp + asm):
        raise ValueError('ordinary SDK cannot override service controls')
    if any(name.split('=', 1)[0] == runtime for _, name in cpp):
        raise ValueError('ordinary runtime must use exported defines')
    if [(action, name) for action, name in asm if name.split('=', 1)[0] == runtime] != (
            [('D', runtime)] if arch == 'mips64' else []):
        raise ValueError('ordinary runtime assembly option differs from architecture')
    names = {x.split('=', 1)[0] for x in defines}
    names.update(name.split('=', 1)[0] for action, name in cpp + asm if action == 'D')
    if private in names:
        raise ValueError('ordinary signal qualification rejects private fixture SDKs')
    if mode == 'release' and 'OK_ENABLE_TEST_POINTS' in names:
        raise ValueError('ordinary Release cannot enable test points')
    return manifest


def admit_sdk(sdk, expected, arch, mode, compiler, compiler_hash):
    return admit_profile(admit_common_sdk(sdk, expected, arch, mode, compiler, compiler_hash), arch, mode)


def admit_libc_mode(manifest, musl_mode, sdk_manifest):
    """Libc mode describes the pinned archive, not the kernel or distro build."""
    if musl_mode != 'debug' or manifest.get('mode') != musl_mode:
        raise ValueError('ordinary probe requires explicit pinned --musl-mode debug')
    compiler = manifest.get('compiler', {})
    if (compiler.get('triple') != sdk_manifest['triple'] or
            compiler.get('version') != sdk_manifest['compiler']['version']):
        raise ValueError('musl and SDK compiler ABI differ')
    return dict(musl_mode=musl_mode, kernel_mode=sdk_manifest['mode'],
                distribution_mode=sdk_manifest['mode'], probe_optimization='-O2')


def failure_line(serial):
    for prefix in REJECTED_PLATFORM_PREFIXES:
        if prefix in serial:
            return 'ordinary platform rejection or private early fixture output: ' + serial[serial.index(prefix):].split(b'\n', 1)[0].decode(errors='replace')
    return policy.failure_line(serial) or pressure.failure_line(serial) or general_failure(serial)


def incomplete_failure_line(serial):
    return (any(prefix in serial and b'\n' not in serial[serial.index(prefix):] for prefix in REJECTED_PLATFORM_PREFIXES) or
            policy.incomplete_failure_line(serial) or pressure.incomplete_failure_line(serial))


def complete_lines(serial):
    return [raw.removesuffix(b'\r') for raw in serial.split(b'\n')[:-1]]


def observe_guest_execution(serial, arch, kind):
    """A complete BEGIN or FAIL records execution even if qualification fails."""
    marker = probe_spec(arch, kind)[0]
    module = policy if kind == KINDS[0] else pressure
    lines = complete_lines(serial)
    begins = [m for line in lines if (m := module.BEGIN.fullmatch(line)) and m[1] == arch.encode()]
    failures = sum(bool(re.fullmatch(rb'CHILD_EXIT_FAIL line=[0-9]{4} case=(?:0[0-9]|1[0-7]|99)', line) if kind == KINDS[0]
                        else re.fullmatch(rb'CHILD_PRESSURE_FAIL line=[0-9]{4} wave=[0129]', line)) for line in lines)
    starts = sum(int(m[2]) == 0 for m in begins) if kind == KINDS[0] else len(begins)
    passes = lines.count(marker)
    return dict(guest_begin_markers_observed=len(begins), guest_invocation_starts_observed=starts,
                guest_failure_markers_observed=failures, observed_pass_markers=passes,
                executed=bool(begins or failures or passes))


def command_lines(span, command):
    if span.count(PROMPT) != 1 or not span.endswith(PROMPT):
        raise ValueError('ordinary command requires one complete final prompt')
    output = span[:-len(PROMPT)]
    if not output.endswith(b'\n'):
        raise ValueError('ordinary command has incomplete output')
    lines = complete_lines(output)
    if any(b'\r' in line for line in lines):
        raise ValueError('unexpected carriage return in ordinary command')
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError('ordinary command has no output')
    # Serial input is normally not echoed. If a terminal echo exists, admit
    # the exact submitted command only at the start, before all diagnostics.
    return lines[1:] if lines[0] == command else lines


def observation(guest, kind):
    if kind == KINDS[0]:
        return dict(cases=guest['count'], policy_cases=guest['policy_cases'], target_info_bytes=128,
                    handlers_observed=sum(c['handlers'] for c in guest['cases']),
                    child_identities_observed=sum(len(c['children']) for c in guest['cases']),
                    user_events_observed=sum(len(c['events']) for c in guest['cases']))
    return dict(waves=3, target_info_bytes=128, pressure_children_observed=guest['pressure_children'],
                failed_forks_observed=guest['failed_forks'], recovery_children_observed=guest['recovery_children'],
                bounded_fork_pressure_observed=True, fixed_capacity_claim=False,
                global_process_exhaustion_claim=False)


def general_records(span, arch, mode, baseline):
    """Validate general diagnostics; never infer hidden child completion facts."""
    frames, stacks = decode_frames(span, arch), decode_stacks(span)
    events = pipe_events(span, arch) + child_events(span, baseline=baseline)
    if mode == 'release' and events:
        raise ValueError('Release contains Debug-only wait diagnostics')
    if any('ORIGIN' in row['tag'] or 'SIGNAL' in row['tag'] for row in events):
        raise ValueError('ordinary transcript contains private signal diagnostics')
    images = []
    source = b'linker' if arch in ('loongarch64', 'mips', 'mips64') else b'firmware'
    for line in complete_lines(span):
        if b'OK_NATIVE_IMAGE' not in line:
            continue
        if not (match := IMAGE.fullmatch(line)) or match[1] != source:
            raise ValueError('ordinary image has malformed or wrong-source admission')
        values = dict(field.split(b'=', 1) for field in line.split()[1:])
        pages = int(values[b'pages'])
        first, last = int(values[b'physical_first'], 16), int(values[b'physical_last'], 16)
        if not first or first % 4096 or last % 4096 or last < first or pages > (last-first)//4096+1:
            raise ValueError('ordinary image extent cannot contain emitted pages')
        images.append(line)
    allowed = set(images + [row['line'] for row in events])
    allowed.update(line for line in complete_lines(span) if line.startswith((b'OK_NATIVE_FRAMES ', b'OK_ENTRY_STACKS ')))
    return dict(frames=frames, stacks=stacks, events=events, images=images, allowed=allowed)


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin,
                       arch, kind='child-exit-policy', mode='release'):
    marker, _, command, _ = probe_spec(arch, kind)
    if mode not in ('debug', 'release'):
        raise ValueError('unsupported ordinary transcript mode')
    bounds = (baseline_begin, probe_begin, probe_mid, probe_end, native_begin)
    if (any(type(x) is not int for x in bounds) or
            not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial)):
        raise ValueError('invalid original ordinary command boundaries')
    if any(not serial[:x].endswith(PROMPT) for x in bounds):
        raise ValueError('ordinary command boundary is not a complete prompt')
    serial, bounds = normalize_transcript(serial, bounds)
    baseline_begin, probe_begin, probe_mid, probe_end, native_begin = bounds
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(PROMPT, 1)
    if len(tail) != 2 or (tail[1] and not TERMINATION.fullmatch(tail[1])):
        raise ValueError('unexpected bytes after final ordinary prompt')
    transcript = serial[:-len(tail[1])] if tail[1] else serial
    boot = transcript[:baseline_begin]
    if boot.count(PROMPT) != 1:
        raise ValueError('ordinary boot requires its first shell prompt')
    platform_records = [line for line in complete_lines(transcript)
                        if b'N64_SIGNAL_PLATFORM_' in line]
    expected_platform = [PLATFORM_PASS] if arch == 'mips64' else []
    if platform_records != expected_platform or (
            arch == 'mips64' and [line for line in complete_lines(boot)
                                  if b'N64_SIGNAL_PLATFORM_' in line] != expected_platform):
        raise ValueError('ordinary MIPS64 platform admission is missing, duplicated, misplaced or malformed')
    if arch == 'mips64' and complete_lines(boot)[0] != PLATFORM_PASS:
        raise ValueError('ordinary MIPS64 platform admission must precede compiled boot output')
    for prefix, expected in ((b'OK_SYSTEM_GUI boot=', b'OK_SYSTEM_GUI boot=complete'),
                            (b'OK_STORAGE ', b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        if [line for line in complete_lines(boot) if prefix in line] != [expected]:
            raise ValueError('missing unique ordinary distribution boot')
    if any(token in boot for token in (b'CHILD_EXIT_', b'CHILD_PRESSURE_', b'OK_NATIVE_IMAGE')):
        raise ValueError('guest markers or private diagnostics outside ordinary commands')
    if re.search(rb'OK_NATIVE_(?:CHILD_(?:EXIT|REAP|SIGNAL)|SIGNAL_|FUTEX_|POLL_|SLEEP_INTERRUPT|PIPE_[A-Z_]*(?:ORIGIN|SIGNAL))', transcript):
        raise ValueError('private signal diagnostic in ordinary transcript')
    child_baseline = boot_baseline(boot, required=mode == 'debug')
    if mode == 'release' and child_baseline:
        raise ValueError('Release contains Debug-only boot wait')
    boot_frames, boot_stacks = decode_frames(boot, arch), decode_stacks(boot)
    boot_pipes = pipe_events(boot, arch)
    if mode == 'release' and boot_pipes:
        raise ValueError('Release contains Debug-only boot pipe')
    all_frames, all_stacks = decode_frames(transcript, arch), decode_stacks(transcript)
    if any(boot_frames[0][key] for key in ('used', 'allocations', 'releases')) or any(boot_stacks[0].values()):
        raise ValueError('ordinary boot lacks initial empty resource snapshot')
    spans = (transcript[baseline_begin:probe_begin], transcript[probe_begin:probe_mid],
             transcript[probe_mid:probe_end], transcript[native_begin:])
    observations = []
    module = policy if kind == KINDS[0] else pressure
    resource_ends = []
    previous_frame, previous_stack = boot_frames[-1], boot_stacks[-1]
    for index, span in enumerate(spans):
        records = general_records(span, arch, mode, child_baseline)
        probe = index in (1, 2)
        lines = command_lines(span, command if probe else b'hello | cat')
        if probe:
            guest = module.guest_events(span, arch)
            if [line for line in lines if line not in records['allowed']] != guest['lines']:
                raise ValueError('unexpected output within ordinary probe command')
            expected_images = 2 if kind == 'child-exit-policy' else 1
            image_positions = [i for i, line in enumerate(lines) if IMAGE.fullmatch(line)]
            if len(records['images']) != expected_images or image_positions[0] >= next(
                    i for i, line in enumerate(lines) if line.startswith((b'CHILD_EXIT_BEGIN', b'CHILD_PRESSURE_BEGIN'))):
                raise ValueError('ordinary probe lacks exact initial/exec image admissions')
            if image_positions[-1] >= lines.index(marker):
                raise ValueError('ordinary image publication follows completion')
            if kind == 'child-exit-policy':
                events = guest['cases'][17]['events']
                failed = next(row['line'] for row in events if row.get('op') == 'EXEC_FAILED')
                checked = next(row['line'] for row in events if row.get('op') == 'EXEC_CHECK')
                if not lines.index(failed) < image_positions[1] < lines.index(checked):
                    raise ValueError('ordinary exec observations lack intervening ELF admission')
            observations.append(observation(guest, kind))
            success = marker
        else:
            success = b'hello from ObfuscationOS userland'
            if records['images'] or [line for line in lines if line not in records['allowed']] != [success]:
                raise ValueError('ordinary native pipeline output differs')
        if any(span.rfind(prefix) <= span.rfind(success) for prefix in (b'OK_NATIVE_FRAMES ', b'OK_ENTRY_STACKS ')):
            raise ValueError('ordinary resource snapshot precedes command completion')
        frame, stack = records['frames'][-1], records['stacks'][-1]
        delta = {key: stack[key]-previous_stack[key] for key in COUNTERS}
        if (frame['allocations'] <= previous_frame['allocations'] or frame['releases'] <= previous_frame['releases'] or
                any(delta[key] <= 0 for key in ('reservations', 'releases', 'activations', 'syscalls')) or
                delta['faults'] or delta['rejected']):
            raise ValueError('ordinary command lacks fresh resource activity or has rejected/faulting captures')
        resource_ends.append(dict(frames=frame, entry_stacks=stack, delta=delta,
                                  generic_wait_records=len(records['events'])))
        previous_frame, previous_stack = frame, stack
    baseline = resource_ends[0]
    if not baseline['entry_stacks']['leased'] or baseline['frames']['objects'] != 1 or any(
            any(row['frames'][key] != baseline['frames'][key] for key in ('used', 'user', 'objects')) or
            row['entry_stacks']['leased'] != baseline['entry_stacks']['leased'] for row in resource_ends):
        raise ValueError('ordinary command resources do not return to shell baseline')
    return dict(runs=2, kind=kind, architecture=arch, mode=mode, sdk_abi=31,
                scope='ordinary-bounded-bootcpu-user-observations', observations=observations,
                native_execution=False, parser_replay_only=True, private_diagnostics=False,
                internal_blocked_waits_verified=False, internal_reclaim_ledger_verified=False,
                fault_injection_verified=False, physical=False, smp=False,
                full_posix_claim=False, native_pipeline_before_and_after=True,
                general_resource_snapshots_validated=True, resource_command_ends=resource_ends,
                resource_frame_records=len(all_frames), resource_stack_records=len(all_stacks),
                private_signal_lifetime_join=False, actual_first_queued_sender_verified=False,
                unpublished_rollback_identity_verified=False)
