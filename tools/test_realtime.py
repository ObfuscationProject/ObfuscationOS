#!/usr/bin/env python3
"""Run actual platform epoch diagnostics using an exact SDK; no kernel source build."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent/'jbd2'))
from native_support import ARCH_TRIPLES, QEMU, snapshot_sdk, machine, boot, validate_sdk

ROOT = Path(__file__).resolve().parents[1]
POSITIVE = {'arm32', 'aarch64', 'rv32', 'rv64'}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = {'scope':'native-platform-RTC-diagnostic', 'arch':args.arch, 'mode':args.mode, 'status':'running',
              'public_adapters_exercised':False, 'user_mode_execution':False, 'physical_hardware':False, 'smp':False,
              'rtc_calendar_writes':False, 'cases':[], 'commands':[]}
    def save(): (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    def run(command, label):
        row = {'argv':[str(x) for x in command], 'label':label, 'status':'running'}
        report['commands'].append(row); save(); start = time.monotonic()
        result = subprocess.run(row['argv'], text=True, capture_output=True)
        (out/(label+'.log')).write_text(result.stdout+result.stderr)
        row.update(status='passed' if result.returncode == 0 else 'failed', returncode=result.returncode, seconds=time.monotonic()-start)
        save()
        if result.returncode: raise RuntimeError(label+' failed')
        return result.stdout
    save()
    try:
        prefix = args.toolchain.resolve()/'bin'/(ARCH_TRIPLES[args.arch]+'-')
        cxx, ar, objcopy = [Path(str(prefix)+suffix) for suffix in ('g++','ar','objcopy')]
        sdk = out/'sdk'; manifest, sdk_sha = snapshot_sdk(args.kernel_sdk, sdk, args.arch, cxx, args.mode)
        if manifest['abi_version'] != 31: raise ValueError('exact SDK31 required')
        if not {'include/ok/time/epoch.hpp','include/ok/time/rtc.hpp','include/ok/arch/realtime.hpp'}.issubset(manifest['files']):
            raise ValueError('missing epoch SDK interfaces')
        if '-frtti' not in manifest['cxxflags'] or '-fno-rtti' in manifest['cxxflags']: raise ValueError('RTTI contract')
        report.update(sdk_manifest_sha256=sdk_sha, sdk_abi=manifest['abi_version'], compiler=manifest['compiler'])
        sources = {}
        for relative in ('tests/native/realtime.cpp','tools/test_realtime.py','tools/jbd2/native_support.py','tools/kernel_sdk.py'):
            target = out/'sources'/relative; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/relative).read_bytes()); sources[relative] = sha(target)
        report['source_sha256'] = sources
        members = run([ar, 't', sdk/'lib/libokernel_boot.a'], 'boot-members').splitlines()
        if members.count('boot.S.o') != 1: raise ValueError('nonunique boot object')
        command = [str(ar),'p',str(sdk/'lib/libokernel_boot.a'),'boot.S.o']
        (out/'boot.o').write_bytes(subprocess.check_output(command)); report['commands'].append({'label':'extract-boot','argv':command,'status':'passed'})
        qemu = shutil.which(QEMU[args.arch])
        if not qemu: raise ValueError('missing QEMU')
        report.update(qemu_binary_sha256=sha(Path(qemu)), qemu_version=run([qemu,'--version'],'qemu-version').splitlines()[0])
        flags = ['-std=c++23',*manifest['cxxflags'],'-fno-builtin','-Wall','-Wextra','-Werror',
                 *('-D'+item for item in manifest['defines']), '-I', str(sdk/'include')]
        for kind in ('normal','early'):
            obj, elf, image = [out/(kind+extension) for extension in ('.o','.elf','.bin')]
            run([cxx,*flags,*(['-DREALTIME_EARLY_FAILURE'] if kind=='early' else []),'-c',out/'sources/tests/native/realtime.cpp','-o',obj], 'compile-'+kind)
            run([cxx,*manifest['ldflags'],'-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(sdk/'boot/linker.ld'),
                 out/'boot.o',obj,sdk/'lib/libokernel.a','-lgcc','-o',elf], 'link-'+kind)
            run([sys.executable,out/'sources/tools/kernel_sdk.py','assemble','--sdk',sdk,'--arch',args.arch,'--mode',args.mode,
                 '--compiler',cxx,'--elf',elf,'--out',image,'--objcopy',objcopy], 'assemble-'+kind)
            dates = ('1970-01-01T00:00:00','2024-02-29T12:34:56','2040-03-01T01:02:03') if kind=='normal' and args.arch in POSITIVE else ('2024-02-29T12:34:56',)
            for fixture in dates:
                label = kind+'-'+fixture.replace(':','-')
                command = machine(qemu,args.arch,image)+['-rtc','base='+fixture+',clock=vm,driftfix=none']
                row = {'case':label,'status':'running','argv':command,'rtc_base':fixture,'rtc_clock':'vm'}
                report['cases'].append(row); save()
                logfile = out/(label+'.log')
                boot(command,'REALTIME_PASS scope=native-platform-diagnostic public-adapters=not-exercised\n',logfile)
                log = logfile.read_text()
                if kind=='early':
                    if 'REALTIME_EARLY_FAILURE_PASS no-retry=1' not in log: raise ValueError('missing early failure evidence')
                    row['capability'] = 'initialization-failure-refused'
                elif args.arch in POSITIVE:
                    if 'REALTIME_READY_PASS' not in log: raise ValueError('missing source execution')
                    samples = {name:(int(sec),int(ns)) for name,sec,ns in re.findall(r'(REALTIME_SOURCE|REALTIME_FIRST|REALTIME_SECOND|REALTIME_LATER_SOURCE) seconds=(\d+) nanoseconds=(\d+)',log)}
                    if len(samples) != 4: raise ValueError('missing source/anchor samples')
                    base = datetime.datetime.fromisoformat(fixture).replace(tzinfo=datetime.timezone.utc)
                    expected = int(base.timestamp())
                    for seconds, nanos in samples.values():
                        if not (expected <= seconds <= expected+10 and 0 <= nanos < 1000000000): raise ValueError('independent UTC oracle mismatch')
                    row.update(capability='actual-RTC-and-anchor', oracle_seconds=expected, samples=samples)
                else:
                    if 'REALTIME_UNAVAILABLE_PASS' not in log: raise ValueError('missing unavailable evidence')
                    row['capability'] = 'unqualified-source-refused'
                    row['rtc_access'] = 'LS7A-control-read' if args.arch=='loongarch64' else 'none-policy-refusal'
                row['status'] = 'passed'; save()
        validate_sdk(sdk,args.arch,args.mode,cxx)
        report.update(status='passed',sdk_snapshot_revalidated=True)
    except Exception as error:
        report.update(status='failed',error=str(error)); print('FAIL',error,flush=True)
    finally:
        report['artifact_sha256'] = {str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='result.json' and 'sdk' not in p.relative_to(out).parts}
        save()
    return 0 if report['status']=='passed' else 1

if __name__ == '__main__': raise SystemExit(main())
