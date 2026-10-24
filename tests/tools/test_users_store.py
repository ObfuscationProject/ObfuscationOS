"""Actual registry-store source with host namespace/fault seams, not native I/O."""
from pathlib import Path
import ctypes
import errno
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest

from test_native_user_registry import ROOT, User, Users, bind, flags, record, registry
from test_native_accounts import Account

EMPTY = registry()
ALICE = record()
BOB = record(b'bob', 1002)
ROTATED = record(b'alice', salt=bytes(range(16, 32)), verifier=bytes(range(32, 64)))
BASE = registry(ALICE, BOB)
ADDED = registry(ALICE, record(b'carol', 1001), BOB)
CHANGED = registry(ROTATED, BOB)


class Store(ctypes.Structure):
    _fields_ = [('directory', ctypes.c_int), ('ready', ctypes.c_int),
        ('recovering', ctypes.c_int), ('observed_present', ctypes.c_int),
        ('recovery_kind', ctypes.c_int), ('change_index', ctypes.c_uint32),
        ('administrator', ctypes.c_char * 32), ('observed', Users), ('users', Users),
        ('work', Users), ('bytes', ctypes.c_ubyte * 4097)]


class UsersStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='users-store-host-build-')
        build = Path(cls.build.name)
        (build / 'ok/uapi').mkdir(parents=True)
        shutil.copy2(ROOT / 'sdk/include/ok/storage.h', build / 'ok/storage.h')
        (build / 'ok/uapi/syscall.h').write_text('struct ok_mount_info;\n')
        names = ['open', 'openat', 'fstat', 'fstatat', 'read', 'write', 'close', 'renameat']
        subprocess.run(flags() + ['-I' + str(build)] + ['-D' + n + '=account_test_' + n for n in names] +
            ['-c', str(ROOT / 'apps/login/users_store.c'), '-o', str(build / 'store.o')], check=True)
        # Reuse the existing syscall seam. Its legacy account_test_* names do
        # not replace parsing, transitions, paths or registry publication.
        subprocess.run(flags() + ['-shared', str(build / 'store.o'),
            str(ROOT / 'tests/tools/account_store_host.c'), str(ROOT / 'apps/login/users.c'),
            str(ROOT / 'apps/login/accounts.c'), str(ROOT / 'apps/login/password.c'),
            '-o', str(build / 'users-store.so')], check=True)
        cls.lib = ctypes.CDLL(str(build / 'users-store.so'), use_errno=True)
        bind(cls.lib)
        cls.lib.account_test_root.argtypes = [ctypes.c_char_p]
        cls.lib.account_test_owner_target.argtypes = [ctypes.c_char_p]
        cls.lib.account_test_trace.restype = ctypes.c_char_p
        cls.lib.account_test_fault.argtypes = [ctypes.c_uint, ctypes.c_int]
        cls.lib.account_test_options.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int]
        cls.lib.ok_users_store_open.argtypes = [ctypes.POINTER(Store), ctypes.c_char_p]
        for name in ('close', 'recover'):
            getattr(cls.lib, 'ok_users_store_' + name).argtypes = [ctypes.POINTER(Store)]
        for name in ('add', 'stage_add', 'rotate'):
            getattr(cls.lib, 'ok_users_store_' + name).argtypes = [ctypes.POINTER(Store), ctypes.POINTER(User)]
        cls.lib.ok_account_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Account)]
        cls.lib.ok_password_verify.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
            ctypes.c_void_p, ctypes.c_void_p]

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='users-store-host-root-')
        self.root = Path(self.directory.name)
        self.descriptors = len(os.listdir('/proc/self/fd'))
        self.reset()

    def tearDown(self):
        self.directory.cleanup()
        self.assertEqual(len(os.listdir('/proc/self/fd')), self.descriptors)

    def reset(self, database=None, staging=None):
        for path in self.root.iterdir():
            if path.is_dir() and not path.is_symlink(): shutil.rmtree(path)
            else: path.unlink()
        (self.root / 'etc').mkdir(mode=0o755)
        self.db = self.root / 'etc/users.db'
        self.next = self.root / 'etc/.users.next'
        for path, data in ((self.db, database), (self.next, staging)):
            if data is not None:
                path.write_bytes(data)
                path.chmod(0o600)
        self.lib.account_test_root(os.fsencode(self.root))

    def open(self, expected=0):
        store = Store(directory=-1)
        self.assertEqual(self.lib.ok_users_store_open(ctypes.byref(store), b'admin'), expected)
        if expected: self.assertEqual(store.directory, -1)
        return store

    def close(self, store):
        self.lib.account_test_fault(0, errno.EIO)
        self.lib.account_test_options(0, 0, 0, 0, 0, 0)
        self.assertEqual(self.lib.ok_users_store_close(ctypes.byref(store)), 0)
        self.assertEqual(store.directory, -1)
        self.assertEqual(bytes(store)[ctypes.sizeof(ctypes.c_int):], b'\0' * (ctypes.sizeof(store)-4))

    def parse(self, wire):
        users = Users()
        self.assertEqual(self.lib.ok_users_parse(wire, len(wire), ctypes.byref(users)), 0)
        return users

    def user(self, row):
        return self.parse(registry(row)).entries[0]

    def wire(self, users):
        output = ctypes.create_string_buffer(4096)
        size = self.lib.ok_users_encode(ctypes.byref(users), output, 4096)
        self.assertGreater(size, 0)
        return output.raw[:size]

    def test_missing_both_is_empty_without_implicit_creation(self):
        store = self.open()
        self.assertEqual((store.ready, store.recovering, store.observed_present), (1, 0, 0))
        self.assertEqual(self.wire(store.users), EMPTY)
        self.assertFalse(self.db.exists())
        self.assertFalse(self.next.exists())
        self.close(store)
        self.reset(EMPTY)
        store = self.open()
        self.assertEqual(store.observed_present, 1)
        self.close(store)

    def test_every_open_syscall_failure_is_closed_and_does_not_publish(self):
        for database, staging in ((None, None), (BASE, None), (BASE, CHANGED)):
            self.reset(database, staging)
            store = self.open()
            operations = self.lib.account_test_trace().decode().splitlines()
            self.close(store)
            for point, event in enumerate(operations, 1):
                with self.subTest(database=database, staging=staging, point=point, event=event):
                    self.reset(database, staging)
                    self.lib.account_test_fault(point, errno.EIO)
                    self.open(-1)
                    self.assertEqual(self.db.read_bytes() if self.db.exists() else None, database)
                    self.assertEqual(self.next.read_bytes() if self.next.exists() else None, staging)

    def test_admitted_administrator_name_excluded_for_open_and_mutations(self):
        self.reset(BASE)
        store = Store(directory=-1)
        self.assertEqual(self.lib.ok_users_store_open(ctypes.byref(store), b'alice'), -1)
        self.assertEqual(store.directory, -1)
        self.reset()
        self.assertEqual(self.lib.ok_users_store_open(ctypes.byref(store), b'alice'), 0)
        user = self.user(ALICE)
        self.assertEqual(self.lib.ok_users_store_add(ctypes.byref(store), ctypes.byref(user)), -1)
        self.assertEqual(store.ready, 1)
        self.assertFalse(self.db.exists())
        self.assertFalse(self.next.exists())
        self.close(store)

    def test_sixteen_users_survive_sorted_insert_and_selected_rotation(self):
        store = self.open()
        rows = []
        for i in reversed(range(16)):
            row = record(('user' + str(i)).encode(), 1000+i)
            user = self.user(row)
            self.assertEqual(self.lib.ok_users_store_add(ctypes.byref(store), ctypes.byref(user)), 0)
            rows.insert(0, row)
            self.assertEqual(self.db.read_bytes(), registry(*rows))
            self.assertEqual(self.wire(store.users), registry(*rows))
            self.assertFalse(self.next.exists())
        user = self.user(record(b'user7', 1007, salt=b'S'*16, verifier=b'V'*32))
        self.assertEqual(self.lib.ok_users_store_rotate(ctypes.byref(store), ctypes.byref(user)), 0)
        rows[7] = record(b'user7', 1007, salt=b'S'*16, verifier=b'V'*32)
        self.assertEqual(self.db.read_bytes(), registry(*rows))
        extra = self.user(record(b'extra', 2000))
        self.assertEqual(self.lib.ok_users_store_add(ctypes.byref(store), ctypes.byref(extra)), -1)
        self.assertEqual(ctypes.get_errno(), errno.ENOSPC)
        self.assertEqual(store.ready, 1)
        self.close(store)
        reopened = self.open()
        self.assertEqual(self.wire(reopened.users), registry(*rows))
        self.close(reopened)

    def test_add_rotation_refuse_admin_duplicates_identity_changes_and_noop(self):
        self.reset(BASE)
        store = self.open()
        for action, row in [('add', record(b'admin', 1001)), ('add', record(b'alice', 1001)),
            ('add', record(b'carol', 1000)), ('rotate', record(b'alice', 1001)),
            ('rotate', record(b'dave', 1000)), ('rotate', ALICE)]:
            user = self.user(row)
            before = bytes(store.users)
            self.lib.account_test_fault(0, errno.EIO)
            self.assertEqual(getattr(self.lib, 'ok_users_store_' + action)(ctypes.byref(store), ctypes.byref(user)), -1)
            self.assertEqual(bytes(store.users), before)
            self.assertEqual(store.ready, 1)
            self.assertEqual(self.lib.account_test_trace(), b'')
            self.assertEqual(self.db.read_bytes(), BASE)
        self.close(store)

    def test_staging_selects_one_add_or_rotation_without_publishing_on_open(self):
        for before, after, kind, index in [(None, registry(ALICE), 1, 0),
            (EMPTY, registry(ALICE), 1, 0), (BASE, ADDED, 1, 1), (BASE, CHANGED, 2, 0)]:
            self.reset(before, after)
            store = self.open()
            self.assertEqual((store.recovering, store.recovery_kind, store.change_index), (1, kind, index))
            self.assertEqual(self.wire(store.users), after)
            self.assertEqual(self.wire(store.observed), EMPTY if before is None else before)
            self.assertEqual(self.next.read_bytes(), after)
            self.assertNotIn(b'rename:', self.lib.account_test_trace())
            # This hosted caller stands in for authentication; the store API
            # deliberately has no password prompt or authentication authority.
            self.assertEqual(self.lib.ok_users_store_recover(ctypes.byref(store)), 0)
            self.assertEqual((store.recovering, store.recovery_kind), (0, 0))
            self.assertEqual(self.db.read_bytes(), after)
            self.assertFalse(self.next.exists())
            self.close(store)

    def test_stage_add_is_durable_selection_without_database_publication(self):
        for before, after, row, index in [(None, registry(ALICE), ALICE, 0),
            (EMPTY, registry(ALICE), ALICE, 0), (BASE, ADDED, record(b'carol', 1001), 1)]:
            with self.subTest(before=before):
                self.reset(before)
                original_inode = self.db.stat().st_ino if self.db.exists() else None
                store = self.open()
                user = self.user(row)
                self.lib.account_test_fault(0, errno.EIO)
                self.assertEqual(self.lib.ok_users_store_stage_add(ctypes.byref(store), ctypes.byref(user)), 0)
                operations = self.lib.account_test_trace().decode().splitlines()
                self.assertNotIn('rename:users.db', operations)
                write = operations.index('write:.users.next')
                sync = operations.index('sync:.users.next', write)
                close = operations.index('close:.users.next', sync)
                self.assertEqual(operations[close + 1], 'sync:etc')
                self.assertEqual((store.ready, store.recovering, store.recovery_kind, store.change_index), (1, 1, 1, index))
                self.assertEqual(self.wire(store.observed), EMPTY if before is None else before)
                self.assertEqual(self.wire(store.users), after)
                self.assertEqual(bytes(store.work), b'\0' * ctypes.sizeof(Users))
                self.assertEqual(bytes(store.bytes), b'\0' * 4097)
                self.assertEqual(self.db.read_bytes() if self.db.exists() else None, before)
                self.assertEqual(self.db.stat().st_ino if self.db.exists() else None, original_inode)
                self.assertEqual(self.next.read_bytes(), after)
                staged_inode = self.next.stat().st_ino
                # A selected transaction cannot be replaced by another add,
                # another staging call or a password rotation on this handle.
                for method in ('add', 'stage_add', 'rotate'):
                    self.lib.account_test_fault(0, errno.EIO)
                    self.assertEqual(getattr(self.lib, 'ok_users_store_' + method)(ctypes.byref(store), ctypes.byref(user)), -1)
                    self.assertEqual(self.lib.account_test_trace(), b'')
                    self.assertEqual((store.ready, store.recovering), (1, 1))
                    self.assertEqual(self.next.read_bytes(), after)
                self.close(store)
                self.assertEqual(self.db.read_bytes() if self.db.exists() else None, before)
                self.assertEqual(self.next.stat().st_ino, staged_inode)
                reopened = self.open()
                self.assertEqual((reopened.ready, reopened.recovering, reopened.recovery_kind, reopened.change_index), (1, 1, 1, index))
                self.assertEqual(self.wire(reopened.users), after)
                self.assertEqual(self.wire(reopened.observed), EMPTY if before is None else before)
                self.assertNotIn(b'rename:', self.lib.account_test_trace())
                self.assertEqual(self.lib.ok_users_store_recover(ctypes.byref(reopened)), 0)
                self.assertEqual(self.db.read_bytes(), after)
                self.assertEqual(self.db.stat().st_ino, staged_inode)
                self.assertFalse(self.next.exists())
                self.close(reopened)

    def test_staged_add_survives_reopen_until_caller_authenticates_administrator(self):
        # Actual legacy parser/password verification guards the hosted caller's
        # recover call. The store itself has no authentication authority, and
        # this control does not substitute for native main/home integration.
        password, salt = b'local-administrator-secret', bytes(range(32, 48))
        verifier = hashlib.pbkdf2_hmac('sha256', password, salt, 600000, 32)
        account_bytes = (b'OKACCOUNTS 1\nstate active\nname admin\nuid 0\ngid 0\nhome /root\n'
            b'kdf pbkdf2-hmac-sha256\nrounds 600000\nsalt ' + salt.hex().encode() +
            b'\nverifier ' + verifier.hex().encode() + b'\n')
        administrator = Account()
        self.assertEqual(self.lib.ok_account_parse(account_bytes, len(account_bytes), ctypes.byref(administrator)), 0)
        self.reset(BASE)
        store = self.open()
        user = self.user(record(b'carol', 1001))
        self.assertEqual(self.lib.ok_users_store_stage_add(ctypes.byref(store), ctypes.byref(user)), 0)
        inode = self.next.stat().st_ino
        self.close(store)
        for attempt in (b'wrong', b'', password):
            store = self.open()
            try:
                self.assertEqual((store.recovering, store.recovery_kind, store.change_index), (1, 1, 1))
                self.lib.account_test_fault(0, errno.EIO)
                # The API rejects empty password sizes. Login substitutes a
                # bounded invalid candidate so every complete attempt pays KDF.
                candidate = attempt or b'\0'
                authenticated = self.lib.ok_password_verify(candidate, len(candidate), administrator.salt, administrator.verifier)
                self.assertEqual(authenticated, int(attempt == password))
                if authenticated == 1:
                    self.assertEqual(self.lib.ok_users_store_recover(ctypes.byref(store)), 0)
                    self.assertEqual(self.db.read_bytes(), ADDED)
                    self.assertEqual(self.db.stat().st_ino, inode)
                    self.assertFalse(self.next.exists())
                else:
                    self.assertEqual(self.lib.account_test_trace(), b'')
                    self.assertEqual(self.db.read_bytes(), BASE)
                    self.assertEqual(self.next.read_bytes(), ADDED)
                    self.assertEqual(self.next.stat().st_ino, inode)
            finally:
                self.close(store)

    def test_stage_add_same_handle_can_publish_after_separate_caller_work(self):
        self.reset(BASE)
        store = self.open()
        user = self.user(record(b'carol', 1001))
        self.lib.account_test_options(7, 11, 0, 0, 0, 0)
        self.assertEqual(self.lib.ok_users_store_stage_add(ctypes.byref(store), ctypes.byref(user)), 0)
        self.assertEqual(self.db.read_bytes(), BASE)
        self.assertEqual(self.next.read_bytes(), ADDED)
        inode = self.next.stat().st_ino
        # Home completion belongs to the separate caller. No home operations
        # are substituted or claimed by this registry-only seam.
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_users_store_recover(ctypes.byref(store)), 0)
        self.assertEqual((store.ready, store.recovering, store.recovery_kind), (1, 0, 0))
        self.assertEqual(self.wire(store.observed), ADDED)
        self.assertEqual(self.db.read_bytes(), ADDED)
        self.assertEqual(self.db.stat().st_ino, inode)
        self.assertFalse(self.next.exists())
        self.assertIn(b'rename:users.db\n', self.lib.account_test_trace())
        self.close(store)

    def test_every_stage_add_syscall_fault_leaves_predecessor_and_retained_staging(self):
        for before, after, row in [(None, registry(ALICE), ALICE),
            (BASE, ADDED, record(b'carol', 1001))]:
            self.reset(before)
            store = self.open()
            user = self.user(row)
            self.lib.account_test_fault(0, errno.EIO)
            self.assertEqual(self.lib.ok_users_store_stage_add(ctypes.byref(store), ctypes.byref(user)), 0)
            operations = self.lib.account_test_trace().decode().splitlines()
            self.assertNotIn('rename:users.db', operations)
            self.close(store)
            for point, event in enumerate(operations, 1):
                with self.subTest(before=before, point=point, event=event):
                    self.reset(before)
                    store = self.open()
                    self.lib.account_test_fault(point, errno.EIO)
                    result = self.lib.ok_users_store_stage_add(ctypes.byref(store), ctypes.byref(user))
                    self.assertEqual(result, -2 if self.next.exists() else -1)
                    self.assertEqual(store.ready, 0)
                    self.assertEqual(self.db.read_bytes() if self.db.exists() else None, before)
                    retained = self.next.read_bytes() if self.next.exists() else None
                    self.assertNotIn(b'rename:', self.lib.account_test_trace())
                    self.assertEqual(self.lib.ok_users_store_stage_add(ctypes.byref(store), ctypes.byref(user)), -1)
                    self.assertEqual(self.lib.ok_users_store_recover(ctypes.byref(store)), -1)
                    self.close(store)
                    self.assertEqual(self.next.read_bytes() if self.next.exists() else None, retained)
                    self.assert_reopen_state(before, after)

    def test_staged_add_recovery_rechecks_predecessor_and_exact_selected_successor(self):
        for issue in ('database', 'missing-database', 'staging', 'partial-staging', 'missing-staging', 'staging-mode'):
            with self.subTest(issue=issue):
                self.reset(BASE)
                store = self.open()
                user = self.user(record(b'carol', 1001))
                self.assertEqual(self.lib.ok_users_store_stage_add(ctypes.byref(store), ctypes.byref(user)), 0)
                self.close(store)
                store = self.open()
                if issue == 'database': self.db.write_bytes(EMPTY)
                elif issue == 'missing-database': self.db.unlink()
                elif issue == 'staging': self.next.write_bytes(CHANGED)
                elif issue == 'partial-staging': self.next.write_bytes(ADDED[:40])
                elif issue == 'missing-staging': self.next.unlink()
                else: self.next.chmod(0o644)
                database = self.db.read_bytes() if self.db.exists() else None
                staging = self.next.read_bytes() if self.next.exists() else None
                self.lib.account_test_fault(0, errno.EIO)
                self.assertIn(self.lib.ok_users_store_recover(ctypes.byref(store)), (-1, -2))
                self.assertEqual(store.ready, 0)
                self.assertEqual(self.db.read_bytes() if self.db.exists() else None, database)
                self.assertEqual(self.next.read_bytes() if self.next.exists() else None, staging)
                self.assertNotIn(b'rename:', self.lib.account_test_trace())
                self.close(store)

    def test_illegal_staging_never_becomes_empty_or_discards_unrelated_records(self):
        illegal = [EMPTY, BASE, registry(ALICE), registry(ALICE, BOB, record(b'carol', 1003), record(b'dave', 1004)),
            registry(ROTATED, record(b'bob', 1002, salt=b'Z'*16)),
            registry(record(b'other', 1000), BOB), registry(record(b'alice', 1001), BOB),
            registry(ALICE, record(b'admin', 1001), BOB)]
        for staging in illegal:
            with self.subTest(staging=staging):
                self.reset(BASE, staging)
                self.open(-1)
                self.assertEqual(self.db.read_bytes(), BASE)
                self.assertEqual(self.next.read_bytes(), staging)
        self.reset(None, registry(ALICE, BOB))
        self.open(-1)

    def test_malformed_metadata_symlink_fifo_and_unsupported_sync_fail_closed(self):
        for role in ('database', 'staging'):
            for issue in ('truncated', 'oversized', 'empty', 'mode', 'owner', 'hardlink', 'symlink', 'fifo'):
                with self.subTest(role=role, issue=issue):
                    self.reset(BASE, CHANGED if role == 'staging' else None)
                    path = self.db if role == 'database' else self.next
                    if issue == 'truncated': path.write_bytes(b'OKUSERS 1\n')
                    elif issue == 'oversized': path.write_bytes(b'X'*4097)
                    elif issue == 'empty': path.write_bytes(b'')
                    elif issue == 'mode': path.chmod(0o644)
                    elif issue == 'owner': self.lib.account_test_owner_target(os.fsencode(path.name))
                    elif issue == 'hardlink': os.link(path, path.with_name('other'))
                    elif issue == 'symlink':
                        path.rename(path.with_name('other')); path.symlink_to('other')
                    else:
                        path.unlink(); os.mkfifo(path, 0o600)
                    self.open(-1)
        self.reset(BASE)
        self.lib.account_test_options(0, 0, 1, 0, 0, 0)
        self.open(-1)

    def test_complete_staging_sync_and_directory_sync_precede_rename(self):
        self.reset(BASE)
        store = self.open()
        user = self.user(record(b'carol', 1001))
        self.lib.account_test_fault(0, errno.EIO)
        self.assertEqual(self.lib.ok_users_store_add(ctypes.byref(store), ctypes.byref(user)), 0)
        operations = self.lib.account_test_trace().decode().splitlines()
        written = operations.index('write:.users.next')
        synced = operations.index('sync:.users.next', written)
        closed = operations.index('close:.users.next', synced)
        directory_synced = operations.index('sync:etc', closed)
        renamed = operations.index('rename:users.db')
        self.assertLess(directory_synced, renamed)
        self.assertEqual(operations[renamed + 1], 'sync:etc')
        self.assertEqual(self.db.read_bytes(), ADDED)
        self.close(store)

    def assert_reopen_state(self, before, after):
        self.lib.account_test_fault(0, errno.EIO)
        self.lib.account_test_options(0, 0, 0, 0, 0, 0)
        database = self.db.read_bytes() if self.db.exists() else None
        staging = self.next.read_bytes() if self.next.exists() else None
        self.assertIn(database, (before, after))
        if staging is not None and staging != after:
            self.assertTrue(after.startswith(staging))
            self.open(-1)
            self.assertEqual(self.next.read_bytes(), staging)
            return
        reopened = self.open()
        self.assertEqual(self.wire(reopened.users), after if staging is not None or database == after else EMPTY if before is None else before)
        if reopened.recovering:
            self.assertEqual(self.lib.ok_users_store_recover(ctypes.byref(reopened)), 0)
            self.assertEqual(self.db.read_bytes(), after)
        self.close(reopened)

    def test_every_add_and_rotation_syscall_fault_is_retained_and_cannot_retry(self):
        for operation, before, after, row in [('add', BASE, ADDED, record(b'carol', 1001)),
            ('add', None, registry(ALICE), ALICE), ('rotate', BASE, CHANGED, ROTATED)]:
            self.reset(before)
            store = self.open()
            user = self.user(row)
            self.lib.account_test_fault(0, errno.EIO)
            method = getattr(self.lib, 'ok_users_store_' + operation)
            self.assertEqual(method(ctypes.byref(store), ctypes.byref(user)), 0)
            operations = self.lib.account_test_trace().decode().splitlines()
            self.close(store)
            for point, event in enumerate(operations, 1):
                with self.subTest(operation=operation, point=point, event=event):
                    self.reset(before)
                    store = self.open()
                    self.lib.account_test_fault(point, errno.EIO)
                    self.assertIn(method(ctypes.byref(store), ctypes.byref(user)), (-1, -2))
                    self.assertEqual(store.ready, 0)
                    self.assertEqual(method(ctypes.byref(store), ctypes.byref(user)), -1)
                    self.assertEqual(self.lib.ok_users_store_recover(ctypes.byref(store)), -1)
                    self.close(store)
                    self.assert_reopen_state(before, after)

    def test_every_recovery_syscall_fault_never_loses_selected_complete_successor(self):
        for after in (ADDED, CHANGED):
            self.reset(BASE, after)
            store = self.open()
            self.lib.account_test_fault(0, errno.EIO)
            self.assertEqual(self.lib.ok_users_store_recover(ctypes.byref(store)), 0)
            operations = self.lib.account_test_trace().decode().splitlines()
            self.close(store)
            for point, event in enumerate(operations, 1):
                with self.subTest(after=after, point=point, event=event):
                    self.reset(BASE, after)
                    store = self.open()
                    self.lib.account_test_fault(point, errno.EIO)
                    self.assertIn(self.lib.ok_users_store_recover(ctypes.byref(store)), (-1, -2))
                    self.assertEqual(store.ready, 0)
                    self.close(store)
                    self.assert_reopen_state(BASE, after)

    def test_short_io_eintr_zero_write_and_rename_after_effect(self):
        for failure_event in (None, 'read:users.db', 'write:.users.next'):
            self.reset(BASE)
            store = self.open()
            user = self.user(ROTATED)
            self.lib.account_test_options(7, 11, 0, 0, 0, 0)
            self.lib.account_test_fault(0, errno.EIO)
            self.assertEqual(self.lib.ok_users_store_rotate(ctypes.byref(store), ctypes.byref(user)), 0)
            operations = self.lib.account_test_trace().decode().splitlines()
            self.close(store)
            if failure_event:
                self.reset(BASE)
                store = self.open()
                self.lib.account_test_options(7, 11, 0, 0, 0, 0)
                self.lib.account_test_fault(operations.index(failure_event) + 1, errno.EINTR)
                self.assertEqual(self.lib.ok_users_store_rotate(ctypes.byref(store), ctypes.byref(user)), 0)
                self.close(store)
            self.assert_reopen_state(BASE, CHANGED)
        for after_effect, zero in ((1, 0), (0, 1)):
            self.reset(BASE)
            store = self.open()
            user = self.user(ROTATED)
            self.lib.account_test_options(0, 0, 0, 0, after_effect, zero)
            self.assertEqual(self.lib.ok_users_store_rotate(ctypes.byref(store), ctypes.byref(user)), -2)
            self.assertEqual(store.ready, 0)
            self.close(store)
            self.assert_reopen_state(BASE, CHANGED)

    def test_observed_database_replacement_or_unexpected_stage_is_not_overwritten(self):
        for issue in ('replacement', 'deleted', 'stage', 'appeared'):
            self.reset(None if issue == 'appeared' else BASE)
            store = self.open()
            if issue == 'replacement': self.db.write_bytes(EMPTY)
            elif issue == 'deleted': self.db.unlink()
            elif issue == 'stage': self.next.write_bytes(ADDED); self.next.chmod(0o600)
            else: self.db.write_bytes(EMPTY); self.db.chmod(0o600)
            user = self.user(record(b'carol', 1001))
            before = self.db.read_bytes() if self.db.exists() else None
            staged = self.next.read_bytes() if self.next.exists() else None
            self.assertEqual(self.lib.ok_users_store_add(ctypes.byref(store), ctypes.byref(user)), -1)
            self.assertEqual(self.db.read_bytes() if self.db.exists() else None, before)
            self.assertEqual(self.next.read_bytes() if self.next.exists() else None, staged)
            self.assertEqual(store.ready, 0)
            self.close(store)


if __name__ == '__main__':
    unittest.main()
