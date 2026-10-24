#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include "../chmod_fixture.h"
#include "../chmod_probe_log.h"

static unsigned checks;
static void fail(unsigned line)
{
    unsigned error=(unsigned)errno;
    chmod_probe_text("LINUX_CHMOD_MUSL_FAIL line="); chmod_probe_unsigned(line);
    chmod_probe_text(" errno="); chmod_probe_unsigned(error);
    chmod_probe_text(" checks="); chmod_probe_unsigned(checks); chmod_probe_text("\n");
    exit(1);
}
#define CHECK(x) do { ++checks; if (!(x)) fail(__LINE__); } while (0)
_Static_assert(sizeof(struct statx)==256,"statx observation layout");
_Static_assert(sizeof(time_t)==8,"musl time64");
static long mode_at(int fd,const char *path,unsigned mode,unsigned flags)
{
    return syscall(SYS_fchmodat2,(long)fd,(long)path,(long)mode,(long)flags);
}
static struct statx query(int fd,const char *path,unsigned flags)
{
    struct statx result;
    memset(&result,0xa5,sizeof result);
    CHECK(syscall(SYS_statx,(long)fd,(long)path,(long)flags,(long)CHMOD_BASIC_MASK,(long)&result)==0);
    CHECK(result.stx_mask==CHMOD_BASIC_MASK && result.stx_ino && result.stx_ctime.tv_nsec<1000000000u);
    return result;
}
static void changed(const struct statx *before,const struct statx *after,unsigned mode,struct timespec floor)
{
    struct timespec now; CHECK(clock_gettime(CLOCK_REALTIME,&now)==0);
    CHECK((after->stx_mode&07777)==mode && (after->stx_mode&S_IFMT)==(before->stx_mode&S_IFMT));
    CHECK(after->stx_uid==before->stx_uid && after->stx_gid==before->stx_gid);
    CHECK(after->stx_ino==before->stx_ino && after->stx_nlink==before->stx_nlink);
    CHECK(after->stx_size==before->stx_size && after->stx_blocks==before->stx_blocks);
    CHECK(!memcmp(&before->stx_atime,&after->stx_atime,sizeof before->stx_atime));
    CHECK(!memcmp(&before->stx_mtime,&after->stx_mtime,sizeof before->stx_mtime));
    CHECK(after->stx_ctime.tv_sec>=floor.tv_sec && after->stx_ctime.tv_sec<=now.tv_sec);
    if(after->stx_ctime.tv_sec==floor.tv_sec) CHECK(after->stx_ctime.tv_nsec>=(unsigned long)floor.tv_nsec);
    if(after->stx_ctime.tv_sec==now.tv_sec) CHECK(after->stx_ctime.tv_nsec<=(unsigned long)now.tv_nsec);
}
static struct timespec now(void)
{
    struct timespec value; CHECK(clock_gettime(CLOCK_REALTIME,&value)==0); return value;
}
static void denied(long value,int expected)
{
    CHECK(value==-1 && errno==expected);
}
int main(void)
{
    CHECK(getuid()==1000 && geteuid()==1000 && getgid()==1000 && getegid()==1000);
    struct statx file=query(AT_FDCWD,CHMOD_FILE,0); CHECK((file.stx_mode&07777)==0600);
    CHECK(file.stx_uid==1000 && file.stx_gid==1000);
    struct timespec floor=now(); CHECK(chmod(CHMOD_FILE,04754)==0);
    struct statx after=query(AT_FDCWD,CHMOD_FILE,0); changed(&file,&after,04754,floor);
    file=after; floor=now(); CHECK(chmod(CHMOD_FILE,04754)==0); // Same-mode change still samples ctime.
    after=query(AT_FDCWD,CHMOD_FILE,0); changed(&file,&after,04754,floor);
    int fd=open(CHMOD_FILE,O_RDONLY|O_CLOEXEC); CHECK(fd>=0);
    CHECK(lseek(fd,3,SEEK_SET)==3); int flags=fcntl(fd,F_GETFL); CHECK(flags>=0);
    file=after; floor=now(); CHECK(fchmod(fd,06750)==0);
    after=query(fd,"",CHMOD_EMPTY_PATH); changed(&file,&after,06750,floor);
    CHECK(lseek(fd,0,SEEK_CUR)==3 && fcntl(fd,F_GETFL)==flags && fcntl(fd,F_GETFD)==FD_CLOEXEC);
    CHECK(mode_at(fd,"",0610,CHMOD_EMPTY_PATH|AT_SYMLINK_NOFOLLOW)==0);
    CHECK((query(AT_FDCWD,CHMOD_ALIAS,0).stx_mode&07777)==0610);
    CHECK(fchmodat(-999,CHMOD_FILE,0640,0)==0);
    CHECK(fchmodat(CHMOD_DIR_FD,"child",0601,0)==0);
    CHECK((query(CHMOD_DIR_FD,"child",0).stx_mode&07777)==0601);
    CHECK(fchmodat(CHMOD_DIR_FD,"child",0701,AT_SYMLINK_NOFOLLOW)==0);
    CHECK((query(CHMOD_DIR_FD,"child",0).stx_mode&07777)==0701);
    struct statx link=query(AT_FDCWD,CHMOD_LINK,AT_SYMLINK_NOFOLLOW);
    denied(fchmodat(AT_FDCWD,CHMOD_LINK,0600,AT_SYMLINK_NOFOLLOW),EOPNOTSUPP);
    struct statx link_after=query(AT_FDCWD,CHMOD_LINK,AT_SYMLINK_NOFOLLOW);
    CHECK(!memcmp(&link,&link_after,sizeof link));
    CHECK(chmod(CHMOD_LINK,0644)==0); CHECK((query(fd,"",CHMOD_EMPTY_PATH).stx_mode&07777)==0644);
    denied(mode_at(fd,0,0600,CHMOD_EMPTY_PATH),EFAULT);
    denied(mode_at(-999,(const char *)1,0600,0x80000000u),EINVAL);
    denied(mode_at(-999,"child",0600,0),EBADF);
    denied(mode_at(fd,"child",0600,0),ENOTDIR);
    denied(mode_at(AT_FDCWD,"",0600,0),ENOENT);
    denied(mode_at(-999,"",0600,CHMOD_EMPTY_PATH),EBADF);
    denied(mode_at(AT_FDCWD,CHMOD_MISSING,0600,0),ENOENT);
    denied(chmod(CHMOD_PROBE,0600),EPERM);
    CHECK(fchmod(CHMOD_HELD_FD,0602)==0);
    struct statx held=query(CHMOD_HELD_FD,"",CHMOD_EMPTY_PATH); CHECK(held.stx_nlink==0 && (held.stx_mode&07777)==0602);
    CHECK(mode_at(AT_FDCWD,"",0000,CHMOD_EMPTY_PATH)==0);
    CHECK(mode_at(AT_FDCWD,"",0700,CHMOD_EMPTY_PATH)==0);
    struct statx cwd=query(AT_FDCWD,"",CHMOD_EMPTY_PATH); CHECK(cwd.stx_nlink==0 && (cwd.stx_mode&07777)==0700);
    unsigned char *pages=mmap(0,CHMOD_PAGE_SIZE*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(pages!=MAP_FAILED); CHECK(mprotect(pages+CHMOD_PAGE_SIZE,CHMOD_PAGE_SIZE,PROT_NONE)==0);
    pages[CHMOD_PAGE_SIZE-1]='x'; denied(mode_at(AT_FDCWD,(char *)pages+CHMOD_PAGE_SIZE-1,0600,0),EFAULT);
    CHECK(munmap(pages,CHMOD_PAGE_SIZE*2)==0);
    CHECK(fsync(fd)==0 && fsync(CHMOD_DIR_FD)==0);
    CHECK(close(fd)==0); denied(fchmod(fd,0600),EBADF);
    struct statx final_file=query(AT_FDCWD,CHMOD_FILE,0);
    struct statx final_child=query(CHMOD_DIR_FD,"child",0);
    struct statx final_dir=query(CHMOD_DIR_FD,"",CHMOD_EMPTY_PATH);
    struct statx final_link=query(AT_FDCWD,CHMOD_LINK,AT_SYMLINK_NOFOLLOW);
    CHECK((final_file.stx_mode&07777)==0644 && (final_child.stx_mode&07777)==0701);
    chmod_probe_snapshot("file",&final_file); chmod_probe_snapshot("child",&final_child);
    chmod_probe_snapshot("directory",&final_dir); chmod_probe_snapshot("symlink",&final_link);
    CHECK(close(CHMOD_HELD_FD)==0 && close(CHMOD_DIR_FD)==0 && chdir("/")==0);
    chmod_probe_text("LINUX_CHMOD_MUSL_PASS checks="); chmod_probe_unsigned(checks);
    chmod_probe_text(" authority=uid1000 mode=maintained\n");
    return 0;
}
