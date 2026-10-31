#!/usr/bin/env python3
"""Measure the guest's clocks against the host's (tests/musl/clock_drift.c).

The probe answers each request line with CLOCK_MONOTONIC and CLOCK_REALTIME.
Every sample is bracketed by the host's monotonic clock and wall clock read
before the request is written and after the answer arrives, so the guest read
lies inside that interval. The monotonic drift is fitted over all samples and
bounded strictly by the first and last brackets; the wall clock's offset and
drift are reported against the host's wall clock, which QEMU's RTC follows.
After the samples the probe runs three seconds of user code without system
calls, so the kernel's OK_TIMER_LATENCY line covers the tick that preempts
user code as well as the one that ends the idle wait.
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

from qemu_distro import command_for
TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from build_musl_probe import admit_musl_build
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from musl_source import inspect_elf
from dynamic_startup_observer import FAILURES

PROMPT = b'oksh> '
SAMPLE = re.compile(rb'CLOCK seq=(\d+) mono=(\d+)\.(\d{9}) real=(?:(\d+)\.(\d{9})|none)[^\r\n]*\r?\n')
READY = re.compile(rb'CLOCK_READY arch=([a-z0-9_]+)\r?\n')
FAILED = re.compile(rb'CLOCK_FAIL[^\r\n]*')
BUSY = re.compile(rb'(CLOCK_BUSY[^\r\n]*)\r?\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receive(process, serial, done, deadline):
    while not done():
        if time.monotonic() > deadline:
            raise RuntimeError('timeout waiting for the guest')
        readable, _, _ = select.select([process.stdout], [], [], .01)
        if not readable:
            continue
        chunk = os.read(process.stdout.fileno(), 8192)
        if not chunk:
            raise RuntimeError('QEMU exited before the probe completed')
        serial.extend(chunk)
        if any(bad in serial for bad in FAILURES) or FAILED.search(serial):
            raise RuntimeError('guest or kernel failure in the clock transcript')


def fit(points):
    """Least-squares slope and the largest residual of (x, y) pairs."""
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    slope = sum((x - mx) * (y - my) for x, y in points) / sxx
    residual = max(abs(y - my - slope * (x - mx)) for x, y in points)
    return slope, residual


def analyse(samples):
    """Drift in parts per million of the guest clocks against the host's."""
    first, last = samples[0], samples[-1]
    host = [((s['sent_ns'] + s['received_ns']) / 2, s['mono_ns']) for s in samples]
    slope, residual = fit(host)
    guest_span = last['mono_ns'] - first['mono_ns']
    # The guest reads lie inside their brackets, so the host span between
    # them lies between these two.
    shortest = last['sent_ns'] - first['received_ns']
    longest = last['received_ns'] - first['sent_ns']
    result = dict(samples=len(samples), window_s=round((longest + shortest) / 2e9, 3),
                  monotonic_drift_ppm=round((slope - 1) * 1e6, 3),
                  monotonic_drift_bound_ppm=[round((guest_span / longest - 1) * 1e6, 3),
                                             round((guest_span / shortest - 1) * 1e6, 3)],
                  monotonic_residual_us=round(residual / 1e3, 3),
                  bracket_max_us=round(max(s['received_ns'] - s['sent_ns'] for s in samples) / 1e3, 3))
    walls = [s for s in samples if s['real_ns'] is not None]
    if len(walls) == len(samples):
        wall = [((s['wall_sent_ns'] + s['wall_received_ns']) / 2, s['real_ns']) for s in walls]
        wall_slope, _ = fit(wall)
        offsets = [y - x for x, y in wall]
        result.update(realtime_offset_ms=round(offsets[0] / 1e6, 3),
                      realtime_offset_change_ms=round((offsets[-1] - offsets[0]) / 1e6, 3),
                      realtime_drift_ppm=round((wall_slope - 1) * 1e6, 3))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    for name in ('qemu', 'kernel', 'kernel-sdk', 'rootfs-tree', 'probe', 'musl-build', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--window', type=float, default=120, help='seconds between the first and last sample')
    parser.add_argument('--samples', type=int, default=13)
    parser.add_argument('--limit-ppm', type=float, default=100,
                        help='largest admitted monotonic drift; the strict bound must reach inside it')
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    if args.samples < 3 or args.window <= 0:
        raise ValueError('the drift needs at least three samples over a positive window')
    validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    musl = admit_musl_build(args.musl_build.resolve(), args.arch)
    manifest_path = args.probe.resolve().parent / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('architecture') != args.arch or manifest.get('mode') != args.mode or
            manifest.get('status') != 'built-not-executed' or manifest.get('executed') is not False or
            manifest.get('source_manifest_sha256') != sha(args.musl_build.resolve() / 'manifest.json') or
            musl['mode'] != args.mode or manifest.get('elf_sha256') != sha(args.probe.resolve()) or
            manifest.get('probe_sha256') != sha(TOOLS.parent / 'tests/musl/clock_drift.c')):
        raise ValueError('clock probe is not the exact mode-matching musl build of tests/musl/clock_drift.c')
    inspect_elf(args.probe.resolve(), args.arch)
    if args.probe.read_bytes()[7] != 3:
        raise ValueError('clock probe lacks the Linux ELF personality')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / 'root'
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    shutil.copy2(args.probe.resolve(), root / 'bin/clock-drift')
    (root / 'bin/clock-drift').chmod(0o755)
    disk = out / 'rootfs.ext4.img'
    with (out / 'package.log').open('xb') as log:
        subprocess.run([sys.executable, '-B', str(TOOLS / 'mkext4.py'), '--root', str(root), '--out', str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    kernel = out / 'kernel-input.bin'
    shutil.copy2(args.kernel.resolve(), kernel)
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, 'none', native_profile=True)
    record = dict(schema=1, architecture=args.arch, mode=args.mode, scope='actual-static-musl-qemu-clock-drift',
                  status='running', command=command, limit_ppm=args.limit_ppm,
                  sdk_manifest_sha256=sha(args.kernel_sdk.resolve() / 'manifest.json'),
                  musl_manifest_sha256=sha(args.musl_build.resolve() / 'manifest.json'),
                  probe_manifest_sha256=sha(manifest_path), probe_sha256=sha(args.probe.resolve()),
                  kernel_sha256=sha(kernel), qemu_sha256=sha(args.qemu.resolve()), input_disk_sha256=sha(disk),
                  script_sha256=sha(Path(__file__)), physical=False, smp=False)
    serial = bytearray()
    samples = []
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        receive(process, serial, lambda: b'OK_SYSTEM_GUI boot=complete' in serial and PROMPT in serial,
                time.monotonic() + args.timeout)
        start = len(serial)
        process.stdin.write(b'/bin/clock-drift\n')
        process.stdin.flush()
        receive(process, serial, lambda: READY.search(serial, start) is not None, time.monotonic() + args.timeout)
        if READY.search(serial, start).group(1).decode() != args.arch:
            raise RuntimeError('clock probe reports another architecture')
        realtime = re.findall(rb'OK_REALTIME scope=runtime[^\r\n]*', serial)
        record['kernel_realtime'] = realtime[-1].decode() if realtime else None
        interval = args.window / (args.samples - 1)
        first = time.monotonic()
        for index in range(args.samples):
            pause = first + index * interval - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            mark = len(serial)
            sent, wall_sent = time.monotonic_ns(), time.time_ns()
            process.stdin.write(b's\n')
            process.stdin.flush()
            receive(process, serial, lambda: SAMPLE.search(serial, mark) is not None, time.monotonic() + 60)
            received, wall_received = time.monotonic_ns(), time.time_ns()
            match = SAMPLE.search(serial, mark)
            if int(match.group(1)) != index:
                raise RuntimeError('clock probe answered out of sequence')
            samples.append(dict(sent_ns=sent, received_ns=received, wall_sent_ns=wall_sent,
                                wall_received_ns=wall_received,
                                mono_ns=int(match.group(2)) * 10**9 + int(match.group(3)),
                                real_ns=None if match.group(4) is None
                                else int(match.group(4)) * 10**9 + int(match.group(5))))
        mark = len(serial)
        process.stdin.write(b'b\n')
        process.stdin.flush()
        receive(process, serial, lambda: BUSY.search(serial, mark) is not None, time.monotonic() + 120)
        record['busy'] = BUSY.search(serial, mark).group(1).decode()
        done = len(serial)
        process.stdin.write(b'q\n')
        process.stdin.flush()
        receive(process, serial, lambda: b'CLOCK_DONE' in serial[done:] and PROMPT in serial[done:],
                time.monotonic() + 60)
        record['samples'] = samples
        record['result'] = analyse(samples)
        latency = re.findall(rb'OK_TIMER_LATENCY scope=hardware[^\r\n]*', serial)
        record['kernel_timer_latency'] = latency[-1].decode() if latency else None
        low, high = record['result']['monotonic_drift_bound_ppm']
        if abs(record['result']['monotonic_drift_ppm']) > args.limit_ppm or low > args.limit_ppm or \
                high < -args.limit_ppm:
            raise RuntimeError('monotonic drift exceeds %g ppm: %s' % (args.limit_ppm, record['result']))
        record['status'] = 'pass'
    except BaseException as error:
        record.update(status='fail', failure=repr(error))
        if samples and 'result' not in record and len(samples) >= 3:
            record['result'] = analyse(samples)
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
    result = record['result']
    print('PASS %s/%s: monotonic drift %+.3f ppm (bound %+.3f..%+.3f) over %.1f s, %d samples' % (
        args.arch, args.mode, result['monotonic_drift_ppm'], *result['monotonic_drift_bound_ppm'],
        result['window_s'], result['samples']))
    if 'realtime_drift_ppm' in result:
        print('realtime offset %+.3f ms, drift %+.3f ppm' % (result['realtime_offset_ms'],
                                                             result['realtime_drift_ppm']))
    if record['kernel_timer_latency']:
        print(record['kernel_timer_latency'])


if __name__ == '__main__':
    main()
