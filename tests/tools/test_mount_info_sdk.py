"""Rehashed mount inventory contract rejection using a standalone SDK fixture."""
import copy
import hashlib
import unittest

import test_kernel_sdk as fixtures
from kernel_sdk import validate_sdk


class MountInfoSdkTests(unittest.TestCase):
    save = fixtures.KernelSdkTests.save

    def setUp(self):
        fixtures.KernelSdkTests.setUp(self)

    def test_missing_profile_and_hashed_inputs_refuse(self):
        validate_sdk(self.sdk, 'x86_64', 'debug')
        baseline = copy.deepcopy(self.manifest)
        for field in ('native_mount_info_profile',):
            for value in (None, '', True, 'other'):
                self.manifest = copy.deepcopy(baseline)
                self.manifest[field] = value
                self.save()
                with self.subTest(value=value), self.assertRaises(ValueError):
                    validate_sdk(self.sdk, 'x86_64', 'debug')
        for name in ('include/ok/fs/mount_snapshot_profile.hpp', 'include/ok/fs/vfs.hpp'):
            self.manifest = copy.deepcopy(baseline)
            del self.manifest['files'][name]
            self.save()
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_rehashed_wire_or_profile_deception_refuses(self):
        baseline = copy.deepcopy(self.manifest)
        uapi = self.sdk / 'include/ok/uapi/syscall.h'
        profile = self.sdk / 'include/ok/fs/mount_snapshot_profile.hpp'
        good = uapi.read_text()
        marker = profile.read_text()
        cases = []
        cases.append((uapi, good.replace('#define OK_UAPI_VERSION_MINOR 16',
            '#define OK_UAPI_VERSION_MINOR 10 /* wrong compiled version */\n'
            '/*\n#define OK_UAPI_VERSION_MINOR 16\n*/')))
        for before, after in (
            ('MINOR 16', 'MINOR 10'), ('MINOR 16', 'MINOR 17'),
            ('OK_SYS_MOUNT_INFO 1034ULL', 'OK_SYS_MOUNT_INFO 1035ULL'),
            ('OK_NATIVE_MOUNT_INFO_VERSION 1', 'OK_NATIVE_MOUNT_INFO_VERSION 2'),
            ('OK_MOUNT_INFO_CAPACITY 9U', 'OK_MOUNT_INFO_CAPACITY 8U'),
            ('OK_MOUNT_INFO_PATH_CAPACITY 256U', 'OK_MOUNT_INFO_PATH_CAPACITY 255U'),
            ('uint32_t generation;', 'uint64_t generation;'),
            ('char path[OK_MOUNT_INFO_PATH_CAPACITY];', 'char *path;'),
            ('char path[OK_MOUNT_INFO_PATH_CAPACITY];', 'char path[255];'),
            ('uint32_t parent_id;', ''),
            ('uint32_t slot;\n    uint32_t capacity;', 'uint32_t capacity;\n    uint32_t slot;'),
        ):
            cases.append((uapi, good.replace(before, after)))
        cases.extend((uapi, good.replace('#endif', extra + '\n#endif')) for extra in (
            '#define OK_SYS_MOUNT_INFO 1034ULL', '#define OK_SYS_MOUNT_INFO() 1034ULL',
            '#define uint32_t uint16_t', '#define path another',
            'struct ok_mount_info { uint32_t value; };'))
        cases.extend((uapi, good.replace('struct ok_mount_info', extra + '\nstruct ok_mount_info', 1))
                     for extra in ('#pragma pack(1)', '#if 0'))
        for before, after in (('wire_bytes = 288', 'wire_bytes = 287'),
                              ('slots = 9', 'slots = 8'), ('version = 1', 'version = 2'),
                              ('derived-generation-v1', 'derived-generation-v2')):
            cases.append((profile, marker.replace(before, after)))
        cases.extend((profile, source) for source in ('#if 0\n' + marker + '#endif\n',
                     marker + marker, '/*\n' + marker + '*/\n'))
        for index, (path, source) in enumerate(cases):
            uapi.write_text(good)
            profile.write_text(marker)
            self.manifest = copy.deepcopy(baseline)
            path.write_text(source)
            self.manifest['files'][str(path.relative_to(self.sdk))] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.save()
            with self.subTest(case=index), self.assertRaises(ValueError):
                validate_sdk(self.sdk, 'x86_64', 'debug')


if __name__ == '__main__':
    unittest.main()
