import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from test_musl_userland import validate_runtime_frames

PREP=b'OK_NATIVE_MEMORY stage=prepare source=firmware status=pass image_begin=0x100000 image_end=0x200000 limit=1024\nOK_NATIVE_MEMORY_RANGE base=0x200000 size=0x400000\n'
STATS=b'OK_NATIVE_FRAMES version=2 source=firmware used=0 total=1024 allocations=0 releases=0 pinned=0 user=0 objects=0 free=1024 pending=0 reserve=8 user_limit=1016\nOK_NATIVE_FRAMES version=2 source=firmware used=2 total=1024 allocations=8 releases=6 pinned=0 user=1 objects=1 free=1022 pending=0 reserve=8 user_limit=1016\nOK_NATIVE_FRAMES version=2 source=firmware used=2 total=1024 allocations=10 releases=8 pinned=0 user=2 objects=0 free=1022 pending=0 reserve=8 user_limit=1016\n'
IMAGE=b'OK_NATIVE_IMAGE personality=linux source=firmware pages=2 physical_first=0x200000 physical_last=0x201000 owner=retained\n'
GOOD=PREP+STATS+IMAGE*4
class RuntimeFrameEvidenceTests(unittest.TestCase):
    def test_supported_and_explicit_fallback(self):
        for arch in ('i386','x86_64','aarch64','rv32','rv64','ppc'):
            self.assertEqual(validate_runtime_frames(GOOD,arch)['source'],'firmware')
        fallback=b'OK_NATIVE_MEMORY stage=prepare source=linker reason=unsupported-firmware-profile limit=1024\n'+(STATS+IMAGE*4).replace(b'firmware',b'linker')
        for arch in ('loongarch64','mips','mips64'):
            self.assertEqual(validate_runtime_frames(fallback,arch)['source'],'linker')
        with self.assertRaises(RuntimeError):validate_runtime_frames(fallback,'x86_64')
        with self.assertRaises(RuntimeError):validate_runtime_frames(GOOD,'mips')
    def test_bad_bounds_capacity_and_owner(self):
        for old,new in [(b'image_end=0x200000',b'image_end=0x300000'),(b'size=0x400000',b'size=0x200000'),(b'physical_first=0x200000',b'physical_first=0x100000'),(b'pages=2',b'pages=129'),(b'owner=retained',b'owner=missing'),(b'pinned=0',b'pinned=1'),(b'releases=8',b'releases=9'),(b'total=1024',b'total=512'),(b'status=pass',b'status=fail')]:
            with self.subTest(old=old),self.assertRaises(RuntimeError):validate_runtime_frames(GOOD.replace(old,new),'x86_64')
    def test_missing_or_duplicated_provenance(self):
        for serial in (STATS+IMAGE*4,PREP+GOOD,PREP+IMAGE*4,PREP+STATS+IMAGE*3):
            with self.assertRaises(RuntimeError):validate_runtime_frames(serial,'x86_64')

    def test_arm32_source_and_entry(self):
        arm = (b'OK_ARM32_ENTRY cpsr=0x400001d3 sctlr=0xc50078 mpidr=0x80000000 status=pass\n'
               b'OK_NATIVE_MEMORY_SOURCE protocol=arm32-linux-image fdt=0x48000000 size=0x100000\n'+GOOD)
        arm = arm.replace(b'image_begin=0x100000',b'image_begin=0x40010000').replace(b'image_end=0x200000',b'image_end=0x41000000').replace(b'base=0x200000',b'base=0x41000000').replace(b'physical_first=0x200000',b'physical_first=0x41000000').replace(b'physical_last=0x201000',b'physical_last=0x41001000')
        self.assertEqual(validate_runtime_frames(arm,'arm32')['source'],'firmware')
        for old,new in [(b'cpsr=0x400001d3',b'cpsr=0x400003d3'),(b'sctlr=0xc50078',b'sctlr=0x2c50078'),(b'cpsr=0x400001d3',b'cpsr=0x400001da'),(b'sctlr=0xc50078',b'sctlr=0xc50079'),(b'mpidr=0x80000000',b'mpidr=0x80000100'),(b'fdt=0x48000000',b'fdt=0x41000000'),(b'fdt=0x48000000',b'fdt=0x40010000'),(b'fdt=0x48000000',b'fdt=0x5ff80000'),(b'fdt=0x48000000',b'fdt=0x48000001'),(b'size=0x100000',b'size=0x0'),(b'image_begin=0x40010000',b'image_begin=0x40008000'),(b'image_end=0x41000000',b'image_end=0x50001000'),(b'base=0x41000000',b'base=0x50000000'),(b'protocol=arm32-linux-image',b'protocol=arm32-direct-elf')]:
            with self.subTest(old=old,new=new),self.assertRaises(RuntimeError):validate_runtime_frames(arm.replace(old,new),'arm32')
        for prefix in (b'OK_ARM32_ENTRY',b'OK_NATIVE_MEMORY_SOURCE'):
            line=next(line for line in arm.splitlines(keepends=True) if line.startswith(prefix))
            for corrupt in (arm.replace(line,b''),line+arm):
                with self.assertRaises(RuntimeError):validate_runtime_frames(corrupt,'arm32')
        with self.assertRaises(RuntimeError):validate_runtime_frames(GOOD,'arm32')

    def test_purpose_accounting_and_version(self):
        result = validate_runtime_frames(GOOD, 'x86_64')
        self.assertEqual((result['accounting_version'], result['object_reserve'], result['user_limit']), (2,8,1016))
        self.assertEqual((result['remaining_user'], result['remaining_objects'], result['free']), (2,0,1022))
        for old,new in [(b'version=2 ',b''), (b'version=2',b'version=1'),
                        (b'user=1 objects=1',b'user=2 objects=1'),
                        (b'free=1022',b'free=1023'), (b'pending=0',b'pending=1'),
                        (b'reserve=8',b'reserve=0'), (b'user_limit=1016',b'user_limit=1024'),
                        (b'objects=1',b'objects=9'), (b'reserve=8 user_limit=1016',b'reserve=1024 user_limit=0')]:
            with self.subTest(old=old,new=new),self.assertRaises(RuntimeError):
                validate_runtime_frames(GOOD.replace(old,new),'x86_64')
        with self.assertRaises(RuntimeError):
            validate_runtime_frames(GOOD.replace(b'reserve=8 user_limit=1016',b'reserve=9 user_limit=1015',1),'x86_64')
