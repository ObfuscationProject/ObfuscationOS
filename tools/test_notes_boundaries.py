"""Check Notes against a real-file model of the qualified block-write limit."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OLD = b'Original English note.\n'
PATTERN = re.compile(r'offset=(\d+) requested=(\d+) returned=(-?\d+) error=(\d+)')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--predecessor-root', type=Path)
    args = parser.parse_args()
    require(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'Disable bytecode')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    compiler = Path(shutil.which(args.cc) or args.cc).resolve(strict=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LC_ALL='C')
    if args.sanitize:
        env['ASAN_OPTIONS'] = 'detect_leaks=0'
    flags = ['-std=c17', '-D_POSIX_C_SOURCE=200809L', '-U_FORTIFY_SOURCE', '-Wall', '-Wextra', '-Werror', '-O1', '-g']
    if args.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    report = {'schema': 1, 'passed': False, 'layer': 'hosted-real-file-block-write-model',
              'sanitizers': args.sanitize, 'compiler': str(compiler), 'compiler_sha256': digest(compiler),
              'source': {}, 'commands': [], 'cases': [], 'guest_execution': False, 'journal_durability': False}

    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    def command(label, argv):
        result = subprocess.run(list(map(str, argv)), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        log = out / (label + '.log')
        log.write_bytes(result.stdout)
        report['commands'].append({'label': label, 'argv': list(map(str, argv)),
                                   'returncode': result.returncode, 'log_sha256': digest(log)})
        save()
        require(result.returncode == 0, 'Compile failed: ' + label)

    def build(label, source):
        names = ('apps/notes/main.c', 'apps/notes/save.c', 'apps/notes/save.h')
        report['source'][label] = {name: digest(source / name) for name in names}
        report['source'][label]['tests/hosted/notes_boundary_fixture.c'] = digest(ROOT / 'tests/hosted/notes_boundary_fixture.c')
        command(label + '-main', [compiler, *flags, '-Dmain=notes_main', '-c', source / names[0], '-o', out / (label + '-main.o')])
        command(label + '-fixture', [compiler, *flags, source / names[1], ROOT / 'tests/hosted/notes_boundary_fixture.c',
            out / (label + '-main.o'), '-Wl,--wrap=openat', '-Wl,--wrap=write', '-o', out / label])
        return out / label

    def case(label, binary, lengths, fault='', expected_success=True, predecessor=False):
        data = out / 'cases' / label
        data.mkdir(parents=True, mode=0o700)
        os.chmod(data, 0o700)
        target = data / 'english.txt'
        target.write_bytes(OLD)
        os.chmod(target, 0o640)
        words = [chr(ord('A') + index % 26) * length for index, length in enumerate(lengths)]
        require(len(words) + 2 <= 16 and all(len(word) <= 255 for word in words), 'Case exceeds actual exec argument bounds')
        expected = (' '.join(words) + '\n').encode('ascii')
        trace = data / 'write.log'
        result = subprocess.run([str(binary), str(target), *words], env=dict(env,
            NOTES_BOUNDARY_TRACE=str(trace), NOTES_BOUNDARY_FAULT=fault), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        (data / 'stdout.log').write_bytes(result.stdout)
        (data / 'stderr.log').write_bytes(result.stderr)
        require(result.returncode == (0 if expected_success else 1), label + ': exit or sanitizer failure')
        rows = []
        for line in trace.read_text().splitlines():
            match = PATTERN.fullmatch(line)
            require(match is not None, label + ': malformed write trace')
            rows.append(dict(zip(('offset', 'requested', 'returned', 'error'), map(int, match.groups()))))
        require(rows, label + ': no staged writes')
        if predecessor:
            require(any(row['requested'] > 1024 - row['offset'] % 1024 and row['returned'] == -1 for row in rows),
                    label + ': predecessor did not reproduce crossing refusal')
        else:
            require(all(0 < row['requested'] <= 1024 - row['offset'] % 1024 for row in rows), label + ': request crosses a block')
        require(target.read_bytes() == (expected if expected_success else OLD), label + ': destination bytes changed incorrectly')
        require(target.stat().st_mode & 0o7777 == 0o640, label + ': destination mode changed')
        require(not list(data.glob('.notes-*.tmp')), label + ': staging file leaked')
        if expected_success:
            require(b'Saved ' in result.stdout and not result.stderr, label + ': missing successful outcome')
            total = sum(row['returned'] for row in rows if row['returned'] > 0)
            require(total == len(expected), label + ': successful byte count differs')
            require(sum(row['returned'] == -1 for row in rows) == (2 if fault == 'short-eintr' else 0), label + ': unexpected retries')
            require(rows[-1]['offset'] + rows[-1]['returned'] == len(expected), label + ': final position differs')
        else:
            require(b'Saved ' not in result.stdout and b'save:' in result.stderr, label + ': failure hidden')
            if fault in ('second-error', 'partial-error'):
                require(b'No space left' in result.stderr, label + ': first write error lost')
            if fault in ('second-zero', 'oversized'):
                require(b'Input/output error' in result.stderr, label + ': invalid count was accepted')
        report['cases'].append({'label': label, 'document_bytes': len(expected), 'fault': fault,
            'expected_success': expected_success, 'predecessor_counterexample': predecessor, 'writes': rows,
            'returncode': result.returncode, 'trace_sha256': digest(trace),
            'destination_sha256': digest(target), 'all_args_within_native_exec_bounds': True})
        save()
        print('PASS hosted Notes boundary ' + label, flush=True)

    try:
        binary = build('successor', ROOT)
        case('five-240-byte-words', binary, [240] * 5)
        case('six-200-byte-words', binary, [200] * 6)
        case('newline-at-1023', binary, [240] * 4 + [58])
        case('newline-at-1024', binary, [240] * 4 + [59])
        case('newline-at-1025', binary, [240] * 4 + [60])
        case('separator-to-boundary', binary, [240] * 4 + [59, 2])
        case('separator-on-boundary', binary, [240] * 4 + [60, 2])
        case('newline-at-2047', binary, [240] * 8 + [118])
        case('two-blocks', binary, [240] * 8 + [119])
        case('three-blocks', binary, [240] * 12 + [179])
        case('short-eintr-across-boundary', binary, [240] * 5, 'short-eintr')
        for fault in ('second-error', 'partial-error', 'second-zero', 'oversized'):
            case(fault, binary, [240] * 5, fault, expected_success=False)
        if args.predecessor_root:
            predecessor = build('predecessor', args.predecessor_root.resolve(strict=True))
            case('unchanged-predecessor-crossing-refusal', predecessor, [240] * 5,
                 expected_success=False, predecessor=True)
        report['passed'] = True
        report['case_count'] = len(report['cases'])
        save()
        print('PASS bounded hosted Notes write controls ' + str(len(report['cases'])), flush=True)
    except Exception as error:
        report['error'] = str(error)
        save()
        raise


if __name__ == '__main__':
    main()
