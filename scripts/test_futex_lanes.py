#!/usr/bin/env python3
"""Run the static-musl futex probes in one native boot (the kernel's futex lanes) on N vCPUs.

One scratch ext4 root holds every probe under /bin; the guest shell runs them
in turn and each must print its pass line before the next starts:

  futex_buckets               wait/wake, timeouts, a timed-out waiter against
                              WAKE(1), CMP_REQUEUE, signal against wake
  native_futex_signal         EINTR, SA_RESTART restarts and timeouts of raw
                              FUTEX_WAIT traps interrupted by caught signals
  native_futex_wake_operation FUTEX_WAKE_OP on private and anonymous shared words
  native_shared_futex         shared keys across fork
  native_threads              clone, CLONE_CHILD_CLEARTID exit wakes
  native_robust_lists         robust-list owner death
  private_futex               private-word layouts, mismatch and timeout
  futex_smp_atomic            FUTEX_WAKE_OP against user atomics

On ppc the three probes that format with printf run as their ppc_ wrappers
(select them with --only; the default list is the eight above).

After the probes the kernel's own reports must show no failed lock check
(every OK_SMP_KERNEL_CHECKS counter 0, max_lock_depth <= 12) and, in a debug
kernel, futex bucket acquisitions (OK_SMP_LOCKS futex=<acquired>:<contended>).
This is QEMU evidence of the user-visible behaviour, not physical hardware,
and it does not show two racing threads running at the same instant.
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
SMP = re.compile(rb'OK_SMP scope=hardware [^\r\n]*\r?\n')
CHECKS = re.compile(rb'OK_SMP(?:_KERNEL)?_CHECKS scope=hardware debug=(\d)([^\r\n]*)\r?\n')
LOCKS = re.compile(rb'OK_SMP_LOCKS scope=hardware debug=(\d)[^\r\n]* futex=(\d+):(\d+)[^\r\n]*\r?\n')
# name -> (arguments, pass line prefix). '{arch}' is the profile name.
PROBES = {
    'futex_buckets': ('{rounds}', b'FUTEX_BUCKETS_PASS arch={arch} '),
    'native_futex_signal': ('', b'FUTEX_SIGNAL_PASS arch={arch} '),
    'native_futex_wake_operation': ('', b'OK_MUSL_FUTEX_WAKE_OP version=1 '),
    'native_shared_futex': ('', b'OK_MUSL_SHARED_FUTEX scope=actual-native '),
    'native_threads': ('', b'OK_MUSL_THREADS clone=pass '),
    'native_robust_lists': ('', b'OK_MUSL_ROBUST_LISTS registration=pass '),
    'private_futex': ('', b'OK_MUSL_PRIVATE_FUTEX mismatch=pass '),
    'futex_smp_atomic': ('{atomic_rounds}', b'FUTEX_SMP_ATOMIC_PASS arch={arch} '),
    # The same probes for ppc, whose libc printf links only through
    # tests/musl/ppc_integer_printf.h (the wrappers include the sources above).
    'ppc_native_futex_signal': ('', b'FUTEX_SIGNAL_PASS arch={arch} '),
    'ppc_native_futex_wake_operation': ('', b'OK_MUSL_FUTEX_WAKE_OP version=1 '),
    'ppc_futex_smp_atomic': ('{atomic_rounds}', b'FUTEX_SMP_ATOMIC_PASS arch={arch} '),
}


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
            raise RuntimeError('QEMU exited before the probes completed')
        tail = max(0, len(serial) - 64)
        serial.extend(chunk)
        if any(serial.find(bad, tail) >= 0 for bad in FAILURES):
            raise RuntimeError('guest or kernel failure in the transcript')


def admit_probe(directory, name, arch, mode, musl):
    manifest = json.loads((directory / 'manifest.json').read_text())
    elf = directory / 'bootstrap.elf'
    if (manifest.get('architecture') != arch or manifest.get('mode') != mode or
            manifest.get('status') != 'built-not-executed' or manifest.get('executed') is not False or
            manifest.get('source_manifest_sha256') != sha(musl / 'manifest.json') or
            manifest.get('elf_sha256') != sha(elf) or
            manifest.get('probe_sha256') != sha(TOOLS.parent / 'tests/musl' / (name + '.c'))):
        raise ValueError('probe is not the exact mode-matching musl build of tests/musl/%s.c' % name)
    inspect_elf(elf, arch)
    if elf.read_bytes()[7] != 3:
        raise ValueError('probe lacks the Linux ELF personality: ' + name)
    return manifest, elf


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    for name in ('qemu', 'kernel', 'kernel-sdk', 'rootfs-tree', 'probes', 'musl-build', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--only', action='append', choices=sorted(PROBES),
                        help='run only these probes (default: all, in the listed order)')
    parser.add_argument('--smp', type=int, default=1, help='QEMU vCPUs (default 1)')
    parser.add_argument('--rounds', type=int, default=200, help='futex_buckets wait/wake rounds (default 200)')
    parser.add_argument('--atomic-rounds', type=int, default=2000, help='futex_smp_atomic rounds (default 2000)')
    parser.add_argument('--timeout', type=float, default=900, help='seconds for the boot and for each probe')
    args = parser.parse_args()
    if not 1 <= args.smp <= SMP_MAX_CPUS:
        raise SystemExit(f'--smp must be from 1 to {SMP_MAX_CPUS}')
    names = [name for name in PROBES if (name in args.only if args.only else not name.startswith('ppc_'))]
    validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    musl = args.musl_build.resolve()
    admitted = admit_musl_build(musl, args.arch)
    if admitted['mode'] != args.mode:
        raise ValueError('musl build mode differs from the kernel mode')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / 'root'
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    probes = {}
    for name in names:
        manifest, elf = admit_probe(args.probes.resolve() / name, name, args.arch, args.mode, musl)
        target = root / 'bin' / name.replace('_', '-')
        shutil.copy2(elf, target)
        target.chmod(0o755)
        probes[name] = dict(elf_sha256=sha(elf), probe_sha256=manifest['probe_sha256'])
    disk = out / 'rootfs.ext4.img'
    with (out / 'package.log').open('xb') as log:
        subprocess.run([sys.executable, '-B', str(TOOLS / 'mkext4.py'), '--root', str(root), '--out', str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    kernel = out / 'kernel-input.bin'
    shutil.copy2(args.kernel.resolve(), kernel)
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, 'none', native_profile=True, cpus=args.smp)
    command += ['-name', 'futex-lanes,debug-threads=on']
    record = dict(schema=1, architecture=args.arch, mode=args.mode, scope='actual-static-musl-qemu-futex-lanes',
                  status='running', command=command, cpus=args.smp, probes=probes, results={},
                  sdk_manifest_sha256=sha(args.kernel_sdk.resolve() / 'manifest.json'),
                  musl_manifest_sha256=sha(musl / 'manifest.json'), kernel_sha256=sha(kernel),
                  qemu_sha256=sha(args.qemu.resolve()), input_disk_sha256=sha(disk),
                  script_sha256=sha(Path(__file__)), physical=False, overlap_claim='none')
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        began = time.monotonic()
        receive(process, serial, lambda: b'OK_SYSTEM_GUI boot=complete' in serial and PROMPT in serial,
                time.monotonic() + args.timeout)
        record['boot_seconds'] = round(time.monotonic() - began, 2)
        record['accelerator'], record['tcg_threads'] = tcg_threads(process.pid)
        boot = SMP.findall(serial)
        if len(boot) != 1:
            raise RuntimeError(f'expected one kernel OK_SMP hardware line before the prompt, saw {len(boot)}')
        record['kernel_smp'] = boot[0].decode().strip()
        problem = smp_problem(smp_fields(record['kernel_smp']), args.arch, args.smp, allow_up=False)
        if problem:
            raise RuntimeError('kernel SMP report does not fit the guest: ' + problem)
        first = len(serial)
        for name in names:
            arguments, marker = PROBES[name]
            arguments = arguments.format(rounds=args.rounds, atomic_rounds=args.atomic_rounds)
            marker = marker.replace(b'{arch}', args.arch.encode())
            start = len(serial)
            process.stdin.write(('/bin/%s %s\n' % (name.replace('_', '-'), arguments)).rstrip().encode() + b'\n')
            process.stdin.flush()
            began = time.monotonic()
            state = {'scanned': start}

            def finished():
                # The probe's own line, then the shell's next prompt.
                at = serial.find(marker, start)
                if at < 0:
                    # A whole failure line: the reason follows the tag.
                    failed = re.search(rb'(?:[A-Z_]*_FAIL[ \r\n]|FAIL arch=)[^\n]*\n',
                                       bytes(serial[max(start, state['scanned'] - 512):]))
                    state['scanned'] = len(serial)
                    if failed:
                        raise RuntimeError('probe %s failed: %s' % (name, failed.group(0).decode(errors='replace').strip()))
                    if serial.find(PROMPT, start) >= 0:
                        raise RuntimeError('probe %s returned to the shell without its pass line' % name)
                    return False
                return serial.find(PROMPT, at) >= 0
            receive(process, serial, finished, time.monotonic() + args.timeout)
            line = re.search(re.escape(marker) + rb'[^\r\n]*', serial[start:]).group(0).decode()
            record['results'][name] = dict(line=line, seconds=round(time.monotonic() - began, 2))
            print('PASS %s %s' % (name, line), flush=True)
        # The kernel reports print at each process exit; take the last ones.
        tail = bytes(serial[first:])
        checks = list(CHECKS.finditer(tail))
        locks = list(LOCKS.finditer(tail))
        if not checks or not locks:
            raise RuntimeError('no kernel check or lock report after the probes')
        fields = dict(token.split('=') for token in checks[-1].group(2).decode().split())
        bad = {key: value for key, value in fields.items() if key != 'max_lock_depth' and value != '0'}
        if bad or int(fields.get('max_lock_depth', '99')) > 12:
            raise RuntimeError('kernel lock checks failed: ' + checks[-1].group(0).decode().strip())
        record['kernel_checks'] = checks[-1].group(0).decode().strip()
        record['kernel_locks'] = locks[-1].group(0).decode().strip()
        debug, acquired, contended = (int(locks[-1].group(index)) for index in (1, 2, 3))
        record['futex_bucket_acquired'], record['futex_bucket_contended'] = acquired, contended
        if debug and acquired == 0:
            raise RuntimeError('a debug kernel counted no futex bucket acquisition')
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
    print('PASS %s/%s smp=%d futex lanes=%d %s' % (args.arch, args.mode, args.smp, len(names), record['kernel_locks']))
    print(record['kernel_checks'])


if __name__ == '__main__':
    main()
