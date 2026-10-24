"""Exercise default Notes on scratch host files with injected syscall failures."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WRAPS = ('open', 'openat', 'close', 'fstat', 'fstatat', 'fsync', 'renameat', 'unlinkat', 'write', 'read')
OLD = b'Original English note.\n'
NEW = b'Updated English note.\n'
RIVAL = b'Intruder English note.\n'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def need(value, message):
    if not value:
        raise RuntimeError(message)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    need(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'disable Python bytecode')
    out = args.output.resolve()
    need(not out.exists(), 'retain prior evidence; output must be new')
    out.mkdir(parents=True)
    compiler = Path(shutil.which(args.cc) or args.cc).resolve()
    report = dict(schema=1, status='running', layer='hosted-scratch-files-and-fault-injection',
        runner_sha256=sha(__file__), compiler=str(compiler), compiler_sha256=sha(compiler),
        native_execution=False, journal_crash_durability=False, source={}, commands=[], cases=[])
    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def run(label, argv):
        row = dict(label=label, argv=list(map(str, argv)))
        report['commands'].append(row)
        save()
        result = subprocess.run(row['argv'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=60)
        log = out / (label + '.log')
        log.write_bytes(result.stdout)
        row.update(returncode=result.returncode, log_sha256=sha(log))
        save()
        need(result.returncode == 0, 'build failed: ' + label)
    inputs = ('apps/notes/main.c', 'apps/notes/save.c', 'apps/notes/save.h', 'tests/hosted/notes_save_fixture.c')
    report['source'] = {name: sha(ROOT / name) for name in inputs}
    for name in (*inputs, 'tools/test_notes_save.py'):
        retained = out / 'retained-source' / name
        retained.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, retained)
    # Fortify redirects read() to __read_chk under ASan and bypasses --wrap=read.
    flags = ['-std=c17', '-D_POSIX_C_SOURCE=200809L', '-U_FORTIFY_SOURCE',
             '-Wall', '-Wextra', '-Werror', '-O1', '-g']
    if args.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    try:
        run('compile-main', [compiler, *flags, '-Dmain=notes_main', '-c', ROOT / inputs[0], '-o', out / 'main.o'])
        run('compile-fixture', [compiler, *flags, ROOT / inputs[1], ROOT / inputs[3], out / 'main.o',
            *['-Wl,--wrap=' + name for name in WRAPS], '-o', out / 'notes-fixture'])
        def case(label, fault='', existing=True, expected='old', special='', read=False):
            case_root = out / 'cases' / label
            data = case_root / 'data'
            data.mkdir(parents=True, mode=0o700)
            os.chmod(data, 0o700)
            target = data / 'english.txt'
            if existing:
                target.write_bytes(OLD)
                os.chmod(target, 0o640)
            if special == 'symlink':
                target.unlink()
                (data / 'other.txt').write_bytes(OLD)
                target.symlink_to('other.txt')
            elif special == 'hardlink':
                os.link(target, data / 'other.txt')
            elif special == 'readonly':
                os.chmod(target, 0o400)
            elif special == 'special-mode':
                os.chmod(target, 0o2640)
            elif special == 'shared-parent':
                os.chmod(data, 0o777)
            elif special == 'directory':
                target.unlink()
                target.mkdir()
            path_arg = str(target)
            if special == 'empty': path_arg = ''
            if special == 'trailing-slash': path_arg += '/'
            if special == 'dot': path_arg = str(data) + '/.'
            if special == 'dotdot': path_arg = str(data) + '/..'
            if special == 'long': path_arg = 'x' * 256
            if special == 'relative': path_arg = 'english.txt'
            before_identity = target.stat() if fault == 'destination-identity' else None
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', NOTES_FAULT=fault,
                       NOTES_TRACE=str(case_root / 'trace.log'), NOTES_MOVE_PARENT=str(data),
                       NOTES_MOVE_TO=str(case_root / 'moved'))
            if args.sanitize:
                env['ASAN_OPTIONS'] = 'detect_leaks=0'
            if special == 'masked-mode':
                env['NOTES_TEST_UMASK'] = '077'
            argv = [str(out / 'notes-fixture'), path_arg]
            if not read: argv += ['Updated', 'English', 'note.']
            result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                    cwd=data if special == 'relative' else None, timeout=10)
            (case_root / 'stdout.log').write_bytes(result.stdout)
            (case_root / 'stderr.log').write_bytes(result.stderr)
            events = (case_root / 'trace.log').read_text().splitlines()
            if fault == 'parent-renamed':
                data = case_root / 'moved'
                target = data / 'english.txt'
                need(not (case_root / 'data').exists(), label + ': directory was not renamed')
            success = expected == 'new' or (read and not fault == 'read')
            need((result.returncode == 0) == success, label + ': incorrect exit status')
            need(result.returncode in (0, 1), label + ': fixture/sanitizer failed')
            if read:
                if success: need(result.stdout == OLD, label + ': read/short stdout mismatch')
                need('rename' not in events and 'stage-open' not in events, label + ': read mutated files')
            elif expected in ('new', 'new-error'):
                need(target.read_bytes() == NEW, label + ': wrong committed payload')
                expected_mode = 0o640 if existing else 0o600
                need(target.stat().st_mode & 0o7777 == expected_mode, label + ': metadata changed')
                for event in ('stage-write', 'stage-fsync', 'stage-close', 'destination-recheck', 'rename', 'parent-fsync', 'parent-close'):
                    need(event in events, label + ': missing ' + event)
                order = [events.index(event) for event in ('stage-fsync', 'stage-close', 'destination-recheck', 'rename', 'parent-fsync', 'parent-close')]
                need(order == sorted(order), label + ': commit ordering')
                need(events.count('stage-close') == events.count('parent-close') == 1, label + ': repeated close')
                if expected == 'new-error':
                    need(b'File replaced; save completion failed.' in result.stderr, label + ': hidden post-commit failure')
                    need(b'Saved ' not in result.stdout, label + ': false success')
                else:
                    need(b'Saved ' in result.stdout, label + ': success not reported')
            elif expected == 'missing':
                need(not target.exists(), label + ': disappeared destination recreated')
            elif expected == 'competitor':
                need(target.read_bytes() == b'competing\n', label + ': concurrent creation overwritten')
            elif expected == 'rival':
                after_identity = target.stat()
                fields = ('st_mode', 'st_size', 'st_uid', 'st_gid', 'st_nlink')
                need(after_identity.st_ino != before_identity.st_ino and
                     all(getattr(after_identity, field) == getattr(before_identity, field) for field in fields),
                     label + ': injected replacement did not preserve metadata while changing inode')
                need(target.read_bytes() == RIVAL, label + ': competing inode bytes changed')
                need('identity-substituted' in events and 'destination-recheck' in events and
                     events.count('cleanup') == 1 and 'rename' not in events,
                     label + ': Notes did not reject changed inode before rename and clean its temp')
            elif special != 'directory':
                need(target.read_bytes() == OLD, label + ': original damaged')
                need('rename' not in events or fault == 'rename', label + ': unexpected commit')
            leftovers = list(data.glob('.notes-*.tmp'))
            if fault == 'first-collision':
                need(len(leftovers) == 1 and leftovers[0].read_bytes() == b'sentinel\n', label + ': collision damaged')
            elif fault == 'write-cleanup':
                need(len(leftovers) == 1 and b'No space left' in result.stderr, label + ': original error or recovery file lost')
            else:
                need(not leftovers, label + ': leaked temporary')
            if fault == 'all-collisions':
                need(events.count('stage-open') == 32 and 'cleanup' not in events, label + ': unowned cleanup or unbounded retry')
            if fault == 'stage-close':
                need(events.count('stage-close') == 1 and 'rename' not in events, label + ': retry of failed close')
            if special == 'symlink':
                need(target.is_symlink() and (data / 'other.txt').read_bytes() == OLD, label + ': symlink followed/replaced')
            if special == 'hardlink':
                need(target.stat().st_nlink == 2 and (data / 'other.txt').read_bytes() == OLD, label + ': hardlink changed')
            row = dict(label=label, status='passed', fault=fault, expected=expected, returncode=result.returncode,
                trace_sha256=sha(case_root / 'trace.log'), stdout_sha256=sha(case_root / 'stdout.log'),
                stderr_sha256=sha(case_root / 'stderr.log'), events=events, leftovers=[p.name for p in leftovers])
            if fault == 'destination-identity':
                row['inode_before'] = before_identity.st_ino
                row['inode_after'] = target.stat().st_ino
            report['cases'].append(row)
            save()
            print('PASS hosted Notes', label, flush=True)
        case('create', existing=False, expected='new')
        case('replace-mode', expected='new')
        case('short-eintr', 'short-eintr', expected='new')
        case('first-collision', 'first-collision', expected='new')
        case('parent-renamed', 'parent-renamed', expected='new')
        case('relative', expected='new', special='relative')
        case('masked-mode', special='masked-mode')
        for fault in ('parent-open', 'parent-stat', 'destination-stat', 'stage-open', 'stage-stat',
                      'stage-metadata', 'write', 'write-zero', 'stage-fsync', 'stage-close',
                      'destination-recheck', 'destination-metadata', 'rename', 'all-collisions', 'write-cleanup'):
            case(fault, fault)
        case('destination-disappeared', 'destination-disappeared', expected='missing')
        case('destination-created', 'destination-created', existing=False, expected='competitor')
        case('destination-identity', 'destination-identity', expected='rival')
        case('parent-fsync', 'parent-fsync', expected='new-error')
        case('parent-close', 'parent-close', expected='new-error')
        for special in ('symlink', 'hardlink', 'readonly', 'special-mode', 'shared-parent',
                        'directory', 'empty', 'trailing-slash', 'dot', 'dotdot', 'long'):
            case('reject-' + special, special=special)
        case('read', read=True)
        case('read-short-eintr', 'read-short-eintr', read=True)
        case('read-error', 'read', read=True)
        report.update(status='passed-hosted-notes-save-controls', case_count=len(report['cases']),
            sanitizers=args.sanitize, binary_sha256=sha(out / 'notes-fixture'))
        save()
        print('PASS bounded hosted Notes controls', len(report['cases']), sha(out / 'result.json'), flush=True)
    except Exception as error:
        report.update(status='failed', error=str(error))
        save()
        raise

if __name__ == '__main__':
    main()
