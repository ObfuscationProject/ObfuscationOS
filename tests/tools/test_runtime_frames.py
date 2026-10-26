import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from test_musl_userland import validate_runtime_frames

# Kernel SDK 75 provenance: discovered boot memory and the shared frame allocator.
BOOT=(b'OK_BOOT_MEMORY version=1 protocol=bios-e820 source=e820 status=pass image_begin=0x0000000000100000 '
      b'image_end=0x0000000000200000 direct_offset=0x0000000000000000 managed_pages=1024 managed_ranges=1 excluded=2\n'
      b'OK_BOOT_MEMORY_SOURCE base=0x0000000000005000 size=0x0000000000000c10 decoded=0x00000000000000b8\n'
      b'OK_BOOT_MEMORY_RANGE base=0x0000000000200000 size=0x0000000000400000\n')
STATS=(b'OK_NATIVE_FRAMES version=3 source=firmware used=0 total=1020 allocations=0 releases=0 pinned=0 user=0 objects=0 free=1012 pending=0 reserve=8 user_limit=1004\n'
       b'OK_NATIVE_FRAMES version=3 source=firmware used=2 total=1020 allocations=8 releases=6 pinned=0 user=1 objects=1 free=1010 pending=0 reserve=8 user_limit=1004\n'
       b'OK_NATIVE_FRAMES version=3 source=firmware used=2 total=1020 allocations=10 releases=8 pinned=0 user=2 objects=0 free=1010 pending=0 reserve=8 user_limit=1004 object_quarantine=0\n')
