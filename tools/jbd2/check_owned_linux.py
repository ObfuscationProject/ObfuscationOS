#!/usr/bin/env python3
"""Independently recover a dirty copy in Linux and mount a completed copy readonly."""
from __future__ import annotations
import argparse,hashlib,json,shutil,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from native_support import boot
from create_linux_fixture import cpio
from admit_linux_fixture import checksum,inspect
from transaction_fixture import expected,clean_capture
ROOT=Path(__file__).resolve().parents[2]
def sha(data):return hashlib.sha256(data).hexdigest()

def clean_controls(data,facts):
    if len(data)!=32*1024*1024:raise ValueError('completed image length')
    sb=data[1024:2048];j=facts['journal_first']*1024;jsb=bytearray(data[j:j+1024])
    if struct.unpack_from('<I',sb,96)[0]!=0x42 or checksum(0xffffffff,sb[:1020])!=struct.unpack_from('<I',sb,1020)[0]:
        raise ValueError('completed filesystem control/checksum')
    sequence,start=struct.unpack_from('>II',jsb,24);recorded=struct.unpack_from('>I',jsb,252)[0]
    struct.pack_into('>I',jsb,252,0)
    if start or sequence!=facts['journal_sequence']+5 or checksum(0xffffffff,jsb)!=recorded or jsb[48:64].hex()!=facts['uuid']:
        raise ValueError('completed journal control/checksum')
    return sequence

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--linux-image',type=Path,required=True);p.add_argument('--completed-image',type=Path,required=True)
    p.add_argument('--published-image',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    r={'scope':'independent-linux-owned-publication-recovery-and-readonly-checkpoint','status':'running','commands':[],
       'host_mounts':False,'physical_power_loss':False,'linux_source_provenance':'not-established'}
    def save():(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    def run(command,label):
        item={'argv':[str(x) for x in command],'label':label};r['commands'].append(item);save()
        result=subprocess.run(item['argv'],text=True,capture_output=True);(out/(label+'.log')).write_text(result.stdout+result.stderr)
        item.update(returncode=result.returncode,status='passed' if not result.returncode else 'failed');save()
        if result.returncode:raise RuntimeError(label+' failed')
        return result.stdout+result.stderr
    save()
    try:
        capture=json.loads((args.fixture/'capture-manifest.json').read_text());dirty=(args.fixture/'linux-dirty-capture.img').read_bytes()
        if sha(dirty)!=capture['capture_sha256']:raise ValueError('capture identity mismatch')
        kernel=out/'linux-bzImage';shutil.copyfile(args.linux_image,kernel)
        if sha(kernel.read_bytes())!=capture['linux_image_sha256']:raise ValueError('Linux binary differs from capture identity')
        completed=args.completed_image.read_bytes();facts=inspect(dirty,True);clean_sequence=clean_controls(completed,facts)
        expected_publication,oracle=expected(clean_capture(dirty,facts),facts)
        published=args.published_image.read_bytes()
        if published!=expected_publication:raise ValueError('owner publication differs from independent oracle')
        if completed!=oracle:raise ValueError('input is not the exact independently constructed transaction oracle')
        r.update(linux_image_sha256=sha(kernel.read_bytes()),capture_sha256=sha(dirty),published_sha256=sha(published),completed_sha256=sha(completed),published_source=str(args.published_image.resolve()),completed_source=str(args.completed_image.resolve()),actual_owner_image_input=True)
        sources=['tests/linux/ext4_transaction_init.c','tools/jbd2/check_owned_linux.py','tools/jbd2/native_support.py',
                 'tools/jbd2/create_linux_fixture.py','tools/jbd2/admit_linux_fixture.py','tools/jbd2/test_completion.py','tools/jbd2/transaction_fixture.py','tools/kernel_sdk.py']
        r['source_sha256']={}
        for relative in sources:
            target=out/'sources'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/relative).read_bytes())
            r['source_sha256']['sources/'+relative]=sha(target.read_bytes())
        init=out/'init';run(['gcc','-static','-O2','-Wall','-Wextra','-Werror',out/'sources/tests/linux/ext4_transaction_init.c','-o',init],'compile-linux-init')
        entries=[(name,0o040755,b'',0,0) for name in ['dev','proc','sys','mnt']]
        entries += [('dev/console',0o020600,b'',5,1),('init',0o100755,init.read_bytes(),0,0)]
        initrd=out/'initramfs.cpio';initrd.write_bytes(cpio(entries))
        images={}
        for label,data,readonly in [('linux-recovery',published,False),('completed-readonly',completed,True)]:
            disk=out/(label+'.img');disk.write_bytes(data);images[label]=disk
            command=['qemu-system-x86_64','-m','512M','-kernel',str(kernel),'-initrd',str(initrd),'-append',
                     'console=ttyS0 rdinit=/init loglevel=4 panic=-1 nokaslr','-drive',
                     f'file={disk},format=raw,if=none,id=fixture,cache=writeback'+(',readonly=on' if readonly else ''),
                     '-device','virtio-blk-pci,drive=fixture']
            r['commands'].append({'argv':command,'label':label});save()
            # The pinned Linux console applies ONLCR to userspace stdout.
            boot(command,'LINUX_TRANSACTION_PASS mode=640 uid=2000 gid=2001 bytes=4096 mount=readonly unmount=pass\r\n',out/(label+'.log'))
            if readonly and disk.read_bytes()!=data:raise ValueError('readonly Linux mount modified completed disk')
            run(['e2fsck','-fn',disk],label+'-e2fsck')
        reference=images['linux-recovery'].read_bytes();reference_sequence=clean_controls(reference,facts)
        if reference_sequence!=clean_sequence:raise ValueError('Linux cleanup control mismatch')
        journal=facts['journal_first']*1024
        # Linux may update its optional clean head and superblock bookkeeping;
        # all replayed inode/data/namespace bytes must exactly match.
        differing=[i for i in range(len(reference)) if reference[i]!=completed[i]]
        allowed=set()
        for start,end in [(44,54),(64,68),(136,200),(376,384),(1020,1024)]:allowed.update(range(1024+start,1024+end))
        for start,end in [(88,92),(252,256)]:allowed.update(range(journal+start,journal+end))
        if any(i not in allowed for i in differing):raise ValueError('Linux differs outside primary control blocks')
        r.update(status='passed',readonly_image_unchanged=True,linux_control_byte_differences=differing,
                 linux_clean_journal_sequence=reference_sequence,independent_home_metadata_equal=True)
    except Exception as error:r.update(status='failed',error=str(error));print('FAIL '+str(error),file=sys.stderr)
    finally:
        r['artifact_sha256']={str(f.relative_to(out)):sha(f.read_bytes()) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='result.json'};save()
    return 0 if r['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
