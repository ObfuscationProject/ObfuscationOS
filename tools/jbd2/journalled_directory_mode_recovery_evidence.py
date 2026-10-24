"""Strict native recovery transcript/disk oracle; execution is bound by the outer capture."""
import hashlib
import re
import struct
from admit_linux_fixture import checksum
from journalled_mode_image import extract_volume, inode_metadata

N=r'(0|[1-9][0-9]*)'
PATTERNS={
'begin':r'JDREC_FIXTURE_BEGIN scope=actual-musl-user-mode sdk=31 sdk-only=1 uid=1000',
'owner':r'JDREC_OWNER acquired=1 aliases=excluded mount=none',
'io':rf'JDREC_IO ordinal={N} kind=(write|flush) sector={N} bytes={N} crc32c={N} status={N}',
'recovered':rf'JDREC_RECOVERY_PASS clean={N} empty={N} actions={N} checked={N} reads={N} writes={N} flushes={N} sequence={N} home=1 journal=1 filesystem=1',
'retired':r'JDREC_OWNER retired=1 stale=denied',
'storage':rf'JDREC_STORAGE virtio=1 policy=maintained-noatime aliases=2 root=archive epoch=1 reads={N}',
'credentials':r'JDREC_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 before-entry=1 personality=linux',
'user':r'JDREC_USER_BEGIN uid=1000 scope=actual-musl-syscalls',
'snapshot':r'LINUX_CHMOD_SNAPSHOT name=directory-recovery-(child|root|seed|other|link|leaf) hex=([0-9a-f]{512})',
'fsync_begin':r'JDREC_FSYNC_BEGIN calls=2',
'fsync_end':r'JDREC_FSYNC_END calls=2',
'user_pass':rf'JDREC_USER_PASS uid=1000 bytes=4096 checks={N}',
'pass':rf'JDREC_FIXTURE_PASS uid=1000 exit=0 reaped=1 personality=linux epoch=1 reads={N} writes={N} flushes={N}',
}
PATTERNS={k:re.compile(v) for k,v in PATTERNS.items()}
def require(value,message):
 if not value:raise ValueError(message)
def records(text):
 require(isinstance(text,str),'text required')
 rows=[]
 for position,line in enumerate(text.splitlines(keepends=True)):
  if not any(x in line for x in ('JDREC','LINUX_CHMOD','JDMODE','JREC','JMODE')):continue
  require(line.endswith('\n'),'truncated protocol line')
  body=line[:-1]
  if body.endswith('\r'):body=body[:-1]
  matches=[(k,p.fullmatch(body)) for k,p in PATTERNS.items() if p.fullmatch(body)]
  require(len(matches)==1,'unknown, malformed or unframed protocol line')
  kind,match=matches[0];values=match.groups()
  if kind=='io':values=(int(values[0]),values[1],*map(int,values[2:]))
  elif kind!='snapshot':values=tuple(map(int,values))
  rows.append(dict(kind=kind,values=values,position=position))
 return rows
def snapshot(node,arch):
 data=bytearray(256);order='>' if arch=='mips' else '<'
 for at,fmt,value in [(0,'I',0x7ff),(4,'I',1024),(16,'I',node['links']),(20,'I',node['uid']),
  (24,'I',node['gid']),(28,'H',node['mode']),(32,'Q',node['inode']),(40,'Q',node['size']),
  (48,'Q',node['blocks512']),(136,'I',0),(140,'I',2)]:struct.pack_into(order+fmt,data,at,value)
 for name,at in [('atime',64),('ctime',96),('mtime',112)]:
  struct.pack_into(order+'qI',data,at,node[name]['seconds'],node[name]['nanoseconds'])
 return bytes(data)
