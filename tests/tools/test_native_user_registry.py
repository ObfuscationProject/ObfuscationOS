"""Independent bounded multi-user wire controls; hosted parsing is not login."""
from pathlib import Path
import ctypes
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREFIX = b'OKUSERS 1\nkdf pbkdf2-hmac-sha256\nrounds 600000\ncount '


class User(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char * 32), ('uid', ctypes.c_uint32),
                ('gid', ctypes.c_uint32), ('salt', ctypes.c_ubyte * 16),
                ('verifier', ctypes.c_ubyte * 32)]


class Users(ctypes.Structure):
    _fields_ = [('count', ctypes.c_uint32), ('entries', User * 16)]


def record(name=b'alice', uid=1000, salt=bytes(range(16)), verifier=bytes(range(32)), gid=None):
    return (b'user ' + name + b' ' + str(uid).encode() + b' ' + str(uid if gid is None else gid).encode() +
            b' ' + salt.hex().encode() + b' ' + verifier.hex().encode() + b'\n')


def registry(*rows):
    return PREFIX + str(len(rows)).encode() + b'\n' + b''.join(rows)


def flags():
    sanitizer = os.environ.get('OK_USERS_SANITIZERS', 'undefined')
    if sanitizer not in ('undefined', 'address,undefined'):
        raise ValueError('unsupported hosted users sanitizer selection')
    return ['cc', '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-U_FORTIFY_SOURCE',
            '-D_FORTIFY_SOURCE=0', '-fno-builtin', '-O2', '-Wall', '-Wextra', '-Werror',
            '-fPIC', '-fsanitize=' + sanitizer, '-fno-sanitize-recover=all']


def bind(lib):
    lib.ok_users_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Users)]
    lib.ok_users_encode.argtypes = [ctypes.POINTER(Users), ctypes.c_void_p, ctypes.c_size_t]
    lib.ok_users_validate.argtypes = [ctypes.POINTER(Users), ctypes.c_char_p]
    lib.ok_users_find.argtypes = [ctypes.POINTER(Users), ctypes.c_char_p, ctypes.c_size_t]
    lib.ok_users_next_uid.argtypes = [ctypes.POINTER(Users), ctypes.POINTER(ctypes.c_uint32)]
    lib.ok_user_home.argtypes = [ctypes.POINTER(User), ctypes.c_void_p]


class NativeUsersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-users-host-')
        output = Path(cls.directory.name) / 'users.so'
        subprocess.run(flags() + ['-shared', str(ROOT / 'apps/login/users.c'),
            str(ROOT / 'apps/login/accounts.c'), str(ROOT / 'apps/login/password.c'), '-o', str(output)], check=True)
        cls.lib = ctypes.CDLL(str(output), use_errno=True)
        bind(cls.lib)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def parse(self, data):
        result = Users()
        self.assertEqual(self.lib.ok_users_parse(data, len(data), ctypes.byref(result)), 0)
        return result

    def test_independent_canonical_roundtrip_zero_to_sixteen(self):
        for count in range(17):
            wire = registry(*(record(('user' + str(i)).encode(), 1000 + i) for i in range(count)))
            users = self.parse(wire)
            self.assertEqual(users.count, count)
            output = ctypes.create_string_buffer(4096)
            self.assertEqual(self.lib.ok_users_encode(ctypes.byref(users), output, 4096), len(wire))
            self.assertEqual(output.raw[:len(wire)], wire)
            self.assertEqual(bytes(users)[4 + count * ctypes.sizeof(User):], b'\0' * ((16-count)*ctypes.sizeof(User)))
        wire = registry(*(record(b'a' * 29 + ('%02d' % i).encode(), 4294967270 + i) for i in range(16)))
        self.assertLess(len(wire), 4096)
        self.parse(wire)

    def test_malformed_truncated_noncanonical_and_duplicate_records_preserve_output(self):
        valid = registry(record(), record(b'bob', 1001))
        attacks = [b'', b'\n', valid + b'\n', valid + b'garbage', b'X' * 4097,
            valid.replace(b'OKUSERS 1', b'OKUSERS 2'), valid.replace(b'600000', b'599999'),
            valid.replace(b'600000', b'0600000'), valid.replace(b'count 2', b'count 02'),
            valid.replace(b'count 2', b'count 1'), valid.replace(b'count 2', b'count 17'),
            valid.replace(b'count 2', b'count 42949672960'), valid.replace(b'\n', b'\r\n'),
            valid.replace(b'alice', b'Alice'), valid.replace(b'alice', b'../alice'),
            valid.replace(b'alice', b'a' * 32), valid.replace(b'alice', b'ali\0ce'),
            valid.replace(b'1000 1000', b'01000 1000'), valid.replace(b'1000 1000', b'999 999'),
            valid.replace(b'1000 1000', b'1000 1001'), valid.replace(b'1000 1000', b'4294967295 4294967295'),
            valid.replace(b'00010203', b'0001020A'), valid.replace(b'00010203', b'0001020x'),
            registry(record(), record(b'alice', 1001)), registry(record(), record(b'bob', 1000)),
            registry(record(b'bob', 1001), record()), registry(record(b'admin')),
            PREFIX + b'1\nuser alice']
        # The administrator collision is syntactically valid, then operation
        # validation rejects it using the actual admitted legacy principal.
        admin = self.parse(attacks.pop(-2))
        self.assertEqual(self.lib.ok_users_validate(ctypes.byref(admin), b'admin'), -1)
        attacks.extend(valid[:i] for i in range(len(valid)))
        for data in attacks:
            output = Users()
            ctypes.memset(ctypes.byref(output), 0xa5, ctypes.sizeof(output))
            before = bytes(output)
            with self.subTest(data=data):
                self.assertEqual(self.lib.ok_users_parse(data, len(data), ctypes.byref(output)), -1)
                self.assertEqual(bytes(output), before)

    def test_encoding_failure_does_not_write_or_discard_hidden_entries(self):
        users = self.parse(registry(record()))
        for capacity in (0, 1, len(registry(record())) - 1):
            output = ctypes.create_string_buffer(b'X' * 4096, 4096)
            self.assertEqual(self.lib.ok_users_encode(ctypes.byref(users), output, capacity), -1)
            self.assertEqual(output.raw, b'X' * 4096)
        for mutate in ('tail', 'unused', 'count', 'uid', 'gid'):
            damaged = self.parse(registry(record()))
            if mutate == 'tail':
                ctypes.c_ubyte.from_address(ctypes.addressof(damaged.entries[0]) + 7).value = 1
            elif mutate == 'unused': damaged.entries[15].uid = 1001
            elif mutate == 'count': damaged.count = 17
            elif mutate == 'uid': damaged.entries[0].uid = 0
            else: damaged.entries[0].gid = 1002
            output = ctypes.create_string_buffer(b'X' * 4096, 4096)
            self.assertEqual(self.lib.ok_users_encode(ctypes.byref(damaged), output, 4096), -1)
            self.assertEqual(output.raw, b'X' * 4096)

    def test_lookup_uid_allocation_and_derived_home(self):
        users = self.parse(registry(record(), record(b'bob', 1002)))
        self.assertEqual(self.lib.ok_users_find(ctypes.byref(users), b'bob', 3), 1)
        self.assertEqual(self.lib.ok_users_find(ctypes.byref(users), b'bo', 2), -1)
        uid = ctypes.c_uint32(99)
        self.assertEqual(self.lib.ok_users_next_uid(ctypes.byref(users), ctypes.byref(uid)), 0)
        self.assertEqual(uid.value, 1001)
        output = ctypes.create_string_buffer(38)
        self.assertEqual(self.lib.ok_user_home(ctypes.byref(users.entries[1]), output), 0)
        self.assertEqual(output.value, b'/home/bob')
        full = self.parse(registry(*(record(('u' + str(i)).encode(), 1000+i) for i in range(16))))
        uid.value = 99
        self.assertEqual(self.lib.ok_users_next_uid(ctypes.byref(full), ctypes.byref(uid)), -1)
        self.assertEqual(uid.value, 99)


if __name__ == '__main__':
    unittest.main()
