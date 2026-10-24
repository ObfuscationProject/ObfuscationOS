"""Execute the real shell engine with hosted processes, files and fault injection.

These are hosted execution tests. Native SDK/guest qualification is separate.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='oksh-hosted-')
        cls.build = Path(cls.temporary.name)
        common = ['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                  '-I', str(ROOT / 'apps/lib')]
        subprocess.run([*common, '-DOKSH_HOSTED', '-Dmain=oksh_main', '-c',
                        str(ROOT / 'apps/oksh/main.c'), '-o', str(cls.build / 'main.o')], check=True)
        cls.shell = cls.build / 'oksh'
        cls.child = cls.build / 'child'
        subprocess.run([*common, str(cls.build / 'main.o'), str(ROOT / 'tests/hosted/oksh_commands.c'),
                        str(ROOT / 'tests/hosted/oksh_faults.c'),
                        '-Wl,--wrap=fork,--wrap=pipe,--wrap=dup2,--wrap=waitpid,'
                        '--wrap=setpgid,--wrap=tcgetsid,--wrap=tcgetpgrp,--wrap=tcsetpgrp',
                        '-o', str(cls.shell)], check=True)
        subprocess.run([*common, str(ROOT / 'tests/hosted/oksh_child.c'), '-o', str(cls.child)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='oksh-case-')
        self.work = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def run_shell(self, command=None, *, input=None, env=None):
        return subprocess.run([str(self.shell), *(['-c', command] if command is not None else [])],
                              input=input, capture_output=True, timeout=8, cwd=self.work,
                              env={**os.environ, **(env or {})})

    def test_multiple_concurrent_stages_and_large_output(self):
        result = self.run_shell(f'{self.child} emit 200000 | cat | cat | cat > output')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / 'output').read_bytes(), b'x' * 200000)

    def test_adjacent_operators_quotes_and_empty_arguments(self):
        result = self.run_shell('echo "a | b" \'\' escaped\\ space|cat>"quoted file"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / 'quoted file').read_bytes(), b'a | b  escaped space\n')

    def test_sequential_lists_trailing_separator_and_quoted_operators(self):
        result = self.run_shell('echo "a;b&&c||d";echo escaped\\;separator;echo final;')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'a;b&&c||d\nescaped;separator\nfinal\n')
        self.assertEqual(self.run_shell(f'echo first;{self.child} status 23;').returncode, 23)
        self.assertEqual(self.run_shell('   ').returncode, 0)

    def test_and_or_short_circuit_and_equal_left_associative_precedence(self):
        for command, output, status in (
                ('echo first || echo skipped && echo last', b'first\nlast\n', 0),
                (f'{self.child} status 23 && echo skipped || echo fallback', b'fallback\n', 0),
                (f'{self.child} status 23 || echo middle && echo last', b'middle\nlast\n', 0),
                (f'{self.child} status 23 && echo skipped && echo also-skipped', b'', 23),
                (f'echo first || {self.child} status 23 || echo skipped', b'first\n', 0),
                (f'echo first && {self.child} status 23 || {self.child} status 42', b'first\n', 42),
                (f'{self.child} status 23 || {self.child} status 42 && echo skipped', b'', 42),
                (f'{self.child} status 23 && echo skipped;echo reset', b'reset\n', 0)):
            with self.subTest(command=command):
                result = self.run_shell(command)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(result.stdout, output)

    def test_skipped_lists_do_not_open_files_change_cwd_or_launch_children(self):
        result = self.run_shell('echo good||echo skipped>side|cat;echo final',
                                env={'OKSH_FAIL_PIPE': '1', 'OKSH_FAIL_FORK': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'good\nfinal\n')
        self.assertEqual(result.stderr, b'')
        self.assertFalse((self.work / 'side').exists())
        result = self.run_shell(f'{self.child} status 23 && echo skipped > side; pwd')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(self.work).encode() + b'\n')
        self.assertFalse((self.work / 'side').exists())
        result = self.run_shell('echo good > output || cd /;pwd')
        self.assertEqual(result.stdout, str(self.work).encode() + b'\n')

    def test_list_pipelines_keep_last_stage_status_and_redirection_spans(self):
        result = self.run_shell(f'{self.child} status 23|cat&&echo first>output;'
                                f'echo ignored|{self.child} status 42||echo second>>output;cat<input')
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.work / 'output').read_bytes(), b'first\nsecond\n')
        result = self.run_shell(f'{self.child} emit 200000|cat|cat>large&&cat<large|cat>copy;echo done')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'done\n')
        self.assertEqual((self.work / 'copy').read_bytes(), b'x' * 200000)

    def test_input_append_and_output_redirection(self):
        (self.work / 'input').write_bytes(b'original\n')
        self.assertEqual(self.run_shell('cat<input|cat>output').returncode, 0)
        self.assertEqual(self.run_shell('echo added>>output').returncode, 0)
        self.assertEqual((self.work / 'output').read_bytes(), b'original\nadded\n')
        self.assertEqual(self.run_shell('echo replacement>output').returncode, 0)
        self.assertEqual((self.work / 'output').read_bytes(), b'replacement\n')

    def test_stderr_and_left_to_right_descriptor_order(self):
        result = self.run_shell(f'{self.child} both > all 2>&1')
        self.assertEqual(result.returncode, 0)
        self.assertEqual((self.work / 'all').read_bytes(), b'stdout\nstderr\n')
        self.assertEqual(result.stdout, b'')
        result = self.run_shell(f'{self.child} both 2>&1 > only-output')
        self.assertEqual(result.stdout, b'stderr\n')
        self.assertEqual((self.work / 'only-output').read_bytes(), b'stdout\n')
        self.assertEqual(self.run_shell(f'{self.child} both 2>errors').returncode, 0)
        self.assertEqual(self.run_shell(f'{self.child} both 2>>errors').returncode, 0)
        self.assertEqual((self.work / 'errors').read_bytes(), b'stderr\nstderr\n')

    def test_pipeline_redirection_overrides_pipe(self):
        result = self.run_shell('echo file > output | cat')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertEqual((self.work / 'output').read_bytes(), b'file\n')

    def test_last_stage_status_signal_and_exec_errors(self):
        self.assertEqual(self.run_shell(f'{self.child} status 42 | cat').returncode, 0)
        self.assertEqual(self.run_shell(f'echo value | {self.child} status 42').returncode, 42)
        self.assertEqual(self.run_shell(f'{self.child} signal').returncode, 143)
        self.assertEqual(self.run_shell('missing-oksh-command').returncode, 127)
        (self.work / 'not-executable').write_text('no')
        self.assertEqual(self.run_shell('./not-executable').returncode, 126)

    def test_parent_builtin_restores_descriptors_and_preserves_cwd(self):
        (self.work / 'childdir').mkdir()
        result = self.run_shell(input=b'echo hidden > output\necho visible\ncd childdir > ../cd-output\npwd\nexit 7\n')
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn(b'visible\n', result.stdout)
        self.assertNotIn(b'hidden\n', result.stdout)
        self.assertIn(str(self.work / 'childdir').encode(), result.stdout)
        self.assertEqual((self.work / 'output').read_bytes(), b'hidden\n')

    def test_parent_builtins_in_lists_preserve_state_and_restore_descriptors(self):
        (self.work / 'childdir').mkdir()
        result = self.run_shell('cd childdir > ../cd-output && echo hidden > output;'
                                'echo closed 1>&- || echo recovered;pwd;'
                                'cd absent && echo skipped > marker;echo done')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'recovered\n' + str(self.work / 'childdir').encode() + b'\ndone\n')
        self.assertEqual((self.work / 'childdir/output').read_bytes(), b'hidden\n')
        self.assertFalse((self.work / 'childdir/marker').exists())

    def test_pipeline_builtin_does_not_change_parent_cwd(self):
        result = self.run_shell(input=b'cd / | cat\npwd\nexit\n')
        self.assertEqual(result.returncode, 0)
        self.assertIn(str(self.work).encode(), result.stdout)

    def test_builtin_write_failure_and_standard_descriptor_restoration(self):
        self.assertEqual(self.run_shell('echo failure 1>&-').returncode, 1)
        result = self.run_shell(input=b'echo failure 1>&-\necho recovered\nexit\n')
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'recovered\n', result.stdout)

    def test_failed_redirection_never_executes_and_shell_recovers(self):
        result = self.run_shell(f'{self.child} touch marker < absent')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.work / 'marker').exists())
        result = self.run_shell(input=b'echo hidden > absent/target\necho recovered\nexit\n')
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'recovered\n', result.stdout)

    def test_syntax_is_rejected_before_side_effects(self):
        for command in ('echo bad > side |', 'echo bad > side ||| cat', 'echo >',
                        'echo "unterminated', 'echo bad > side & cat', 'echo 9>side',
                        'echo bad > side ;; cat', 'echo > side | | cat',
                        'echo bad > side;echo later&&', 'echo bad > side || echo >',
                        'echo bad > side;echo later||', 'echo bad > side;echo && || echo',
                        'echo bad > side;echo && & echo', ';echo bad > side',
                        '&&echo bad > side', '||echo bad > side',
                        'exit;echo bad > side &&', 'echo bad > side;>'):
            with self.subTest(command=command):
                self.assertEqual(self.run_shell(command).returncode, 2)
                self.assertFalse((self.work / 'side').exists())

    def test_capacity_failures_are_explicit(self):
        for command in ('echo ' + ' '.join(['x'] * 31), '|'.join(['echo'] * 17),
                        'echo ' + ' > output' * 33,
                        'echo first > output;' + ';'.join(['echo'] * 16),
                        'echo > output' + ' > output' * 16 + ';echo' + ' > output' * 16):
            self.assertEqual(self.run_shell(command).returncode, 2)
            self.assertFalse((self.work / 'output').exists())
        self.assertEqual(self.run_shell(';'.join(['echo'] * 16) + ';').returncode, 0)
        self.assertEqual(self.run_shell('|'.join(['echo'] * 16)).returncode, 0)
        self.assertEqual(self.run_shell('echo ' + ' '.join(['x'] * 30)).returncode, 0)
        result = self.run_shell('echo first' + ' > first' * 17 + ';echo second' + ' > second' * 15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / 'first').read_bytes(), b'first\n')
        self.assertEqual((self.work / 'second').read_bytes(), b'second\n')
        result = self.run_shell(input=b'echo ' + b'x' * 1200 + b'\necho recovered\nexit\n')
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'recovered\n', result.stdout)
        self.assertNotIn(b'x' * 20, result.stdout)

    def test_fork_and_pipe_failures_abort_all_started_children(self):
        for kind, point in (('FORK', '1'), ('FORK', '2'), ('FORK', '3'),
                            ('PIPE', '1'), ('PIPE', '2'), ('PIPE', '3')):
            with self.subTest(kind=kind, point=point):
                result = self.run_shell(f'{self.child} touch marker | cat | cat',
                                        env={f'OKSH_FAIL_{kind}': point})
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse((self.work / 'marker').exists())

    def test_list_recovers_after_partial_pipeline_construction_failure(self):
        for kind, point in (('FORK', '2'), ('FORK', '3'), ('PIPE', '2'), ('PIPE', '3')):
            with self.subTest(kind=kind, point=point):
                result = self.run_shell(f'{self.child} touch marker|cat|cat&&echo bad>side||'
                                        'echo recovered>output;echo final|cat',
                                        env={f'OKSH_FAIL_{kind}': point})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, b'final\n')
                self.assertFalse((self.work / 'marker').exists())
                self.assertFalse((self.work / 'side').exists())
                self.assertEqual((self.work / 'output').read_bytes(), b'recovered\n')

    def test_repeated_lists_reap_children_and_restore_descriptors(self):
        line = ('echo repeat|cat>first&&cat<first|cat>second;'
                f'{self.child} status 23&&echo skipped>side||echo recovered;\n').encode()
        result = self.run_shell(input=line * 64 + b'echo final\nexit\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count(b'recovered\n'), 64)
        self.assertIn(b'final\n', result.stdout)
        self.assertEqual((self.work / 'second').read_bytes(), b'repeat\n')
        self.assertFalse((self.work / 'side').exists())

    def test_dup_failure_and_wait_interruption_cleanup(self):
        self.assertEqual(self.run_shell('echo value | cat', env={'OKSH_FAIL_DUP2': '1'}).returncode, 1)
        result = self.run_shell('echo value | cat | cat', env={'OKSH_INTERRUPT_WAIT': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'value\n')

    def test_internal_pipe_descriptors_do_not_alias_closed_standard_fds(self):
        for variable in ("OKSH_CLOSE_STDIN", "OKSH_CLOSE_STDOUT"):
            result = self.run_shell("echo complete|cat>output", env={variable: "1"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((self.work / "output").read_bytes(), b"complete\n")

    def test_exit_uses_last_status_and_validates_argument(self):
        self.assertEqual(self.run_shell(input=f'{self.child} status 23\nexit\n'.encode()).returncode, 23)
        self.assertEqual(self.run_shell('exit -1').returncode, 255)
        self.assertEqual(self.run_shell('exit invalid').returncode, 2)
        self.assertEqual(self.run_shell('> empty').returncode, 0)
        self.assertEqual((self.work / 'empty').read_bytes(), b'')

    def test_list_exit_stops_parent_but_not_pipeline_and_respects_short_circuit(self):
        for command, expected in (('exit 19;echo unreachable>side', 19),
                                  ('exit invalid;echo unreachable>side', 2),
                                  (f'{self.child} status 23&&echo skipped;exit', 23),
                                  (f'{self.child} status 23||exit;echo unreachable>side', 23)):
            with self.subTest(command=command):
                self.assertEqual(self.run_shell(command).returncode, expected)
                self.assertFalse((self.work / 'side').exists())
        result = self.run_shell('echo first||exit 19;exit 7|cat&&echo alive;'
                                'exit 1 2;echo continued;exit 8 >absent/output||echo recovered')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'first\nalive\ncontinued\nrecovered\n')
        result = self.run_shell(input=b'echo before;exit 17;echo same-line>side\necho next-line>side\n')
        self.assertEqual(result.returncode, 17)
        self.assertFalse((self.work / 'side').exists())

    def test_redirection_only_list_commands_obey_short_circuit(self):
        result = self.run_shell('>empty&&echo first>>empty;echo skip>output||>side;cat<empty')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'first\n')
        self.assertEqual((self.work / 'empty').read_bytes(), b'first\n')
        self.assertFalse((self.work / 'side').exists())

    def console_run(self, command, *, mask='1', env=None, next_line=b'exit\n'):
        events = self.work / 'terminal-events'
        events.unlink(missing_ok=True)
        result = self.run_shell(input=command.encode() + b'\n' + next_line,
                                env={'OKSH_CONSOLE_MASK': mask,
                                     'OKSH_CONSOLE_EVENTS': str(events), **(env or {})})
        return result, [line.split() for line in events.read_text().splitlines()]

    def test_console_chooses_an_inherited_standard_alias_and_restores_after_redirections(self):
        for mask, expected in (('1', '0'), ('2', '1'), ('4', '2')):
            with self.subTest(mask=mask):
                result, events = self.console_run(
                    f'echo hidden 0<&- > output;{self.child} identity terminal-events', mask=mask)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([row[1] for row in events if row[0] == 'SID' and int(row[1]) < 3],
                                 [str(fd) for fd in range(int(expected) + 1)])
                self.assertTrue(all(int(row[1]) >= 3 for row in events if row[0] == 'SET'))
                self.assertEqual((self.work / 'output').read_bytes(), b'hidden\n')
                self.assertIn(b'oksh> ', result.stdout)

    def test_console_pipeline_groups_exist_before_handoff_and_any_command_execution(self):
        command = '|'.join([f'{self.child} identity terminal-events'] * 3)
        result, events = self.console_run(command + ';' + command)
        self.assertEqual(result.returncode, 0, result.stderr)
        shell = events[0]
        children = [row for row in events if row[0] == 'CHILD']
        self.assertEqual(len(children), 6)
        groups = [row for row in events if row[0] == 'GROUP']
        transfers = [row for row in events if row[0] == 'SET']
        self.assertEqual(len(groups), 6)
        self.assertEqual(len(transfers), 4)
        for batch in range(2):
            assigned = groups[batch * 3:batch * 3 + 3]
            group = assigned[0][1]
            self.assertTrue(all(row[2:] == [group, group] for row in assigned))
            transfer = transfers[batch * 2]
            self.assertEqual(transfer[2], group)
            members = [row for row in children if row[4] == group]
            self.assertEqual(len(members), 3)
            self.assertEqual({row[1] for row in members}, {row[1] for row in assigned})
            self.assertTrue(all(row[2:4] == shell[1:3] for row in members))
            self.assertTrue(all(events.index(row) < events.index(transfer) for row in assigned))
            self.assertTrue(all(events.index(transfer) < events.index(row) for row in members))
            self.assertEqual(transfers[batch * 2 + 1][2], shell[3])
        self.assertNotEqual(transfers[0][2], transfers[2][2])

    def test_command_mode_and_nonconsole_input_do_not_manage_foreground_groups(self):
        events = self.work / 'terminal-events'
        result = self.run_shell(f'{self.child} identity terminal-events|cat',
                                env={'OKSH_CONSOLE_MASK': '7', 'OKSH_CONSOLE_EVENTS': str(events)})
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [line.split() for line in events.read_text().splitlines()]
        self.assertEqual([row[0] for row in rows], ['SHELL', 'CHILD'])
        self.assertEqual(rows[1][4], rows[0][3])
        result, rows = self.console_run(f'{self.child} identity terminal-events|cat', mask='0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(row[0] in ('SET', 'GET', 'GROUP') for row in rows))

    def test_console_reclaims_after_partial_launch_and_foreground_errors(self):
        command = '|'.join([f'{self.child} identity terminal-events'] * 3)
        for variable, point in (('FORK', '1'), ('FORK', '2'), ('FORK', '3'),
                                ('PIPE', '1'), ('PIPE', '2'), ('PIPE', '3'),
                                ('SETPGID', '1'), ('SETPGID', '2'), ('SETPGID', '3'),
                                ('FOREGROUND', '1')):
            with self.subTest(variable=variable, point=point):
                result, events = self.console_run(command, env={f'OKSH_FAIL_{variable}': point})
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(any(row[0] == 'CHILD' for row in events))
                self.assertEqual([row for row in events if row[0] == 'SET'][-1][2], events[0][3])

    def test_console_reclaims_after_signals_and_permanent_or_interrupted_wait(self):
        for command, env, expected in (
                (f'{self.child} signal', {}, 143),
                (f'{self.child} identity terminal-events|cat', {'OKSH_FAIL_WAIT': '1'}, 1),
                (f'{self.child} identity terminal-events|cat', {'OKSH_INTERRUPT_WAIT': '1'}, 0),
                (f'{self.child} identity terminal-events|cat',
                 {'OKSH_FAIL_FORK': '2', 'OKSH_FAIL_WAIT': '1'}, 1)):
            with self.subTest(command=command, env=env):
                result, events = self.console_run(command, env=env)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual([row for row in events if row[0] == 'SET'][-1][2], events[0][3])

    def test_console_restore_failure_stops_the_current_list_and_next_prompt(self):
        result, events = self.console_run(
            f'{self.child} status 0;echo unreachable>side',
            env={'OKSH_FAIL_RESTORE': '1'}, next_line=b'echo unreachable>side\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.work / 'side').exists())
        self.assertEqual(result.stdout.count(b'oksh> '), 1)
        self.assertTrue(any(row[0] == 'RESTORE_FAIL' for row in events))

    def test_console_alias_is_closed_in_builtin_children(self):
        result, events = self.console_run('help|help|help', env={'OKSH_CHECK_BUILTIN_FDS': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len([row for row in events if row[0] == 'GROUP']), 3)

    def test_console_with_a_different_session_never_launches_commands(self):
        result, events = self.console_run(f'{self.child} touch side',
                                          env={'OKSH_WRONG_CONSOLE_SID': '1'})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.work / 'side').exists())
        self.assertFalse(any(row[0] in ('GROUP', 'SET') for row in events))


if __name__ == '__main__':
    unittest.main()
