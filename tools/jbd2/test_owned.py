#!/usr/bin/env python3
"""Run bounded ext4 metadata transactions through an exact SDK and disposable QEMU devices."""
from __future__ import annotations
import argparse,hashlib,json,shutil,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from native_support import ARCH_TRIPLES,QEMU,snapshot_sdk,machine,boot,validate_sdk
from admit_linux_fixture import inspect,header_for,checksum
from transaction_fixture import expected,clean_capture
ROOT=Path(__file__).resolve().parents[2]
def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arch',choices=tuple(ARCH_TRIPLES),required=True)
    p.add_argument('--mode',choices=('debug','release'),default='debug')
    p.add_argument('--kernel-sdk',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--qemu');p.add_argument('--faults',action='store_true')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'scope':'qemu-device-owned-ext4-transaction-checkpoint','status':'running','arch':args.arch,'mode':args.mode,
            'commands':[],'cases':[],'exclusive_session':'canonical-cache-private-session','mount_admission':False,
            'bounded_metadata_writer':True,'physical_power_loss':False,'faults_after_completed_device_operations':args.faults}
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
        if 'include/ok/fs/ext4_owned_transaction.hpp' not in manifest['files']:raise ValueError('exact SDK lacks transaction API')
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
        (out/'linux-dirty-capture.img').write_bytes(captured);clean=clean_capture(captured,facts);publication,oracle=expected(clean,facts);(out/'clean-input.img').write_bytes(clean);(out/'expected-published.img').write_bytes(publication);(out/'expected.img').write_bytes(oracle)
        report.update(capture_sha256=sha(captured),linux_image_sha256=capture['linux_image_sha256'],linux_source_provenance=capture['linux_source_provenance'])
        sources={}
        for relative in ['drivers/virtio/block.cpp','drivers/virtio/block.hpp','drivers/virtio/poll.hpp']:
            f=out/'external'/relative;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((ROOT/relative).read_bytes());sources['external/'+relative]=sha(f.read_bytes())
        for relative in ['tests/native/ext4_owned.cpp','tools/jbd2/test_owned.py','tools/jbd2/native_support.py','tools/jbd2/admit_linux_fixture.py','tools/jbd2/test_completion.py','tools/jbd2/transaction_fixture.py','tools/kernel_sdk.py']:
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
        definitions={'publish':['-DOK_OWNED_PUBLISH_ONLY'],'checkpoint':[],'discard':['-DOK_OWNED_DISCARD'],'reject':['-DOK_OWNED_REJECT'],'recover-new':['-DOK_OWNED_RECOVER','-DOK_OWNED_EXPECT_NEW=1'],'recover-old':['-DOK_OWNED_RECOVER','-DOK_OWNED_EXPECT_NEW=0']}
        if args.faults:
            for kind in ('write','flush'):
                for point in range(1,12 if kind=='write' else 10):definitions[f'{kind}-{point}']=[f'-DOK_OWNED_FAIL_{kind.upper()}={point}']
        images={}
        for case,extra in definitions.items():
            obj,elf,image=[out/(case+suffix) for suffix in ('.o','.elf','.bin')]
            run([cxx,*flags,*extra,'-DOK_OWNED_CASE="'+case+'"','-c',out/'sources/tests/native/ext4_owned.cpp','-o',obj],'compile-'+case)
            run([cxx,*manifest['ldflags'],'-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(sdk/'boot/linker.ld'),out/'boot.o',out/'driver.o',obj,sdk/'lib/libokernel.a','-lgcc','-o',elf],'link-'+case)
            run([sys.executable,out/'sources/tools/kernel_sdk.py','assemble','--sdk',sdk,'--arch',args.arch,'--mode',args.mode,'--compiler',cxx,'--elf',elf,'--out',image,'--objcopy',objcopy],'assemble-'+case)
            images[case]=image
        def launch(case,disk,label):
            command=machine(qemu,args.arch,images[case]);transport='virtio-blk-device' if args.arch in ('aarch64','arm32','rv32','rv64') else 'virtio-blk-pci'
            command+=['-drive',f'file={disk},format=raw,if=none,id=completion,cache=writeback','-device',transport+',drive=completion']
            record={'scenario':label,'status':'running','before_sha256':sha(disk.read_bytes())};report['cases'].append(record)
            report['commands'].append({'argv':command,'label':'qemu-'+label});save()
            boot(command,'EXT4_OWNED_PASS scope=qemu-device case='+case+' owner=private-session mount=none\n',out/(label+'.log'))
            record.update(status='passed',after_sha256=sha(disk.read_bytes()));save()
            return record
        disk=out/'published.img';disk.write_bytes(clean);launch('publish',disk,'publish')
        if disk.read_bytes()!=publication:raise ValueError('publication differs from independent byte oracle')
        recovered=out/'completed.img';recovered.write_bytes(clean);launch('checkpoint',recovered,'checkpoint')
        if recovered.read_bytes()!=oracle:raise ValueError('checkpoint differs from independent byte oracle')
        negative=out/'reject.img';negative.write_bytes(clean);launch('reject',negative,'reject')
        if negative.read_bytes()!=clean:raise ValueError('rejected request modified its disk')
        discarded=out/'discard.img';discarded.write_bytes(clean);launch('discard',discarded,'discard')
        if discarded.read_bytes()!=clean:raise ValueError('discard changed disk')
        if args.faults:
            for case in definitions:
                if case in ('publish','checkpoint','discard','reject','recover-new','recover-old'):continue
                disk=out/(case+'.img');disk.write_bytes(clean);launch(case,disk,case)
                before=disk.read_bytes();is_new=int(case.split('-')[1]) >= (7 if case.startswith('write-') else 5)
                launch('recover-new' if is_new else 'recover-old',disk,case+'-restart')
                if is_new:
                    if disk.read_bytes()!=oracle:raise ValueError(case+' new restart differs from oracle')
                else:
                    old=bytearray(clean);j=facts['journal_first']*1024;old[j+1024:j+6144]=before[j+1024:j+6144]
                    if disk.read_bytes()!=old:raise ValueError(case+' unpublished restart changed original metadata')
        run(['e2fsck','-fn',out/'completed.img'],'completed-readonly-e2fsck')
        control=out/'e2fsprogs-recovery.img';control.write_bytes(publication)
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
