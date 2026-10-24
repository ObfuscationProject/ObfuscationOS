#!/usr/bin/env python3
"""Qualify SDK-only native identity and readonly ext4 epoch providers on private disks."""
from __future__ import annotations
import argparse, hashlib, json, shutil, struct, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
from native_support import ARCH_TRIPLES, QEMU, snapshot_sdk, machine, boot, validate_sdk
ROOT = Path(__file__).resolve().parents[2]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    p.add_argument('--mode', choices=('debug', 'release'), default='debug')
    p.add_argument('--kernel-sdk', type=Path, required=True); p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--fixtures', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--qemu')
    args = p.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = {'scope': 'qemu-device-native-file-attributes', 'status': 'running', 'arch': args.arch, 'mode': args.mode,
              'commands': [], 'cases': [], 'linux_stat_enabled': False, 'native_service_fork': True,
              'user_mode_fork_probe': False, 'native_smp': False, 'physical_hardware': False}
    def save(): (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    def run(command, label):
        item = {'argv': [str(x) for x in command], 'label': label, 'status': 'running'}; report['commands'].append(item); save()
        start = time.monotonic(); result = subprocess.run(item['argv'], text=True, capture_output=True)
        (out/(label+'.log')).write_text(result.stdout+result.stderr)
        item.update(status='passed' if not result.returncode else 'failed', returncode=result.returncode, seconds=time.monotonic()-start); save()
        if result.returncode: raise RuntimeError(label+' failed')
        return result.stdout+result.stderr
    save()
    try:
        prefix = args.toolchain.resolve()/'bin'/(ARCH_TRIPLES[args.arch]+'-'); cxx, ar, objcopy = [Path(str(prefix)+x) for x in ('g++','ar','objcopy')]
        sdk = out/'sdk'; manifest, sdk_sha = snapshot_sdk(args.kernel_sdk, sdk, args.arch, cxx, args.mode)
        if manifest['abi_version'] != 31: raise ValueError('file attributes require exact SDK31')
        if not {'include/ok/fs/attributes.hpp','include/ok/fs/ext4_times.hpp'}.issubset(manifest['files']): raise ValueError('missing attribute SDK')
        if '-frtti' not in manifest['cxxflags'] or '-fno-rtti' in manifest['cxxflags']: raise ValueError('SDK RTTI disabled')
        report.update(sdk_abi=manifest['abi_version'], sdk_manifest_sha256=sdk_sha, compiler=manifest['compiler'])
        fixtures = json.loads((args.fixtures/'result.json').read_text())
        if fixtures['status'] != 'passed' or len(fixtures['fixtures']) != 6: raise ValueError('complete raw oracle fixtures required')
        (out/'fixture-result.json').write_bytes((args.fixtures/'result.json').read_bytes())
        sources = {}
        for relative in ['drivers/virtio/block.cpp','drivers/virtio/block.hpp','drivers/virtio/poll.hpp','tests/native/file_attributes.cpp','tools/jbd2/test_file_attributes.py','tools/jbd2/native_support.py','tools/kernel_sdk.py']:
            target = out/'sources'/relative; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes((ROOT/relative).read_bytes()); sources[relative] = sha(target)
        report['source_sha256'] = sources
        members = run([ar,'t',sdk/'lib/libokernel_boot.a'],'boot-members').splitlines()
        if members.count('boot.S.o') != 1: raise ValueError('nonunique boot member')
        command = [str(ar),'p',str(sdk/'lib/libokernel_boot.a'),'boot.S.o']; report['commands'].append({'argv': command,'label':'extract-boot'})
        (out/'boot.o').write_bytes(subprocess.check_output(command))
        flags = ['-std=c++23',*manifest['cxxflags'],'-fno-builtin','-Werror',*('-D'+d for d in manifest['defines']),'-I',str(sdk/'include'),'-I',str(out/'sources'),'-I',str(out)]
        run([cxx,*flags,'-c',out/'sources/drivers/virtio/block.cpp','-o',out/'driver.o'],'compile-driver')
        qemu = shutil.which(args.qemu or QEMU[args.arch])
        if not qemu: raise ValueError('missing QEMU profile')
        report['qemu'] = run([qemu,'--version'],'qemu-version').splitlines()[0]
        for fixture in fixtures['fixtures']:
            name = str(fixture['block_size'])+'-'+str(fixture['inode_size']); source = args.fixtures/(name+'.img')
            if sha(source) != fixture['sha256']: raise ValueError('fixture hash mismatch')
            raw = source.read_bytes(); at = fixture['inode_offset']; times = []
            for base, extension in ((8,140),(16,136),(12,132)):
                seconds = struct.unpack_from('<i',raw,at+base)[0]
                extra = struct.unpack_from('<I',raw,at+extension)[0] if fixture['inode_size'] == 256 else 0
                times += [seconds+(extra&3)*4294967296,extra>>2]
            if times != fixture['times']: raise ValueError('raw timestamp oracle mismatch')
            header = '#pragma once\nnamespace attribute_fixture {\ninline constexpr ok::u64 inode='+str(fixture['inode'])+';\n'
            header += 'inline constexpr ok::i64 seconds[3]={'+','.join(str(n)+'LL' for n in times[::2])+'};\n'
            header += 'inline constexpr ok::u32 nanoseconds[3]={'+','.join(str(n) for n in times[1::2])+'};\n}\n'
            (out/'attribute_fixture.hpp').write_text(header); (out/(name+'-fixture.hpp')).write_text(header)
            obj, elf, image = [out/(name+suffix) for suffix in ('.o','.elf','.bin')]
            run([cxx,*flags,'-c',out/'sources/tests/native/file_attributes.cpp','-o',obj],'compile-'+name)
            run([cxx,*manifest['ldflags'],'-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(sdk/'boot/linker.ld'),out/'boot.o',out/'driver.o',obj,sdk/'lib/libokernel.a','-lgcc','-o',elf],'link-'+name)
            run([sys.executable,out/'sources/tools/kernel_sdk.py','assemble','--sdk',sdk,'--arch',args.arch,'--mode',args.mode,'--compiler',cxx,'--elf',elf,'--out',image,'--objcopy',objcopy],'assemble-'+name)
            disk = out/(name+'.img'); disk.write_bytes(raw)
            command = machine(qemu,args.arch,image); transport = 'virtio-blk-device' if args.arch in ('aarch64','arm32','rv32','rv64') else 'virtio-blk-pci'
            command += ['-drive',f'file={disk},format=raw,if=none,id=attributes,cache=writeback','-device',transport+',drive=attributes']
            record = {'fixture': name,'status':'running','before_sha256':sha(disk),'oracle':fixture}; report['cases'].append(record)
            report['commands'].append({'argv':command,'label':'qemu-'+name}); save()
            boot(command,'FILE_ATTRIBUTES_PASS scope=qemu-device-service disk-writes=0 linux-stat=not-executed\n',out/(name+'.log'))
            if disk.read_bytes() != raw: raise ValueError('native attribute probe modified disk')
            record.update(status='passed',after_sha256=sha(disk)); save()
        validate_sdk(sdk,args.arch,args.mode,cxx); report.update(status='passed',sdk_snapshot_revalidated=True)
    except Exception as error:
        report.update(status='failed',error=str(error)); print('FAIL '+str(error),flush=True)
    finally:
        report['artifact_sha256'] = {str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='result.json' and 'sdk' not in f.relative_to(out).parts}; save()
    return 0 if report['status']=='passed' else 1
if __name__ == '__main__': raise SystemExit(main())
