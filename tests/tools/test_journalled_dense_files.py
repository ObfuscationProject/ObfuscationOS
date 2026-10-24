"""Actual ext4 packaging controls; no native code, guest or durability claim."""
from pathlib import Path
import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parents[2]/'tools'
sys.path.insert(0,str(TOOLS))
import journalled_dense_files as dense
import journalled_rootfs_policy as policy
import mkext4_journalled as packager


class ActivationMarkerTests(unittest.TestCase):
    def test_exclusive_marker_refuses_every_preexisting_entry_without_following_links(self):
        with tempfile.TemporaryDirectory(prefix='journal-marker-') as directory:
            work=Path(directory);root=work/'root';root.mkdir()
            marker=root/'.journal-profile';outside=work/'outside'
            for kind in ('regular','directory','dangling-symlink','existing-symlink'):
                with self.subTest(kind=kind):
                    if kind=='regular':marker.write_bytes(b'preserved')
                    elif kind=='directory':marker.mkdir()
                    else:
                        if kind=='existing-symlink':outside.write_bytes(b'preserved target')
                        marker.symlink_to(outside)
                    with self.assertRaisesRegex(ValueError,'journal activation marker'):
                        packager.create_activation_marker(root)
                    if kind=='regular':self.assertEqual(marker.read_bytes(),b'preserved')
                    elif kind=='existing-symlink':self.assertEqual(outside.read_bytes(),b'preserved target')
                    elif kind=='dangling-symlink':self.assertFalse(outside.exists())
                    if marker.is_dir() and not marker.is_symlink():marker.rmdir()
                    else:marker.unlink()
                    if outside.exists():outside.unlink()
            packager.create_activation_marker(root)
            self.assertEqual(marker.read_bytes(),b'linux journal activation marker\n')
            self.assertEqual(marker.stat().st_mode&0o777,0o644)


