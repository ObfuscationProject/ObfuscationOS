#!/usr/bin/env python3
"""SDK-only actual native/musl ext4 timestamp events on a retained disposable image."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import struct
import json
import os
import selectors
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/jbd2'), str(ROOT/'tools'), str(ROOT/'scripts')]
from native_support import ARCH_TRIPLES, QEMU, snapshot_sdk, validate_sdk
from qemu_distro import command_for


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def executable_identity(path, arch, linux):
    expected = {'i386':(1,1,3),'x86_64':(2,1,62),'aarch64':(2,1,183),'arm32':(1,1,40),
                'rv32':(1,1,243),'rv64':(2,1,243),'loongarch64':(2,1,258),
                'mips':(1,2,8),'mips64':(2,2,8),'ppc':(1,2,20)}
    data = Path(path).read_bytes()
    if len(data) < 52 or data[:4] != b'\x7fELF' or data[6] != 1 or data[5] not in (1,2):
        raise ValueError('invalid explicit user ELF identity')
    kind,machine = struct.unpack_from(('<' if data[5] == 1 else '>')+'HH',data,16)
    abi_version = 1 if linux and arch in ('mips','mips64') else 0
    if (kind != 2 or (data[4],data[5],machine) != expected[arch] or
            data[7] != (3 if linux else 0) or data[8] != abi_version):
        raise ValueError('explicit user ELF architecture/personality mismatch')
    return {'elf_class':32 if data[4] == 1 else 64,'byte_order':'little' if data[5] == 1 else 'big',
            'machine':machine,'osabi':data[7],'abi_version':data[8]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug','release'), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--rootfs', type=Path, required=True)
    parser.add_argument('--native-runner', type=Path, required=True)
    parser.add_argument('--native-identity', type=Path, required=True)
    parser.add_argument('--native-source', type=Path, default=ROOT/'tests/musl/ext4_timestamps_runner.c')
    parser.add_argument('--musl-probe', type=Path, required=True)
    parser.add_argument('--musl-source', type=Path, default=ROOT/'tests/musl/ext4_timestamps.c')
    parser.add_argument('--shared-header', type=Path, default=ROOT/'tests/musl/ext4_timestamp_log.h')
    parser.add_argument('--fixture-source', type=Path, default=ROOT/'tests/native/ext4_timestamp_user.cpp')
    parser.add_argument('--evidence-source', type=Path, default=ROOT/'tools/ext4_timestamp_user_evidence.py')
    parser.add_argument('--musl-dependencies', type=Path, required=True)
    parser.add_argument('--source-inventory', type=Path, required=True,
                        help='Exact source-sha256.json bound by the musl dependency sidecar')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = {'status':'running','scope':'actual native and musl user-mode maintained ext4 timestamp fixture',
              'architecture':args.arch,'mode':args.mode,'authority':'uid1000',
              'sdk_only':True,'kernel_source_compiled':False,'physical':False,'smp':False,
              'test_reaper':'unscheduled lifecycle record; not target execution evidence',
              'native_execution':False,'musl_execution':False,'linux_stat':'not-executed',
              'linux_reference_boot':False,'cpus':1,'commands':[]}
    def save(): (out/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    def snapshot_json(source,name):
        data = Path(source).read_bytes()
        (out/name).write_bytes(data)
        return json.loads(data)
    def run(command,label,binary=False,**kwargs):
        command = list(map(str, command))
        row = {'label':label,'argv':command}; report['commands'].append(row); save()
        start = time.monotonic()
        result = subprocess.run(command,stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE if binary else subprocess.STDOUT,**kwargs)
        (out/(label+'.log')).write_bytes(result.stderr if binary else result.stdout)
        if binary:
            (out/(label+'.bin')).write_bytes(result.stdout)
            row['binary_sha256'] = sha(out/(label+'.bin'))
        row.update(returncode=result.returncode,seconds=time.monotonic()-start,log_sha256=sha(out/(label+'.log')))
        save()
        if result.returncode: raise RuntimeError(label+' failed')
        return result.stdout
    save(); disk = None; initial = None; process = None; serial = bytearray()
    try:
        prefix = args.toolchain.resolve()/'bin'/(ARCH_TRIPLES[args.arch]+'-')
        cxx, ar, objcopy = [Path(str(prefix)+suffix) for suffix in ('g++','ar','objcopy')]
        sdk = out/'sdk'
        manifest, sdk_hash = snapshot_sdk(args.kernel_sdk,sdk,args.arch,cxx,args.mode)
        if manifest['abi_version'] != 31: raise ValueError('exact SDK31 required')
        report.update(sdk_manifest_sha256=sdk_hash,sdk_abi=31,compiler=manifest['compiler'])
        native = args.native_runner.resolve(); native_identity = snapshot_json(args.native_identity,'native-identity.json')
        if (native_identity.get('status') != 'built-not-executed' or
                native_identity.get('sdk_manifest_sha256') != sdk_hash or
                native_identity.get('architecture') != args.arch or native_identity.get('mode') != args.mode):
            raise ValueError('native artifact SDK/architecture/mode identity admission failed')
        for name,path in [('ext4_timestamps_runner.c',args.native_source),
                          ('ext4_timestamp_log.h',args.shared_header),
                          ('ext4-timestamps-runner.elf',native)]:
            if sha(path) != native_identity.get('files',{}).get(name):
                raise ValueError('native artifact hash admission failed: '+name)
        musl = args.musl_probe.resolve(); musl_manifest = snapshot_json(musl/'manifest.json','musl-manifest.json')
        if musl_manifest.get('status') != 'built-not-executed' or sha(musl/'bootstrap.elf') != musl_manifest.get('elf_sha256'):
            raise ValueError('musl artifact admission failed')
        if (musl_manifest.get('architecture') != args.arch or musl_manifest.get('mode') not in ('debug','release') or
                musl_manifest.get('source_mode') not in ('debug','release') or musl_manifest.get('executed') is not False):
            raise ValueError('musl architecture/source-mode admission failed')
        dependencies = snapshot_json(args.musl_dependencies,'musl-dependencies.json')
        inventory = snapshot_json(args.source_inventory,'source-inventory.json')
        if (dependencies.get('status') != 'built-not-executed' or dependencies.get('architecture') != args.arch or
                dependencies.get('mode') != musl_manifest['mode'] or
                dependencies.get('musl_manifest_sha256') != sha(out/'musl-manifest.json') or
                dependencies.get('elf_sha256') != musl_manifest['elf_sha256'] or
                dependencies.get('source_rechecked_after_build') is not True or
                dependencies.get('source_snapshot_sha256') != sha(out/'source-inventory.json')):
            raise ValueError('musl dependency identity admission failed')
        for name,path in [('ext4_timestamps.c',args.musl_source),('ext4_timestamp_log.h',args.shared_header)]:
            if sha(path) != dependencies.get('files',{}).get(name):
                raise ValueError('musl actual source/dependency hash mismatch: '+name)
        for name,path in [('ext4_timestamps_runner.c',args.native_source),
                          ('ext4_timestamps.c',args.musl_source),('ext4_timestamp_log.h',args.shared_header)]:
            if inventory.get('tests/musl/'+name) != sha(path):
                raise ValueError('compiled source inventory mismatch: '+name)
        if sha(args.musl_source) != musl_manifest.get('probe_sha256'):
            raise ValueError('selected musl source differs from explicit artifact')
        if musl_manifest.get('probe_sources',{}).get(str(args.musl_source.resolve())) != sha(args.musl_source):
            raise ValueError('musl build did not record the selected source path')
        report['user_elf_identity'] = {
            'native':executable_identity(native,args.arch,False),
            'musl':executable_identity(musl/'bootstrap.elf',args.arch,True)}
        report.update(musl_source_mode=musl_manifest['source_mode'],musl_artifact_mode=musl_manifest['mode'],
                      musl_mode_reused=musl_manifest['mode'] != args.mode,
                      musl_sdk_dependency='none; audited static Linux ABI ELF reused independently of exact native SDK mode')
        report['input_identity_sha256'] = {name:sha(out/name) for name in
            ('native-identity.json','musl-manifest.json','musl-dependencies.json','source-inventory.json')}
        sources = ('tests/native/ext4_timestamp_user.cpp','tests/musl/ext4_timestamps.c',
                   'tests/musl/ext4_timestamps_runner.c','tests/musl/ext4_timestamp_log.h','drivers/virtio/block.cpp','drivers/virtio/block.hpp','drivers/virtio/poll.hpp',
                   'tools/mkext4.py','tools/kernel_sdk.py','tools/jbd2/native_support.py','scripts/qemu_distro.py',
                   'tools/ext4_timestamp_user_evidence.py','tools/test_ext4_timestamp_user.py')
        report['source_sha256'] = {}
        overrides = {'tests/musl/ext4_timestamps_runner.c':args.native_source.resolve(),
                     'tests/musl/ext4_timestamps.c':args.musl_source.resolve(),
                     'tests/musl/ext4_timestamp_log.h':args.shared_header.resolve(),
                     'tests/native/ext4_timestamp_user.cpp':args.fixture_source.resolve(),
                     'tools/ext4_timestamp_user_evidence.py':args.evidence_source.resolve()}
        report['explicit_probe_sources'] = {name:str(path) for name,path in overrides.items()}
        for relative in sources:
            path = out/'sources'/relative; path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(overrides.get(relative,ROOT/relative),path); report['source_sha256'][relative] = sha(path)
        if report['source_sha256']['tests/musl/ext4_timestamps_runner.c'] != native_identity['files']['ext4_timestamps_runner.c'] or report['source_sha256']['tests/musl/ext4_timestamps.c'] != musl_manifest['probe_sha256']:
            raise ValueError('probe source changed during snapshot')
        if report['source_sha256']['tests/musl/ext4_timestamp_log.h'] != dependencies['files']['ext4_timestamp_log.h']:
            raise ValueError('shared dependency changed during snapshot')
        evidence_path = out/'sources/tools/ext4_timestamp_user_evidence.py'
        spec = importlib.util.spec_from_file_location('ext4_timestamp_fixture_evidence',evidence_path)
        evidence_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evidence_module)
        # Keep manifested SDK bytes immutable; transform only a separate copy to
        # reuse its C/C++ runtime support while the fixture owns kernel_main.
        members = run([ar,'t',sdk/'lib/libokernel_boot.a'],'boot-members').decode().splitlines()
        for member in ('boot.S.o','platform.cpp.o','kernel_main.cpp.o'):
            if members.count(member) != 1: raise ValueError('ambiguous boot member '+member)
            (out/member).write_bytes(run([ar,'p',sdk/'lib/libokernel_boot.a',member],'extract-'+member,binary=True))
        run([objcopy,'--redefine-sym','kernel_main=ext4_time_fixture_unused_sdk_entry',
             out/'kernel_main.cpp.o',out/'sdk-support.o'],'rename-unused-entry')
        report['sdk_support_transform'] = {'input_member':'kernel_main.cpp.o',
              'input_sha256':sha(out/'kernel_main.cpp.o'),'output_sha256':sha(out/'sdk-support.o'),
              'change':'only kernel_main symbol renamed in a separate copied SDK object; no Kernel source build'}
        project = out/'project'; project.mkdir()
        def lua(value): return json.dumps(str(value))
        def values(items): return ', '.join(lua(item) for item in items)
        flags = ['-std=c++23',*manifest['cxxflags'],'-fno-builtin','-Werror']
        definitions = list(manifest['defines'])
        objects = [out/'boot.S.o',out/'platform.cpp.o',out/'sdk-support.o']
        link = [*manifest['ldflags'],'-nostdlib','-static','-no-pie','-Wl,--build-id=none',
                '-Wl,-z,max-page-size=0x1000','-Wl,-T,'+str(sdk/'boot/linker.ld'),
                '-Wl,--start-group',*objects,sdk/'lib/libokernel.a','-lgcc','-Wl,--end-group']
        (project/'xmake.lua').write_text('\n'.join([
            'set_project("ext4-timestamp-user-fixture")','set_languages("c++23")',
            'toolchain("ext4-time-fixture-cross")','set_kind("standalone")',
            'set_toolset("cxx", '+lua(cxx)+')','set_toolset("ld", '+lua(cxx)+')',
            'toolchain_end()',
            'target("ext4-timestamp-user-fixture")','set_kind("binary")','set_toolchains("ext4-time-fixture-cross")',
            'set_targetdir('+lua(out)+')','set_filename("fixture.elf")',
            'add_cxxflags('+values(flags)+', {force = true})',
            'add_defines('+values(definitions)+')','add_includedirs('+lua(sdk/'include')+')',
            'add_files('+values(out/'sources'/p for p in ('tests/native/ext4_timestamp_user.cpp',
                       'drivers/virtio/block.cpp'))+')',
            'add_ldflags('+values(link)+', {force = true})','target_end()','']))
        env = dict(os.environ, XMAKE_ROOT='y', TZ='UTC')
        for variable in ('CPATH','CPLUS_INCLUDE_PATH','C_INCLUDE_PATH','LIBRARY_PATH','GCC_EXEC_PREFIX','COMPILER_PATH'):
            env.pop(variable,None)
        xmake = Path(shutil.which('xmake') or '')
        if not xmake.is_file(): raise ValueError('missing xmake')
        run([xmake,'f','-P',project,'-y','--ccache=n'],'xmake-configure',env=env,cwd=project)
        run([xmake,'-vD','-P',project,'ext4-timestamp-user-fixture'],'xmake-build',env=env,cwd=project)
        image = out/'fixture.bin'
        run([sys.executable,out/'sources/tools/kernel_sdk.py','assemble','--sdk',sdk,'--arch',args.arch,
             '--mode',args.mode,'--compiler',cxx,'--elf',out/'fixture.elf','--out',image,'--objcopy',objcopy], 'assemble')
        root = out/'rootfs'; shutil.copytree(args.rootfs.resolve(),root,symlinks=True)
        for name,mode in [('apps',0o755),('bin',0o755),('home',0o777),('tmp',0o1777)]:
            directory = root/name
            if directory.is_symlink(): raise ValueError('fixture directory must not be a symlink: '+name)
            directory.mkdir(exist_ok=True); directory.chmod(mode)
        fixture_link = root/'home/fixture-link'
        if fixture_link.exists() or fixture_link.is_symlink():
            raise ValueError('fixture symlink collides with input rootfs')
        fixture_link.symlink_to('musl-time')
        for source,target in [(args.native_runner.resolve(),root/'apps/ext4-timestamps-runner.elf'),
                              (musl/'bootstrap.elf',root/'bin/musl-ext4-timestamps')]:
            if target.is_symlink(): raise ValueError('fixture executable destination is a symlink')
            shutil.copy2(source,target); target.chmod(0o555)
        report['native_runner_sha256'] = sha(root/'apps/ext4-timestamps-runner.elf')
        report['musl_elf_sha256'] = sha(root/'bin/musl-ext4-timestamps')
        if report['native_runner_sha256'] != native_identity['files']['ext4-timestamps-runner.elf'] or report['musl_elf_sha256'] != musl_manifest['elf_sha256']:
            raise ValueError('probe artifact changed during snapshot')
        disk = out/'rootfs.ext4.img'; initial = out/'rootfs-input.ext4.img'
        run([sys.executable,out/'sources/tools/mkext4.py','--root',root,'--out',disk],'package-ext4')
        shutil.copy2(disk,initial)
        report['initial_disk_sha256'] = sha(initial)
        run(['e2fsck','-fn',initial],'initial-fsck')
        if sha(initial) != report['initial_disk_sha256']: raise ValueError('initial fsck changed bytes')
        qemu = Path(shutil.which(QEMU[args.arch]) or '')
        if not qemu.is_file(): raise ValueError('missing QEMU')
        command = command_for(qemu,args.arch,image,disk,'none')
        command += ['-smp','1','-rtc','base=2024-02-29T12:34:56,clock=vm,driftfix=none']
        if args.arch in ('x86_64','i386'):
            command += ['-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
        report['guest_argv'] = list(map(str,command))
        report['tool_sha256'] = {str(p.resolve()):sha(p.resolve()) for p in
                    (cxx,ar,objcopy,xmake,qemu,Path(sys.executable),Path(shutil.which('e2fsck')))}
        report['kernel_image_sha256'] = sha(image); save()
        process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        selector = selectors.DefaultSelector(); selector.register(process.stdout,selectors.EVENT_READ)
        guest_started = time.monotonic(); deadline = guest_started+100
        while time.monotonic() < deadline:
            for key,_ in selector.select(timeout=0.1):
                data = os.read(key.fileobj.fileno(),65536)
                if data: serial.extend(data)
            completed = serial.split(b'\n')[:-1]
            if any(line.startswith((b'EXT4_TIME_USER_FIXTURE_PASS ', b'EXT4_TIME_USER_FIXTURE_FAIL ', b'EXT4_TIME_NATIVE_FAIL ', b'EXT4_TIME_MUSL_FAIL ')) for line in completed) or process.poll() is not None:
                break
        report['guest_elapsed_seconds'] = time.monotonic()-guest_started
        report['guest_timed_out'] = time.monotonic() >= deadline
        if process.poll() is None: process.terminate()
        try: tail,_ = process.communicate(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); tail,_ = process.communicate()
        serial.extend(tail or b''); selector.close(); (out/'serial.log').write_bytes(serial)
        report['guest_returncode'] = process.returncode; process = None
        if report['guest_timed_out']: raise ValueError('user fixture timed out after100 seconds')
        text = serial.decode(errors='replace')
        report['evidence'] = evidence_module.validate(text, initial.read_bytes(), disk.read_bytes())
        if report['evidence'].get('linux_stat') != 'qualified':
            raise ValueError('SDK31 requires qualified Linux stat evidence')
        report.update(native_execution=True,musl_execution=True,linux_stat='qualified')
        final_before_fsck = sha(disk)
        run(['e2fsck','-fn',disk],'final-fsck')
        if sha(disk) != final_before_fsck: raise ValueError('readonly final fsck changed bytes')
        report.update(final_disk_sha256=sha(disk),initial_disk_unchanged=sha(initial)==report['initial_disk_sha256'])
        if not report['initial_disk_unchanged']: raise ValueError('retained initial image changed')
        for name,expected in report['source_sha256'].items():
            if sha(out/'sources'/name) != expected: raise ValueError('snapshot source drift '+name)
        for name,expected in report['input_identity_sha256'].items():
            if sha(out/name) != expected: raise ValueError('retained identity drift '+name)
        validate_sdk(sdk,args.arch,args.mode,cxx)
        report.update(status='passed',sdk_snapshot_revalidated=True)
    except BaseException as error:
        report.update(status='failed',error=str(error)); print('FAIL',error,flush=True)
    finally:
        if process is not None:
            process.terminate()
            try: tail,_=process.communicate(timeout=3)
            except subprocess.TimeoutExpired: process.kill();tail,_=process.communicate()
            serial.extend(tail or b'')
        if serial: (out/'serial.log').write_bytes(serial)
        if disk and disk.exists(): report['final_disk_sha256']=sha(disk)
        if initial and initial.exists(): report['retained_initial_disk_sha256']=sha(initial)
        report['artifact_sha256']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*'))
                                  if p.is_file() and p.name!='result.json' and 'sdk' not in p.relative_to(out).parts}
        save()
    print(report['status'],report['scope'],flush=True)
    return 0 if report['status']=='passed' else 1

if __name__ == '__main__': raise SystemExit(main())
