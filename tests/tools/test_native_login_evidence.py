"""Synthetic tamper controls for the native login reader; no guest acceptance."""
from pathlib import Path
import hashlib
import importlib.util
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
import native_login_evidence as evidence
import qualify_native_login as runner
import native_login_build as build_reader
import read_native_login as retained_reader


class NativeLoginEvidenceTests(unittest.TestCase):
    password = b'qualification-password-317ac45f'
    wrong = b'wrong-password-b981c76d'
    boot = b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=ordered-data\n'
    session = b'NATIVE_LOGIN_SESSION pid=7 ppid=1 uid=0 gid=0 epoch=17 user=qual_admin home=/root\n'

    @classmethod
    def setUpClass(cls):
        cls.salt = bytes(range(16))
        cls.verifier = hashlib.pbkdf2_hmac('sha256', cls.password, cls.salt, 600000, 32)

    def database(self, state=b'active'):
        return (b'OKACCOUNTS 1\nstate ' + state + b'\nname qual_admin\nuid 0\ngid 0\nhome /root\n'
                b'kdf pbkdf2-hmac-sha256\nrounds 600000\nsalt ' + self.salt.hex().encode() +
                b'\nverifier ' + self.verifier.hex().encode() + b'\n')

    def test_account_uses_independent_crypto_oracle_and_exact_canonical_policy(self):
        for state in ('pending', 'active'):
            value = evidence.account(self.database(state.encode()), self.password, state)
            self.assertEqual((value['state'], value['name'], value['uid'], value['gid'], value['home']),
                             (state, 'qual_admin', 0, 0, '/root'))
        for data, password, state in [(self.database(), self.wrong, 'active'),
                (self.database(b'pending'), self.password, 'active'),
                (self.database() + b'\n', self.password, 'active'),
                (self.database().replace(b'uid 0', b'uid 1'), self.password, 'active'),
                (self.database().replace(b'600000', b'0600000'), self.password, 'active'),
                (self.database().replace(b'qual_admin', b'other'), self.password, 'active')]:
            with self.subTest(data=data, state=state):
                with self.assertRaises(ValueError):
                    evidence.account(data, password, state)

    def test_serial_requires_actual_provider_and_expected_identity(self):
        value = evidence.serial(self.boot + self.session, (self.password, self.wrong), 1)
        self.assertEqual(value['sessions'], [dict(pid=7, epoch=17)])
        for data in (self.session, self.boot + self.session.replace(b'uid=0', b'uid=1'),
                     self.boot + self.session.replace(b'epoch=17', b'epoch=0'),
                     self.boot + self.session.replace(b'ppid=1', b'ppid=2')):
            with self.assertRaises(ValueError):
                evidence.serial(data, (self.password,), 1)

    def test_reused_epoch_duplicate_session_and_secret_fragments_fail(self):
        for data, count in [(self.boot + self.session * 2, 2),
                            (self.boot + self.session + self.session.replace(b'pid=7', b'pid=8'), 2),
                            (self.boot + self.session + self.session.replace(b'epoch=17', b'epoch=18'), 2),
                            (self.boot + self.session + self.password[5:13], 1)]:
            with self.assertRaises(ValueError):
                evidence.serial(data, (self.password,), count)
        newer = self.session.replace(b'pid=7', b'pid=8').replace(b'epoch=17', b'epoch=18')
        self.assertEqual(len(evidence.serial(self.boot + self.session + newer, (self.password,), 2)['sessions']), 2)

    def test_cut_and_publication_counts_and_order_are_exact(self):
        evidence.serial(self.boot + evidence.CUT + b'\n', (self.password,), 0, cut=True)
        publication = b'NATIVE_LOGIN_PUBLICATION state=pending\nNATIVE_LOGIN_PUBLICATION state=active\n'
        evidence.serial(self.boot + publication + self.session, (self.password,), 1,
                        publications=('pending', 'active'))
        for data in (self.boot + publication + self.session,
                     self.boot + publication.replace(b'pending', b'active') + self.session):
            with self.assertRaises(ValueError):
                evidence.serial(data, (self.password,), 1)
        with self.assertRaises(ValueError):
            evidence.serial(self.boot + self.session, (self.password,), 1, cut=True)

    def test_late_failure_cannot_be_hidden_by_success_marker(self):
        for marker in (b'NATIVE_LOGIN_FIXTURE_FAIL component=cut', b'event=fatal-hold', b'OK_TEST_FAIL'):
            with self.assertRaises(ValueError):
                evidence.serial(self.boot + self.session + marker, (self.password,), 1)

    def test_prompt_cursor_retains_already_arrived_next_prompt(self):
        guest = object.__new__(runner.Guest)
        guest.data = bytearray(b'Password: \nLogin incorrect.\nLogin: ')
        guest.receive = lambda predicate, **kwargs: self.assertTrue(predicate(bytes(guest.data[kwargs.get('start', 0):])))
        at = guest.prompt(b'Login incorrect.')
        self.assertLess(at, len(guest.data))
        self.assertEqual(guest.prompt(b'Login: ', start=at), len(guest.data))

    def test_fixture_staging_keeps_unwrapped_login_and_actual_shell_bytes(self):
        import tempfile
        spec = importlib.util.spec_from_file_location('stage_login_fixture', ROOT / 'tests/native/stage_login_fixture.py')
        stage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage)
        with tempfile.TemporaryDirectory(prefix='login-stage-host-') as directory:
            build = Path(directory)
            for name, data in [('rootfs/init', b'init'), ('rootfs/bin/oksh', b'old'),
                    ('apps/login.elf', b'actual-production-login'), ('apps/oksh.elf', b'actual-shell'),
                    ('fixtures/native-login-session.elf', b'session-wrapper'),
                    ('fixtures/native-login-cut.elf', b'cut-wrapped-login')]:
                path = build / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            stage.stage(build)
            for product, target in [('apps/login.elf', 'bin/login'), ('apps/oksh.elf', 'bin/oksh-real'),
                    ('fixtures/native-login-session.elf', 'bin/oksh'), ('fixtures/native-login-cut.elf', 'bin/login-cut')]:
                self.assertEqual((build / product).read_bytes(), (build / 'rootfs' / target).read_bytes())
                self.assertEqual((build / 'rootfs' / target).stat().st_mode & 0o777, 0o755)

    def test_dependency_reader_accepts_literals_and_refuses_code_or_duplicate_keys(self):
        text = '{ files = {"apps/login/main.c"}, values = {"gcc", {"-c", "-g"}}, depfiles_format = "gcc", depfiles = "x: y\\n" }'
        parsed = build_reader.LiteralTable(text).parse()
        self.assertEqual(parsed['files'], ['apps/login/main.c'])
        for malformed in (text + ' os.execute("bad")', '{ files = {}, files = {} }',
                          '{ files = require("bad") }', '{ files = {"x", named="y"} }'):
            with self.assertRaises(ValueError):
                build_reader.LiteralTable(malformed).parse()

    def test_input_reader_rederives_exact_lines_and_authentication_order(self):
        data = (b'ObfuscationOS\nLogin: Password: Login incorrect.\nLogin: Password: ' +
                self.session + b'oksh> LOGIN_SHELL_' + b'a' * 24 + b'\noksh> Login: Password: ' +
                self.session.replace(b'pid=7', b'pid=8').replace(b'epoch=17', b'epoch=18') +
                b'oksh> LOGIN_SHELL_' + b'b' * 24 + b'\noksh> ')
        begin = data.index(b'Login incorrect.')
        end = data.index(b'Login: ', begin) + len(b'Login: ')
        values = [b'qual_admin', self.wrong, b'qual_admin', self.password,
                  b'echo LOGIN_SHELL_' + b'a' * 24, b'exit', b'qual_admin', self.password,
                  b'echo LOGIN_SHELL_' + b'b' * 24]
        offsets = [0, begin, end, end, end, end, end, end, end]
        row = dict(label='ordinary-restart', wrong_password_span=dict(start=begin, end=end),
                   wrong_password_denied_seconds=1.1,
                   shell_commands=[dict(output='LOGIN_SHELL_' + c * 24, completed=True) for c in ('a', 'b')],
                   stdin=[dict(before_serial_offset=offsets[i], monotonic_seconds=i * 1.1, bytes=len(value),
                               line_sha256=hashlib.sha256(value).hexdigest()) for i, value in enumerate(values)])
        retained_reader.inspect_inputs(row, data, self.password, self.wrong)
        import copy
        windows = data.replace(b'\n', b'\r\n')
        framed = copy.deepcopy(row)
        for event in framed['stdin']:
            event['before_serial_offset'] = len(data[:event['before_serial_offset']].replace(b'\n', b'\r\n'))
        framed['wrong_password_span'] = {
            key: len(data[:offset].replace(b'\n', b'\r\n'))
            for key, offset in row['wrong_password_span'].items()}
        retained_reader.inspect_inputs(framed, windows, self.password, self.wrong)
        with self.assertRaises(ValueError):
            retained_reader.inspect_inputs(row, data.replace(b'LOGIN_SHELL_', b'BROKEN_SHELL_'),
                                          self.password, self.wrong)
        altered = copy.deepcopy(row)
        altered['stdin'][1]['line_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            retained_reader.inspect_inputs(altered, data, self.password, self.wrong)
        with self.assertRaises(ValueError):
            retained_reader.inspect_inputs(row, data[:begin] + b'NATIVE_LOGIN_PUBLICATION state=pending' + data[begin:], self.password, self.wrong)

    def test_shell_observer_retains_raw_lf_and_crlf_coalesced_prompt_cursors(self):
        class SerialGuest:
            def __init__(self, session, ending):
                self.data = bytearray(session + b'oksh> ')
                self.ending = ending
                self.row = {}

            def receive(self, predicate, *, start=0):
                if not predicate(bytes(self.data[start:])):
                    raise ValueError('expected serial output absent')

            def prompt(self, value, *, start=0):
                return self.data.index(value, start) + len(value)

            def send(self, value):
                self.data.extend(value.removeprefix(b'echo ') + self.ending + b'oksh> ')

        campaign = object.__new__(runner.Campaign)
        for ending in (b'\n', b'\r\n'):
            guest = SerialGuest(self.session, ending)
            with self.subTest(ending=ending), patch.object(runner.secrets, 'token_hex', return_value='a' * 24):
                self.assertEqual(campaign.shell(guest), len(guest.data))
                self.assertIn(b'LOGIN_SHELL_' + b'a' * 24 + ending, guest.data)
                self.assertTrue(guest.row['shell_commands'][0]['completed'])
        with self.assertRaises(ValueError):
            campaign.shell(SerialGuest(self.session, b'\r'))

    def test_entropy_refusal_allows_only_input_free_supervisor_relaunch(self):
        import copy
        prefix = b'Create the first administrator\nAccount name: Password: Repeat password: '
        failure = b'login: unable to establish an authenticated console session.\n'
        values = (b'qual_admin', self.password, self.password)
        row = dict(label='no-entropy-refusal', stdin=[dict(before_serial_offset=10 + index,
            monotonic_seconds=index, bytes=len(value), line_sha256=hashlib.sha256(value).hexdigest())
            for index, value in enumerate(values)])
        for tail in (b'', b'NATIVE_PID1 event=reap\nCreate the first administrator\nAccount name: '):
            retained_reader.inspect_inputs(row, prefix + failure + tail, self.password, self.wrong)
        altered = copy.deepcopy(row)
        altered['stdin'][-1]['before_serial_offset'] = len(prefix) + 1
        for record, data in ((altered, prefix + failure), (row, prefix),
                             (row, prefix + prefix + failure)):
            with self.assertRaises(ValueError):
                retained_reader.inspect_inputs(record, data, self.password, self.wrong)

    def test_qualified_handoff_requires_actual_new_reader_field_and_complete_matrix(self):
        import tempfile
        import json
        with tempfile.TemporaryDirectory(prefix='login-handoff-host-') as directory:
            base = Path(directory)
            sdk = base / 'sdk'
            sdk.mkdir()
            sdk_pin = 'a' * 64
            rows = [dict(arch=arch, mode=mode, sdk_path=str(sdk), sdk=dict(manifest_sha256=sdk_pin),
                         sdk_build_pass=True, consumer_pass=True)
                    for arch in runner.ARCH_TRIPLES for mode in ('debug', 'release')]
            contract = dict(schema=1, status='ready', frozen_source=str(base))
            def put(key, value):
                path = base / (key + '.json')
                path.write_text(json.dumps(value))
                contract[key] = dict(path=str(path), sha256=runner.sha(path))
            put('sdk_producer', dict(status='pass', rows=rows))
            put('sdk_readback', dict(status='passed', input_result_sha256=contract['sdk_producer']['sha256'],
                exact_unique_expected_rows=20, original_commands=61,
                rows=[dict(arch=r['arch'], mode=r['mode'], pass_=True) for r in rows]))
            put('source_ready', dict(files={}))
            def terminals():
                for key, target in (('sdk_producer_terminal', 'sdk_producer'), ('sdk_reader_terminal', 'sdk_readback')):
                    put(key, dict(exit_code=0, session_id=123, chunk_id='actual-completion', result_sha256=contract[target]['sha256']))
            terminals()
            handoff = base / 'handoff.json'
            def admit():
                handoff.write_text(json.dumps(contract))
                return runner.admit_handoff(handoff, runner.sha(handoff), sdk, sdk_pin, 'debug')
            admit()
            readback = json.loads((base / 'sdk_readback.json').read_text())
            readback['original_result_sha256'] = readback.pop('input_result_sha256')
            put('sdk_readback', readback)
            terminals()
            with self.assertRaises(ValueError):
                admit()
            readback['input_result_sha256'] = readback.pop('original_result_sha256')
            readback['rows'].pop()
            put('sdk_readback', readback)
            terminals()
            with self.assertRaises(ValueError):
                admit()


if __name__ == '__main__':
    unittest.main()
