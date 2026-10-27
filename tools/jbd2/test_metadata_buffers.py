#!/usr/bin/env python3
"""Read canonical/private metadata through an exact Kernel SDK on private QEMU disks."""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from native_support import ARCH_TRIPLES,QEMU,snapshot_sdk,machine,boot,validate_sdk
from admit_linux_fixture import inspect,header_for
from transaction_fixture import clean_capture
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
    report={'scope':'qemu-device-canonical-metadata-buffer-ownership','status':'running','arch':args.arch,'mode':args.mode,
            'commands':[],'cases':[],'kernel_session_service':True,'canonical_buffer_owner':True,'private_versions':True,
            'home_writeback':False,'transaction_commit':False,'quarantine_reset_supported':False,'mount_admission':False,
            'native_smp':False,'physical_power_loss':False,'faults_after_completed_device_operations':args.faults}
    def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(command,label):
        item={'argv':[str(x) for x in command],'label':label,'status':'running'};report['commands'].append(item);save();start=time.monotonic()
        result=subprocess.run(item['argv'],text=True,capture_output=True);(out/(label+'.log')).write_text(result.stdout+result.stderr)
        item.update(status='passed' if not result.returncode else 'failed',returncode=result.returncode,seconds=time.monotonic()-start);save()
        if result.returncode:raise RuntimeError(label+' failed')
        return result.stdout+result.stderr
    save()
    try:
        prefix=args.toolchain.resolve()/'bin'/(ARCH_TRIPLES[args.arch]+'-');cxx,ar,objcopy=[Path(str(prefix)+x) for x in ('g++','ar','objcopy')]
        sdk=out/'sdk';manifest,sdk_hash=snapshot_sdk(args.kernel_sdk,sdk,args.arch,cxx,args.mode)
        if not {'include/ok/block/sessions.hpp','include/ok/fs/ext4/txn.hpp'}.issubset(manifest['files']):raise ValueError('exact SDK lacks session/metadata API')
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
        (out/'linux-dirty-capture.img').write_bytes(captured);clean=clean_capture(captured,facts);(out/'clean-input.img').write_bytes(clean)
        blocks={'superblock':1,'inodeblock':facts['seed_block'],'journal':facts['journal_first']}
        generated=['#pragma once\nnamespace metadata_fixture {\n']
        for name,block in blocks.items():
            value=clean[block*1024:(block+1)*1024]
            generated.append('inline constexpr std::array<ok::u8,1024> '+name+'{'+','.join(str(x) for x in value)+'};\n')
        generated.append('}\n');(out/'metadata_fixture.hpp').write_text(''.join(generated))
        report.update(capture_sha256=sha(captured),clean_input_sha256=sha(clean),metadata_blocks=blocks)
        sources={}
        for relative in ['drivers/virtio/block.cpp','drivers/virtio/block.hpp','drivers/virtio/poll.hpp']:
            f=out/'external'/relative;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((ROOT/relative).read_bytes());sources['external/'+relative]=sha(f.read_bytes())
        for relative in ['tests/native/metadata_buffers.cpp','tools/jbd2/test_metadata_buffers.py','tools/jbd2/native_support.py','tools/jbd2/admit_linux_fixture.py','tools/jbd2/test_completion.py','tools/jbd2/transaction_fixture.py','tools/kernel_sdk.py']:
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
        definitions={'ownership':[],'readonly':['-DOK_METADATA_READONLY']}
        if args.faults:
            for point in range(1,4):definitions[f'read-{point}']=[f'-DOK_METADATA_FAIL_READ={point}']
        for case,extra in definitions.items():
            obj,elf,image=[out/(case+suffix) for suffix in ('.o','.elf','.bin')]
            run([cxx,*flags,*extra,'-DOK_METADATA_CASE="'+case+'"','-c',out/'sources/tests/native/metadata_buffers.cpp','-o',obj],'compile-'+case)
            run([cxx,*manifest['ldflags'],'-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(sdk/'boot/linker.ld'),out/'boot.o',out/'driver.o',obj,sdk/'lib/libokernel.a','-lgcc','-o',elf],'link-'+case)
            run([sys.executable,out/'sources/tools/kernel_sdk.py','assemble','--sdk',sdk,'--arch',args.arch,'--mode',args.mode,'--compiler',cxx,'--elf',elf,'--out',image,'--objcopy',objcopy],'assemble-'+case)
            disk=out/(case+'.img');disk.write_bytes(clean)
            command=machine(qemu,args.arch,image);transport='virtio-blk-device' if args.arch in ('aarch64','arm32','rv32','rv64') else 'virtio-blk-pci'
            command+=['-drive',f'file={disk},format=raw,if=none,id=metadata,cache=writeback','-device',transport+',drive=metadata']
            record={'scenario':case,'status':'running','before_sha256':sha(clean)};report['cases'].append(record)
            report['commands'].append({'argv':command,'label':'qemu-'+case});save()
            boot(command,'METADATA_BUFFER_PASS scope=qemu-device case='+case+' home-writes=0 mount=none\n',out/(case+'.log'))
            after=disk.read_bytes()
            if after!=clean:raise ValueError(case+' changed disk during canonical/private reads')
            record.update(status='passed',after_sha256=sha(after));save()
        run(['e2fsck','-fn',out/'clean-input.img'],'unchanged-input-readonly-e2fsck')
        if (out/'clean-input.img').read_bytes()!=clean:raise ValueError('readonly fsck modified input')
        validate_sdk(sdk,args.arch,args.mode,cxx);report.update(status='passed',sdk_snapshot_revalidated=True)
    except Exception as error:
        report.update(status='failed',error=str(error));print('FAIL '+str(error),flush=True)
    finally:
        report['artifact_sha256']={str(p.relative_to(out)):sha(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='result.json' and 'sdk' not in p.relative_to(out).parts};save()
    return 0 if report['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
