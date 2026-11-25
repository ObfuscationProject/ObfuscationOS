#!/usr/bin/env python3
"""Run the static-musl CPU sysfs probe (tests/musl/cpu_sysfs_probe.c) on scratch ext4 with N vCPUs.

The probe reads /sys/devices/system/cpu (the kernel's CpuSysFileSystem, mounted at /sys by the boot module),
compares it with sched_getaffinity, sysconf(_SC_NPROCESSORS_ONLN) and sched_getcpu, pins itself to each online
CPU in turn, and checks the kernfs refusals (cpu0/online, read-only attributes, bad writes, uid 1000); it prints
one CPU_SYSFS_PASS line and never takes a CPU offline. The boot must mount /sys, the kernel's OK_SMP line must
fit the guest, the probe must see every vCPU present and online on the SMP profiles (x86_64, aarch64, rv64) and
one CPU elsewhere, and on SMP boots the OK_SMP_HOTPLUG_USER report its exit prints must show its no-op writes
and no failure. QEMU evidence (TCG), not physical hardware.
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

from qemu_distro import SMP_MAX_CPUS, command_for, smp_fields, smp_problem
from test_smp_stress import tcg_threads
TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from build_musl_probe import admit_musl_build
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from musl_source import inspect_elf
from dynamic_startup_observer import FAILURES

PROMPT = b'oksh> '
RESULT = re.compile(rb'CPU_SYSFS_(PASS|FAIL) arch=([a-z0-9_]+)([^\r\n]*)\r?\n')
HOTPLUG = re.compile(rb'OK_SMP_HOTPLUG_USER scope=hardware((?: [a-z_]+=\d+)+)\r?\n')
MOUNTED = b'OK_SYS source=kernel tree=devices/system/cpu'
SMP = re.compile(rb'OK_SMP scope=hardware [^\r\n]*\r?\n')
CPUS = re.compile(rb'OK_SMP_CPUS scope=hardware online=(\d+)((?: cpu\d+=\d+:\d+:\d+:\d+:\d+)+)\r?\n')
LATENCY = re.compile(rb'OK_TIMER_LATENCY scope=hardware[^\r\n]*\r?\n')


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
        # Scan only what arrived.
        tail = max(0, len(serial) - 64)
        serial.extend(chunk)
        if any(serial.find(bad, tail) >= 0 for bad in FAILURES):
            raise RuntimeError('guest or kernel failure in the transcript')


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    for name in ('qemu', 'kernel', 'kernel-sdk', 'rootfs-tree', 'probe', 'musl-build', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--smp', type=int, default=2, help='QEMU vCPUs (default 2)')
    parser.add_argument('--allow-up', action='store_true',
                        help='development only: accept a UP boot on an SMP profile and skip the per-CPU check')
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    if not 1 <= args.smp <= SMP_MAX_CPUS:
        raise SystemExit(f'--smp must be from 1 to {SMP_MAX_CPUS}')
    validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    musl = admit_musl_build(args.musl_build.resolve(), args.arch)
    manifest_path = args.probe.resolve().parent / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('architecture') != args.arch or manifest.get('mode') != args.mode or
            manifest.get('status') != 'built-not-executed' or manifest.get('executed') is not False or
            manifest.get('source_manifest_sha256') != sha(args.musl_build.resolve() / 'manifest.json') or
            musl['mode'] != args.mode or manifest.get('elf_sha256') != sha(args.probe.resolve()) or
            manifest.get('probe_sha256') != sha(TOOLS.parent / 'tests/musl/cpu_sysfs_probe.c')):
        raise ValueError('probe is not the exact mode-matching musl build of tests/musl/cpu_sysfs_probe.c')
    inspect_elf(args.probe.resolve(), args.arch)
    if args.probe.read_bytes()[7] != 3:
        raise ValueError('probe lacks the Linux ELF personality')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / 'root'
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    shutil.copy2(args.probe.resolve(), root / 'bin/cpu-sysfs-probe')
    (root / 'bin/cpu-sysfs-probe').chmod(0o755)
    disk = out / 'rootfs.ext4.img'
    with (out / 'package.log').open('xb') as log:
        subprocess.run([sys.executable, '-B', str(TOOLS / 'mkext4.py'), '--root', str(root), '--out', str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    kernel = out / 'kernel-input.bin'
    shutil.copy2(args.kernel.resolve(), kernel)
    # The native PPC profile is single-CPU; command_for refuses more vCPUs there.
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, 'none', native_profile=True, cpus=args.smp)
    # Named host threads let the receipt record QEMU's TCG thread mode.
    command += ['-name', 'cpu-sysfs-probe,debug-threads=on']
    record = dict(schema=1, architecture=args.arch, mode=args.mode, scope='actual-static-musl-qemu-cpu-sysfs',
                  status='running', command=command, cpus=args.smp, smp=args.smp > 1, allow_up=args.allow_up,
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
        # Counters are cumulative: the last report before the probe is its baseline.
        baseline = list(re.finditer(CPUS, serial))
        baseline = cpu_counters(baseline[-1].group(0)) if baseline else None

        process.stdin.write(b'/bin/cpu-sysfs-probe\n')
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
            return LATENCY.search(after) is not None and (online < 2 or (CPUS.search(after) is not None and
                                                                       HOTPLUG.search(after) is not None))
        receive(process, serial, finished, time.monotonic() + args.timeout)
        record['probe_seconds'] = round(time.monotonic() - began, 2)
        result = state['result']
        record['result'] = result.group(0).decode().strip()
        record['transcript_bytes'] = len(serial)
        if result.group(1) != b'PASS' or result.group(2).decode() != args.arch:
            raise RuntimeError('probe failed: ' + record['result'])
        counts = {key: int(value) for key, value in (token.split('=') for token in result.group(3).decode().split())}
        record['probe'] = counts
        if MOUNTED not in serial[:start]:
            raise RuntimeError('the boot did not mount the CPU sysfs tree at /sys')
        # No CPU went offline: every started CPU is present and online, and the
        # probe pinned itself to each of them.
        for name in ('present', 'online', 'nproc_all', 'sysconf', 'pinned'):
            if counts.get(name) != online:
                raise RuntimeError(f'probe {name}={counts.get(name)} differs from the {online} online CPUs')
        if counts.get('affinity_bytes') not in (4, 8):
            raise RuntimeError('sched_getaffinity did not return one native word: ' + record['result'])
        if counts.get('negatives', 0) < (8 if online > 1 else 6):
            raise RuntimeError('probe skipped refusals: ' + record['result'])
        tail = serial[result.end():]
        if b'OK_SMP_AFFINITY_BROKEN' in tail:
            raise RuntimeError('pinning to online CPUs broke an affinity')
        hotplug = list(HOTPLUG.finditer(tail))
        if online < 2:
            if hotplug:
                raise RuntimeError('kernel printed OK_SMP_HOTPLUG_USER for a UP boot')
            record['hotplug_user'] = 'skipped-up'
        else:
            if not hotplug:
                raise RuntimeError('no OK_SMP_HOTPLUG_USER report after the probe')
            fields = {key: int(value) for key, value in
                      (token.split('=') for token in hotplug[-1].group(1).decode().split())}
            record['hotplug_user'] = fields
            # Two no-op writes (write and pwrite of the current state), nothing else.
            if (fields['requests'] < 2 or fields['noop'] < 2 or fields['offline'] or fields['online'] or
                    fields['failures'] or fields['busy'] or fields['orphaned'] or fields['wedged'] or
                    fields['affinity_broken']):
                raise RuntimeError('unexpected hotplug activity: ' + hotplug[-1].group(0).decode().strip())

        # The report the probe's own exit prints; its thread's exit prints an earlier one.
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
    print('accelerator=' + record['accelerator'])


if __name__ == '__main__':
    main()
