#!/usr/bin/env python3
"""Run privileged software realtime provenance checks against one exact SDK31."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent/'jbd2'))
from native_support import ARCH_TRIPLES, QEMU, snapshot_sdk, machine, boot, validate_sdk

ROOT = Path(__file__).resolve().parents[1]
POSITIVE = {'arm32', 'aarch64', 'rv32', 'rv64'}
MARKER = 'CLOCK_SET_DIAGNOSTIC_PASS scope=privileged-platform-diagnostic public-adapters=not-exercised\n'
SOURCES = ('tests/native/clock_set.cpp', 'tools/test_clock_set.py',
           'tools/jbd2/native_support.py', 'tools/kernel_sdk.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(text, prefix, key):
    result = {}
    for line in text.splitlines():
        if not line.startswith(prefix + ' '):
            continue
        fields = {}
        for item in line.split()[1:]:
            name, value = item.split('=', 1)
            if name in fields:
                raise ValueError('duplicate diagnostic field')
            fields[name] = value
        identity = fields.pop(key)
        if identity in result:
            raise ValueError('duplicate diagnostic record')
        result[identity] = fields
    return result


def validate(text, arch, fixture):
    if text.count(MARKER) != 1 or 'CLOCK_SET_DIAGNOSTIC_FAIL' in text:
        raise ValueError('missing or failed privileged diagnostic marker')
    boots = records(text, 'CLOCK_SET_BOOT', 'phase')
    commits = records(text, 'CLOCK_SET_COMMIT', 'phase')
    samples = records(text, 'CLOCK_SET_SAMPLE', 'phase')
    refusals = records(text, 'CLOCK_SET_REFUSED', 'case')
    if set(boots) != {'before', 'after'} or boots['before'] != boots['after']:
        raise ValueError('boot provenance changed')
    if set(commits) != {'first', 'backward', 'post2038'}:
        raise ValueError('incomplete software selections')
    if set(samples) != {'first', 'later', 'after-refusals', 'backward', 'post2038'}:
        raise ValueError('incomplete active samples')
    expected_failures = {'negative-seconds':('invalid-argument',0), 'seconds-bound':('invalid-argument',0),
                        'negative-nanoseconds':('invalid-argument',0), 'nanoseconds-bound':('invalid-argument',0),
                        'malformed-nonroot':('invalid-argument',0), 'nonroot':('permission',0),
                        'nonroot-before-floor':('permission',0), 'below-monotonic':('invalid-argument',1)}
    if set(refusals) != set(expected_failures):
        raise ValueError('incomplete failed-set evidence')
    continuity = [line for line in text.splitlines() if line.startswith('CLOCK_SET_CONTINUITY ')]
    if len(continuity) != 1:
        raise ValueError('missing continuity record')
    continuity = dict(item.split('=',1) for item in continuity[0].split()[1:])
    for field, value in {'no-retry':'1', 'rtc-writes':'0', 'provider-reset':'0',
                         'authority':'diagnostic-credentials'}.items():
        if continuity.get(field) != value:
            raise ValueError('incorrect diagnostic scope')
    mono_generation = int(continuity['mono_generation'])
    before_ns, after_ns = int(continuity['before_ns']), int(continuity['after_ns'])
    if mono_generation <= 0 or before_ns < 0 or after_ns <= before_ns:
        raise ValueError('monotonic continuity bounds')
    first_generation = 2 if arch in POSITIVE else 1
    if int(continuity['wall_generation']) != first_generation + 2:
        raise ValueError('incorrect final wall generation')
    original = boots['before']
    source = 'pl031' if arch in ('aarch64','arm32') else 'goldfish'
    if original['accuracy'] != 'unknown':
        raise ValueError('diagnostic claimed physical accuracy')
    if arch in POSITIVE:
        if (original['state'] != 'ready' or original['source'] != source or
                int(original['mono_generation']) != mono_generation or int(original['resolution_ns']) <= 0 or
                not 0 <= int(original['acquisition_ns']) <= 100000000):
            raise ValueError('qualified boot source provenance')
    elif (original['state'] != 'unavailable' or original['source'] != 'unavailable' or
          any(int(original[k]) != 0 for k in ('mono_generation','resolution_ns','acquisition_ns'))):
        raise ValueError('unqualified source was promoted')
    epochs = {'first':(2208988800,123456789), 'backward':(946684800,456789123), 'post2038':(2208988801,987654321)}
    previous = before_ns
    for index, phase in enumerate(epochs):
        item = commits[phase]
        if ((int(item['seconds']),int(item['nanoseconds'])) != epochs[phase] or
                int(item['wall_generation']) != first_generation + index or
                int(item['mono_generation']) != mono_generation or
                not previous <= int(item['mono_ns']) <= after_ns):
            raise ValueError('software commit identity or monotonic order')
        previous = int(item['mono_ns'])
    for phase, item in samples.items():
        committed = commits[phase if phase in epochs else 'first']
        elapsed = int(item['mono_ns']) - int(committed['mono_ns'])
        expected = int(committed['seconds'])*1000000000 + int(committed['nanoseconds']) + elapsed
        actual = int(item['seconds'])*1000000000 + int(item['nanoseconds'])
        if (elapsed < 0 or actual != expected or not 0 <= int(item['nanoseconds']) < 1000000000 or
                int(item['mono_generation']) != mono_generation or
                int(item['wall_generation']) != int(committed['wall_generation']) or
                item['origin'] != 'administrator-software' or item['accuracy'] != 'unknown' or
                not before_ns <= int(item['mono_ns']) <= after_ns):
            raise ValueError('independent software epoch arithmetic or provenance')
    if int(samples['later']['mono_ns']) - int(samples['first']['mono_ns']) < 20000000:
        raise ValueError('insufficient actual monotonic progress')
    if int(samples['after-refusals']['mono_ns']) < int(samples['later']['mono_ns']):
        raise ValueError('refusal sample moved monotonic backwards')
    if int(samples['backward']['seconds']) >= int(samples['later']['seconds']):
        raise ValueError('no explicit backward wall step')
    for name, (status, reads) in expected_failures.items():
        item = refusals[name]
        if (item['status'] != status or int(item['samples']) != reads or item['commits'] != '0' or
                int(item['wall_generation']) != first_generation):
            raise ValueError('refused request order or mutation')
    rtc = {}
    for label in ('BEFORE','AFTER'):
        lines = [line for line in text.splitlines() if line.startswith('CLOCK_SET_RTC_'+label+' ')]
        if arch in POSITIVE:
            if len(lines) != 1:
                raise ValueError('missing actual RTC reread')
            values = dict(item.split('=',1) for item in lines[0].split()[1:])
            seconds, nanos = int(values['seconds']), int(values['nanoseconds'])
            expected = int(datetime.datetime.fromisoformat(fixture).replace(tzinfo=datetime.timezone.utc).timestamp())
            if not expected <= seconds <= expected+30 or not 0 <= nanos < 1000000000:
                raise ValueError('physical RTC did not retain its independent UTC base')
            rtc[label.lower()] = {'seconds':seconds,'nanoseconds':nanos}
        elif lines:
            raise ValueError('unavailable RTC emitted a calendar')
    return {'boot':boots, 'commits':commits, 'samples':samples, 'refusals':refusals,
            'continuity':continuity, 'rtc':rtc, 'software_selections':3, 'refused_requests':8,
            'capability':'actual-RTC-preserved-and-software' if arch in POSITIVE else 'unavailable-RTC-and-software'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug','release'), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    fixture = '2024-02-29T12:34:56'
    report = {'status':'running','scope':'privileged-platform-software-clock-diagnostic','arch':args.arch,'mode':args.mode,
              'public_adapters_exercised':False,'user_mode_execution':False,'physical_hardware':False,'smp':False,
              'rtc_calendar_writes':False,'provider_reset_or_invalidation':False,'fault_injection':False,
              'authority_source':'explicit diagnostic credential records; not an unprivileged process execution',
              'rtc_write_scope':'No RTC write operation is requested; this diagnostic does not trace the MMIO bus.',
              'cases':[],'commands':[]}
    def save():
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(command, label, binary=False):
        row = {'argv':list(map(str,command)), 'label':label, 'status':'running'}
        report['commands'].append(row); save(); started = time.monotonic()
        result = subprocess.run(row['argv'],capture_output=True)
        if binary:
            (out/(label+'.bin')).write_bytes(result.stdout)
            (out/(label+'.log')).write_bytes(result.stderr)
        else:
            (out/(label+'.log')).write_bytes(result.stdout+result.stderr)
        row.update(status='passed' if result.returncode == 0 else 'failed',returncode=result.returncode,
                   seconds=time.monotonic()-started,log_sha256=sha(out/(label+'.log')))
        save()
        if result.returncode:
            raise RuntimeError(label+' failed')
        return result.stdout
    save()
    try:
        prefix = args.toolchain.resolve()/'bin'/(ARCH_TRIPLES[args.arch]+'-')
        cxx, ar, objcopy = [Path(str(prefix)+suffix) for suffix in ('g++','ar','objcopy')]
        sdk = out/'sdk'; manifest, sdk_sha = snapshot_sdk(args.kernel_sdk,sdk,args.arch,cxx,args.mode)
        required = {'include/ok/arch/clock.hpp','include/ok/arch/realtime.hpp','include/ok/time/realtime_clock.hpp',
                    'include/ok/user/clock_set.hpp','include/ok/user/user.hpp'}
        if manifest['abi_version'] != 31 or not required.issubset(manifest['files']):
            raise ValueError('exact SDK31 clock setter interfaces required')
        if '-frtti' not in manifest['cxxflags'] or '-fno-rtti' in manifest['cxxflags']:
            raise ValueError('RTTI contract')
        report.update(sdk_abi=31,sdk_manifest_sha256=sdk_sha,compiler=manifest['compiler'],
                      sdk_input_manifest=str(args.kernel_sdk.resolve()/'manifest.json'))
        sources = {}
        for relative in SOURCES:
            target = out/'sources'/relative; target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/relative).read_bytes()); sources[relative] = sha(target)
        report['source_sha256'] = sources
        members = run([ar,'t',sdk/'lib/libokernel_boot.a'],'boot-members').decode().splitlines()
        if members.count('boot.S.o') != 1:
            raise ValueError('nonunique boot object')
        boot_object = run([ar,'p',sdk/'lib/libokernel_boot.a','boot.S.o'],'extract-boot',binary=True)
        (out/'boot.o').write_bytes(boot_object)
        qemu = shutil.which(QEMU[args.arch])
        if not qemu:
            raise ValueError('missing QEMU')
        report['tool_sha256'] = {str(p):sha(p) for p in (cxx,ar,objcopy,Path(qemu))}
        report.update(qemu_binary_sha256=sha(Path(qemu)),qemu_version=run([qemu,'--version'],'qemu-version').decode().splitlines()[0])
        flags = ['-std=c++23',*manifest['cxxflags'],'-fno-builtin','-Wall','-Wextra','-Werror',
                 *('-D'+item for item in manifest['defines']),'-I',str(sdk/'include')]
        obj, elf, image = [out/('clock-set'+ext) for ext in ('.o','.elf','.bin')]
        run([cxx,*flags,'-c',out/'sources/tests/native/clock_set.cpp','-o',obj],'compile')
        run([cxx,*manifest['ldflags'],'-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(sdk/'boot/linker.ld'),
             out/'boot.o',obj,sdk/'lib/libokernel.a','-lgcc','-o',elf],'link')
        run([sys.executable,out/'sources/tools/kernel_sdk.py','assemble','--sdk',sdk,'--arch',args.arch,'--mode',args.mode,
             '--compiler',cxx,'--elf',elf,'--out',image,'--objcopy',objcopy],'assemble')
        command = machine(qemu,args.arch,image)+['-smp','1','-rtc','base='+fixture+',clock=vm,driftfix=none']
        image_sha = sha(image)
        row = {'case':'software-provenance','status':'running','argv':command,'rtc_base':fixture,'rtc_clock':'vm',
               'cpus':1,'image_sha256':image_sha}
        report['cases'].append(row); save()
        logfile = out/'software-provenance.log'
        row['qemu_returncode'] = boot(command,MARKER,logfile)
        row['evidence'] = validate(logfile.read_text(),args.arch,fixture)
        if sha(image) != image_sha:
            raise ValueError('diagnostic changed its input image')
        row.update(status='passed',log_sha256=sha(logfile),image_unchanged=True); save()
        validate_sdk(sdk,args.arch,args.mode,cxx)
        for name,digest in sources.items():
            if sha(ROOT/name) != digest:
                raise ValueError('diagnostic source changed during execution: '+name)
        for name,digest in report['tool_sha256'].items():
            if sha(Path(name)) != digest:
                raise ValueError('diagnostic tool changed during execution')
        report.update(status='passed',sdk_snapshot_revalidated=True,source_unchanged=True)
    except Exception as error:
        report.update(status='failed',error=str(error)); print('FAIL',error,flush=True)
    finally:
        report['artifact_sha256'] = {str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*'))
                                    if p.is_file() and p.name != 'result.json' and 'sdk' not in p.relative_to(out).parts}
        save()
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
