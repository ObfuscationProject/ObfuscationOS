"""Host namespace and syscall-failure coverage; no native persistence claim."""
from pathlib import Path
import ctypes
import errno
import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

from test_native_accounts import Account, configured

ROOT = Path(__file__).resolve().parents[2]
SEED = b'OKACCOUNTS 1\nstate unconfigured\n'


def rotation_record(password, salt):
    # Independent wire bytes and hashlib oracle, never the account encoder.
    verifier = hashlib.pbkdf2_hmac('sha256', password, salt, 600000, 32)
    return (b'OKACCOUNTS 1\nstate active\nname admin\nuid 0\ngid 0\nhome /root\n'
            b'kdf pbkdf2-hmac-sha256\nrounds 600000\nsalt ' + salt.hex().encode() +
            b'\nverifier ' + verifier.hex().encode() + b'\n')


PASSWORD_A, PASSWORD_B = b'host-old-password', b'host-new-password'
ACTIVE_A = rotation_record(PASSWORD_A, bytes(range(16)))
ACTIVE_B = rotation_record(PASSWORD_B, bytes(range(16, 32)))


class Store(ctypes.Structure):
    _fields_ = [('directory', ctypes.c_int), ('ready', ctypes.c_int),
                ('recovering', ctypes.c_int), ('observed', Account), ('account', Account)]


class AccountStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='account-store-build-')
        build = Path(cls.build.name)
        (build / 'ok').mkdir()
        shutil.copy2(ROOT / 'sdk/include/ok/storage.h', build / 'ok/storage.h')
        # This account-store seam calls only the replaced persistent-sync
        # boundary. An incomplete inventory type supplies no SDK evidence.
        (build / 'ok/uapi').mkdir()
        (build / 'ok/uapi/syscall.h').write_text('struct ok_mount_info;\n')
        sanitizer = os.environ.get('OK_ACCOUNT_STORE_SANITIZERS', 'undefined')
        if sanitizer not in ('undefined', 'address,undefined'):
            raise ValueError('unsupported hosted account-store sanitizer selection')
        flags = ['cc', '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-U_FORTIFY_SOURCE',
                 '-D_FORTIFY_SOURCE=0', '-fno-builtin', '-O2', '-Wall', '-Wextra',
                 '-Werror', '-fPIC', '-fsanitize=' + sanitizer, '-fno-sanitize-recover=all']
        names = ['open', 'openat', 'fstat', 'fstatat', 'read', 'write', 'close', 'renameat']
        subprocess.run(flags + ['-I' + str(build)] + ['-D' + n + '=account_test_' + n for n in names] +
                       ['-c', str(ROOT / 'apps/login/store.c'), '-o', str(build / 'store.o')], check=True)
        subprocess.run(flags + ['-shared', str(build / 'store.o'),
                       str(ROOT / 'tests/tools/account_store_host.c'),
                       str(ROOT / 'apps/login/accounts.c'), str(ROOT / 'apps/login/password.c'),
                       '-o', str(build / 'store.so')], check=True)
        cls.lib = ctypes.CDLL(str(build / 'store.so'), use_errno=True)
        cls.lib.account_test_root.argtypes = [ctypes.c_char_p]
        cls.lib.account_test_owner_target.argtypes = [ctypes.c_char_p]
        cls.lib.account_test_trace.restype = ctypes.c_char_p
        cls.lib.account_test_fault.argtypes = [ctypes.c_uint, ctypes.c_int]
        cls.lib.account_test_options.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_int,
                                               ctypes.c_int, ctypes.c_int, ctypes.c_int]
        for name in ('open', 'close', 'recover'):
            getattr(cls.lib, 'ok_account_store_' + name).argtypes = [ctypes.POINTER(Store)]
        for name in ('commit', 'rotate'):
            getattr(cls.lib, 'ok_account_store_' + name).argtypes = [ctypes.POINTER(Store), ctypes.POINTER(Account)]
        cls.lib.ok_password_verify.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
        cls.lib.ok_account_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Account)]

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='account-store-root-')
        self.root = Path(self.directory.name)
        self.descriptors_before = len(os.listdir('/proc/self/fd'))
        self.reset()

    def tearDown(self):
        self.directory.cleanup()
        self.assertEqual(len(os.listdir('/proc/self/fd')), self.descriptors_before)

    def reset(self, database=SEED, staging=None):
        for child in self.root.iterdir():
            if child.is_dir() and not child.is_symlink(): shutil.rmtree(child)
            else: child.unlink()
        (self.root / 'etc').mkdir(mode=0o755)
        (self.root / 'root').mkdir(mode=0o700)
        self.db = self.root / 'etc/accounts.db'
        self.db.write_bytes(database)
        self.db.chmod(0o600)
        self.next = self.root / 'etc/.accounts.next'
        if staging is not None:
            self.next.write_bytes(staging)
            self.next.chmod(0o600)
        self.lib.account_test_root(os.fsencode(self.root))

    def account(self, state=b'pending', name=b'admin'):
        return self.parse(configured(state, name))

    def parse(self, raw):
        result = Account()
        self.assertEqual(self.lib.ok_account_parse(raw, len(raw), ctypes.byref(result)), 0)
        return result

    def open(self):
        store = Store()
        self.assertEqual(self.lib.ok_account_store_open(ctypes.byref(store)), 0,
                         self.lib.account_test_trace().decode())
        return store

    def close(self, store):
        self.assertEqual(self.lib.ok_account_store_close(ctypes.byref(store)), 0)
        cleared = Store(directory=-1)
        self.assertEqual(bytes(store), bytes(cleared))

    def namespace(self):
        result = {}
        for path in sorted(self.root.rglob('*')):
            info = path.lstat()
            row = [stat.S_IFMT(info.st_mode), stat.S_IMODE(info.st_mode),
                   info.st_uid, info.st_gid, info.st_nlink]
            if stat.S_ISREG(info.st_mode): row.append(path.read_bytes())
            if stat.S_ISLNK(info.st_mode): row.append(os.readlink(path))
            result[str(path.relative_to(self.root))] = row
        return result

    def assert_active(self, account, raw):
        # Expected fields come from independently generated wire bytes.
        lines = dict(line.split(b' ', 1) for line in raw.splitlines()[1:])
        self.assertEqual(account.state, 2)
        self.assertEqual(ctypes.string_at(ctypes.addressof(account) + Account.name.offset, 32),
                         lines[b'name'].ljust(32, b'\0'))
        self.assertEqual(bytes(account.salt), bytes.fromhex(lines[b'salt'].decode()))
        self.assertEqual(bytes(account.verifier), bytes.fromhex(lines[b'verifier'].decode()))

    def assert_rotation_reopen(self):
        """Inspect the actual A/B namespace without repairing or deleting it."""
        before = self.namespace()
        database = self.db.read_bytes()
        staging = self.next.read_bytes() if self.next.exists() else None
        self.assertIn(database, (ACTIVE_A, ACTIVE_B))
        store = Store()
        result = self.lib.ok_account_store_open(ctypes.byref(store))
        if staging is None:
            self.assertEqual(result, 0)
            self.assertFalse(store.recovering)
            self.assert_active(store.account, database)
            self.assert_active(store.observed, database)
            self.close(store)
        elif staging == ACTIVE_B:
            self.assertEqual(result, 0)
            self.assertTrue(store.recovering)
            self.assert_active(store.account, ACTIVE_B)
            self.assert_active(store.observed, database)
            self.close(store)
        else:
            self.assertEqual(database, ACTIVE_A)
            self.assertEqual(result, -1)
            self.assertEqual(bytes(store), bytes(Store(directory=-1)))
        self.assertEqual(self.namespace(), before)

    def assert_poisoned(self, store, candidate):
        self.assertFalse(store.ready)
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), -1)
        self.assertEqual(self.lib.ok_account_store_recover(ctypes.byref(store)), -1)
        self.assertEqual(self.lib.account_test_trace(), b'')

    def test_ordered_pending_active_publication_and_reopen(self):
        store = self.open()
        pending = self.account()
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(pending)), 0)
        trace = self.lib.account_test_trace().decode().splitlines()
        rename = trace.index('rename:accounts.db')
        self.assertIn('sync:.accounts.next', trace[:rename])
        self.assertIn('close:.accounts.next', trace[:rename])
        self.assertEqual(trace[rename + 1], 'sync:etc')
        self.assertEqual(self.db.read_bytes(), configured(b'pending'))
        self.assertFalse(self.next.exists())
        self.close(store)
        store = self.open()
        active = self.account(b'active')
        self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(active)), 0)
        self.close(store)
        store = self.open()
        self.assertEqual(store.account.state, 2)
        self.assertEqual(self.db.read_bytes(), configured())
        self.assertFalse(store.recovering)
        self.close(store)

    def test_unsupported_sync_and_protected_path_attacks_fail_closed(self):
        def unsupported(): self.lib.account_test_options(0, 0, 1, 0, 0, 0)
        def wrong_owner(): self.lib.account_test_options(0, 0, 0, 1, 0, 0)
        def missing(): self.db.unlink()
        def corrupt(): self.db.write_bytes(b'not an account database\n')
        def permissions(): self.db.chmod(0o644)
        def special(): self.db.chmod(0o4600)
        def home(): (self.root / 'root').chmod(0o755)
        def writable_etc(): (self.root / 'etc').chmod(0o777)
        def symlink(): self.db.rename(self.root / 'actual'); self.db.symlink_to('../actual')
        def hardlink(): os.link(self.db, self.root / 'extra')
        def fifo(): self.db.unlink(); os.mkfifo(self.db, 0o600)
        def directory(): self.db.unlink(); self.db.mkdir(mode=0o600)
        def parent_symlink(): (self.root / 'etc').rename(self.root / 'real'); (self.root / 'etc').symlink_to('real')
        def home_symlink(): (self.root / 'root').rename(self.root / 'home'); (self.root / 'root').symlink_to('home')
        for attack in (unsupported, wrong_owner, missing, corrupt, permissions, special, home,
                       writable_etc, symlink, hardlink, fifo, directory, parent_symlink, home_symlink):
            with self.subTest(attack=attack.__name__):
                self.reset(); attack(); store = Store()
                self.assertEqual(self.lib.ok_account_store_open(ctypes.byref(store)), -1)
                self.assertEqual((store.ready, store.directory), (0, -1))
                self.assertNotIn('write:', self.lib.account_test_trace().decode())

    def test_complete_staging_recovers_chosen_identity(self):
        for original, staged, state in ((SEED, configured(b'pending'), 1),
                (configured(b'pending'), configured(), 2), (configured(), configured(), 2)):
            with self.subTest(state=state):
                self.reset(original, staged)
                store = self.open()
                self.assertTrue(store.recovering)
                self.assertEqual(store.account.state, state)
                self.assertEqual(store.account.name, b'admin')
                self.assertEqual(self.lib.ok_account_store_recover(ctypes.byref(store)), 0)
                self.assertEqual(self.db.read_bytes(), staged)
                self.assertFalse(self.next.exists())
                self.close(store)

    def test_incomplete_conflicting_and_reversing_transactions_refuse(self):
        for original, staged in ((SEED, b''), (SEED, configured()),
                (SEED, configured(b'pending')[:-1]), (configured(), SEED),
                (configured(), configured(b'pending')),
                (configured(b'pending'), configured(name=b'other'))):
            self.reset(original, staged)
            store = Store()
            self.assertEqual(self.lib.ok_account_store_open(ctypes.byref(store)), -1)
            self.assertEqual(self.db.read_bytes(), original)
            self.assertEqual(self.next.read_bytes(), staged)

    def test_stale_writer_and_illegal_transition_cannot_replace_account(self):
        store = self.open()
        active = self.account(b'active')
        self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(active)), -1)
        self.assertFalse(self.next.exists())
        self.db.write_bytes(configured(name=b'other'))
        pending = self.account()
        self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(pending)), -1)
        self.assertFalse(self.next.exists())
        self.close(store)

    def test_noncanonical_in_memory_identity_never_creates_staging(self):
        store = self.open()
        pending = self.account()
        ctypes.c_ubyte.from_address(ctypes.addressof(pending) + Account.name.offset + 6).value = ord('X')
        self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(pending)), -1)
        self.assertEqual(self.db.read_bytes(), SEED)
        self.assertFalse(self.next.exists())
        self.close(store)

    def test_partial_io_and_interrupted_read_write_retry(self):
        pending = self.account()
        for interrupted in (None, 'read:accounts.db', 'write:.accounts.next'):
            self.reset()
            store = self.open()
            self.lib.account_test_options(7, 11, 0, 0, 0, 0)
            self.lib.account_test_fault(0, errno.EIO)
            self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(pending)), 0)
            trace = self.lib.account_test_trace().decode().splitlines()
            self.close(store)
            if interrupted:
                point = trace.index(interrupted) + 1
                self.reset(); store = self.open()
                self.lib.account_test_options(7, 11, 0, 0, 0, 0)
                self.lib.account_test_fault(point, errno.EINTR)
                self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(pending)), 0)
                self.close(store)

    def test_every_commit_syscall_failure_and_after_rename_uncertainty(self):
        pending = self.account()
        store = self.open()
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(pending)), 0)
        operations = self.lib.account_test_trace().decode().splitlines()
        self.close(store)
        for point, operation in enumerate(operations, 1):
            with self.subTest(point=point, operation=operation):
                self.reset(); store = self.open()
                self.lib.account_test_fault(point, errno.EIO)
                result = self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(pending))
                self.assertIn(result, (-1, -2))
                self.assertFalse(store.ready)
                self.lib.account_test_fault(0, errno.EIO)
                self.close(store)
                reopened = Store()
                result = self.lib.ok_account_store_open(ctypes.byref(reopened))
                if not result:
                    self.assertIn(reopened.account.state, (0, 1))
                    if self.next.exists():
                        self.assertEqual(reopened.account.state, 1)
                        self.assertTrue(reopened.recovering)
                    self.close(reopened)
                else:
                    self.assertTrue(self.next.exists())
                    self.assertNotEqual(self.next.read_bytes(), configured(b'pending'))
        for after_effect, zero_write in ((1, 0), (0, 1)):
            self.reset(); store = self.open()
            self.lib.account_test_options(0, 0, 0, 0, after_effect, zero_write)
            self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(pending)), -2)
            self.lib.account_test_options(0, 0, 0, 0, 0, 0)
            self.close(store)
            if after_effect:
                reopened = self.open()
                self.assertEqual(reopened.account.state, 1)
                self.close(reopened)
            else:
                self.assertEqual(self.db.read_bytes(), SEED)
                self.assertEqual(self.next.read_bytes(), b'')

    def test_every_open_failure_releases_descriptors_and_clears_state(self):
        for database, staged in ((SEED, None), (ACTIVE_A, ACTIVE_B)):
            self.reset(database, staged)
            store = self.open()
            operations = self.lib.account_test_trace().decode().splitlines()
            self.close(store)
            for point, operation in enumerate(operations, 1):
                with self.subTest(staged=staged is not None, point=point, operation=operation):
                    self.reset(database, staged)
                    before = len(os.listdir('/proc/self/fd'))
                    namespace = self.namespace()
                    self.lib.account_test_fault(point, errno.EIO)
                    store = Store()
                    # Optional staging ENOENT is an ordinary absence, not an error.
                    self.assertEqual(self.lib.ok_account_store_open(ctypes.byref(store)), -1)
                    self.assertEqual(bytes(store), bytes(Store(directory=-1)))
                    self.assertEqual(len(os.listdir('/proc/self/fd')), before)
                    self.assertEqual(self.namespace(), namespace)

    def test_every_recovery_failure_preserves_the_configured_identity(self):
        self.reset(configured(b'pending'), configured())
        store = self.open()
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_account_store_recover(ctypes.byref(store)), 0)
        operations = self.lib.account_test_trace().decode().splitlines()
        self.close(store)
        for point, operation in enumerate(operations, 1):
            with self.subTest(point=point, operation=operation):
                self.reset(configured(b'pending'), configured())
                store = self.open()
                self.lib.account_test_fault(point, errno.EIO)
                self.assertIn(self.lib.ok_account_store_recover(ctypes.byref(store)), (-1, -2))
                self.assertFalse(store.ready)
                self.lib.account_test_fault(0, errno.EIO)
                self.close(store)
                reopened = self.open()
                self.assertEqual(reopened.account.state, 2)
                self.assertEqual(reopened.account.name, b'admin')
                self.close(reopened)

    def test_rotation_publishes_independent_new_credentials_in_order(self):
        self.reset(ACTIVE_A)
        store = self.open()
        old, new = self.parse(ACTIVE_A), self.parse(ACTIVE_B)
        self.assertEqual(self.lib.ok_password_verify(PASSWORD_A, len(PASSWORD_A), old.salt, old.verifier), 1)
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(new)), 0)
        operations = self.lib.account_test_trace().decode().splitlines()
        rename = operations.index('rename:accounts.db')
        self.assertLess(operations.index('sync:.accounts.next'), operations.index('close:.accounts.next'))
        self.assertIn('read:.accounts.next', operations[:rename])
        self.assertGreater(operations[:rename].count('read:accounts.db'), 1)
        self.assertEqual(operations[rename + 1], 'sync:etc')
        self.assertIn('read:accounts.db', operations[rename + 2:])
        self.assertEqual(self.db.read_bytes(), ACTIVE_B)
        self.assertFalse(self.next.exists())
        self.assert_active(store.account, ACTIVE_B)
        self.assert_active(store.observed, ACTIVE_B)
        self.assertFalse(store.recovering)
        self.close(store)
        reopened = self.open()
        self.assertEqual(self.lib.ok_password_verify(PASSWORD_A, len(PASSWORD_A),
                                                    reopened.account.salt, reopened.account.verifier), 0)
        self.assertEqual(self.lib.ok_password_verify(PASSWORD_B, len(PASSWORD_B),
                                                    reopened.account.salt, reopened.account.verifier), 1)
        self.close(reopened)

    def test_commit_keeps_enrollment_rules_and_cannot_rotate(self):
        for original, next_raw in ((SEED, ACTIVE_B),
                (ACTIVE_A.replace(b'state active', b'state pending'), ACTIVE_B),
                (ACTIVE_A, ACTIVE_B), (ACTIVE_A, ACTIVE_A)):
            with self.subTest(original=original.splitlines()[1], candidate=next_raw.splitlines()[1]):
                self.reset(original)
                store = self.open()
                candidate = self.parse(next_raw)
                self.lib.account_test_fault(0, errno.EIO)
                self.assertEqual(self.lib.ok_account_store_commit(ctypes.byref(store), ctypes.byref(candidate)), -1)
                self.assertEqual(self.lib.account_test_trace(), b'')
                self.assertTrue(store.ready)
                self.assertEqual(self.db.read_bytes(), original)
                self.assertFalse(self.next.exists())
                self.close(store)

    def test_rotate_requires_active_nonrecovering_same_canonical_principal(self):
        cases = [(SEED, None, ACTIVE_B, None),
                 (ACTIVE_A.replace(b'state active', b'state pending'), None, ACTIVE_B, None),
                 (ACTIVE_A, ACTIVE_B, ACTIVE_B, None),
                 (ACTIVE_A, None, SEED, None),
                 (ACTIVE_A, None, ACTIVE_B.replace(b'state active', b'state pending'), None),
                 (ACTIVE_A, None, ACTIVE_B.replace(b'name admin', b'name other'), None),
                 (ACTIVE_A, None, ACTIVE_B, 'name-tail'),
                 (ACTIVE_A, None, ACTIVE_B, 'unobserved-account'),
                 (ACTIVE_A, None, ACTIVE_B, 'not-ready')]
        for original, staged, raw, mutation in cases:
            with self.subTest(state=original.splitlines()[1], staged=staged is not None, mutation=mutation):
                self.reset(original, staged)
                store = self.open()
                candidate = self.parse(raw)
                if mutation == 'name-tail':
                    ctypes.c_ubyte.from_address(ctypes.addressof(candidate) + Account.name.offset + 6).value = 88
                if mutation == 'unobserved-account': store.account.verifier[0] ^= 1
                if mutation == 'not-ready': store.ready = 0
                before = self.namespace()
                self.lib.account_test_fault(0, errno.EIO)
                self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), -1)
                self.assertEqual(self.lib.account_test_trace(), b'')
                self.assertEqual(self.namespace(), before)
                self.close(store)
        candidate = self.parse(ACTIVE_B)
        self.assertEqual(self.lib.ok_account_store_rotate(None, ctypes.byref(candidate)), -1)
        self.reset(ACTIVE_A)
        store = self.open()
        self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), None), -1)
        self.close(store)

    def test_complete_active_stage_selects_B_without_publication_until_caller_authenticates(self):
        self.reset(ACTIVE_A, ACTIVE_B)
        before = self.namespace()
        store = self.open()
        self.assertTrue(store.recovering)
        self.assert_active(store.observed, ACTIVE_A)
        self.assert_active(store.account, ACTIVE_B)
        self.assertEqual(self.lib.ok_password_verify(PASSWORD_A, len(PASSWORD_A),
                                                    store.account.salt, store.account.verifier), 0)
        self.assertEqual(self.namespace(), before)
        self.assertNotIn(b'rename:', self.lib.account_test_trace())
        self.assertEqual(self.lib.ok_password_verify(PASSWORD_B, len(PASSWORD_B),
                                                    store.account.salt, store.account.verifier), 1)
        self.assertEqual(self.lib.ok_account_store_recover(ctypes.byref(store)), 0)
        self.assertEqual(self.db.read_bytes(), ACTIVE_B)
        self.assertFalse(self.next.exists())
        self.assertFalse(store.recovering)
        self.assert_active(store.account, ACTIVE_B)
        self.assert_active(store.observed, ACTIVE_B)
        self.close(store)
        self.assert_rotation_reopen()

    def test_identical_active_stages_keep_existing_idempotent_recovery(self):
        for raw in (ACTIVE_A, ACTIVE_B):
            self.reset(raw, raw)
            store = self.open()
            self.assertTrue(store.recovering)
            self.assert_active(store.account, raw)
            self.assertEqual(self.lib.ok_account_store_recover(ctypes.byref(store)), 0)
            self.assertEqual(self.db.read_bytes(), raw)
            self.assertFalse(self.next.exists())
            self.close(store)

    def test_malformed_wrong_principal_and_reversing_active_stages_hold_closed(self):
        attacks = [b'', ACTIVE_B[:-1], ACTIVE_B + b'\n', b'not an account\n', SEED,
                   ACTIVE_B.replace(b'name admin', b'name other'),
                   ACTIVE_B.replace(b'state active', b'state pending'),
                   ACTIVE_B.replace(b'uid 0', b'uid 1'),
                   ACTIVE_B.replace(b'rounds 600000', b'rounds 599999')]
        attacks.extend(ACTIVE_B[:size] for size in (1, 25, 70, 150))
        for staged in attacks:
            with self.subTest(size=len(staged)):
                self.reset(ACTIVE_A, staged)
                before = self.namespace()
                store = Store()
                self.assertEqual(self.lib.ok_account_store_open(ctypes.byref(store)), -1)
                self.assertEqual(bytes(store), bytes(Store(directory=-1)))
                self.assertEqual(self.namespace(), before)
                self.assertNotIn(b'write:', self.lib.account_test_trace())
                self.assertNotIn(b'rename:', self.lib.account_test_trace())

    def test_active_staged_and_canonical_path_attacks_never_repair_or_discard(self):
        for role in ('database', 'staging'):
            for attack in ('owner', 'mode', 'special', 'symlink', 'hardlink', 'fifo', 'directory', 'corrupt'):
                with self.subTest(role=role, attack=attack):
                    self.reset(ACTIVE_A, ACTIVE_B)
                    path = self.db if role == 'database' else self.next
                    if attack == 'owner': self.lib.account_test_owner_target(os.fsencode(path.name))
                    elif attack == 'mode': path.chmod(0o644)
                    elif attack == 'special': path.chmod(0o4600)
                    elif attack == 'symlink':
                        path.rename(self.root / 'foreign'); path.symlink_to('../foreign')
                    elif attack == 'hardlink': os.link(path, self.root / 'foreign')
                    elif attack in ('fifo', 'directory'):
                        path.unlink()
                        if attack == 'fifo': os.mkfifo(path, 0o600)
                        else: path.mkdir(mode=0o600)
                    elif attack == 'corrupt': path.write_bytes(b'corrupt\n')
                    before = self.namespace()
                    store = Store()
                    self.assertEqual(self.lib.ok_account_store_open(ctypes.byref(store)), -1)
                    self.assertEqual(bytes(store), bytes(Store(directory=-1)))
                    self.assertEqual(self.namespace(), before)
        self.reset(ACTIVE_A, ACTIVE_B)
        self.db.unlink()
        before = self.namespace()
        store = Store()
        self.assertEqual(self.lib.ok_account_store_open(ctypes.byref(store)), -1)
        self.assertEqual(self.namespace(), before)

    def test_new_rotation_stage_wrong_ownership_is_uncertain_and_not_written(self):
        self.reset(ACTIVE_A)
        store = self.open()
        candidate = self.parse(ACTIVE_B)
        self.lib.account_test_owner_target(b'.accounts.next')
        self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), -2)
        self.assertEqual(self.db.read_bytes(), ACTIVE_A)
        self.assertEqual(self.next.read_bytes(), b'')
        self.assertNotIn(b'write:', self.lib.account_test_trace())
        self.assert_poisoned(store, candidate)
        self.close(store)
        self.lib.account_test_options(0, 0, 0, 0, 0, 0)
        self.assert_rotation_reopen()

    def test_rotation_refuses_stale_database_conflicting_stage_and_unsupported_sync(self):
        for attack in ('stale', 'owner', 'mode', 'directory-mode', 'unsupported',
                       'stage-file', 'stage-symlink', 'stage-fifo', 'stage-directory'):
            with self.subTest(attack=attack):
                self.reset(ACTIVE_A)
                store = self.open()
                candidate = self.parse(ACTIVE_B)
                if attack == 'stale': self.db.write_bytes(ACTIVE_B)
                elif attack == 'owner': self.lib.account_test_options(0, 0, 0, 1, 0, 0)
                elif attack == 'mode': self.db.chmod(0o644)
                elif attack == 'directory-mode': (self.root / 'etc').chmod(0o777)
                elif attack == 'unsupported': self.lib.account_test_options(0, 0, 1, 0, 0, 0)
                elif attack == 'stage-file': self.next.write_bytes(ACTIVE_A); self.next.chmod(0o600)
                elif attack == 'stage-symlink': self.next.symlink_to('accounts.db')
                elif attack == 'stage-fifo': os.mkfifo(self.next, 0o600)
                elif attack == 'stage-directory': self.next.mkdir(mode=0o600)
                before = self.namespace()
                self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), -1)
                self.assertFalse(store.ready)
                self.assertEqual(self.namespace(), before)
                self.close(store)

    def test_every_rotation_failure_reopens_exact_A_B_or_closed_partial_stage(self):
        candidate = self.parse(ACTIVE_B)
        self.reset(ACTIVE_A)
        store = self.open()
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), 0)
        operations = self.lib.account_test_trace().decode().splitlines()
        self.close(store)
        for point, operation in enumerate(operations, 1):
            with self.subTest(point=point, operation=operation):
                self.reset(ACTIVE_A)
                store = self.open()
                self.lib.account_test_fault(point, errno.EIO)
                self.assertIn(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), (-1, -2))
                self.assert_poisoned(store, candidate)
                self.close(store)
                self.assert_rotation_reopen()

    def test_short_interrupted_and_zero_rotation_writes_preserve_reopen_table(self):
        candidate = self.parse(ACTIVE_B)
        for interrupted in (None, 'read:accounts.db', 'write:.accounts.next', 'read:.accounts.next'):
            self.reset(ACTIVE_A)
            store = self.open()
            self.lib.account_test_options(7, 11, 0, 0, 0, 0)
            self.lib.account_test_fault(0, errno.EIO)
            self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), 0)
            operations = self.lib.account_test_trace().decode().splitlines()
            self.close(store)
            if interrupted:
                self.reset(ACTIVE_A)
                store = self.open()
                self.lib.account_test_options(7, 11, 0, 0, 0, 0)
                self.lib.account_test_fault(operations.index(interrupted) + 1, errno.EINTR)
                self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), 0)
                self.close(store)
                self.assert_rotation_reopen()
        for after_effect, zero_write, partial in ((1, 0, False), (0, 1, False), (0, 0, True)):
            self.reset(ACTIVE_A)
            store = self.open()
            self.lib.account_test_options(0, 11 if partial else 0, 0, 0, after_effect, zero_write)
            if partial:
                # The second actual short write fails, leaving independent B's prefix.
                self.lib.account_test_fault(0, errno.EIO)
                self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), 0)
                operations = self.lib.account_test_trace().decode().splitlines()
                point = [i for i, op in enumerate(operations, 1) if op == 'write:.accounts.next'][1]
                self.close(store)
                self.reset(ACTIVE_A)
                store = self.open()
                self.lib.account_test_options(0, 11, 0, 0, 0, 0)
                self.lib.account_test_fault(point, errno.EIO)
            self.assertEqual(self.lib.ok_account_store_rotate(ctypes.byref(store), ctypes.byref(candidate)), -2)
            self.assert_poisoned(store, candidate)
            self.close(store)
            self.lib.account_test_options(0, 0, 0, 0, 0, 0)
            if after_effect:
                self.assertEqual(self.db.read_bytes(), ACTIVE_B)
                self.assertFalse(self.next.exists())
            else:
                self.assertEqual(self.db.read_bytes(), ACTIVE_A)
                self.assertEqual(self.next.read_bytes(), ACTIVE_B[:11] if partial else b'')
            self.assert_rotation_reopen()

    def test_every_active_recovery_failure_keeps_B_selected_or_already_published(self):
        self.reset(ACTIVE_A, ACTIVE_B)
        store = self.open()
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_account_store_recover(ctypes.byref(store)), 0)
        operations = self.lib.account_test_trace().decode().splitlines()
        self.close(store)
        candidate = self.parse(ACTIVE_B)
        for point, operation in enumerate(operations, 1):
            with self.subTest(point=point, operation=operation):
                self.reset(ACTIVE_A, ACTIVE_B)
                store = self.open()
                self.lib.account_test_fault(point, errno.EIO)
                self.assertIn(self.lib.ok_account_store_recover(ctypes.byref(store)), (-1, -2))
                self.assert_poisoned(store, candidate)
                self.close(store)
                self.assert_rotation_reopen()
                reopened = self.open()
                self.assert_active(reopened.account, ACTIVE_B)
                if reopened.recovering:
                    self.assertEqual(self.lib.ok_account_store_recover(ctypes.byref(reopened)), 0)
                self.assertEqual(self.db.read_bytes(), ACTIVE_B)
                self.assertFalse(self.next.exists())
                self.close(reopened)
        self.reset(ACTIVE_A, ACTIVE_B)
        store = self.open()
        self.lib.account_test_options(0, 0, 0, 0, 1, 0)
        self.assertEqual(self.lib.ok_account_store_recover(ctypes.byref(store)), -2)
        self.assert_poisoned(store, candidate)
        self.close(store)
        self.lib.account_test_options(0, 0, 0, 0, 0, 0)
        self.assertEqual(self.db.read_bytes(), ACTIVE_B)
        self.assertFalse(self.next.exists())
        self.assert_rotation_reopen()

    def test_persistent_sync_wrapper_zeros_reserved_words_and_preserves_errors(self):
        # This isolated UAPI stub checks marshalling only. Separate SDK contract
        # tests validate exported headers/capability; this is no SDK substitute.
        with tempfile.TemporaryDirectory(prefix='storage-wrapper-host-') as directory:
            build = Path(directory)
            (build / 'ok/uapi').mkdir(parents=True)
            (build / 'ok/uapi/syscall.h').write_text(
                '#ifndef TEST_STORAGE_UAPI\n#define TEST_STORAGE_UAPI\n'
                '#define OK_NATIVE_PERSISTENT_SYNC_VERSION 1\n'
                '#define OK_SYS_SYNC_PERSISTENT 1031ULL\n'
                '#include <stdint.h>\n'
                '#define OK_NATIVE_MOUNT_INFO_VERSION 1\n#define OK_SYS_MOUNT_INFO 1034ULL\n'
                'struct ok_mount_info { uint32_t version, size, generation, slot, capacity, state, parent_id, path_length; char path[256]; };\n'
                '#define OK_EOPNOTSUPP 95\n#define OK_EBADF 9\n#define OK_EIO 5\n'
                '#define OK_EFAULT 14\n#define OK_ENOSYS 38\n#endif\n')
            binary = build / 'wrapper'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(build),
                '-I', str(ROOT / 'sdk/include'), '-I', str(ROOT / 'lib/okcrt/include'),
                str(ROOT / 'lib/okcrt/src/storage.c'),
                str(ROOT / 'tests/native_storage_wrapper_tests.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=8)


if __name__ == '__main__':
    unittest.main()
