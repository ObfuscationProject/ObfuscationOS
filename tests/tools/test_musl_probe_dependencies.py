from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from build_musl_probe import (capture_compile_dependencies, compile_dependency_names,
                              verify_compile_dependencies)


class CompileDependencyTests(unittest.TestCase):
    def test_make_escaped_names_and_occurrences(self):
        text = 'musl-probe-object: /a\\ b /a\\#b /a$$b \\\n /back\\\\slash /again /again\n'
        self.assertEqual(compile_dependency_names(text),
                         ['/a b', '/a#b', '/a$b', '/back\\slash', '/again', '/again'])

    def test_malformed_rules_are_rejected(self):
        for text in ('', 'other: a', 'musl-probe-object:', 'musl-probe-object: a\\',
                     'musl-probe-object: a\nother: b', 'musl-probe-object: $(ROOT)',
                     'musl-probe-object: a # comment', 'musl-probe-object: a\0b'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                compile_dependency_names(text)

    def test_missing_omitted_and_changed_dependencies(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source, header, dep = root / 'probe.c', root / 'header.h', root / 'probe.d'
            source.write_text('#include "header.h"\n')
            header.write_text('#define VALUE 1\n')
            dep.write_text(f'musl-probe-object: {source} {header}\n')
            record = capture_compile_dependencies(dep, source, root)
            verify_compile_dependencies(record)
            header.write_text('#define VALUE 2\n')
            with self.assertRaisesRegex(ValueError, 'closure changed'):
                verify_compile_dependencies(record)
            header.unlink()
            with self.assertRaisesRegex(ValueError, 'missing regular'):
                capture_compile_dependencies(dep, source, root)
            dep.write_text(f'musl-probe-object: {source.parent}/other.c\n')
            with self.assertRaisesRegex(ValueError, 'omit'):
                capture_compile_dependencies(dep, source, root)
            dep.unlink()
            with self.assertRaises(OSError):
                capture_compile_dependencies(dep, source, root)

    def test_actual_object_command_includes_system_headers(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source, dep, obj = root / 'probe.c', root / 'probe.d', root / 'probe.o'
            source.write_text('#include <stddef.h>\n#include <sys/socket.h>\n'
                              'int probe(void) { return sizeof(struct sockaddr) + sizeof(size_t); }\n')
            command = ['/usr/bin/cc', '-MD', '-MF', str(dep), '-MT', 'musl-probe-object',
                       '-c', str(source), '-o', str(obj)]
            subprocess.run(command, cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertGreater(obj.stat().st_size, 0)
            record = capture_compile_dependencies(dep, source, root)
            self.assertIn(str(source), record['files'])
            self.assertTrue(any(path.endswith('/sys/socket.h') for path in record['files']))
            self.assertTrue(any(path.endswith('/stddef.h') for path in record['files']))
            self.assertTrue(record['same_command_as_object'])
            verify_compile_dependencies(record)
            dep.write_text(dep.read_text() + ' ')
            with self.assertRaisesRegex(ValueError, 'file changed'):
                verify_compile_dependencies(record)


if __name__ == '__main__':
    unittest.main()