IMAGE=b'OK_NATIVE_IMAGE personality=linux source=firmware pages=2 physical_first=0x200000 physical_last=0x201000 owner=retained\n'
GOOD=BOOT+STATS+IMAGE*4
class RuntimeFrameEvidenceTests(unittest.TestCase):
    def test_every_profile_discovers_memory(self):
        for arch in ('i386','x86_64','aarch64','rv32','rv64','ppc','loongarch64','mips','mips64'):
            self.assertEqual(validate_runtime_frames(GOOD,arch)['source'],'firmware')
        legacy=(b'OK_NATIVE_MEMORY stage=prepare source=linker reason=unsupported-firmware-profile limit=1024\n'+
                (STATS+IMAGE*4).replace(b'firmware',b'linker'))
        for arch in ('loongarch64','mips','x86_64'):
            with self.assertRaises(RuntimeError):validate_runtime_frames(legacy,arch)
    def test_kseg0_images_use_the_direct_offset(self):
        mips=(GOOD.replace(b'direct_offset=0x0000000000000000',b'direct_offset=0xffffffff80000000')
              .replace(b'physical_first=0x200000',b'physical_first=0xffffffff80200000')
              .replace(b'physical_last=0x201000',b'physical_last=0xffffffff80201000'))
        self.assertEqual(validate_runtime_frames(mips,'mips64')['source'],'firmware')
        with self.assertRaises(RuntimeError):validate_runtime_frames(GOOD.replace(b'direct_offset=0x0000000000000000',b'direct_offset=0xffffffff80000000'),'mips64')
    def test_bad_bounds_capacity_and_owner(self):
        for old,new in [(b'image_end=0x0000000000200000',b'image_end=0x0000000000300000'),(b'size=0x0000000000400000',b'size=0x0000000000200000'),
                        (b'managed_ranges=1',b'managed_ranges=2'),(b'RANGE base=0x0000000000200000',b'RANGE base=0x0000000000000000'),
                        (b'physical_first=0x200000',b'physical_first=0x100000'),(b'pages=2',b'pages=1025'),(b'owner=retained',b'owner=missing'),
                        (b'pinned=0',b'pinned=1'),(b'releases=8',b'releases=9'),(b'total=1020',b'total=2048'),(b'status=pass',b'status=fail'),
                        (b'source=e820',b'source=synthetic')]:
            with self.subTest(old=old),self.assertRaises(RuntimeError):validate_runtime_frames(GOOD.replace(old,new),'x86_64')
    def test_missing_or_duplicated_provenance(self):
        for serial in (STATS+IMAGE*4,BOOT+GOOD,BOOT+IMAGE*4,BOOT+STATS+IMAGE*3):
            with self.assertRaises(RuntimeError):validate_runtime_frames(serial,'x86_64')

    def test_arm32_source_and_entry(self):
        arm=(b'OK_ARM32_ENTRY cpsr=0x400001d3 sctlr=0xc50078 mpidr=0x80000000 status=pass\n'+GOOD)
        arm=(arm.replace(b'protocol=bios-e820 source=e820',b'protocol=arm32-linux-image source=fdt')
             .replace(b'image_begin=0x0000000000100000',b'image_begin=0x0000000040010000').replace(b'image_end=0x0000000000200000',b'image_end=0x0000000041000000')
             .replace(b'OK_BOOT_MEMORY_SOURCE base=0x0000000000005000 size=0x0000000000000c10',b'OK_BOOT_MEMORY_SOURCE base=0x0000000048000000 size=0x0000000000100000')
             .replace(b'RANGE base=0x0000000000200000',b'RANGE base=0x0000000041000000')
             .replace(b'physical_first=0x200000',b'physical_first=0x41000000').replace(b'physical_last=0x201000',b'physical_last=0x41001000'))
        self.assertEqual(validate_runtime_frames(arm,'arm32')['source'],'firmware')
        for old,new in [(b'cpsr=0x400001d3',b'cpsr=0x400003d3'),(b'sctlr=0xc50078',b'sctlr=0x2c50078'),(b'cpsr=0x400001d3',b'cpsr=0x400001da'),
                        (b'sctlr=0xc50078',b'sctlr=0xc50079'),(b'mpidr=0x80000000',b'mpidr=0x80000100'),
                        (b'SOURCE base=0x0000000048000000',b'SOURCE base=0x0000000041000000'),(b'SOURCE base=0x0000000048000000',b'SOURCE base=0x0000000040010000'),
                        (b'SOURCE base=0x0000000048000000',b'SOURCE base=0x000000005ff80000'),(b'SOURCE base=0x0000000048000000',b'SOURCE base=0x0000000048000001'),
                        (b'SOURCE base=0x0000000048000000 size=0x0000000000100000',b'SOURCE base=0x0000000048000000 size=0x0000000000000000'),
                        (b'image_begin=0x0000000040010000',b'image_begin=0x0000000040008000'),
                        (b'image_end=0x0000000041000000',b'image_end=0x0000000050001000'),(b'RANGE base=0x0000000041000000',b'RANGE base=0x0000000050000000')]:
            with self.subTest(old=old,new=new),self.assertRaises(RuntimeError):validate_runtime_frames(arm.replace(old,new),'arm32')
        for prefix in (b'OK_ARM32_ENTRY',b'OK_BOOT_MEMORY_SOURCE'):
            line=next(line for line in arm.splitlines(keepends=True) if line.startswith(prefix))
            for corrupt in (arm.replace(line,b''),line+arm):
                with self.assertRaises(RuntimeError):validate_runtime_frames(corrupt,'arm32')
        with self.assertRaises(RuntimeError):validate_runtime_frames(GOOD,'arm32')

    def test_purpose_accounting_and_version(self):
        result=validate_runtime_frames(GOOD,'x86_64')
        self.assertEqual((result['accounting_version'],result['object_reserve'],result['user_limit'],result['total']),(3,8,1004,1020))
        self.assertEqual((result['remaining_user'],result['remaining_objects'],result['free']),(2,0,1010))
        for old,new in [(b'version=3 ',b''),(b'version=3',b'version=2'),(b'user=1 objects=1',b'user=2 objects=1'),
                        (b'free=1010',b'free=1019'),(b'pending=0',b'pending=1'),(b'reserve=8',b'reserve=0'),
                        (b'user_limit=1004',b'user_limit=1016'),(b'objects=1',b'objects=9'),
                        (b'object_quarantine=0',b'object_quarantine=1')]:
            with self.subTest(old=old,new=new),self.assertRaises(RuntimeError):
                validate_runtime_frames(GOOD.replace(old,new),'x86_64')
        # The quota and reserve are fixed at activation.
        with self.assertRaises(RuntimeError):
            validate_runtime_frames(GOOD.replace(b'reserve=8 user_limit=1004',b'reserve=9 user_limit=1003',1),'x86_64')
