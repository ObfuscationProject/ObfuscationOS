#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>

static void fail(const char *operation)
{
    printf("JBD2_NATIVE_FAIL linux-completion operation=%s errno=%d\n",operation,errno);
    for(;;)pause();
}
int main(void)
{
    mkdir("/dev",0755);mount("devtmpfs","/dev","devtmpfs",0,"");
    mknod("/dev/console",S_IFCHR|0600,makedev(5,1));
    int console=open("/dev/console",O_RDWR);
    if(console>=0){dup2(console,0);dup2(console,1);dup2(console,2);}
    setvbuf(stdout,NULL,_IONBF,0);
    struct utsname version;if(uname(&version))fail("uname");
    printf("LINUX_COMPLETION_BEGIN release=%s version=%s machine=%s\n",version.release,version.version,version.machine);
    mkdir("/proc",0755);mkdir("/sys",0755);mkdir("/mnt",0755);
    mount("proc","/proc","proc",0,"");mount("sysfs","/sys","sysfs",0,"");
    for(int i=0;access("/dev/vda",F_OK)&&i<100;++i)usleep(50000);
    if(mount("/dev/vda","/mnt","ext4",MS_RDONLY|MS_NOSUID|MS_NODEV|MS_NOEXEC,""))fail("readonly ext4 mount");
    int fd=open("/mnt/seed",O_RDONLY);if(fd<0)fail("seed open");
    struct stat st;
    if(fstat(fd,&st)||st.st_ino!=12||st.st_size!=4096||(st.st_mode&07777)!=0600||st.st_uid!=1000||st.st_gid!=1001)
        fail("recovered inode metadata");
    unsigned char bytes[4096];size_t done=0;
    while(done<sizeof(bytes)){ssize_t count=read(fd,bytes+done,sizeof(bytes)-done);if(count<=0)fail("seed read");done+=(size_t)count;}
    for(size_t i=0;i<sizeof(bytes);++i)if(bytes[i]!=(unsigned char)(i*17+29))fail("seed contents");
    if(close(fd))fail("seed close");
    if(umount("/mnt"))fail("readonly unmount");
    printf("LINUX_COMPLETION_PASS mode=600 uid=1000 gid=1001 bytes=4096 mount=readonly unmount=pass\n");
    for(;;)pause();
}