@unittest.skipUnless(all(shutil.which(tool) for tool in ('mke2fs','debugfs','e2fsck')), 'ext4 fixture tools unavailable')
class DenseBootstrapFilesTests(unittest.TestCase):
    def root(self,work):
        root=work/'root';(root/'etc').mkdir(parents=True);(root/'bin').mkdir()
        (root/'etc/accounts.db').write_bytes(b'OKACCOUNTS 1\nstate unconfigured\n')
        (root/'etc/services.conf').write_bytes(b'OK_SERVICE_MANIFEST 1\n')
        content=(b'A'*1024+bytes(1024))*8+bytes(17)
        (root/'bin/login').write_bytes(content);(root/'bin/login').chmod(0o755)
        (root/'zero').write_bytes(bytes(2049));(root/'empty').touch()
        (root/'link').symlink_to('bin/login')
        return root,content
    def image(self,work,root,name):
        image=work/name
        subprocess.run(['mke2fs','-q','-t','ext4','-b','1024','-I','256',
            '-O','none,has_journal,extents,filetype,metadata_csum','-J','size=4',
            '-E','lazy_itable_init=0,lazy_journal_init=0','-m','0','-d',str(root),str(image),'32M'],
            check=True,capture_output=True)
        return image
    def test_sparse_external_tree_becomes_inline_without_changing_any_original_byte(self):
        with tempfile.TemporaryDirectory(prefix='dense-bootstrap-') as directory:
            work=Path(directory);root,content=self.root(work)
            debugfs=Path(shutil.which('debugfs'))
            sparse=self.image(work,root,'sparse.img')
            before=subprocess.check_output([str(debugfs),'-R','stat /bin/login',str(sparse)],stderr=subprocess.DEVNULL)
            self.assertIn(b'(ETB0)',before)
            with self.assertRaisesRegex(ValueError,'requires initialized inline extents'):
                dense.validate_initialized_inline(debugfs,sparse,root)
            original={str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file() and not path.is_symlink()}
            plan=dense.prepare(root)
            self.assertEqual(plan['/bin/login']['zero_blocks'],list(range(1,16,2))+[16])
            self.assertEqual(plan['/zero']['zero_blocks'],[0,1,2])
            self.assertNotIn('/empty',plan)
            self.assertEqual((root/'link').readlink(),Path('bin/login'))
            image=self.image(work,root,'dense.img')
            result=dense.restore(debugfs,image,root,work,plan)
            self.assertTrue(result['regular_file_bytes_preserved'])
            self.assertEqual(original,{str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file() and not path.is_symlink()})
            observed=subprocess.check_output([str(debugfs),'-R','stat /bin/login',str(image)],stderr=subprocess.DEVNULL)
            self.assertNotIn(b'(ETB',observed)
            self.assertIn(b'(0-16)',observed)
            metadata=policy.normalize(debugfs,image,root,work)
            self.assertTrue(metadata['regular_file_bytes_preserved'])
            self.assertTrue(metadata['literal_symlink_targets_preserved'])
            admitted=dense.validate_initialized_inline(debugfs,image,root)
            self.assertTrue(admitted['initialized_inline_regular_files'])
            self.assertEqual(admitted['files']['/empty']['initialized_blocks'],0)
            self.assertEqual(admitted['files']['/empty']['extents'],[])
            self.assertEqual(admitted['files']['/bin/login']['size'],len(content))
            self.assertEqual(admitted['files']['/zero']['initialized_blocks'],3)
            checked=subprocess.run(['e2fsck','-fn',str(image)],capture_output=True)
            self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr)
    def test_changed_prepared_bytes_are_refused_before_any_image_write(self):
        with tempfile.TemporaryDirectory(prefix='dense-bootstrap-') as directory:
            work=Path(directory);root,_=self.root(work);plan=dense.prepare(root)
            image=self.image(work,root,'dense.img');before=image.read_bytes()
            with (root/'bin/login').open('r+b') as stream:stream.write(b'B')
            with self.assertRaisesRegex(ValueError,'preparation changed'):
                dense.restore(Path('/not-a-debugfs-tool'),image,root,work,plan)
            self.assertEqual(image.read_bytes(),before)
            self.assertFalse((work/'dense-files.debugfs').exists())
    def test_hardlink_alias_and_command_operand_are_refused(self):
        import os
        with tempfile.TemporaryDirectory(prefix='dense-bootstrap-') as directory:
            work=Path(directory);root,_=self.root(work)
            os.link(root/'bin/login',root/'alias')
            with self.assertRaisesRegex(ValueError,'unaliased'):
                dense.prepare(root)
            (root/'alias').unlink();(root/'bad;operand').write_bytes(bytes(1024))
            with self.assertRaisesRegex(ValueError,'pathname'):
                dense.prepare(root)
    def test_inline_admission_refuses_structural_faults_without_writing_the_image(self):
        with tempfile.TemporaryDirectory(prefix='dense-bootstrap-') as directory:
            work=Path(directory);root,_=self.root(work)
            plan=dense.prepare(root);image=self.image(work,root,'dense.img')
            debugfs=Path(shutil.which('debugfs'))
            dense.restore(debugfs,image,root,work,plan)
            admitted=dense.validate_initialized_inline(debugfs,image,root)
            original=image.read_bytes();number=admitted['files']['/bin/login']['inode']
            per_group=struct.unpack_from('<I',original,1024+40)[0]
            group,local=divmod(number-1,per_group)
            table=struct.unpack_from('<I',original,2048+group*32+8)[0]
            at=table*1024+local*256
            physical=struct.unpack_from('<I',original,at+60)[0]
            faults={
                'external-tree':[(46,'<H',1)],
                'too-many-extents':[(42,'<H',5)],
                'reduced-capacity':[(44,'<H',3)],
                'missing-extents-flag':[(32,'<I',0)],
                'logical-hole':[(52,'<I',1)],
                'uninitialized':[(56,'<H',32769)],
                'high-address':[(58,'<H',1)],
                'outside-image':[(60,'<I',32768)],
                'wrong-sectors':[(28,'<I',32)],
                'wrong-size':[(4,'<I',17)],
                'incomplete-coverage':[(56,'<H',16),(28,'<I',32)],
                'extra-coverage':[(56,'<H',18),(28,'<I',36)],
                'overlap':[(42,'<H',2),(56,'<H',8),(64,'<I',8),
                           (68,'<H',9),(70,'<H',0),(72,'<I',physical+7)],
            }
            for name,changes in faults.items():
                with self.subTest(fault=name):
                    changed=bytearray(original)
                    for offset,encoding,value in changes:struct.pack_into(encoding,changed,at+offset,value)
                    image.write_bytes(changed)
                    with self.assertRaises(ValueError):
                        dense.validate_initialized_inline(debugfs,image,root)
                    self.assertEqual(image.read_bytes(),changed)
            image.write_bytes(original)
            self.assertTrue(dense.validate_initialized_inline(debugfs,image,root)['initialized_inline_regular_files'])

if __name__=='__main__':unittest.main()
