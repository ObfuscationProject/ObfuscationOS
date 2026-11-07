#!/usr/bin/env python3
"""Run the static-musl SMP stress probe (tests/musl/smp_stress.c) on scratch ext4 with N vCPUs.

The probe forks its workers together and each races file, AF_UNIX socketpair
and fork/exec rounds; it prints one SMP_STRESS_PASS line. With several vCPUs
the kernel's boot OK_SMP line must show every vCPU online on the profiles that
start secondaries (x86_64, aarch64, rv64), and the OK_SMP_CPUS report the
probe's exit prints must show user code entered on every online CPU during the
probe. --allow-up, for developing this tooling only, accepts a UP boot on those
profiles and skips the per-CPU check; the receipt records it.

Kernel sections (--smp-sections; by default on for x86_64, aarch64 and rv64,
the only profiles that build them, and off elsewhere): a kernel built with
them prints OK_SMP_KERNEL, OK_SMP_KERNEL_FAMILIES and OK_SMP_KERNEL_DECLINES
with the probe's exit report. The converted families must cover the probe's file
traffic (fsync >= files, write, read and lseek >= 2 * files); with two or more
CPUs sections must run on at least two CPUs and overlap other kernel work
(concurrent, witnessed, max_parallel >= 2). Its debug= field must match
--mode; shadow mismatches must be 0, and so must the assertion counters the
kernel keeps: all of them in a debug kernel, exclusive_asserts,
section_asserts and cow_refused in a release kernel (the others exist only
with the debug lock checks). --smp-sections off requires that no
OK_SMP_KERNEL line appears (the smp_sections=n kernel). The receipt records
QEMU's TCG thread mode, read from its host threads: only multi-threaded TCG
runs vCPUs in parallel. This is QEMU evidence, not physical hardware.

A kernel built with the smp_hotplug_test knob stops and restarts its highest
secondary CPU periodically and repeats an OK_SMP_HOTPLUG line in every
interrupt report. When the transcript has one (always with --require-hotplug),
its counters must never go back and the one the probe's exit prints must show
failures=0, a secondary CPU and more cycles than the last line before the
probe started (cycling begins at userland start, so only those later cycles
ran under the probe's load). A debug kernel's boot test point also
stops and restarts CPU 1 before userland; its OK_SMP_HOTPLUG_BOOT line, when
printed, must pass every check.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import sys
import time

from qemu_distro import SMP_MAX_CPUS, SMP_PROFILES, command_for, smp_fields, smp_problem
TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from build_musl_probe import admit_musl_build
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from musl_source import inspect_elf
from dynamic_startup_observer import FAILURES

PROMPT = b'oksh> '
RESULT = re.compile(rb'SMP_STRESS_(PASS|FAIL) arch=([a-z0-9_]+)([^\r\n]*)\r?\n')
SMP = re.compile(rb'OK_SMP scope=hardware [^\r\n]*\r?\n')
CPUS = re.compile(rb'OK_SMP_CPUS scope=hardware online=(\d+)((?: cpu\d+=\d+:\d+:\d+:\d+:\d+)+)\r?\n')
LATENCY = re.compile(rb'OK_TIMER_LATENCY scope=hardware[^\r\n]*\r?\n')
KERNEL = re.compile(rb'OK_SMP_KERNEL scope=hardware debug=([01]) online=(\d+) ((?:[a-z_]+=\d+(?:/\d+)? )*[a-z_]+=\d+/\d+)((?: cpu\d+=\d+:\d+:\d+:\d+:\d+)+)\r?\n')
FAMILIES = re.compile(rb'OK_SMP_KERNEL_FAMILIES scope=hardware((?: [a-z0-9_]+=\d+)+)\r?\n')
DECLINES = re.compile(rb'OK_SMP_KERNEL_DECLINES scope=hardware((?: [a-z_]+=\d+)+)\r?\n')
KERNEL_FIELDS = ('sections', 'completed', 'declined', 'handoffs', 'concurrent', 'witnessed', 'max_parallel', 'spun',
                 'drains', 'drain_waits', 'bkl_acquired', 'bkl_contended', 'lock_violations', 'exclusive_asserts',
                 'drain_asserts', 'depth_asserts', 'section_asserts', 'cow_refused', 'purity_faults', 'shadow')
ASSERTS = ('lock_violations', 'exclusive_asserts', 'drain_asserts', 'depth_asserts', 'section_asserts',
           'cow_refused', 'purity_faults')
# What a release kernel counts as well: require_exclusive's direct callers,
# section_assert's unconditional sites and the copy-on-write refusal (and the
# shadow comparison, checked in both modes). Lock ranks, drain and depth
# checks and the decline digest exist only in a debug kernel (OK_LOCK_DEBUG).
RELEASE_ASSERTS = ('exclusive_asserts', 'section_asserts', 'cow_refused')
FAMILY_NAMES = ('getpid', 'gettid', 'clock_gettime', 'clock_getres', 'read', 'write', 'pread64', 'pwrite64',
                'lseek', 'fsync', 'fdatasync')
DECLINE_NAMES = ('runtime', 'personality', 'number', 'pending', 'console', 'descriptor', 'kind', 'append', 'size',
                 'fault', 'shadow', 'shutdown')
HOTPLUG = re.compile(rb'OK_SMP_HOTPLUG scope=hardware cycles=(\d+) failures=(\d+) cpu=(\d+)\r?\n')
HOTPLUG_BOOT = re.compile(rb'OK_SMP_HOTPLUG_BOOT scope=hardware cpu=1 stop=(\w+) parked_ipi=(\w+) '
                          rb'restart=(\w+) ipi=(\w+)\r?\n')
# Messages per round in the probe; files and forks are two per round.
MESSAGES = 4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receive(process, serial, done, deadline):
    while not done():
        if time.monotonic() > deadline:
            raise RuntimeError('timeout waiting for the guest')
        readable, _, _ = select.select([process.stdout], [], [], .1)
        if not readable:
            continue
        chunk = os.read(process.stdout.fileno(), 65536)
        if not chunk:
            raise RuntimeError('QEMU exited before the probe completed')
        # The stress transcript is long: scan only what arrived.
        tail = max(0, len(serial) - 64)
        serial.extend(chunk)
        if any(serial.find(bad, tail) >= 0 for bad in FAILURES):
            raise RuntimeError('guest or kernel failure in the stress transcript')


def cpu_counters(line):
    """{cpu: (user_entries, local_ticks, ipis_received, ipis_sent, shootdowns)} of one OK_SMP_CPUS line."""
    match = CPUS.fullmatch(line)
    counters = {}
    for token in match.group(2).decode().split():
        name, values = token.split('=')
        counters[int(name[3:])] = tuple(int(value) for value in values.split(':'))
    if len(counters) != int(match.group(1)):
        raise RuntimeError('OK_SMP_CPUS names a different number of CPUs than it reports online')
    return counters


def probe_entries(line, baseline, online):
    """User entries per CPU during the probe, from the probe's own OK_SMP_CPUS line.

    Every online CPU must have entered user code since `baseline`, the last
    report before the probe (None if there was none).
    """
    after = cpu_counters(line)
    if sorted(after) != list(range(online)):
        raise RuntimeError('OK_SMP_CPUS does not name CPUs 0..%d' % (online - 1))
    entered = {cpu: values[0] - (baseline.get(cpu, (0,))[0] if baseline else 0) for cpu, values in after.items()}
    idle = [cpu for cpu, value in entered.items() if value <= 0]
    if idle:
        raise RuntimeError('no user code entered on CPU %s during the probe' % ','.join(map(str, idle)))
    return after, entered


def kernel_sections(line):
    """The fields of one OK_SMP_KERNEL line: debug, online, the named counters, shadow and per-CPU tuples."""
    match = KERNEL.fullmatch(line)
    fields = dict(token.split('=') for token in match.group(3).decode().split())
    if tuple(fields) != KERNEL_FIELDS:
        raise RuntimeError('OK_SMP_KERNEL fields differ from the section report format')
    checked, mismatched = fields.pop('shadow').split('/')
    record = {name: int(value) for name, value in fields.items()}
    record.update(debug=int(match.group(1)), online=int(match.group(2)), shadow_checked=int(checked),
                  shadow_mismatched=int(mismatched))
    cpus = {}
    for token in match.group(4).decode().split():
        name, values = token.split('=')
        cpus[int(name[3:])] = dict(zip(('sections', 'concurrent', 'witnessed', 'bkl_acquired', 'bkl_contended'),
                                       (int(value) for value in values.split(':'))))
    record['cpus'] = cpus
    return record


def named_counts(match, names, what):
    counts = {}
    for token in match.group(1).decode().split():
        name, value = token.split('=')
        counts[name] = int(value)
    if tuple(counts) != names:
        raise RuntimeError(what + ' fields differ from the section report format')
    return counts


def check_sections(record, kernel, families, online, files, mode='debug'):
    """The kernel-section requirements for one passing probe run."""
    problems = []
    if kernel['debug'] != (1 if mode == 'debug' else 0):
        problems.append('OK_SMP_KERNEL debug=%d for a %s kernel' % (kernel['debug'], mode))
    if kernel['online'] != online:
        problems.append('OK_SMP_KERNEL online=%d, boot online=%d' % (kernel['online'], online))
    floors = dict(fsync=files, write=2 * files, read=2 * files, lseek=2 * files)
    for name, floor in floors.items():
        if families[name] < floor:
            problems.append('%s=%d below the probe floor %d' % (name, families[name], floor))
    if online >= 2:
        running = [cpu for cpu, values in kernel['cpus'].items() if values['sections'] > 0]
        if len(running) < 2:
            problems.append('sections ran on %d CPU(s), not two or more' % len(running))
        for name in ('concurrent', 'witnessed'):
            if kernel[name] <= 0:
                problems.append(name + '=0')
        if kernel['max_parallel'] < 2:
            problems.append('max_parallel=%d' % kernel['max_parallel'])
    for name in ASSERTS if kernel['debug'] == 1 else RELEASE_ASSERTS:
        if kernel[name] != 0:
            problems.append('%s=%d' % (name, kernel[name]))
    if kernel['shadow_mismatched'] != 0:
        problems.append('shadow mismatches=%d' % kernel['shadow_mismatched'])
    record['section_requirements'] = 'pass' if not problems else problems
    if problems:
        raise RuntimeError('kernel section requirements failed: ' + '; '.join(problems))


def tcg_threads(pid):
    """QEMU's TCG vCPU threads by name: 'CPU n/TCG' per vCPU is multi-threaded TCG."""
    names = []
    try:
        for task in sorted(Path('/proc/%d/task' % pid).iterdir()):
            names.append((task / 'comm').read_text().strip())
    except OSError:
        return 'unknown', []
    tcg = [name for name in names if name.endswith('/TCG')]
    if tcg and all(name.startswith('CPU ') for name in tcg):
        mode = 'multi-threaded-tcg' if len(tcg) > 1 else 'single-vcpu-tcg'
    elif tcg:
        mode = 'single-threaded-tcg'
    else:
        mode = 'unknown'
    return mode, tcg


