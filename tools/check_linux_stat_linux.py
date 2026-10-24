#!/usr/bin/env python3
"""Compare a pinned SDK31 stat image with a disposable readonly Linux guest."""
from pathlib import Path
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/jbd2'))
from create_linux_fixture import cpio
from native_support import boot

ARCHES = ('i386', 'x86_64', 'aarch64', 'arm32', 'rv64', 'rv32', 'loongarch64', 'mips', 'mips64', 'ppc')
SOURCES = ('tests/linux/linux_stat_reference_init.c', 'tools/check_linux_stat_linux.py',
           'tools/jbd2/create_linux_fixture.py', 'tools/jbd2/native_support.py', 'tools/kernel_sdk.py')
APIS = ('lstat', 'fstatat', 'fstat', 'statx', 'statx-fd')
PASS = 'LINUX_STAT_REFERENCE_PASS nodes=9 observations=45 snapshots=9 mount=readonly-noload'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_inventory(path, expected):
    if sha(path) != expected:
        raise ValueError('reference source inventory pin mismatch')
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or data.get('scope') != 'linux-stat-linux-reference-sources':
        raise ValueError('reference source inventory schema mismatch')
    if set(data.get('files', {})) != set(SOURCES):
        raise ValueError('reference source inventory file set mismatch')
    if any(sha(ROOT / name) != value for name, value in data['files'].items()):
        raise ValueError('reference source differs from inventory')
    return data['files']

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def normalize(node):
    data = {key: node[key] for key in ('inode', 'mode', 'uid', 'gid', 'nlink', 'size', 'blocks', 'blksize')}
    for label in ('atime', 'mtime', 'ctime'):
        data[label + '_s'], data[label + '_ns'] = node['times'][label]
    data.update(rdev_major=0, rdev_minor=0)
    return data

def linux_statx(data):
    if len(data) != 256:
        raise ValueError('Linux raw statx byte count')
    u32 = lambda at: struct.unpack_from('<I', data, at)[0]
    u64 = lambda at: struct.unpack_from('<Q', data, at)[0]
    if u32(0) & 0x7ff != 0x7ff:
        raise ValueError('Linux did not return all basic stat fields')
    value = {'inode': u64(32), 'mode': struct.unpack_from('<H', data, 28)[0],
             'uid': u32(20), 'gid': u32(24), 'nlink': u32(16), 'size': u64(40),
             'blocks': u64(48), 'blksize': u32(4), 'dev_major': u32(136), 'dev_minor': u32(140),
             'rdev_major': u32(128), 'rdev_minor': u32(132)}
    for name, at in (('atime', 64), ('mtime', 112), ('ctime', 96)):
        value[name + '_s'], value[name + '_ns'] = struct.unpack_from('<qI', data, at)
        if value[name + '_ns'] >= 1000000000:
            raise ValueError('Linux returned unnormalized nanoseconds')
    # These fields are recorded, not equated to the deliberately smaller SDK31 contract.
    extra = dict(mask=u32(0), attributes=u64(8), attributes_mask=u64(56),
                 mount_id=u64(144), birthtime=list(struct.unpack_from('<qI', data, 80)))
    return value, extra

