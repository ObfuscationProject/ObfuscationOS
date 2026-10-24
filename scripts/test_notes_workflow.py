"""Run bounded English file workflows through actual native shell applications."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time

from qemu_distro import command_for

ARCHES = ('i386', 'x86_64', 'aarch64', 'arm32', 'rv64', 'rv32', 'loongarch64', 'mips', 'mips64', 'ppc')
FIRST = 'First English document.'
SECOND = 'Updated English document.'
DIRECTORY = '/home/english-workflow'
DOCUMENT = DIRECTORY + '/document.txt'
RENAMED = DIRECTORY + '/renamed.txt'
NESTED = DIRECTORY + '/folder/document.txt'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def need(value, message):
    if not value:
        raise RuntimeError(message)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ARCHES, required=True)
    for name in ('qemu', 'kernel', 'rootfs'):
        parser.add_argument('--' + name, type=Path, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=100)
    args = parser.parse_args()
    need(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'disable Python bytecode')
    out = args.output.resolve()
    need(not out.exists(), 'retain prior evidence; output must be unused')
    for name in ('qemu', 'kernel', 'rootfs'):
        need(sha(getattr(args, name)) == getattr(args, name + '_sha256'), 'wrong ' + name + ' input')
    out.mkdir(parents=True)
    disk = out / 'scratch.simplefs.img'
    shutil.copy2(args.rootfs, disk)
    argv = command_for(args.qemu.resolve(), args.arch, args.kernel.resolve(), disk, 'none', native_profile=True)
    report = dict(schema=1, status='running', architecture=args.arch,
        layer='native-user-instructions-and-syscalls-qemu', filesystem='simplefs-ram-workflow',
        runner_sha256=sha(__file__), qemu_helper_sha256=sha(Path(__file__).with_name('qemu_distro.py')),
        argv=argv, input_sha256={n: getattr(args, n + '_sha256') for n in ('qemu', 'kernel', 'rootfs')},
        commands=[], physical=False, smp=False, journal_crash_durability=False,
        isolated_graphical_workflow=False, synchronized_guest_shutdown=False)
    serial = bytearray()
    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        (out / 'serial.log').write_bytes(serial)
    save()
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    try:
        def receive(predicate):
            deadline = time.monotonic() + args.timeout
            while not predicate():
                need(time.monotonic() < deadline, 'timeout waiting for native shell')
                ready, _, _ = select.select([process.stdout], [], [], .1)
                if not ready:
                    need(process.poll() is None, 'QEMU stopped')
                    continue
                chunk = os.read(process.stdout.fileno(), 16384)
                need(bool(chunk), 'QEMU output ended')
                serial.extend(chunk)
                for bad in (b'OK_TEST_FAIL ', b'POSIX_CHECK failed:', b'Kernel panic', b'ASSERTION FAILED'):
                    need(bad not in serial, 'guest failure marker: ' + repr(bad))
        receive(lambda: b'OK_SYSTEM_GUI boot=complete' in serial and b'oksh> ' in serial)
        need(b'OK_NATIVE' in serial or b'OK_USER' in serial, 'missing native boot evidence')
        def command(text, expected=None, absent=None):
            start = len(serial)
            process.stdin.write((text + '\n').encode('ascii'))
            process.stdin.flush()
            receive(lambda: b'oksh> ' in serial[start:])
            segment = bytes(serial[start:]).replace(b'\r', b'')
            # Full output lines cannot be satisfied by the echoed input command.
            lines = segment.decode('ascii', errors='replace').splitlines()
            if expected is not None:
                need(expected in lines, 'missing actual output line for ' + text + ': ' + repr(lines))
            if absent is not None:
                need(absent not in lines, 'unexpected success output for ' + text)
            response = out / ('response-%02d.log' % (len(report['commands']) + 1))
            response.write_bytes(segment)
            report['commands'].append(dict(command=text, expected_line=expected, absent_line=absent,
                response_sha256=sha(response), status='passed'))
            save()
        command('mkdir ' + DIRECTORY)
        command('notes ' + DOCUMENT + ' ' + FIRST, 'Saved ' + DOCUMENT)
        command('notes ' + DOCUMENT, FIRST)
        command('notes ' + DOCUMENT + ' ' + SECOND, 'Saved ' + DOCUMENT)
        command('notes ' + DOCUMENT, SECOND)
        command('mv ' + DOCUMENT + ' ' + RENAMED)
        command('notes ' + RENAMED, SECOND)
        command('notes ' + DOCUMENT, 'Usage: notes [path] [text to save]')
        command('cat ' + RENAMED, SECOND)
        command('mkdir ' + DIRECTORY + '/folder')
        command('mv ' + RENAMED + ' ' + NESTED)
        command('notes ' + NESTED, SECOND)
        command('ln ' + NESTED + ' ' + DIRECTORY + '/linked.txt')
        command('notes ' + NESTED + ' Must preserve old contents', absent='Saved ' + NESTED)
        command('notes ' + NESTED, SECOND)
        command('cat ' + DIRECTORY + '/linked.txt', SECOND)
        command('rm ' + DIRECTORY + '/linked.txt')
        command('notes ' + NESTED + ' Final English document.', 'Saved ' + NESTED)
        command('notes ' + NESTED, 'Final English document.')
        report.update(status='passed-bounded-native-english-notes-workflow', command_count=len(report['commands']),
            serial_sha256=hashlib.sha256(serial).hexdigest(), original_rootfs_unchanged=sha(args.rootfs) == args.rootfs_sha256)
        need(report['original_rootfs_unchanged'], 'packaged input mutated')
        save()
        print('PASS native English Notes workflow', args.arch, report['command_count'], sha(out / 'result.json'), flush=True)
    except Exception as error:
        report.update(status='failed', error=str(error))
        save()
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        process.stdin.close()
        process.stdout.close()

if __name__ == '__main__':
    main()
