"""Actual home.c hosted controls with injected filesystem and credential edges.

The modeled namespace and persistence calls are not guest or durable-media tests.
"""
from pathlib import Path
import ctypes
import errno
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = r'''
#include "home.h"
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

enum { ROOT=10, HOMES=11, CHILD=12, ETC=13, CONFIG=14 };
static struct stat nodes[5], named;
static int child_exists, live[5], bad, operation, fail_at, mismatch, gid_done, uid_done, entered, mask_done;
static int chmod_effect, chown_effect, named_change, after_sync_change;
static int current_uid, current_gid, read_offset, manifest_missing;
static char events[1024], manifest[4097];
static unsigned event_count;
static void event(char value) { if (event_count+1 < sizeof(events)) events[event_count++]=value; else bad=1; }
static int step(char value) { event(value); ++operation; if (operation == fail_at) { errno=EIO; return -1; } return 0; }
static int slot(int fd) { if (fd < ROOT || fd > CONFIG) { bad=1; return 0; } return fd-ROOT; }
static void check(int value) { if (!value) bad=1; }
void home_reset(void)
{
 memset(nodes,0,sizeof(nodes)); memset(live,0,sizeof(live)); memset(events,0,sizeof(events));
 bad=operation=fail_at=mismatch=gid_done=uid_done=entered=mask_done=0;
 current_uid=current_gid=read_offset=manifest_missing=0; child_exists=0; event_count=0;
 chmod_effect=chown_effect=1; named_change=after_sync_change=0;
 nodes[0]=(struct stat){.st_mode=S_IFDIR|0755,.st_uid=0,.st_gid=0,.st_ino=1,.st_nlink=2};
 nodes[1]=(struct stat){.st_mode=S_IFDIR|0700,.st_uid=0,.st_gid=0,.st_ino=2,.st_nlink=2};
 nodes[2]=(struct stat){.st_mode=S_IFDIR|0700,.st_uid=0,.st_gid=0,.st_ino=3,.st_nlink=2};
 nodes[3]=(struct stat){.st_mode=S_IFDIR|0755,.st_uid=0,.st_gid=0,.st_ino=4,.st_nlink=2};
 nodes[4]=(struct stat){.st_mode=S_IFREG|0600,.st_uid=0,.st_gid=0,.st_ino=5,.st_nlink=1};
 strcpy(manifest,"OK_SERVICE_MANIFEST 2\nservice base simple /bin/base - 0 0\n");
 nodes[4].st_size=(off_t)strlen(manifest);named=nodes[2];
}
void home_fail(int value) { fail_at=value; }
void home_node(int which,unsigned mode,unsigned uid,unsigned gid,int exists)
{ nodes[which].st_mode=mode;nodes[which].st_uid=uid;nodes[which].st_gid=gid;if(which==2){child_exists=exists;named=nodes[2];} }
void home_effects(int cm,int co,int nm,int sync) { chmod_effect=cm;chown_effect=co;named_change=nm;after_sync_change=sync; }
void home_mismatch(int value) { mismatch=value; }
void home_manifest(const char *value,int missing) { strcpy(manifest,value);nodes[4].st_size=(off_t)strlen(value);manifest_missing=missing; }
const char *home_events(void) { return events; }
int home_bad(void) { return bad; }
int home_live(void) { return live[0]+live[1]+live[2]+live[3]+live[4]; }
int home_operations(void) { return operation; }
unsigned home_mode(unsigned index) { return nodes[index].st_mode; }
unsigned home_uid(unsigned index) { return nodes[index].st_uid; }
unsigned home_gid(unsigned index) { return nodes[index].st_gid; }
static int opened(int fd) { check(!live[slot(fd)]);live[slot(fd)]=1;return fd; }
int home_open(const char *path,int flags,...)
{
 check((flags&(O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC))==(O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
 check((flags&O_ACCMODE)==O_RDONLY);
 if (!strcmp(path,"/")) { if(step('R'))return -1;return opened(ROOT); }
 check(!strcmp(path,"/etc"));if(step('E'))return -1;return opened(ETC);
}
int home_openat(int fd,const char *path,int flags,...)
{
 check(live[slot(fd)]);check((flags&(O_NOFOLLOW|O_CLOEXEC))==(O_NOFOLLOW|O_CLOEXEC));
 check((flags&O_ACCMODE)==O_RDONLY);
 if(fd==ROOT) {check(!strcmp(path,"home")&&(flags&O_DIRECTORY));if(step('H'))return -1;return opened(HOMES);}
 if(fd==HOMES) {check(!strcmp(path,"alice")&&(flags&O_DIRECTORY));if(step('C'))return -1;if(!child_exists){errno=ENOENT;return -1;}return opened(CHILD);}
 check(fd==ETC&&!strcmp(path,"services.conf")&&(flags&O_NONBLOCK));
 if(step('V'))return -1;if(manifest_missing){errno=ENOENT;return -1;}read_offset=0;return opened(CONFIG);
}
int home_close(int fd)
{ check(live[slot(fd)]);live[slot(fd)]=0;return step(fd==ROOT?'r':fd==HOMES?'h':fd==CHILD?'c':fd==ETC?'e':'v'); }
int home_fstat(int fd,struct stat *out)
{ check(live[slot(fd)]);if(step(fd==ROOT?'A':fd==HOMES?'B':fd==CHILD?'D':fd==ETC?'T':'F'))return -1;*out=nodes[slot(fd)];return 0; }
int home_fstatat(int fd,const char *name,struct stat *out,int flags)
{
 check(fd==HOMES&&live[1]&&!strcmp(name,"alice")&&flags==AT_SYMLINK_NOFOLLOW);
 if(step('N'))return -1;if(!child_exists){errno=ENOENT;return -1;}*out=nodes[2];
 if(named_change) { if(named_change==1)out->st_ino++;if(named_change==2)out->st_uid++;if(named_change==3)out->st_mode=S_IFLNK|0700; }
 return 0;
}
int home_fchmod(int fd,mode_t mode)
{ check(fd==HOMES&&live[1]&&mode==0755);if(step('M'))return -1;if(chmod_effect)nodes[1].st_mode=S_IFDIR|mode;return 0; }
int home_fchown(int fd,uid_t uid,gid_t gid)
{ check(fd==CHILD&&live[2]&&uid==1000&&gid==1000);if(step('O'))return -1;if(chown_effect){nodes[2].st_uid=uid;nodes[2].st_gid=gid;}return 0; }
int home_sync(int fd)
{ check((fd==CHILD||fd==HOMES)&&live[slot(fd)]);if(step(fd==CHILD?'S':'P'))return -1;if(fd==HOMES&&after_sync_change)nodes[2].st_ino++;return 0; }
long home_syscall3(long number,long fd,long pointer,long mode)
{ check(number==258&&fd==HOMES&&live[1]&&!strcmp((const char *)pointer,"alice")&&mode==0700);if(step('K'))return -EIO;if(child_exists)return -EEXIST;child_exists=1;return 0; }
long home_syscall1(long number,long value)
{
 if(number==81){check(live[2]&&value==CHILD&&gid_done&&uid_done&&!live[0]&&!live[1]);if(step('I'))return -EIO;entered=1;return 0;}
 check(number==95&&value==0077&&entered);if(step('U'))return -EIO;mask_done=1;return 0;
}
long home_ret(long result) { if(result<0){errno=(int)-result;return -1;}return result; }
int home_setresgid(gid_t r,gid_t e,gid_t s)
{ check(r==1000&&e==1000&&s==1000&&!live[0]&&!live[1]&&live[2]&&!uid_done);if(step('G'))return -1;gid_done=1;current_gid=1000;return 0; }
int home_setresuid(uid_t r,uid_t e,uid_t s)
{ check(r==1000&&e==1000&&s==1000&&!live[0]&&!live[1]&&live[2]&&gid_done);if(step('J'))return -1;uid_done=1;current_uid=1000;return 0; }
int home_getresgid(gid_t *r,gid_t *e,gid_t *s)
{ check(gid_done&&uid_done);if(step('g'))return -1;*r=*e=*s=current_gid;if(mismatch>=1&&mismatch<=3){if(mismatch==1)(*r)++;if(mismatch==2)(*e)++;if(mismatch==3)(*s)++;}return 0; }
int home_getresuid(uid_t *r,uid_t *e,uid_t *s)
{ check(gid_done&&uid_done);if(step('j'))return -1;*r=*e=*s=current_uid;if(mismatch>=4&&mismatch<=6){if(mismatch==4)(*r)++;if(mismatch==5)(*e)++;if(mismatch==6)(*s)++;}return 0; }
ssize_t home_read(int fd,void *buffer,size_t count)
{check(fd==CONFIG&&live[4]);if(step('L'))return -1;size_t remain=strlen(manifest)-(size_t)read_offset;if(count>remain)count=remain;memcpy(buffer,manifest+read_offset,count);read_offset+=(int)count;return (ssize_t)count;}
'''


