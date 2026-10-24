#!/usr/bin/env python3
"""Run bounded ext4 completion through an exact SDK and disposable QEMU devices."""
from __future__ import annotations
import argparse,hashlib,json,shutil,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from native_support import ARCH_TRIPLES,QEMU,snapshot_sdk,machine,boot,validate_sdk
from admit_linux_fixture import inspect,header_for,checksum
ROOT=Path(__file__).resolve().parents[2]
def sha(data):return hashlib.sha256(data).hexdigest()

def altered(captured, facts, scenario):
    data = bytearray(captured)
    size = facts["block_size"]
    first = facts["journal_first"] * size
    inode = first + size * 3 + facts["seed_offset"]
    if scenario == "payload-corrupt":
        data[inode + 124] ^= 1
    elif scenario == "mapping-reject":
        physical = struct.unpack_from("<I", data, inode + 60)[0]
        struct.pack_into("<I", data, inode + 60, physical + 1)
        data[inode + 124:inode + 126] = bytes(2)
        data[inode + 130:inode + 132] = bytes(2)
        seed = checksum(0xffffffff, bytes.fromhex(facts["uuid"]))
        crc = checksum(checksum(seed, struct.pack("<I", facts["seed_inode"])), data[inode + 100:inode + 104])
        crc = checksum(crc, data[inode:inode + 256])
        struct.pack_into("<H", data, inode + 124, crc & 0xffff)
        struct.pack_into("<H", data, inode + 130, crc >> 16)
        sequence = data[first + size + 8:first + size + 12]
        crc = checksum(checksum(seed, sequence), data[first + size * 3:first + size * 4])
        struct.pack_into(">I", data, first + size + 56, crc)
        struct.pack_into(">I", data, first + size * 2 - 4, 0)
        crc = checksum(seed, data[first + size:first + size * 2])
        struct.pack_into(">I", data, first + size * 2 - 4, crc)
    return data


