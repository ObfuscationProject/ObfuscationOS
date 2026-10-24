"""Independent host crypto oracle and strict first-administrator format controls.

These checks neither authenticate a guest nor establish durable account storage.
"""
from pathlib import Path
import ctypes
import hashlib
import random
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Account(ctypes.Structure):
    _fields_ = [('state', ctypes.c_int), ('name', ctypes.c_char * 32),
                ('salt', ctypes.c_ubyte * 16), ('verifier', ctypes.c_ubyte * 32)]


def configured(state=b'active', name=b'admin'):
    return (b'OKACCOUNTS 1\nstate ' + state + b'\nname ' + name +
            b'\nuid 0\ngid 0\nhome /root\nkdf pbkdf2-hmac-sha256\nrounds 600000\nsalt ' +
            bytes(range(16)).hex().encode() + b'\nverifier ' +
            bytes(range(32)).hex().encode() + b'\n')


class NativeAccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-accounts-host-')
        output = Path(cls.directory.name) / 'accounts.so'
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-fPIC', '-shared', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        str(ROOT / 'apps/login/password.c'), str(ROOT / 'apps/login/accounts.c'),
                        '-o', str(output)], check=True)
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.ok_pbkdf2_sha256.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_void_p]
        cls.lib.ok_password_derive.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
            ctypes.c_void_p, ctypes.c_void_p]
        cls.lib.ok_password_verify.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
            ctypes.c_void_p, ctypes.c_void_p]
        cls.lib.ok_account_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Account)]
        cls.lib.ok_account_encode.argtypes = [ctypes.POINTER(Account), ctypes.c_void_p, ctypes.c_size_t]

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def derive(self, password, salt, rounds):
        output = ctypes.create_string_buffer(32)
        self.assertEqual(self.lib.ok_pbkdf2_sha256(password, len(password), salt, len(salt), rounds, output), 0)
        return output.raw

    def test_published_pbkdf2_sha256_vectors(self):
        # Published PBKDF2-HMAC-SHA-256 test vectors, independently hard-coded.
        for rounds, expected in [
            (1, '120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b'),
            (2, 'ae4d0c95af6b46d32d0adff928f06dd02a303f8ef3c251dfd6e2d85a95474c43'),
            (4096, 'c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a')]:
            self.assertEqual(self.derive(b'password', b'salt', rounds).hex(), expected)

    def test_independent_hashlib_oracle_block_boundaries(self):
        rng = random.Random(0x4f4b4143)
        for size in (0, 1, 31, 32, 55, 56, 63, 64, 65, 119, 120, 127, 128):
            for salt_size in (0, 1, 51, 52, 55, 56, 60, 63, 64):
                password = rng.randbytes(size)
                salt = rng.randbytes(salt_size)
                rounds = rng.randrange(1, 10)
                self.assertEqual(self.derive(password, salt, rounds),
                                 hashlib.pbkdf2_hmac('sha256', password, salt, rounds, 32))

    def test_production_work_factor_and_verification(self):
        password = 'First boot 密码'.encode()
        salt = bytes(range(16))
        expected = hashlib.pbkdf2_hmac('sha256', password, salt, 600000, 32)
        output = ctypes.create_string_buffer(32)
        self.assertEqual(self.lib.ok_password_derive(password, len(password), salt, output), 0)
        self.assertEqual(output.raw, expected)
        self.assertEqual(self.lib.ok_password_verify(password, len(password), salt, expected), 1)
        for index in (0, 15, 31):
            changed = bytearray(expected)
            changed[index] ^= 1
            self.assertEqual(self.lib.ok_password_verify(password, len(password), salt, bytes(changed)), 0)
        self.assertEqual(self.lib.ok_password_verify(b'wrong', 5, salt, expected), 0)

    def test_crypto_rejects_invalid_sizes_without_output_mutation(self):
        for password, size, salt, salt_size, rounds in [
            (None, 1, b's', 1, 1), (b'p', 129, b's', 1, 1),
            (b'p', 1, None, 1, 1), (b'p', 1, b's', 65, 1),
            (b'p', 1, b's', 1, 0), (b'p', 1, b's', 1, 1000001)]:
            output = ctypes.create_string_buffer(b'X' * 32, 32)
            self.assertEqual(self.lib.ok_pbkdf2_sha256(password, size, salt, salt_size, rounds, output), -1)
            self.assertEqual(output.raw, b'X' * 32)
        output = ctypes.create_string_buffer(b'X' * 32, 32)
        self.assertEqual(self.lib.ok_password_derive(b'', 0, b'S' * 16, output), -1)
        self.assertEqual(self.lib.ok_password_derive(b'p', 1, None, output), -1)
        self.assertEqual(output.raw, b'X' * 32)

    def parse(self, data):
        result = Account()
        self.assertEqual(self.lib.ok_account_parse(data, len(data), ctypes.byref(result)), 0)
        return result

    def test_canonical_states_roundtrip(self):
        for data, state in [(b'OKACCOUNTS 1\nstate unconfigured\n', 0),
                            (configured(b'pending'), 1), (configured(), 2)]:
            result = self.parse(data)
            self.assertEqual(result.state, state)
            if state:
                self.assertEqual(result.name, b'admin')
                self.assertEqual(bytes(result.salt), bytes(range(16)))
                self.assertEqual(bytes(result.verifier), bytes(range(32)))
            output = ctypes.create_string_buffer(512)
            self.assertEqual(self.lib.ok_account_encode(ctypes.byref(result), output, 512), len(data))
            self.assertEqual(output.raw[:len(data)], data)
        self.parse(configured(name=b'a' * 31))

    def test_invalid_database_never_becomes_unconfigured(self):
        valid = configured()
        attacks = [b'', b'\n', valid + b'\n', valid + b'state unconfigured\n',
            valid.replace(b'OKACCOUNTS 1', b'OKACCOUNTS 2'),
            valid.replace(b'uid 0', b'uid 1000'), valid.replace(b'gid 0', b'gid 1'),
            valid.replace(b'home /root', b'home /home/admin'),
            valid.replace(b'600000', b'599999'), valid.replace(b'600000', b'0600000'),
            valid.replace(b'pbkdf2-hmac-sha256', b'sha256'),
            valid.replace(b'state active', b'state unconfigured'),
            valid.replace(b'\n', b'\r\n'), valid.replace(b'admin', b'../root'),
            valid.replace(b'admin', b'a' * 32), valid.replace(b'admin', b'Admin'),
            valid.replace(b'admin', b'9admin'), valid.replace(b'admin', b'ad\x00min'),
            valid.replace(b'00010203', b'0001020G'), valid.replace(b'00010203', b'0001020A'),
            b'OKACCOUNTS 1\nstate unconfigured\nname admin\n', b'X' * 513]
        attacks.extend(valid[:i] for i in range(len(valid)))
        for data in attacks:
            result = Account()
            ctypes.memset(ctypes.byref(result), 0xa5, ctypes.sizeof(result))
            before = bytes(result)
            with self.subTest(data=data):
                self.assertEqual(self.lib.ok_account_parse(data, len(data), ctypes.byref(result)), -1)
                self.assertEqual(bytes(result), before)

    def test_failed_encoding_is_atomic_and_cannot_erase_identity(self):
        account = self.parse(configured())
        for capacity in (0, 1, len(configured()) - 1):
            output = ctypes.create_string_buffer(b'X' * 512, 512)
            self.assertEqual(self.lib.ok_account_encode(ctypes.byref(account), output, capacity), -1)
            self.assertEqual(output.raw, b'X' * 512)
        account.state = 0
        output = ctypes.create_string_buffer(b'X' * 512, 512)
        self.assertEqual(self.lib.ok_account_encode(ctypes.byref(account), output, 512), -1)
        self.assertEqual(output.raw, b'X' * 512)

    def test_noncanonical_name_tail_is_rejected_before_publication(self):
        account = self.parse(configured(b'pending'))
        ctypes.c_ubyte.from_address(ctypes.addressof(account) + Account.name.offset + 6).value = ord('X')
        output = ctypes.create_string_buffer(b'X' * 512, 512)
        self.assertEqual(self.lib.ok_account_encode(ctypes.byref(account), output, 512), -1)
        self.assertEqual(output.raw, b'X' * 512)


if __name__ == '__main__':
    unittest.main()