class User(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char * 32), ('uid', ctypes.c_uint32), ('gid', ctypes.c_uint32),
                ('salt', ctypes.c_ubyte * 16), ('verifier', ctypes.c_ubyte * 32)]


class Users(ctypes.Structure):
    _fields_ = [('count', ctypes.c_uint32), ('entries', User * 16)]


class NativeLoginHomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-home-host-')
        temporary = Path(cls.directory.name)
        (temporary / 'ok/uapi').mkdir(parents=True)
        shutil.copyfile(ROOT / 'sdk/include/ok/storage.h', temporary / 'ok/storage.h')
        shutil.copyfile(ROOT / 'lib/okcrt/include/ok/syscall.h', temporary / 'ok/syscall.h')
        (temporary / 'ok/uapi/syscall.h').write_text('struct ok_mount_info;\n#define OK_SYS_MKDIRAT 258ULL\n#define OK_SYS_FCHDIR 81ULL\n#define OK_SYS_UMASK 95ULL\n')
        (temporary / 'backend.c').write_text(BACKEND)
        common = ['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                  '-fPIC', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-D_GNU_SOURCE',
                  '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(temporary),
                  '-I', str(ROOT / 'apps/login')]
        replacements = {'open':'home_open','openat':'home_openat','fstat':'home_fstat',
            'fstatat':'home_fstatat','close':'home_close','fchmod':'home_fchmod','fchown':'home_fchown',
            'read':'home_read','setresgid':'home_setresgid','setresuid':'home_setresuid',
            'getresgid':'home_getresgid','getresuid':'home_getresuid','ok_sync_persistent':'home_sync',
            'ok_syscall3':'home_syscall3','ok_syscall1':'home_syscall1','ok_syscall_ret':'home_ret'}
        objects = []
        for source, name in ((ROOT / 'apps/login/home.c','home'),(temporary / 'backend.c','backend'),
                             (ROOT / 'apps/login/accounts.c','accounts'),(ROOT / 'apps/login/password.c','password')):
            output = temporary / (name+'.o')
            defines = ['-D'+key+'='+value for key,value in replacements.items()] if name=='home' else []
            subprocess.run(common+defines+['-c',str(source),'-o',str(output)],check=True)
            objects.append(str(output))
        shared = temporary / 'home.so'
        subprocess.run(['cc','-shared','-fsanitize=undefined']+objects+['-o',str(shared)],check=True)
        cls.lib = ctypes.CDLL(str(shared),use_errno=True)
        cls.lib.ok_login_home_available.argtypes=[ctypes.POINTER(User)]
        cls.lib.ok_login_home_prepare.argtypes=[ctypes.POINTER(User)]
        cls.lib.ok_login_home_enter.argtypes=[ctypes.c_char_p,ctypes.c_uint32,ctypes.c_uint32]
        cls.lib.ok_login_user_next_uid.argtypes=[ctypes.POINTER(Users),ctypes.POINTER(ctypes.c_uint32)]
        cls.lib.home_events.restype=ctypes.c_char_p
        cls.lib.home_manifest.argtypes=[ctypes.c_char_p,ctypes.c_int]

    @classmethod
    def tearDownClass(cls): cls.directory.cleanup()

    def setUp(self):
        self.lib.home_reset()
        self.user=User(name=b'alice',uid=1000,gid=1000)

    def events(self): return self.lib.home_events().decode()
    def clean(self):
        self.assertEqual(self.lib.home_bad(),0,self.events())
        self.assertEqual(self.lib.home_live(),0,self.events())
    def prepare(self): return self.lib.ok_login_home_prepare(ctypes.byref(self.user))
    def available(self): return self.lib.ok_login_home_available(ctypes.byref(self.user))
    def enter(self): return self.lib.ok_login_home_enter(b'alice',1000,1000)
    def exact_child(self): self.lib.home_node(2,0o40700,1000,1000,1)

    def test_absent_preflight_never_creates_or_changes_ownership(self):
        self.assertEqual(self.available(),0)
        self.assertEqual(self.events(),'RAHBNhr')
        self.clean()
        for mode in (0o40700,0o100600,0o120777):
            self.lib.home_reset();self.lib.home_node(2,mode,0,0,1)
            self.assertEqual(self.available(),-1)
            self.assertEqual(ctypes.get_errno(),errno.EEXIST)
            self.assertNotIn('K',self.events());self.clean()

    def test_fresh_prepare_updates_parent_and_persists_child_then_parent(self):
        self.assertEqual(self.prepare(),0)
        self.assertEqual(self.events(),'RAHBBMBKCDODNSPDchr')
        self.assertEqual(self.lib.home_mode(1)&0o7777,0o755)
        self.assertEqual((self.lib.home_uid(1),self.lib.home_gid(1)),(0,0))
        self.assertEqual((self.lib.home_uid(2),self.lib.home_gid(2)),(1000,1000))
        self.clean()

    def test_resume_accepts_root_or_exact_owner_only(self):
        for uid,gid in ((0,0),(1000,1000)):
            self.lib.home_reset();self.lib.home_node(1,0o40755,0,0,1);self.lib.home_node(2,0o40700,uid,gid,1)
            self.assertEqual(self.prepare(),0)
            self.assertEqual('O' in self.events(),uid==0)
            self.assertNotIn('M',self.events());self.assertIn('SP',self.events());self.clean()

    def test_parent_type_owner_and_permissions_fail_closed(self):
        for which,mode,uid,gid in ((0,0o100755,0,0),(0,0o40777,0,0),(0,0o44755,0,0),
            (0,0o40755,1,0),(0,0o40755,0,1),(1,0o100700,0,0),(1,0o40777,0,0),
            (1,0o40750,0,0),(1,0o40755,1,0),(1,0o40755,0,1)):
            self.lib.home_reset();self.lib.home_node(which,mode,uid,gid,1)
            self.assertEqual(self.prepare(),-1,(which,oct(mode),uid,gid))
            self.assertNotIn('K',self.events());self.clean()

    def test_child_type_owner_mode_and_name_mismatch_refused(self):
        for mode,uid,gid in ((0o100700,0,0),(0o120700,0,0),(0o40755,0,0),
                             (0o44700,0,0),(0o40700,1001,1001),(0o40700,1000,0),(0o40700,0,1000)):
            self.lib.home_reset();self.lib.home_node(2,mode,uid,gid,1)
            self.assertEqual(self.prepare(),-1,(oct(mode),uid,gid));self.assertNotIn('S',self.events());self.clean()
        for mismatch in (1,2,3):
            self.lib.home_reset();self.lib.home_effects(1,1,mismatch,0)
            self.assertEqual(self.prepare(),-1);self.assertNotIn('S',self.events());self.clean()

    def test_successful_syscalls_without_expected_effect_and_posts_sync_changes_refuse(self):
        for effects in ((0,1,0,0),(1,0,0,0),(1,1,0,1)):
            self.lib.home_reset();self.lib.home_effects(*effects)
            self.assertEqual(self.prepare(),-1,effects);self.clean()

    def test_every_preflight_and_prepare_operation_failure_closes_all_handles(self):
        for operation in ('available','prepare'):
            self.lib.home_reset();self.assertEqual(getattr(self,operation)(),0)
            count=self.lib.home_operations()
            for failure in range(1,count+1):
                self.lib.home_reset();self.lib.home_fail(failure)
                with self.subTest(operation=operation,failure=failure):
                    self.assertEqual(getattr(self,operation)(),-1,self.events());self.clean()

    def test_enter_closes_privileged_parents_before_gid_uid_readbacks_and_chdir(self):
        self.exact_child();self.assertEqual(self.enter(),0)
        self.assertEqual(self.events(),'RAHBCD NhrGJgjIUc'.replace(' ',''));self.clean()

    def test_all_six_credential_readbacks_must_match_and_no_chdir_follows_failure(self):
        for mismatch in range(1,7):
            self.lib.home_reset();self.exact_child();self.lib.home_mismatch(mismatch)
            self.assertEqual(self.enter(),-1);self.assertNotIn('I',self.events());self.clean()
        self.lib.home_reset();self.exact_child();self.assertEqual(self.enter(),0)
        count=self.lib.home_operations()
        for failure in range(1,count+1):
            self.lib.home_reset();self.exact_child();self.lib.home_fail(failure)
            self.assertEqual(self.enter(),-1,(failure,self.events()));self.clean()
            if failure<=self.events().find('G')+1:self.assertNotIn('J',self.events())

    def test_enter_rejects_wrong_owner_mode_type_or_named_inode(self):
        for mode,uid,gid in ((0o40755,1000,1000),(0o100700,1000,1000),(0o40700,0,0),(0o40700,1000,1001)):
            self.lib.home_reset();self.lib.home_node(2,mode,uid,gid,1)
            self.assertEqual(self.enter(),-1);self.assertNotIn('G',self.events());self.clean()
        self.lib.home_reset();self.exact_child();self.lib.home_effects(1,1,1,0)
        self.assertEqual(self.enter(),-1);self.assertNotIn('G',self.events());self.clean()

    def test_principal_validation_precedes_any_open(self):
        for name,uid,gid in ((b'../alice',1000,1000),(b'',1000,1000),(b'Alice',1000,1000),
                             (b'alice',0,0),(b'alice',1000,1001),(b'alice',0xffffffff,0xffffffff)):
            self.lib.home_reset();self.user=User(name=name,uid=uid,gid=gid)
            self.assertEqual(self.prepare(),-1);self.assertEqual(self.events(),'');self.clean()
        self.assertEqual(self.lib.ok_login_home_available(None),-1)
        self.assertEqual(self.lib.ok_login_home_prepare(None),-1)

    def test_allocator_skips_user_uid_and_gid_and_service_uid_and_gid(self):
        users=Users(count=2);users.entries[0].uid=1000;users.entries[0].gid=1001
        users.entries[1].uid=1003;users.entries[1].gid=1006
        self.lib.home_manifest(b'OK_SERVICE_MANIFEST 2\nservice svc simple /bin/svc - 1002 1004\n',0)
        uid=ctypes.c_uint32(99)
        self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),ctypes.byref(uid)),0)
        self.assertEqual(uid.value,1005);self.clean()

    def test_allocator_manifest_malformed_untrusted_and_operation_failures_preserve_output(self):
        users=Users();uid=ctypes.c_uint32(99)
        for data in (b'',b'OK_SERVICE_MANIFEST 2\n',b'OK_SERVICE_MANIFEST 2\nservice svc simple /bin/svc - 4294967295 0\n',
                     b'OK_SERVICE_MANIFEST 2\nservice svc simple /bin/svc - 01000 0\n',b'garbage\n'):
            self.lib.home_reset();self.lib.home_manifest(data,0);uid.value=99
            self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),ctypes.byref(uid)),-1,data)
            self.assertEqual(uid.value,99);self.clean()
        for which,mode,owner in ((3,0o40777,0),(3,0o40755,1),(4,0o100666,0),(4,0o100600,1),(4,0o40600,0)):
            self.lib.home_reset();self.lib.home_node(which,mode,owner,0,1);uid.value=99
            self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),ctypes.byref(uid)),-1)
            self.assertEqual(uid.value,99);self.clean()
        self.lib.home_reset();self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),ctypes.byref(uid)),0)
        count=self.lib.home_operations()
        for failure in range(1,count+1):
            self.lib.home_reset();self.lib.home_fail(failure);uid.value=99
            self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),ctypes.byref(uid)),-1,(failure,self.events()))
            self.assertEqual(uid.value,99);self.clean()

    def test_allocator_invalid_arguments_full_registry_and_missing_manifest(self):
        users=Users(count=16);uid=ctypes.c_uint32(99)
        self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),ctypes.byref(uid)),-1)
        self.assertEqual(self.events(),'');self.assertEqual(uid.value,99)
        users.count=17
        self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),ctypes.byref(uid)),-1)
        self.assertEqual(uid.value,99)
        users.count=0
        self.assertEqual(self.lib.ok_login_user_next_uid(None,ctypes.byref(uid)),-1)
        self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),None),-1)
        self.lib.home_manifest(b'',1)
        self.assertEqual(self.lib.ok_login_user_next_uid(ctypes.byref(users),ctypes.byref(uid)),0)
        self.assertEqual(uid.value,1000);self.clean()


if __name__=='__main__': unittest.main()
