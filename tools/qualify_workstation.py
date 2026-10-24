#!/usr/bin/env python3
"""Qualify standalone Kernel and exact OS SDK consumer; preserves every run log."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import tarfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kernel-repo', type=Path, required=True)
parser.add_argument('--toolchain-root', type=Path)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--arches', default='x86_64,i386,mips,aarch64,arm32,rv64,rv32,loongarch64,mips64,ppc')
parser.add_argument('--modes', default='debug,release')
parser.add_argument('--musl-probes', type=Path, help='Explicit directory containing ARCH/manifest.json and bootstrap.elf')
parser.add_argument('--jbd2-fixture', type=Path, help='Explicit Linux-created recovery fixture for SDK-only actual-device replay')
parser.add_argument('--jbd2-runtime-binding', action='store_true', help='Require device-derived internal-journal ownership and mapping')
parser.add_argument('--jbd2-preview', action='store_true', help='Require read-only final journal view and unchanged-device rejection probes')
parser.add_argument('--jbd2-completion', action='store_true', help='Require bounded recovery completion and restart/rejection checks on private disks')
parser.add_argument('--musl-files', action='store_true', help='Require musl file/sync and offline ext4 checks')
parser.add_argument('--musl-heap', action='store_true', help='Require musl heap and mapped VM checks')
parser.add_argument('--musl-process', action='store_true', help='Require musl identity/fork/exec/wait and process exhaustion/recovery')
parser.add_argument('--musl-paths', action='store_true', help='Require musl cwd/readlink/copy-boundary checks plus process/file/heap gates')
parser.add_argument('--musl-runtime-frames', action='store_true', help='Require retained firmware/linker process frame provenance and reclamation')
parser.add_argument('--musl-fds', action='store_true', help='Require descriptor duplication/flags/exec/pressure and preceding musl gates')
parser.add_argument('--musl-seek', action='store_true', help='Require bounded seek ABI/offset/error checks and preceding musl gates')
parser.add_argument('--jbd2-transaction', action='store_true', help='Require bounded metadata journal publication and all private-device restart/fault gates')
parser.add_argument('--musl-pipes', action='store_true', help='Require pipes, reference lifetime, fork exchange and preceding musl gates')
parser.add_argument('--musl-sleep', action='store_true', help='Require elapsed Linux sleep/deadline/resolution and preceding musl gates')
parser.add_argument('--block-sessions', action='store_true', help='Require exclusive Kernel block-session publication, quarantine and private-device restart/fault gates')
parser.add_argument('--musl-poll', action='store_true', help='Require Linux poll/ppoll readiness, deadlines and all preceding musl gates')
parser.add_argument('--metadata-buffers', action='store_true', help='Require canonical metadata ownership, private versions and actual-device read-fault gates')
parser.add_argument('--musl-open', action='store_true', help='Require public open/creat and preceding musl gates')
parser.add_argument('--musl-positional', action='store_true', help='Require public positional I/O and preceding musl gates')
parser.add_argument('--owned-ext4', action='store_true', help='Require private-session owned ext4 transaction/checkpoint and fault/recovery gates')
parser.add_argument('--mounted-ext4', action='store_true', help='Require repeated mounted internal metadata updates and actual-device fault/recovery gates')
parser.add_argument('--musl-select', action='store_true', help='Require public select/pselect, raw layouts and preceding musl gates')
parser.add_argument('--file-attributes-fixtures', type=Path, help='Explicit six-image raw inode/timestamp oracle for readonly native attribute checks')
parser.add_argument('--musl-directory', action='store_true', help='Require bounded public directory streams and all preceding musl gates')
parser.add_argument('--musl-umask', action='store_true', help='Require process creation-mask and offline modes plus preceding gates')
parser.add_argument('--musl-realtime', action='store_true', help='Require native and musl public realtime in parent, fork and exec plus preceding gates')
parser.add_argument('--rtc-base', help='Explicit UTC fixture for --musl-realtime')
parser.add_argument('--realtime-foundation', action='store_true', help='Require actual RTC/epoch diagnostics and explicit unsupported-source refusal')
parser.add_argument('--musl-mkdir', action='store_true', help='Require directory creation and offline metadata plus preceding gates')
parser.add_argument('--clock-set-probes', type=Path, help='Explicit ten-profile static musl clock-setting probes; run separate root/UID1000 guests')
parser.add_argument('--clock-set-diagnostic', action='store_true', help='Require privileged software clock provenance, separate from public adapters')
parser.add_argument('--maintained-ext4', action='store_true', help='Require SDK-only maintained timestamp diagnostics across all six ext4 layouts')
parser.add_argument('--maintained-time-probes', type=Path, help='Explicit ten-profile musl maintained timestamp probe bundle with dependency and source inventories')
parser.add_argument('--linux-stat-musl-builds', type=Path, help='Explicit musl root with ARCH/debug-optimized-v1 builds; require six SDK31 stat policy/epoch guests per row')
parser.add_argument('--linux-stat-ppc-clang', type=Path, help='Explicit clang for the retained PPC musl build')
a = parser.parse_args()
a.musl_realtime = a.musl_realtime or a.musl_mkdir
if a.rtc_base and not a.musl_realtime:
    parser.error('--rtc-base requires --musl-realtime')
if a.musl_realtime:
    from realtime_evidence import fixture_seconds
    a.rtc_base = a.rtc_base or '2024-02-29T12:34:56'
    fixture_seconds(a.rtc_base)
    a.musl_umask = True
if (a.jbd2_runtime_binding or a.jbd2_preview or a.jbd2_completion or a.jbd2_transaction or a.block_sessions or a.metadata_buffers or a.owned_ext4 or a.mounted_ext4) and not a.jbd2_fixture:
    parser.error('requested journal acceptance options require --jbd2-fixture')
if (a.musl_files or a.musl_heap or a.musl_process or a.musl_paths or a.musl_runtime_frames or a.musl_fds or a.musl_seek or a.musl_pipes or a.musl_sleep or a.musl_poll or a.musl_open or a.musl_positional or a.musl_select or a.musl_directory or a.musl_umask) and not a.musl_probes:
    parser.error('requested musl acceptance options require --musl-probes')
kernel = a.kernel_repo.resolve()
osrepo = Path(__file__).resolve().parents[1]
output = a.out.resolve()
output.mkdir(parents=True, exist_ok=False)
session_folder = output
toolchains = (a.toolchain_root or kernel/'toolchains').resolve()
profiles = {
 'i386': ('i386-elf', 'i386'), 'x86_64': ('x86_64-elf', 'x86_64'),
 'aarch64': ('aarch64-elf', 'aarch64'), 'arm32': ('arm-none-eabi', 'arm'),
 'rv64': ('riscv64-elf', 'riscv64'), 'rv32': ('riscv32-elf', 'riscv32'),
 'loongarch64': ('loongarch64-elf', 'loongarch64'), 'mips': ('mips-elf', 'mips'),
 'mips64': ('mips64-elf', 'mips64'), 'ppc': ('powerpc-eabi', 'ppc')}
if any(arch not in profiles for arch in a.arches.split(',')) or any(mode not in ('debug','release') for mode in a.modes.split(',')):
    parser.error('unknown architecture or mode; all ten profiles remain available')
results=[]
artifacts=[]
preserved=[]

def executable_identity(name):
    executable = shutil.which(str(name))
    if executable is None:
        raise RuntimeError('qualification executable unavailable: ' + str(name))
    path = Path(executable).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def artifact(path):
    data=path.read_bytes()
    artifacts.append({'architecture':arch,'mode':mode,'path':str(path),
                      'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    (output/'artifacts.json').write_text(json.dumps(artifacts,indent=2)+'\n')

# Reject mixed source snapshots instead of accidentally testing an old Kernel
# with newly compiled OS acceptance programs. Build/output directories are not inputs.
def source_snapshot():
    rows={}
    for repo, directories in ((kernel,('include','src','tests','xmake','tools','scripts')),
                              (osrepo,('sdk','apps','lib','modules','drivers','xmake','tools','scripts','tests'))):
        for directory in directories:
            for path in sorted((repo/directory).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                    rows[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        path=repo/'xmake.lua'
        rows[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    return rows
snapshot=source_snapshot()
(output/'source-hashes.json').write_text(json.dumps(snapshot,indent=2)+'\n')
with tarfile.open(output/'source-inputs.tar.gz', 'w:gz') as archive:
    for filename, expected in snapshot.items():
        path = Path(filename)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('source changed while preserving qualification inputs')
        repo = kernel if path.is_relative_to(kernel) else osrepo
        archive.add(path, arcname=str(Path(repo.name)/path.relative_to(repo)), recursive=False)
(output/'build-policy.json').write_text(json.dumps({
    'compiler_cache': False, 'kernel_sdk_rebuild': True,
    'os_image_rebuild': True, 'musl_runner_rebuild': True,
    'reason': 'Source hashes cannot invalidate objects copied with preserved mtimes.'
}, indent=2)+'\n')

from qualification_artifacts import preserved_artifact_path


def preserve_row():
    """Save verified binaries before another configuration can replace them."""
    target = output/'preserved'/arch/mode
    target.mkdir(parents=True, exist_ok=False)
    saved = []
    for item in artifacts:
        if (item['architecture'], item['mode']) != (arch, mode):
            continue
        source = Path(item['path'])
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise RuntimeError('artifact changed before preservation: '+str(source))
        relative = preserved_artifact_path(source, kernel, osrepo, output,
                                           a.musl_probes, a.clock_set_probes, a.maintained_time_probes)
        destination = target/relative
        if destination.exists():
            raise RuntimeError('duplicate artifact preservation destination: '+str(destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        saved.append({'original':str(source), 'preserved':str(destination.relative_to(output)),
                      'sha256':item['sha256']})
    sdk = kernel/'build/sdk'/arch/mode
    shutil.copytree(sdk, target/'sdk')
    manifest = json.loads((target/'sdk/manifest.json').read_text())
    for filename, expected in manifest['files'].items():
        source = target/'sdk'/filename
        if not source.resolve().is_relative_to((target/'sdk').resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise RuntimeError('preserved SDK artifact mismatch: '+filename)
    preserved.append({'architecture':arch, 'mode':mode, 'artifacts':saved,
                      'sdk_manifest':str((target/'sdk/manifest.json').relative_to(output))})
    (output/'preserved-index.json').write_text(json.dumps(preserved,indent=2)+'\n')

def run(cwd, name, argv):
    if argv[0] == 'xmake':
        argv = ([argv[0], argv[1], '-P', str(cwd), *argv[2:]] if argv[1] == 'f'
                else [argv[0], '-P', str(cwd), *argv[1:]])
    if source_snapshot() != snapshot:
        raise RuntimeError('source changed during qualification; start a new output run')
    log = folder/(name+'.log')
    executable = executable_identity(argv[0])
    begin=time.monotonic()
    with log.open('w') as stream:
        result=subprocess.run(argv,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT)
    row={'architecture':arch,'mode':mode,'step':name,'command':list(map(str,argv)),
         'cwd':str(cwd),'exit_code':result.returncode,'seconds':round(time.monotonic()-begin,2),
         'log':str(log.relative_to(output)), 'sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
         'executable': executable}
    results.append(row)
    (output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(f"{arch}/{mode} {name}: {'PASS' if result.returncode==0 else 'FAIL'} {row['seconds']}s",flush=True)
    if result.returncode:
        print(log.read_text(errors='replace')[-4500:],flush=True)
        raise RuntimeError(f'{arch}/{mode}: {name} failed')
    if executable_identity(argv[0]) != executable:
        raise RuntimeError('qualification executable changed during command')
    if source_snapshot() != snapshot:
        raise RuntimeError('source changed while command ran; recorded output is not qualification of this snapshot')

try:
    for mode in a.modes.split(','):
        for arch in a.arches.split(','):
            triple, qemu_name=profiles[arch]
            prefix=toolchains/triple
            qemu=Path('/usr/bin')/('qemu-system-'+qemu_name)
            folder=session_folder/arch/mode
            folder.mkdir(parents=True,exist_ok=True)
            binaries = [prefix/'bin'/(triple+'-'+tool) for tool in
                        ('gcc', 'g++', 'as', 'ld', 'ar', 'objcopy', 'readelf')]
            binaries += [qemu, 'xmake', 'python3', 'mke2fs', 'debugfs', 'e2fsck']
            identities = {str(tool): executable_identity(tool) for tool in binaries}
            (folder/'tool-identities.json').write_text(json.dumps(identities,indent=2)+'\n')
            cfg=['xmake','f','-y','-a',arch,'-m',mode,'--ccache=n','--systoolchain_dir='+str(prefix)]
            run(kernel,'kernel-configure',cfg)
            run(kernel,'kernel-sdk',['xmake','-y','-r','-b','kernel-sdk'])
            artifact(kernel/'build/sdk'/arch/mode/'manifest.json')
            artifact(kernel/'build/sdk'/arch/mode/'image/kernel.bin')
            if mode=='debug':
                run(kernel,'kernel-qemu',['python3','scripts/qemu_test.py','--arch',arch,
                    '--qemu',str(qemu),'--kernel',str(kernel/'build/linux'/arch/mode/'kernel.bin')])
            run(osrepo,'os-configure',cfg+['--kernel_sdk='+str(kernel/'build/sdk'/arch/mode),
                '--native_init_acceptance=' + ('y' if mode == 'debug' else 'n')])
            for target in ['distro_image','uapi-test','libc-test','rootfs-simplefs','rootfs-ext4']:
                run(osrepo,target,['xmake','-y',*(['-r'] if target=='distro_image' else []),'-b',target])
            image=osrepo/'build'/arch/mode/'distro/kernel.bin'
            for fs in ('simplefs','ext4'):
                disk=osrepo/'build'/arch/mode/f'rootfs.{fs}.img'
                if mode=='debug':
                    cmd=['python3','scripts/qemu_distro.py','--arch',arch,'--qemu',str(qemu),
                         '--kernel',str(image),'--rootfs',str(disk),'--fs',fs,'--require-native','--timeout','100',
                         '--failure-dir',str(folder/('native-'+fs+'-failure'))]
                else:
                    cmd=['python3','scripts/test_interactive_userland.py','--arch',arch,'--qemu',str(qemu),
                         '--kernel',str(image),'--rootfs',str(disk),'--posix-check','--timeout','100',
                         '--log',str(folder/f'release-{fs}-serial.log')]
                run(osrepo,'native-'+fs,cmd)
            for path in (image, osrepo/'build'/arch/mode/'rootfs.simplefs.img', osrepo/'build'/arch/mode/'rootfs.ext4.img'):
                artifact(path)
            # Namespace changes survive guest sync followed by host retirement/restart.
            run(osrepo,'ext4-persistence',['python3','scripts/test_persistent_ext4.py','--arch',arch,
                '--qemu',str(qemu),'--kernel',str(image),'--rootfs',str(osrepo/'build'/arch/mode/'rootfs.ext4.img'),
                '--out',str(folder/'persistence'),'--timeout','100',
                *(['--require-native'] if mode == 'debug' else [])])
            if a.musl_probes:
                run(osrepo,'musl-native-runner',['xmake','-y','-r','-b','app-musl-test-runner'])
                runner=osrepo/'build'/arch/mode/'apps/musl-test-runner.elf'
                probe=a.musl_probes.resolve()/arch
                artifact(runner)
                artifact(probe/'manifest.json')
                artifact(probe/'bootstrap.elf')
                # The musl scratch binaries enter the mounted ext4 namespace.
                # Baseline simplefs/archive native acceptance remains above.
                for filesystem in ('ext4',):
                    run(osrepo,'musl-'+filesystem,['python3','scripts/test_musl_userland.py','--arch',arch,
                        '--qemu',str(qemu),'--kernel',str(image),'--rootfs-tree',str(osrepo/'build'/arch/mode/'rootfs'),
                        '--probe',str(probe),'--runner',str(runner),'--fs',filesystem,
                        '--out',str(folder/('musl-'+filesystem)),'--timeout','100',
                        *(['--require-files'] if a.musl_files else []),
                        *(['--require-heap'] if a.musl_heap else []),
                        *(['--require-process'] if a.musl_process else []),
                        *(['--require-paths'] if a.musl_paths else []),
                        *(['--require-runtime-frames'] if a.musl_runtime_frames else []),
                        *(['--require-fds'] if a.musl_fds else []),
                        *(['--require-seek'] if a.musl_seek else []),
                        *(['--require-pipes'] if a.musl_pipes else []),
                        *(['--require-sleep'] if a.musl_sleep else []),
                        *(['--require-poll'] if a.musl_poll else []),
                        *(['--require-open'] if a.musl_open else []),
                        *(['--require-positional'] if a.musl_positional else []),

                        *(['--require-select'] if a.musl_select else []),
                        *(['--require-directory'] if a.musl_directory else []),
                        *(['--require-umask'] if a.musl_umask else []),
                        *(['--require-mkdir'] if a.musl_mkdir else []),
                        *(['--require-realtime', '--rtc-base', a.rtc_base] if a.musl_realtime else [])])
            if a.jbd2_fixture:
                run(osrepo,'jbd2-replay',['python3','tools/jbd2/test_native.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixture',str(a.jbd2_fixture.resolve()),
                    '--output',str(folder/'jbd2-replay'),'--qemu',str(qemu),
                    *(['--runtime-binding'] if a.jbd2_runtime_binding else [])])
            if a.jbd2_preview:
                run(osrepo,'jbd2-preview',['python3','tools/jbd2/test_preview.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixture',str(a.jbd2_fixture.resolve()),
                    '--output',str(folder/'jbd2-preview'),'--qemu',str(qemu)])
            if a.jbd2_completion:
                run(osrepo,'jbd2-completion',['python3','tools/jbd2/test_completion.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixture',str(a.jbd2_fixture.resolve()),
                    '--output',str(folder/'jbd2-completion'),'--qemu',str(qemu),'--faults'])
            if a.jbd2_transaction:
                run(osrepo,'jbd2-transaction',['python3','tools/jbd2/test_transaction.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixture',str(a.jbd2_fixture.resolve()),
                    '--output',str(folder/'jbd2-transaction'),'--qemu',str(qemu),'--faults'])
            if a.block_sessions:
                run(osrepo,'block-sessions',['python3','tools/jbd2/test_block_sessions.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixture',str(a.jbd2_fixture.resolve()),
                    '--output',str(folder/'block-sessions'),'--qemu',str(qemu),'--faults'])
            if a.metadata_buffers:
                run(osrepo,'metadata-buffers',['python3','tools/jbd2/test_metadata_buffers.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixture',str(a.jbd2_fixture.resolve()),
                    '--output',str(folder/'metadata-buffers'),'--qemu',str(qemu),'--faults'])
            if a.owned_ext4:
                run(osrepo,'owned-ext4',['python3','tools/jbd2/test_owned.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixture',str(a.jbd2_fixture.resolve()),
                    '--output',str(folder/'owned-ext4'),'--qemu',str(qemu),'--faults'])
            if a.file_attributes_fixtures:
                run(osrepo,'file-attributes',['python3','tools/jbd2/test_file_attributes.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixtures',str(a.file_attributes_fixtures.resolve()),
                    '--output',str(folder/'file-attributes'),'--qemu',str(qemu)])
            if a.mounted_ext4:
                run(osrepo,'mounted-ext4',['python3','tools/jbd2/test_mounted.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--fixture',str(a.jbd2_fixture.resolve()),
                    '--output',str(folder/'mounted-ext4'),'--qemu',str(qemu),
                    *(['--faults'] if arch in ('x86_64','ppc') else [])])
            if a.realtime_foundation:
                run(osrepo,'realtime-foundation',['python3','tools/test_realtime.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--output',str(folder/'realtime-foundation')])
            if a.clock_set_diagnostic:
                run(osrepo,'clock-set-diagnostic',['python3','tools/test_clock_set.py','--arch',arch,
                    '--mode',mode,'--kernel-sdk',str(kernel/'build/sdk'/arch/mode),
                    '--toolchain',str(prefix),'--output',str(folder/'clock-set-diagnostic')])
            if a.clock_set_probes:
                run(osrepo,'clock-set-native-runner',['xmake','-y','-r','-b','app-clock-set-runner'])
                runner = osrepo/'build'/arch/mode/'apps/clock-set-runner.elf'
                probe = a.clock_set_probes.resolve()/arch
                sdk = kernel/'build/sdk'/arch/mode
                sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
                identity = folder/'clock-set-native-identity.json'
                identity.write_text(json.dumps({'status':'built-not-executed',
                    'sdk_manifest_sha256':sha(sdk/'manifest.json'),
                    'files':{'clock_set_runner.c':sha(osrepo/'tests/musl/clock_set_runner.c'),
                             'clock-set-runner.elf':sha(runner)}},indent=2)+'\n')
                for path in (runner,identity,probe/'manifest.json',probe/'bootstrap.elf'):
                    artifact(path)
                for authority in ('root','deny'):
                    run(osrepo,'clock-set-'+authority,['python3','tools/test_clock_set_foundation.py',
                        '--arch',arch,'--mode',mode,'--kernel-sdk',str(sdk),'--toolchain',str(prefix),
                        '--rootfs',str(osrepo/'build'/arch/mode/'rootfs'),
                        '--native-runner',str(runner),'--native-identity',str(identity),
                        '--musl-probe',str(probe),'--output',str(folder/('clock-set-'+authority)),
                        *(['--root-mode'] if authority=='root' else [])])
            if a.maintained_ext4:
                sdk = kernel/'build/sdk'/arch/mode
                sdk_hash = hashlib.sha256((sdk/'manifest.json').read_bytes()).hexdigest()
                run(osrepo,'maintained-ext4',['python3','tools/test_ext4_timestamps.py',
                    '--arch',arch,'--mode',mode,'--kernel-sdk',str(sdk),'--toolchain',str(prefix),
                    '--sdk-manifest-sha256',sdk_hash,'--output',str(folder/'maintained-ext4')])
            if a.maintained_time_probes:
                run(osrepo,'maintained-time-native-runner',['xmake','-y','-r','-b','app-ext4-timestamps-runner'])
                runner = osrepo/'build'/arch/mode/'apps/ext4-timestamps-runner.elf'
                bundle = a.maintained_time_probes.resolve()
                probe = bundle/arch
                probe_source = bundle/'input/ObfuscationOS/tests/musl/ext4_timestamps.c'
                header = bundle/'input/ObfuscationOS/tests/musl/ext4_timestamp_log.h'
                sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
                if sha(probe_source) != sha(osrepo/'tests/musl/ext4_timestamps.c') or sha(header) != sha(osrepo/'tests/musl/ext4_timestamp_log.h'):
                    raise ValueError('maintained probe bundle does not match qualified source')
                sdk = kernel/'build/sdk'/arch/mode
                identity = folder/'maintained-time-native-identity.json'
                identity.write_text(json.dumps({'status':'built-not-executed','architecture':arch,'mode':mode,
                    'sdk_manifest_sha256':sha(sdk/'manifest.json'),
                    'files':{'ext4_timestamps_runner.c':sha(osrepo/'tests/musl/ext4_timestamps_runner.c'),
                             'ext4_timestamp_log.h':sha(header),
                             'ext4-timestamps-runner.elf':sha(runner)}},indent=2)+'\n')
                for path in (runner,identity,probe/'manifest.json',probe/'bootstrap.elf',
                             probe/'dependencies.json',bundle/'source-sha256.json',probe_source,header):
                    artifact(path)
                run(osrepo,'maintained-time-user',['python3','tools/test_ext4_timestamp_user.py',
                    '--arch',arch,'--mode',mode,'--kernel-sdk',str(sdk),'--toolchain',str(prefix),
                    '--rootfs',str(osrepo/'build'/arch/mode/'rootfs'),
                    '--native-runner',str(runner),'--native-identity',str(identity),
                    '--musl-probe',str(probe),'--musl-source',str(probe_source),'--shared-header',str(header),
                    '--musl-dependencies',str(probe/'dependencies.json'),
                    '--source-inventory',str(bundle/'source-sha256.json'),
                    '--output',str(folder/'maintained-time-user')])
            if a.linux_stat_musl_builds:
                sdk = kernel/'build/sdk'/arch/mode
                sdk_hash = hashlib.sha256((sdk/'manifest.json').read_bytes()).hexdigest()
                run(osrepo,'linux-stat',['python3','tools/qualify_linux_stat.py',
                    '--arch',arch,'--mode',mode,'--kernel-sdk',str(sdk),
                    '--sdk-manifest-sha256',sdk_hash,'--toolchain',str(prefix),
                    '--rootfs',str(osrepo/'build'/arch/mode/'rootfs'),
                    '--musl-build',str(a.linux_stat_musl_builds.resolve()/arch/'debug-optimized-v1'),
                    '--output',str(folder/'linux-stat'),
                    *(['--ppc-clang',str(a.linux_stat_ppc_clang.resolve())] if arch == 'ppc' and a.linux_stat_ppc_clang else [])])
            preserve_row()
finally:
    for repo in (kernel,osrepo):
        subprocess.run(['xmake','f','-P',str(repo),'-y','-a','x86_64','-m','debug','--ccache=n',
                        '--systoolchain_dir='+str(toolchains/'x86_64-elf')]+
                       (['--kernel_sdk='+str(kernel/'build/sdk/x86_64/debug')] if repo==osrepo else []),cwd=repo,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