def verify(text,before_guarded,after_guarded,expected_volume,facts,arch,cut,clean=False):
 require(arch in ('x86_64','i386','mips') and 1<=cut<=20,'profile/cut admission')
 before=extract_volume(before_guarded);after=extract_volume(after_guarded)
 require(len(expected_volume)==len(before) and after==expected_volume,'complete recovered disk differs')
 require(after_guarded==before_guarded[:facts['origin']*512]+expected_volume+before_guarded[-facts['suffix_sectors']*512:],'guarded disk differs')
 if clean:require(before==expected_volume and before_guarded==after_guarded,'clean reboot changed disk')
 rows=records(text);cursor=0
 def take(kind):
  nonlocal cursor
  require(cursor<len(rows) and rows[cursor]['kind']==kind,'missing/out-of-order '+kind)
  row=rows[cursor];cursor+=1;return row
 take('begin');take('owner')
 io=[]
 while cursor<len(rows) and rows[cursor]['kind']=='io':io.append(take('io')['values'])
 report=take('recovered');r=report['values'];retired=take('retired');storage=take('storage');credentials=take('credentials');user=take('user')
 j=facts['journal_first'];home=facts['nodes']['child']['block'];origin=facts['origin']
 recipe=[]
 def flush():recipe.append((len(recipe)+1,'flush',0,0,0,0))
 def write(block,payload):recipe.append((len(recipe)+1,'write',origin+block*2,1024,checksum(0xffffffff,payload),0))
 flush()
 nonempty=not clean and 11<=cut<=16
 dirty=not clean and 9<=cut<=18
 if nonempty:
  write(1,before[(j+2)*1024:(j+3)*1024]);write(home,before[(j+3)*1024:(j+4)*1024]);flush()
  write(j,expected_volume[j*1024:(j+1)*1024]);flush()
 if dirty:write(1,expected_volume[1024:2048]);flush()
 require(io==recipe,'recovery I/O differs from exact completion sequence')
 writes=sum(row[1]=='write' for row in recipe);flushes=len(recipe)-writes
 sequence=struct.unpack_from('>I',expected_volume,j*1024+24)[0]
 require((r[0],r[1],r[2],r[3],r[5],r[6],r[7])==(int(not dirty),int(not nonempty),2 if nonempty else 0,6,writes,flushes,sequence),'recovery report accounting')
 require(r[4]>0 and storage['values'][0]>r[4],'recovery/mount read accounting')
 native_lines=text.splitlines(keepends=True);image=[];loaded=[]
 image_pattern=re.compile(r'OK_NATIVE_IMAGE personality=linux source=(firmware|linker) pages=([1-9][0-9]*) physical_first=(0x[0-9a-f]{16}) physical_last=(0x[0-9a-f]{16}) owner=retained\r?\n')
 for i,line in enumerate(native_lines):
  if 'OK_NATIVE_IMAGE' in line:
   match=image_pattern.fullmatch(line);require(match is not None,'native image full grammar/framing')
   source,pages,first,last=match.groups();first,last=int(first,16),int(last,16)
   require(source==('linker' if arch=='mips' else 'firmware') and int(pages)>0 and first%4096==last%4096==0 and last>=first,'native image profile/address identity')
   image.append(i)
  if 'OK_NATIVE scope=hardware init=' in line:
   require(re.fullmatch(r'OK_NATIVE scope=hardware init=loaded\r?\n',line) is not None,'native loaded grammar/framing');loaded.append(i)
 require(len(image)==len(loaded)==1 and storage['position']<image[0]<loaded[0]<credentials['position']<user['position'],'native Linux entry ordering')
 snapshots={}
 for label,node_label in [('child','child'),('root','root'),('seed','seed'),('other','other_owner'),('link','seed_link'),('leaf','leaf')]:
  values=take('snapshot')['values'];require(values[0]==label,'snapshot identity/order')
  node=inode_metadata(expected_volume,facts['nodes'][node_label]['inode'])
  require(bytes.fromhex(values[1])==snapshot(node,arch),'public statx full wire snapshot '+label)
  snapshots[label]=node
 require(snapshots['child']['mode']==(0o42750 if cut>=11 else 0o40755),'old/new cut inode semantics')
 take('fsync_begin')
 for _ in range(2):
  value=take('io')['values'];require(value==(len(recipe)+1,'flush',0,0,0,0),'user fsync I/O');recipe.append(value)
 take('fsync_end');checks=take('user_pass')['values'][0];require(checks==4233,'complete public probe checks')
 final=take('pass')['values'];require(cursor==len(rows),'activity after final pass')
 require(final[0]>storage['values'][0] and final[1:]==(writes,flushes+2),'exit/reap runtime transport accounting')
 return dict(cut=cut,clean_reboot=clean,recovered_new_inode=cut>=11,checked_inodes=6,recovery_writes=writes,
  recovery_flushes=flushes,user_flushes=2,user_checks=checks,io=[list(v) for v in recipe],
  snapshots=snapshots,reads=dict(recovery=r[4],mounted=storage['values'][0],final=final[0]),journal_sequence=sequence,
  guarded_sha256=hashlib.sha256(after_guarded).hexdigest(),intermediate_payload_evidence='Write order/sector/length/status/CRC32C observations; intermediate superblock bytes are supported by pinned source review because whole-block CRC includes its stored checksum and has a common residue.',
  scope='Strict native transcript and exact whole guarded final disk oracle; execution bound separately. Intermediate payload byte identity is not independently established by CRC32C ledger.')
