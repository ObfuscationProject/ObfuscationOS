#!/usr/bin/env python3
"""Check actual maintained guest output using a pinned disposable Linux guest."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/jbd2'))
from create_linux_fixture import cpio
from native_support import boot
from ext4_timestamp_user_evidence import Image, validate


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-evidence', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = {'status':'running','scope':'actual-linux-readonly-maintained-timestamps-interoperability',
              'host_mounts':False,'host_clock_changes':False,'linux_source_provenance':'not-established',
              'linux_guest_boots':0,'commands':[]}
    def save(): (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    def run(command, label):
        command = list(map(str, command)); row = {'argv':command,'label':label}
        report['commands'].append(row); save()
        result = subprocess.run(command, capture_output=True)
        log = out/(label+'.log'); log.write_bytes(result.stdout+result.stderr)
        row.update(returncode=result.returncode, log_sha256=sha(log)); save()
        if result.returncode: raise RuntimeError(label+' failed')
    save()
    try:
        native = args.native_evidence.resolve()
        receipt = json.loads((native/'result.json').read_text())
        initial, final = native/'rootfs-input.ext4.img', native/'rootfs.ext4.img'
        if receipt['status'] != 'passed' or sha(initial) != receipt['initial_disk_sha256'] or sha(final) != receipt['final_disk_sha256']:
            raise ValueError('actual guest image identity mismatch')
        serial = native/'serial.log'
        if receipt['artifact_sha256'].get('serial.log') != sha(serial): raise ValueError('actual serial identity mismatch')
        facts = validate(serial.read_text(), initial.read_bytes(), final.read_bytes())
        report.update(native_receipt_sha256=sha(native/'result.json'), native_serial_sha256=sha(serial),
                      native_evidence=str(native), source_image_sha256=sha(final), independently_reparsed=facts)
        shutil.copy2(native/'result.json', out/'native-result.json')
        shutil.copy2(serial, out/'native-serial.log')
        capture = args.fixture.resolve()/'capture-manifest.json'
        pin = json.loads(capture.read_text()); kernel = args.fixture.resolve()/'linux-bzImage'
        if sha(kernel) != pin['linux_image_sha256']: raise ValueError('Linux binary pin mismatch')
        shutil.copy2(capture, out/'capture-manifest.json'); shutil.copy2(kernel, out/'linux-bzImage')
        report['linux_image_sha256'] = sha(out/'linux-bzImage')
        names = ['tests/linux/ext4_timestamp_init.c','tools/check_ext4_timestamps_linux.py',
                 'tools/ext4_timestamp_user_evidence.py','tools/jbd2/create_linux_fixture.py',
                 'tools/jbd2/native_support.py','tools/kernel_sdk.py']
        report['source_sha256'] = {}
        for name in names:
            path = out/'sources'/name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/name, path); report['source_sha256'][name] = sha(path)
        image = Image(final.read_bytes()); rows = []
        for name, value in facts['raw_nodes'].items():
            number = value['inode']; at = image.inode(number)
            seconds = ','.join(str(pair[0])+'LL' for pair in value['times'])
            nanos = ','.join(str(pair[1]) for pair in value['times'])
            mode = image.u16(at); uid = image.u16(at+2) | image.u16(at+120) << 16
            gid = image.u16(at+24) | image.u16(at+122) << 16
            rows.append('{'+json.dumps('/mnt/home/'+name)+f',{number}ULL,{mode},{uid}u,{gid}u,{image.u16(at+26)},{image.u32(at+4)}ULL,'+'{'+seconds+'},{'+nanos+'}}')
        (out/'timestamp_expected.h').write_text('static const struct expected_node expected[] = {\n'+',\n'.join(rows)+'\n};\n')
        init = out/'init'
        run(['gcc','-static','-O2','-Wall','-Wextra','-Werror','-I',out,
             out/'sources/tests/linux/ext4_timestamp_init.c','-o',init], 'compile-init')
        entries = [(name,0o040755,b'',0,0) for name in ('dev','mnt')]
        entries += [('dev/console',0o020600,b'',5,1),('init',0o100755,init.read_bytes(),0,0)]
        initrd = out/'initramfs.cpio'; initrd.write_bytes(cpio(entries))
        disk = out/'guest-output.img'; shutil.copy2(final,disk)
        command = ['qemu-system-x86_64','-m','512M','-kernel',str(out/'linux-bzImage'),'-initrd',str(initrd),
                   '-append','console=ttyS0 rdinit=/init loglevel=4 panic=-1 nokaslr','-drive',
                   f'file={disk},format=raw,if=none,id=fixture,readonly=on','-device','virtio-blk-pci,drive=fixture']
        report['commands'].append({'label':'linux-readonly','argv':command}); save()
        marker = 'LINUX_EXT4_TIME_PASS nodes=7 fields=21 mount=readonly image=unchanged extra16=accepted\r\n'
        boot(command, marker, out/'linux.log')
        lines = (out/'linux.log').read_text().splitlines()
        expected_lines = []
        for index, value in enumerate(facts['raw_nodes'].values()):
            for field, (seconds,nanos) in enumerate(value['times']):
                expected_lines.append(f'LINUX_EXT4_TIME_FIELD node={index} field={field} inode={value["inode"]} seconds={seconds} nanos={nanos}')
        if [line for line in lines if line.startswith('LINUX_EXT4_TIME_FIELD ')] != expected_lines:
            raise ValueError('Linux exact timestamp receipt mismatch')
        if sha(disk) != report['source_image_sha256']: raise ValueError('readonly Linux changed image')
        run(['e2fsck','-fn',disk], 'post-linux-fsck')
        report.update(status='passed',linux_guest_boots=1,nodes=7,fields=21,image_unchanged=True)
    except BaseException as error:
        report.update(status='failed',error=str(error)); print('FAIL',error,flush=True)
    finally:
        report['tool_sha256'] = {name:sha(Path(shutil.which(name)).resolve()) for name in ('gcc','as','ld','qemu-system-x86_64','e2fsck')}
        report['artifact_sha256'] = {str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='result.json'}
        save()
    return 0 if report['status']=='passed' else 1


if __name__ == '__main__': raise SystemExit(main())