def hotplug_cycles(serial, final, cpus, baseline=None):
    """The kernel's CPU hotplug cycles: {cycles, failures, cpu, probe_cycles}
    of `final`, the OK_SMP_HOTPLUG line of the probe's exit report.

    Every OK_SMP_HOTPLUG line in `serial` is cumulative: counters never go
    back and the CPU stays the same. `final` must show failures=0 and a
    secondary CPU below `cpus`, and more cycles than `baseline`, the last
    OK_SMP_HOTPLUG line before the probe started (None: none printed, 0
    cycles): cycling began at userland start, so only cycles beyond the
    baseline ran under the probe's load.
    """
    reports = [tuple(int(value) for value in match.groups()) for match in HOTPLUG.finditer(serial)]
    for previous, current in zip(reports, reports[1:]):
        if current[0] < previous[0] or current[1] < previous[1] or current[2] != previous[2]:
            raise RuntimeError('OK_SMP_HOTPLUG counters went back or its CPU changed')
    cycles, failures, cpu = (int(value) for value in final.groups())
    before = int(baseline.group(1)) if baseline is not None else 0
    if failures != 0 or not 1 <= cpu < cpus:
        raise RuntimeError(f'CPU hotplug cycles={cycles} failures={failures} cpu={cpu}')
    if cycles <= before:
        raise RuntimeError(f'no CPU hotplug cycle during the probe: cycles={cycles}, {before} before it')
    return dict(cycles=cycles, failures=failures, cpu=cpu, probe_cycles=cycles - before)