def parse_linux(text, expected):
    if 'JBD2_NATIVE_FAIL' in text or '_FAIL' in text:
        raise ValueError('Linux guest failure marker')
    lines = text.splitlines()
    if lines.count(PASS) != 1:
        raise ValueError('missing or duplicate Linux completion marker')
    devices = [re.fullmatch(r'LINUX_STAT_REFERENCE_DEVICE dev_major=(\d+) dev_minor=(\d+) source=virtio-block-rdev', line)
               for line in lines if line.startswith('LINUX_STAT_REFERENCE_DEVICE')]
    if len(devices) != 1 or devices[0] is None:
        raise ValueError('Linux block device identity marker')
    dev = tuple(map(int, devices[0].groups()))
    if dev == (0, 0):
        raise ValueError('Linux device identity is zero')
    fields, snapshots, extras = {}, {}, {}
    for line in lines:
        if line.startswith('LINUX_STAT_REFERENCE_FIELD'):
            tokens = [word.split('=', 1) for word in line.split()[1:]]
            if any(len(token) != 2 for token in tokens):
                raise ValueError('malformed Linux observation')
            record = dict(tokens)
            if len(record) != len(tokens):
                raise ValueError('duplicate Linux observation key')
            name, api = record.pop('name', None), record.pop('api', None)
            if name not in expected or api not in APIS or (name, api) in fields:
                raise ValueError('unknown or duplicate Linux observation')
            want = {**expected[name], 'dev_major': dev[0], 'dev_minor': dev[1]}
            values = {key: int(value) for key, value in record.items()}
            if values != want:
                raise ValueError('Linux/public raw field mismatch: ' + name + '/' + api)
            fields[name, api] = values
        elif line.startswith('LINUX_STAT_REFERENCE_STATX'):
            match = re.fullmatch(r'LINUX_STAT_REFERENCE_STATX name=([a-z]+) hex=([0-9a-f]{512})', line)
            if match is None or match[1] not in expected or match[1] in snapshots:
                raise ValueError('malformed or duplicate Linux statx record')
            values, extra = linux_statx(bytes.fromhex(match[2]))
            want = {**expected[match[1]], 'dev_major': dev[0], 'dev_minor': dev[1]}
            if values != want:
                raise ValueError('Linux raw statx differs from image/SDK31: ' + match[1])
            snapshots[match[1]], extras[match[1]] = values, extra
    if set(fields) != {(name, api) for name in expected for api in APIS} or set(snapshots) != set(expected):
        raise ValueError('incomplete Linux comparison matrix')
    if (snapshots['file']['inode'], snapshots['file']['dev_major'], snapshots['file']['dev_minor']) != (
            snapshots['alias']['inode'], snapshots['alias']['dev_major'], snapshots['alias']['dev_minor']):
        raise ValueError('Linux hard-link identity differs')
    return dict(nodes=len(snapshots), observations=len(fields), raw_statx_records=len(snapshots),
                linux_device=dict(major=dev[0], minor=dev[1], source='mounted virtio block device rdev'),
                core_fields=snapshots, linux_additional_fields=extras,
                device_comparison='mount-local identity validated separately; no cross-kernel device-number equality',
                linux_additional_fields_comparison='recorded only; SDK31 intentionally projects BASIC_STATS only')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-evidence', type=Path, required=True)
    parser.add_argument('--native-result-sha256', required=True)
    parser.add_argument('--sdk-manifest-sha256', required=True)
    parser.add_argument('--harness-source', type=Path, required=True,
                        help='Explicit source root used by this native evidence; no source fallback')
    parser.add_argument('--image-source-name', choices=('stat_image.py', 'linux_stat_image.py'), default='linux_stat_image.py')
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--fixture-capture-sha256', required=True)
    parser.add_argument('--linux-image-sha256', required=True)
    parser.add_argument('--source-inventory', type=Path, required=True)
    parser.add_argument('--source-inventory-sha256', required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', scope='actual-Linux-readonly-SDK31-stat-reference', sdk_abi=31,
                  host_mounts=False, host_clock_changes=False, physical=False, linux_guest_boots=0,
                  guest_parallelism=1, linux_reference_architecture='x86_64',
                  linux_source_provenance='not-established', commands=[])
    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    def run(argv, label):
        argv = list(map(str, argv))
        row = dict(argv=argv, label=label)
        report['commands'].append(row)
        save()
        completed = subprocess.run(argv, capture_output=True)
        log = out / (label + '.log')
        log.write_bytes(completed.stdout + completed.stderr)
        row.update(returncode=completed.returncode, log_sha256=sha(log))
        save()
        if completed.returncode:
            raise ValueError(label + ' failed')
    save()
    try:
        sources = source_inventory(args.source_inventory, args.source_inventory_sha256)
        native = args.native_evidence.resolve()
        receipt_path = native / 'result.json'
        if sha(receipt_path) != args.native_result_sha256:
            raise ValueError('explicit SDK31 result pin mismatch')
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get('status') != 'passed' or receipt.get('sdk_abi') != 31 or
                receipt.get('architecture') not in ARCHES or receipt.get('mode') not in ('debug', 'release') or
                receipt.get('policy') not in ('maintained', 'readonly') or
                receipt.get('native_execution') is not True or receipt.get('musl_execution') is not True or
                receipt.get('linux_stat') != 'qualified'):
            raise ValueError('source result is not qualified actual SDK31 user execution')
        sdk = native / 'sdk'
        if sha(sdk / 'manifest.json') != args.sdk_manifest_sha256 or receipt.get('sdk_manifest_sha256') != args.sdk_manifest_sha256:
            raise ValueError('explicit source SDK manifest pin mismatch')
        manifest = json.loads((sdk / 'manifest.json').read_text())
        if (manifest.get('schema') != 1 or manifest.get('abi_version') != 31 or
                manifest.get('arch') != receipt['architecture'] or manifest.get('mode') != receipt['mode']):
            raise ValueError('source SDK architecture/mode/ABI mismatch')
        for name, expected in manifest['files'].items():
            path = sdk / name
            if Path(name).is_absolute() or not path.resolve().is_relative_to(sdk.resolve()) or sha(path) != expected:
                raise ValueError('source SDK member mismatch: ' + name)
        image_source = 'tools/' + args.image_source_name
        for name in (image_source, 'tools/linux_stat_oracle.py'):
            expected = receipt['source_sha256'].get(name)
            actual = args.harness_source.resolve() / name
            if not expected or sha(actual) != expected or sha(native / 'sources' / name) != expected:
                raise ValueError('explicit harness/source snapshot mismatch: ' + name)
            target = out / 'sources/harness' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(actual, target)
        image_module = load_module('linux_stat_image', out / 'sources/harness' / image_source)
        sys.modules['stat_image'] = image_module
        oracle = load_module('linux_stat_reference_oracle', out / 'sources/harness/tools/linux_stat_oracle.py')
        initial, final, serial = native / 'rootfs-input.ext4.img', native / 'rootfs.ext4.img', native / 'serial.log'
        if (sha(initial) != receipt['initial_disk_sha256'] or sha(final) != receipt['final_disk_sha256'] or
                receipt['artifact_sha256'].get('serial.log') != sha(serial)):
            raise ValueError('source image or serial identity mismatch')
        facts = oracle.validate(serial.read_text(), initial.read_bytes(), final.read_bytes(), receipt['architecture'],
                                receipt['policy'], receipt['epoch_seconds'])
        if json.loads(json.dumps(facts)) != receipt['evidence'] or facts['snapshot_count'] != 9:
            raise ValueError('independent SDK31 snapshot/raw-image reparse differs')
        expected_nodes = {name: normalize(facts['raw_nodes'][name]) for name in image_module.PATHS}
        sdk_devices = set()
        for line in serial.read_text().splitlines():
            match = re.fullmatch(r'LINUX_STAT_SNAPSHOT name=([a-z]+) hex=([0-9a-f]{512})', line)
            if match:
                sdk_devices.add(tuple(oracle.decode_statx(bytes.fromhex(match[2]), receipt['architecture'])['device']))
        if len(sdk_devices) != 1 or (0, 0) in sdk_devices:
            raise ValueError('SDK31 device identity is not stable/nonzero')
        report.update(native_evidence=str(native), native_result_sha256=args.native_result_sha256,
                      native_architecture=receipt['architecture'], native_mode=receipt['mode'],
                      epoch=receipt['epoch'], epoch_seconds=receipt['epoch_seconds'], policy=receipt['policy'],
                      native_serial_sha256=sha(serial), source_image_sha256=sha(final),
                      sdk_manifest_sha256=args.sdk_manifest_sha256, sdk_members_verified=len(manifest['files']),
                      independently_reparsed=facts, sdk21_device=list(next(iter(sdk_devices))),
                      harness_sources={name: receipt['source_sha256'][name] for name in (image_source, 'tools/linux_stat_oracle.py')})
        for source, name in ((receipt_path, 'native-result.json'), (serial, 'native-serial.log'),
                             (sdk / 'manifest.json', 'sdk-manifest.json'), (args.source_inventory, 'source-inventory.json')):
            shutil.copy2(source, out / name)
        capture, kernel = args.fixture.resolve() / 'capture-manifest.json', args.fixture.resolve() / 'linux-bzImage'
        if sha(capture) != args.fixture_capture_sha256:
            raise ValueError('Linux capture manifest pin mismatch')
        pin = json.loads(capture.read_text())
        if sha(kernel) != args.linux_image_sha256 or pin['linux_image_sha256'] != args.linux_image_sha256:
            raise ValueError('Linux binary pin mismatch')
        shutil.copy2(capture, out / 'capture-manifest.json')
        shutil.copy2(kernel, out / 'linux-bzImage')
        report.update(linux_image_sha256=args.linux_image_sha256, capture_manifest_sha256=args.fixture_capture_sha256,
                      source_inventory_sha256=args.source_inventory_sha256, source_sha256=sources)
        for name in SOURCES:
            target = out / 'sources' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
            if sha(target) != sources[name]:
                raise ValueError('reference source drift during snapshot')
        rows = []
        for name, path in image_module.PATHS.items():
            value = facts['raw_nodes'][name]
            seconds = ','.join(str(value['times'][label][0]) + 'LL' for label in ('atime', 'mtime', 'ctime'))
            nanos = ','.join(str(value['times'][label][1]) + 'U' for label in ('atime', 'mtime', 'ctime'))
            if not path.startswith('/home/'):
                raise ValueError('reference expected path is outside fixture home')
            columns = [json.dumps(name), json.dumps('/mnt' + path), json.dumps(path[len('/home/'):]),
                       *(str(value[key]) + 'ULL' for key in ('inode', 'size', 'blocks')),
                       *(str(value[key]) + 'U' for key in ('mode', 'uid', 'gid', 'nlink', 'blksize')),
                       '{' + seconds + '}', '{' + nanos + '}']
            rows.append('{' + ','.join(columns) + '}')
        (out / 'linux_stat_expected.h').write_text('static const struct expected_node expected[] = {\n' + ',\n'.join(rows) + '\n};\n')
        (out / 'expected-fields.json').write_text(json.dumps(expected_nodes, indent=2) + '\n')
        init = out / 'init'
        run(['gcc', '-static', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', out,
             out / 'sources/tests/linux/linux_stat_reference_init.c', '-o', init], 'compile-init')
        entries = [(name, 0o040755, b'', 0, 0) for name in ('dev', 'mnt')]
        entries += [('dev/console', 0o020600, b'', 5, 1), ('init', 0o100755, init.read_bytes(), 0, 0)]
        initrd = out / 'initramfs.cpio'
        initrd.write_bytes(cpio(entries))
        disk = out / 'sdk21-output-copy.img'
        shutil.copy2(final, disk)
        if sha(disk) != report['source_image_sha256']:
            raise ValueError('image changed during copying')
        run(['e2fsck', '-fn', disk], 'pre-linux-fsck')
        command = ['qemu-system-x86_64', '-m', '512M', '-kernel', str(out / 'linux-bzImage'), '-initrd', str(initrd),
                   '-append', 'console=ttyS0 rdinit=/init loglevel=4 panic=-1 nokaslr', '-drive',
                   f'file={disk},format=raw,if=none,id=fixture,readonly=on', '-device', 'virtio-blk-pci,drive=fixture',
                   '-smp', '1']
        report['guest_argv'] = command + ['-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-no-reboot']
        report.update(init_sha256=sha(init), initramfs_sha256=sha(initrd))
        if args.prepare_only:
            report['status'] = 'prepared-not-executed'
        else:
            report['commands'].append(dict(label='linux-readonly-stat-reference', argv=list(report['guest_argv'])))
            report['linux_guest_boots'] = 1
            save()
            with contextlib.redirect_stdout(io.StringIO()):
                report['guest_returncode'] = boot(command, PASS + '\r\n', out / 'linux.log')
            report['comparison'] = parse_linux((out / 'linux.log').read_text(), expected_nodes)
            if sha(disk) != report['source_image_sha256'] or sha(final) != report['source_image_sha256']:
                raise ValueError('readonly Linux or source image bytes changed')
            run(['e2fsck', '-fn', disk], 'post-linux-fsck')
            report.update(status='passed', image_unchanged=True)
        if sha(disk) != report['source_image_sha256'] or sha(receipt_path) != args.native_result_sha256:
            raise ValueError('input/result drift after reference check')
        source_inventory(args.source_inventory, args.source_inventory_sha256)
        if sha(kernel) != args.linux_image_sha256 or sha(capture) != args.fixture_capture_sha256:
            raise ValueError('Linux pin drift after reference check')
        report['inputs_rechecked'] = True
    except BaseException as error:
        report.update(status='failed', error=str(error))
        print('FAIL', error, flush=True)
    finally:
        report['tool_sha256'] = {name: sha(Path(shutil.which(name)).resolve()) for name in
                                ('gcc', 'as', 'ld', 'qemu-system-x86_64', 'e2fsck') if shutil.which(name)}
        report['artifact_sha256'] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                                    if p.is_file() and p.name != 'result.json'}
        save()
    print(report['status'], out / 'result.json')
    return 1 if report['status'] == 'failed' else 0

if __name__ == '__main__':
    raise SystemExit(main())
