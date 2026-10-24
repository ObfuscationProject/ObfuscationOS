#!/usr/bin/env python3
"""SDK-only real native/musl clock-set authority fixture on disposable ext4."""
from pathlib import Path
import argparse
import hashlib
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
from clock_set_evidence import validate_clock_set

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug','release'), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--rootfs', type=Path, required=True)
    parser.add_argument('--native-runner', type=Path, required=True)
    parser.add_argument('--native-identity', type=Path, required=True)
    parser.add_argument('--native-source', type=Path, default=ROOT/'tests/musl/clock_set_runner.c')
    parser.add_argument('--musl-probe', type=Path, required=True)
    parser.add_argument('--musl-source', type=Path, default=ROOT/'tests/musl/clock_set.c')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--root-mode', action='store_true')
    parser.add_argument('--require-wait', action='append', choices=('sleep','poll','select'), default=[])
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = {'status':'running','scope':'actual native and musl user-mode clock setting fixture',
              'architecture':args.arch,'mode':args.mode,'authority':'root' if args.root_mode else 'nonroot',
              'sdk_only':True,'kernel_source_compiled':False,'physical':False,'smp':False,
              'test_reaper':'unscheduled lifecycle record; not target execution evidence',
              'commands':[]}
    def save(): (out/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    def run(command,label,**kwargs):
        command = list(map(str, command))
        row = {'label':label,'argv':command}; report['commands'].append(row); save()
        start = time.monotonic()
        result = subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,**kwargs)
        (out/(label+'.log')).write_bytes(result.stdout)
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
        native = args.native_runner.resolve(); native_identity = read(args.native_identity)
        if native_identity.get('status') != 'built-not-executed' or native_identity.get('sdk_manifest_sha256') != sdk_hash:
            raise ValueError('native artifact SDK identity admission failed')
        for name,path in [('clock_set_runner.c',args.native_source),('clock-set-runner.elf',native)]:
            if sha(path) != native_identity.get('files',{}).get(name):
                raise ValueError('native artifact hash admission failed: '+name)
        shutil.copy2(args.native_identity,out/'native-identity.json')
        report['native_identity_sha256'] = sha(out/'native-identity.json')
        musl = args.musl_probe.resolve(); musl_manifest = read(musl/'manifest.json')
        if musl_manifest['status'] != 'built-not-executed' or sha(musl/'bootstrap.elf') != musl_manifest['elf_sha256']:
            raise ValueError('musl artifact admission failed')
        if musl_manifest['architecture'] != args.arch or musl_manifest['mode'] not in ('debug','release') or musl_manifest['source_mode'] not in ('debug','release'):
            raise ValueError('musl architecture/source-mode admission failed')
        report.update(musl_source_mode=musl_manifest['source_mode'],musl_artifact_mode=musl_manifest['mode'],
                      musl_mode_reused=musl_manifest['mode'] != args.mode,
                      musl_sdk_dependency='none; audited static Linux ABI ELF reused independently of exact native SDK mode')
        if sha(args.musl_source) != musl_manifest['probe_sha256']:
            raise ValueError('selected musl source differs from explicit artifact')
        sources = ('tests/native/clock_set_unprivileged.cpp','tests/musl/clock_set.c',
                   'tests/musl/clock_set_runner.c','modules/boot/storage.cpp',
                   'drivers/virtio/block.cpp','drivers/virtio/block.hpp','drivers/virtio/poll.hpp',
                   'tools/mkext4.py','tools/kernel_sdk.py','tools/jbd2/native_support.py','scripts/qemu_distro.py',
                   'tools/clock_set_evidence.py','tools/test_clock_set_foundation.py')
        report['source_sha256'] = {}
        overrides = {'tests/musl/clock_set_runner.c':args.native_source.resolve(),
                     'tests/musl/clock_set.c':args.musl_source.resolve()}
        report['explicit_probe_sources'] = {name:str(path) for name,path in overrides.items()}
        for relative in sources:
            path = out/'sources'/relative; path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(overrides.get(relative,ROOT/relative),path); report['source_sha256'][relative] = sha(path)
        if report['source_sha256']['tests/musl/clock_set_runner.c'] != native_identity['files']['clock_set_runner.c'] or report['source_sha256']['tests/musl/clock_set.c'] != musl_manifest['probe_sha256']:
            raise ValueError('probe source changed during snapshot')
        shutil.copy2(musl/'manifest.json',out/'musl-manifest.json')
        # Keep manifested SDK bytes immutable; transform only a separate copy to
        # reuse its C/C++ runtime support while the fixture owns kernel_main.
        members = run([ar,'t',sdk/'lib/libokernel_boot.a'],'boot-members').decode().splitlines()
        for member in ('boot.S.o','platform.cpp.o','kernel_main.cpp.o'):
            if members.count(member) != 1: raise ValueError('ambiguous boot member '+member)
            (out/member).write_bytes(run([ar,'p',sdk/'lib/libokernel_boot.a',member],'extract-'+member))
        run([objcopy,'--redefine-sym','kernel_main=clock_fixture_unused_sdk_entry',
             out/'kernel_main.cpp.o',out/'sdk-support.o'],'rename-unused-entry')
        report['sdk_support_transform'] = {'input_member':'kernel_main.cpp.o',
              'input_sha256':sha(out/'kernel_main.cpp.o'),'output_sha256':sha(out/'sdk-support.o'),
              'change':'only kernel_main symbol renamed in a separate copied SDK object; no Kernel source build'}
        project = out/'project'; project.mkdir()
        def lua(value): return json.dumps(str(value))
        def values(items): return ', '.join(lua(item) for item in items)
        flags = ['-std=c++23',*manifest['cxxflags'],'-fno-builtin','-Werror']
        definitions = [*manifest['defines'],*(['CLOCK_SET_FIXTURE_ROOT'] if args.root_mode else [])]
        objects = [out/'boot.S.o',out/'platform.cpp.o',out/'sdk-support.o']
        link = [*manifest['ldflags'],'-nostdlib','-static','-no-pie','-Wl,--build-id=none',
                '-Wl,-z,max-page-size=0x1000','-Wl,-T,'+str(sdk/'boot/linker.ld'),
                '-Wl,--start-group',*objects,sdk/'lib/libokernel.a','-lgcc','-Wl,--end-group']
        (project/'xmake.lua').write_text('\n'.join([
            'set_project("clock-set-fixture")','set_languages("c++23")',
            'toolchain("clock-fixture-cross")','set_kind("standalone")',
            'set_toolset("cxx", '+lua(cxx)+')','set_toolset("ld", '+lua(cxx)+')',
            'toolchain_end()',
            'target("clock-set-fixture")','set_kind("binary")','set_toolchains("clock-fixture-cross")',
            'set_targetdir('+lua(out)+')','set_filename("fixture.elf")',
            'add_cxxflags('+values(flags)+', {force = true})',
            'add_defines('+values(definitions)+')','add_includedirs('+lua(sdk/'include')+')',
            'add_files('+values(out/'sources'/p for p in ('tests/native/clock_set_unprivileged.cpp',
                       'modules/boot/storage.cpp','drivers/virtio/block.cpp'))+')',
            'add_ldflags('+values(link)+', {force = true})','target_end()','']))
        env = dict(os.environ, XMAKE_ROOT='y')
        xmake = Path(shutil.which('xmake') or '')
        if not xmake.is_file(): raise ValueError('missing xmake')
        run([xmake,'f','-P',project,'-y','--ccache=n'],'xmake-configure',env=env,cwd=project)
        run([xmake,'-vD','-P',project,'clock-set-fixture'],'xmake-build',env=env,cwd=project)
        image = out/'fixture.bin'
        run([sys.executable,out/'sources/tools/kernel_sdk.py','assemble','--sdk',sdk,'--arch',args.arch,
             '--mode',args.mode,'--compiler',cxx,'--elf',out/'fixture.elf','--out',image,'--objcopy',objcopy], 'assemble')
        root = out/'rootfs'; shutil.copytree(args.rootfs.resolve(),root,symlinks=True)
        (root/'apps').mkdir(exist_ok=True); (root/'apps').chmod(0o755)
        for source,target in [(args.native_runner.resolve(),root/'apps/clock-set-runner.elf'),
                              (musl/'bootstrap.elf',root/'bin/musl-clock-set')]:
            shutil.copy2(source,target); target.chmod(0o755)
        report['native_runner_sha256'] = sha(root/'apps/clock-set-runner.elf')
        report['musl_elf_sha256'] = sha(root/'bin/musl-clock-set')
        if report['native_runner_sha256'] != native_identity['files']['clock-set-runner.elf'] or report['musl_elf_sha256'] != musl_manifest['elf_sha256']:
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
        command += ['-rtc','base=2024-02-29T12:34:56,clock=vm,driftfix=none']
        if args.arch in ('x86_64','i386'):
            command += ['-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
        report['guest_argv'] = list(map(str,command))
        report['tool_sha256'] = {str(p.resolve()):sha(p.resolve()) for p in
                    (cxx,ar,objcopy,xmake,qemu,Path(sys.executable),Path(shutil.which('e2fsck')))}
        report['kernel_image_sha256'] = sha(image); save()
        process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        selector = selectors.DefaultSelector(); selector.register(process.stdout,selectors.EVENT_READ)
        deadline = time.monotonic()+100
        while time.monotonic() < deadline:
            for key,_ in selector.select(timeout=0.1):
                data = os.read(key.fileobj.fileno(),65536)
                if data: serial.extend(data)
            completed = serial.split(b'\n')[:-1]
            if any(line.startswith((b'CLOCK_SET_FIXTURE_PASS ', b'CLOCK_SET_FIXTURE_FAIL ')) for line in completed) or process.poll() is not None:
                break
        if process.poll() is None: process.terminate()
        try: tail,_ = process.communicate(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); tail,_ = process.communicate()
        serial.extend(tail or b''); selector.close(); (out/'serial.log').write_bytes(serial)
        report['guest_returncode'] = process.returncode; process = None
        text = serial.decode(errors='replace')
        report['clock_set_evidence'] = validate_clock_set(text,sdk,args.arch,
                'root' if args.root_mode else 'denied',require_fixture=True,require_held=args.root_mode)
        for api in args.require_wait:
            if 'CLOCK_SET_FIXTURE_WAIT_SET api='+api+' ' not in text: raise ValueError('missing armed waiter '+api)
        run(['e2fsck','-fn',disk],'final-fsck')
        report.update(final_disk_sha256=sha(disk),initial_disk_unchanged=sha(initial)==report['initial_disk_sha256'])
        if not report['initial_disk_unchanged']: raise ValueError('retained initial image changed')
        for name,expected in report['source_sha256'].items():
            if sha(out/'sources'/name) != expected: raise ValueError('snapshot source drift '+name)
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