def expected(captured,facts):
    b=bytearray(captured);size=facts['block_size'];j=facts['journal_first']*size
    for tag,payload in [(12,2),(44,3)]:
        target=struct.unpack_from('>I',captured,j+size+tag)[0]
        b[target*size:(target+1)*size]=captured[j+payload*size:j+(payload+1)*size]
    struct.pack_into('>I',b,j+24,(facts['journal_sequence']+2)&0xffffffff)
    struct.pack_into('>I',b,j+28,0);struct.pack_into('>I',b,j+252,0)
    struct.pack_into('>I',b,j+252,checksum(0xffffffff,b[j:j+1024]))
    struct.pack_into('<I',b,1120,struct.unpack_from('<I',b,1120)[0]&~4)
    struct.pack_into('<I',b,2044,checksum(0xffffffff,b[1024:2044]))
    return bytes(b)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arch',choices=tuple(ARCH_TRIPLES),required=True)
    p.add_argument('--mode',choices=('debug','release'),default='debug')
    p.add_argument('--kernel-sdk',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--qemu');p.add_argument('--faults',action='store_true')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'scope':'qemu-device-bounded-ext4-recovery-completion','status':'running','arch':args.arch,'mode':args.mode,
            'commands':[],'cases':[],'exclusive_session':'single-boot-owner-no-mounts-or-caches','mount_admission':False,
            'journal_writer':False,'physical_power_loss':False,'faults_after_completed_device_operations':args.faults}
    def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(command,label,allowed=(0,)):
        item={'argv':[str(x) for x in command],'label':label,'status':'running'};report['commands'].append(item);save();start=time.monotonic()
        result=subprocess.run(item['argv'],text=True,capture_output=True);(out/(label+'.log')).write_text(result.stdout+result.stderr)
        item.update(status='passed' if result.returncode in allowed else 'failed',returncode=result.returncode,seconds=time.monotonic()-start);save()
        if result.returncode not in allowed:raise RuntimeError(label+' failed')
        return result.stdout+result.stderr
    save()
    try:
        prefix=args.toolchain.resolve()/'bin'/(ARCH_TRIPLES[args.arch]+'-');cxx,ar,objcopy=[Path(str(prefix)+x) for x in ('g++','ar','objcopy')]
        sdk=out/'sdk';manifest,sdk_hash=snapshot_sdk(args.kernel_sdk,sdk,args.arch,cxx,args.mode)
        if 'include/ok/fs/ext4_completion.hpp' not in manifest['files']:raise ValueError('exact SDK lacks completion API')
        if '-frtti' not in manifest['cxxflags'] or '-fno-rtti' in manifest['cxxflags']:raise ValueError('SDK RTTI disabled')
        report.update(sdk_abi=manifest['abi_version'],sdk_manifest_sha256=sdk_hash,compiler=manifest['compiler'])
        for f in sdk.rglob('*'):
            if f.is_file():f.chmod(0o444)
        for f in sorted(sdk.rglob('*'),reverse=True):
            if f.is_dir():f.chmod(0o555)
        sdk.chmod(0o555)
        fixture=args.fixture.resolve();capture=json.loads((fixture/'capture-manifest.json').read_text());captured=(fixture/'linux-dirty-capture.img').read_bytes()
        if sha(captured)!=capture['capture_sha256']:raise ValueError('Linux capture identity mismatch')
        facts=inspect(captured,True)
        if json.loads(json.dumps(facts))!=json.loads((fixture/'admission.json').read_text()):raise ValueError('admission mismatch')
        header=header_for(facts)
        if header!=(fixture/'linux_fixture.hpp').read_text():raise ValueError('fixture header mismatch')
        (out/'linux_fixture.hpp').write_text(header);(out/'capture-manifest.json').write_bytes((fixture/'capture-manifest.json').read_bytes())
        (out/'linux-dirty-capture.img').write_bytes(captured);oracle=expected(captured,facts);(out/'expected.img').write_bytes(oracle)
        report.update(capture_sha256=sha(captured),linux_image_sha256=capture['linux_image_sha256'],linux_source_provenance=capture['linux_source_provenance'])
        sources={}
        for relative in ['drivers/virtio/block.cpp','drivers/virtio/block.hpp','drivers/virtio/poll.hpp']:
            f=out/'external'/relative;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((ROOT/relative).read_bytes());sources['external/'+relative]=sha(f.read_bytes())
        for relative in ['tests/native/ext4_completion.cpp','tools/jbd2/test_completion.py','tools/jbd2/native_support.py','tools/jbd2/admit_linux_fixture.py','tools/kernel_sdk.py']:
            f=out/'sources'/relative;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((ROOT/relative).read_bytes());sources['sources/'+relative]=sha(f.read_bytes())
        report['source_sha256']=sources
        members=run([ar,'t',sdk/'lib/libokernel_boot.a'],'boot-members').splitlines()
        if members.count('boot.S.o')!=1:raise ValueError('SDK boot member not unique')
        command=[str(ar),'p',str(sdk/'lib/libokernel_boot.a'),'boot.S.o'];report['commands'].append({'argv':command,'label':'extract-boot'})
        (out/'boot.o').write_bytes(subprocess.check_output(command))
        flags=['-std=c++23',*manifest['cxxflags'],'-fno-builtin','-Werror',*('-D'+d for d in manifest['defines']),'-I',str(sdk/'include'),'-I',str(out/'external'),'-I',str(out)]
        run([cxx,*flags,'-c',out/'external/drivers/virtio/block.cpp','-o',out/'driver.o'],'compile-driver')
        qemu=shutil.which(args.qemu or QEMU[args.arch])
        if not qemu:raise ValueError('QEMU profile absent')
        report['qemu']=run([qemu,'--version'],'qemu-version').splitlines()[0]
        definitions={'complete':[],'mapping-reject':['-DOK_COMPLETION_REJECT']}
        if args.faults:
            for kind in ('write','flush'):
                for point in range(1,5):definitions[f'{kind}-{point}']=[f'-DOK_COMPLETION_FAIL_{kind.upper()}={point}']
        images={}
        for case,extra in definitions.items():
            obj,elf,image=[out/(case+suffix) for suffix in ('.o','.elf','.bin')]
            run([cxx,*flags,*extra,'-DOK_COMPLETION_CASE="'+case+'"','-c',out/'sources/tests/native/ext4_completion.cpp','-o',obj],'compile-'+case)
            run([cxx,*manifest['ldflags'],'-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(sdk/'boot/linker.ld'),out/'boot.o',out/'driver.o',obj,sdk/'lib/libokernel.a','-lgcc','-o',elf],'link-'+case)
            run([sys.executable,out/'sources/tools/kernel_sdk.py','assemble','--sdk',sdk,'--arch',args.arch,'--mode',args.mode,'--compiler',cxx,'--elf',elf,'--out',image,'--objcopy',objcopy],'assemble-'+case)
            images[case]=image
        def launch(case,disk,label):
            command=machine(qemu,args.arch,images[case]);transport='virtio-blk-device' if args.arch in ('aarch64','arm32','rv32','rv64') else 'virtio-blk-pci'
            command+=['-drive',f'file={disk},format=raw,if=none,id=completion,cache=writeback','-device',transport+',drive=completion']
            record={'scenario':label,'status':'running','before_sha256':sha(disk.read_bytes())};report['cases'].append(record)
            report['commands'].append({'argv':command,'label':'qemu-'+label});save()
            boot(command,'EXT4_COMPLETION_PASS scope=qemu-device case='+case+' owner=exclusive-boot mount=none\n',out/(label+'.log'))
            record.update(status='passed',after_sha256=sha(disk.read_bytes()));save()
            return record
        disk=out/'completed.img';disk.write_bytes(captured);launch('complete',disk,'complete')
        if disk.read_bytes()!=oracle:raise ValueError('native completion differs from independent byte oracle')
        launch('complete',disk,'reopen')
        if disk.read_bytes()!=oracle:raise ValueError('clean reopen modified disk')
        negative=out/'mapping-reject.img';negative.write_bytes(altered(captured,facts,'mapping-reject'));before=negative.read_bytes()
        launch('mapping-reject',negative,'mapping-reject')
        if negative.read_bytes()!=before:raise ValueError('rejected metadata changed its disk')
        if args.faults:
            for case in definitions:
                if case in ('complete','mapping-reject'):continue
                disk=out/(case+'.img');disk.write_bytes(captured);launch(case,disk,case)
                launch('complete',disk,case+'-restart')
                if disk.read_bytes()!=oracle:raise ValueError(case+' restart differs from independent oracle')
        run(['e2fsck','-fn',out/'completed.img'],'completed-readonly-e2fsck')
        control=out/'e2fsprogs-recovery.img';control.write_bytes(captured)
        run(['e2fsck','-fy','-E','journal_only',control],'independent-journal-recovery',(0,1));run(['e2fsck','-fn',control],'independent-readonly-e2fsck')
        ref=control.read_bytes();allowed=set(range(1072,1078))|set(range(1088,1092))|set(range(1400,1408))|set(range(2044,2048))
        diffs=[i for i in range(len(ref)) if ref[i]!=oracle[i]]
        if any(i not in allowed for i in diffs):raise ValueError('e2fsprogs oracle differs outside documented bookkeeping')
        report['reference_bookkeeping_byte_differences']=diffs
        validate_sdk(sdk,args.arch,args.mode,cxx);report.update(status='passed',sdk_snapshot_revalidated=True)
    except Exception as error:
        report.update(status='failed',error=str(error));print('FAIL '+str(error),flush=True)
    finally:
        report['artifact_sha256']={str(p.relative_to(out)):sha(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='result.json' and 'sdk' not in p.relative_to(out).parts};save()
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