def hotplug_boot(serial):
    """The boot test point's OK_SMP_HOTPLUG_BOOT line, or None when the kernel
    printed none. Printed at most once, and every check must pass."""
    if serial.count(b'OK_SMP_HOTPLUG_BOOT ') == 0:
        return None
    lines = HOTPLUG_BOOT.findall(serial)
    if len(lines) != 1 or serial.count(b'OK_SMP_HOTPLUG_BOOT ') != 1:
        raise RuntimeError('expected one complete OK_SMP_HOTPLUG_BOOT line')
    if any(verdict != b'pass' for verdict in lines[0]):
        raise RuntimeError('CPU hotplug boot test point failed: ' + b' '.join(lines[0]).decode())
    return HOTPLUG_BOOT.search(serial).group(0).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    for name in ('qemu', 'kernel', 'kernel-sdk', 'rootfs-tree', 'probe', 'musl-build', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--smp', type=int, default=2, help='QEMU vCPUs (default 2)')
    # The kernel's 16 system-wide stream buffers bound the probe to six workers.
    parser.add_argument('--workers', type=int, default=6, help='concurrent probe workers (1-6, default 6)')
    parser.add_argument('--rounds', type=int, default=40, help='rounds per worker (default 40)')
    parser.add_argument('--allow-up', action='store_true',
                        help='development only: accept a UP boot on an SMP profile and skip the per-CPU check')
    parser.add_argument('--require-hotplug', action='store_true',
                        help='the kernel must report CPU hotplug cycles (built with smp_hotplug_test)')
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--smp-sections', choices=('on', 'off'),
                        help='the kernel runs converted syscalls as kernel sections (on) or was built with '
                             'smp_sections=n (off); default on for x86_64, aarch64 and rv64, off elsewhere')
    args = parser.parse_args()
    # Only the SMP profiles build kernel sections; the others never print their report.
    if args.smp_sections is None:
        args.smp_sections = 'on' if args.arch in SMP_PROFILES else 'off'
    elif args.smp_sections == 'on' and args.arch not in SMP_PROFILES:
        raise SystemExit(f'--smp-sections on needs x86_64, aarch64 or rv64; {args.arch} builds no kernel sections')
    if not 1 <= args.smp <= SMP_MAX_CPUS:
        raise SystemExit(f'--smp must be from 1 to {SMP_MAX_CPUS}')
    if not 1 <= args.workers <= 6 or not 1 <= args.rounds <= 10000:
        raise SystemExit('--workers must be from 1 to 6 and --rounds from 1 to 10000')
    validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    musl = admit_musl_build(args.musl_build.resolve(), args.arch)
    manifest_path = args.probe.resolve().parent / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('architecture') != args.arch or manifest.get('mode') != args.mode or
            manifest.get('status') != 'built-not-executed' or manifest.get('executed') is not False or
            manifest.get('source_manifest_sha256') != sha(args.musl_build.resolve() / 'manifest.json') or
            musl['mode'] != args.mode or manifest.get('elf_sha256') != sha(args.probe.resolve()) or
            manifest.get('probe_sha256') != sha(TOOLS.parent / 'tests/musl/smp_stress.c')):
        raise ValueError('stress probe is not the exact mode-matching musl build of tests/musl/smp_stress.c')
    inspect_elf(args.probe.resolve(), args.arch)
    if args.probe.read_bytes()[7] != 3:
        raise ValueError('stress probe lacks the Linux ELF personality')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / 'root'
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    shutil.copy2(args.probe.resolve(), root / 'bin/smp-stress')
    (root / 'bin/smp-stress').chmod(0o755)
    disk = out / 'rootfs.ext4.img'
    with (out / 'package.log').open('xb') as log:
        subprocess.run([sys.executable, '-B', str(TOOLS / 'mkext4.py'), '--root', str(root), '--out', str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    kernel = out / 'kernel-input.bin'
    shutil.copy2(args.kernel.resolve(), kernel)
    # The native PPC profile is single-CPU; command_for refuses more vCPUs there.
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, 'none', native_profile=True, cpus=args.smp)
    # Named host threads let the receipt record QEMU's TCG thread mode.
    command += ['-name', 'smp-stress,debug-threads=on']
    record = dict(schema=1, architecture=args.arch, mode=args.mode, scope='actual-static-musl-qemu-smp-stress',
                  status='running', command=command, cpus=args.smp, smp=args.smp > 1, allow_up=args.allow_up,
                  workers=args.workers, rounds=args.rounds, smp_sections=args.smp_sections,
                  require_hotplug=args.require_hotplug,
                  sdk_manifest_sha256=sha(args.kernel_sdk.resolve() / 'manifest.json'),
                  musl_manifest_sha256=sha(args.musl_build.resolve() / 'manifest.json'),
                  probe_manifest_sha256=sha(manifest_path), probe_sha256=sha(args.probe.resolve()),
                  kernel_sha256=sha(kernel), qemu_sha256=sha(args.qemu.resolve()), input_disk_sha256=sha(disk),
                  script_sha256=sha(Path(__file__)), physical=False)
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        began = time.monotonic()
        receive(process, serial, lambda: b'OK_SYSTEM_GUI boot=complete' in serial and PROMPT in serial,
                time.monotonic() + args.timeout)
        record['boot_seconds'] = round(time.monotonic() - began, 2)
        record['accelerator'], record['tcg_threads'] = tcg_threads(process.pid)
        start = len(serial)
        boot = SMP.findall(serial)
        if len(boot) != 1:
            raise RuntimeError(f'expected one kernel OK_SMP hardware line before the prompt, saw {len(boot)}')
        record['kernel_smp'] = boot[0].decode().strip()
        fields = smp_fields(record['kernel_smp'])
        problem = smp_problem(fields, args.arch, args.smp, allow_up=args.allow_up)
        if problem:
            raise RuntimeError('kernel SMP report does not fit the guest: ' + problem)
        online = int(fields['online'])
        record['online_cpus'] = online
        if (boot_hotplug := hotplug_boot(serial)) is not None:
            if online < 2:
                raise RuntimeError('kernel printed OK_SMP_HOTPLUG_BOOT for a UP boot')
            record['kernel_smp_hotplug_boot'] = boot_hotplug
        # Counters are cumulative: the last report before the probe is its baseline.
        baseline = list(re.finditer(CPUS, serial))
        baseline = cpu_counters(baseline[-1].group(0)) if baseline else None
        hotplug_baseline = list(HOTPLUG.finditer(serial))
        hotplug_baseline = hotplug_baseline[-1] if hotplug_baseline else None

        process.stdin.write(b'/bin/smp-stress %d %d\n' % (args.workers, args.rounds))
        process.stdin.flush()
        began = time.monotonic()
        state = {'result': None, 'scanned': start}

        # The probe's exit prints the kernel's report; wait for it as well.
        def finished():
            if state['result'] is None:
                state['result'] = RESULT.search(serial, max(start, state['scanned'] - 256))
                state['scanned'] = len(serial)
                if state['result'] is None:
                    return False
            match = state['result']
            after = serial[match.end():]
            if PROMPT not in after:
                return False
            if match.group(1) != b'PASS':
                return True
            hotplug = args.require_hotplug or HOTPLUG.search(serial) is not None
            return (LATENCY.search(after) is not None and (online < 2 or CPUS.search(after) is not None) and
                    (args.smp_sections == 'off' or DECLINES.search(after) is not None) and
                    (not hotplug or HOTPLUG.search(after) is not None))
        receive(process, serial, finished, time.monotonic() + args.timeout)
        record['probe_seconds'] = round(time.monotonic() - began, 2)
        result = state['result']
        record['result'] = result.group(0).decode().strip()
        record['transcript_bytes'] = len(serial)
        if result.group(1) != b'PASS' or result.group(2).decode() != args.arch:
            raise RuntimeError('stress probe failed: ' + record['result'])
        counts = dict(token.split('=') for token in result.group(3).decode().split())
        total = args.workers * args.rounds
        expected = dict(workers=args.workers, rounds=args.rounds, files=2 * total, messages=MESSAGES * total,
                        forks=2 * total)
        if any(int(counts.get(name, -1)) != value for name, value in expected.items()):
            raise RuntimeError('stress probe counts differ from the requested run: ' + record['result'])
        record['guest_seconds'] = float(counts['seconds'])

        # The report the probe's own exit prints; its workers' exits print earlier ones.
        reports = list(re.finditer(CPUS, serial[result.end():]))
        if online < 2:
            if reports:
                raise RuntimeError('kernel printed OK_SMP_CPUS for a UP boot')
            record['per_cpu_user_entries'] = 'skipped-up'
        else:
            line = reports[-1].group(0)
            record['kernel_smp_cpus'] = line.decode().strip()
            if baseline is not None:
                record['baseline_user_entries'] = {str(cpu): values[0] for cpu, values in baseline.items()}
            after, entered = probe_entries(line, baseline, online)
            record['cpu_counters'] = {str(cpu): dict(zip(('user_entries', 'local_ticks', 'ipis_received',
                                                          'ipis_sent', 'shootdowns'), values))
                                      for cpu, values in after.items()}
            record['probe_user_entries'] = {str(cpu): value for cpu, value in entered.items()}
            record['per_cpu_user_entries'] = 'pass'
        if args.smp_sections == 'off':
            if b'OK_SMP_KERNEL' in serial:
                raise RuntimeError('a kernel without sections printed OK_SMP_KERNEL')
            record['section_requirements'] = 'absent-as-required'
        else:
            # The report the probe's own exit prints, as for OK_SMP_CPUS.
            tail = serial[result.end():]
            kernels = list(re.finditer(KERNEL, tail))
            families = list(re.finditer(FAMILIES, tail))
            declines = list(re.finditer(DECLINES, tail))
            if not kernels or not families or not declines:
                raise RuntimeError('no OK_SMP_KERNEL report after the probe')
            kernel = kernel_sections(kernels[-1].group(0))
            family_counts = named_counts(families[-1], FAMILY_NAMES, 'OK_SMP_KERNEL_FAMILIES')
            decline_counts = named_counts(declines[-1], DECLINE_NAMES, 'OK_SMP_KERNEL_DECLINES')
            record['kernel_sections_line'] = kernels[-1].group(0).decode().strip()
            record['kernel_sections'] = kernel
            record['kernel_families'] = family_counts
            record['kernel_declines'] = decline_counts
            check_sections(record, kernel, family_counts, online, int(counts['files']), args.mode)
        cycles = list(HOTPLUG.finditer(serial[result.end():]))
        if cycles:
            if online < 2:
                raise RuntimeError('kernel printed OK_SMP_HOTPLUG for a UP boot')
            record['kernel_smp_hotplug'] = cycles[-1].group(0).decode().strip()
            if hotplug_baseline is not None:
                record['kernel_smp_hotplug_baseline'] = hotplug_baseline.group(0).decode().strip()
            record['hotplug'] = hotplug_cycles(serial, cycles[-1], online, hotplug_baseline)
        elif args.require_hotplug or HOTPLUG.search(serial):
            raise RuntimeError('the probe exit report lacks OK_SMP_HOTPLUG')
        record['status'] = 'pass'
    except BaseException as error:
        record.update(status='fail', failure=repr(error))
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()
        (out / 'serial.log').write_bytes(serial)
        record['serial_sha256'] = sha(out / 'serial.log')
        (out / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('PASS ' + args.arch + '/' + args.mode + ' smp=' + str(args.smp) +
          (' allow-up' if args.allow_up else '') + ': ' + record['result'])
    print(record['kernel_smp'])
    if 'kernel_smp_cpus' in record:
        print(record['kernel_smp_cpus'])
    if 'kernel_sections_line' in record:
        print(record['kernel_sections_line'])
    print('accelerator=' + record['accelerator'])
    if 'kernel_smp_hotplug' in record:
        print(record['kernel_smp_hotplug'])


if __name__ == '__main__':
    main()
