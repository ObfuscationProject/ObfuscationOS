#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>
#ifndef OK_MOUNTED_NEIGHBOR_MODE
#define OK_MOUNTED_NEIGHBOR_MODE 0644
#endif

static void fail(const char *operation)
{
    printf("JBD2_NATIVE_FAIL linux-transaction operation=%s errno=%d\n",operation,errno);
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
    printf("LINUX_TRANSACTION_BEGIN release=%s version=%s machine=%s\n",version.release,version.version,version.machine);
    mkdir("/proc",0755);mkdir("/sys",0755);mkdir("/mnt",0755);
    mount("proc","/proc","proc",0,"");mount("sysfs","/sys","sysfs",0,"");
    for(int i=0;access("/dev/vda",F_OK)&&i<100;++i)usleep(50000);
    if(mount("/dev/vda","/mnt","ext4",MS_RDONLY|MS_NOSUID|MS_NODEV|MS_NOEXEC,""))fail("readonly ext4 mount");
    int fd=open("/mnt/seed",O_RDONLY);if(fd<0)fail("seed open");
    struct stat st;
    if(fstat(fd,&st)||st.st_ino!=12||st.st_size!=4096||(st.st_mode&07777)!=0640||st.st_uid!=2000||st.st_gid!=2001)
        fail("recovered inode metadata");
    unsigned char bytes[4096];size_t done=0;
    while(done<sizeof(bytes)){ssize_t count=read(fd,bytes+done,sizeof(bytes)-done);if(count<=0)fail("seed read");done+=(size_t)count;}
    for(size_t i=0;i<sizeof(bytes);++i)if(bytes[i]!=(unsigned char)(i*17+29))fail("seed contents");
    if(close(fd))fail("seed close");
    for(int index=0;index<4;++index)
    {
        char path[64];snprintf(path,sizeof(path),"/mnt/other%d",index);fd=open(path,O_RDONLY);if(fd<0)fail("other open");
        const unsigned expected_mode=index==3?0604:OK_MOUNTED_NEIGHBOR_MODE;
        if(fstat(fd,&st)||st.st_ino!=(unsigned long)(13+index)||st.st_size!=20||(st.st_mode&07777)!=expected_mode||
           st.st_uid!=(index==3?5000U:0U)||st.st_gid!=(index==3?6000U:0U))fail("other/neighbor metadata");
        char payload[20];if(read(fd,payload,sizeof(payload))!=(ssize_t)sizeof(payload))fail("other contents read");
        const char wanted[]="mounted fixture data";
        for(size_t byte=0;byte<sizeof(payload);++byte)if(payload[byte]!=wanted[byte])fail("other contents");
        if(close(fd))fail("other close");
    }
    if(umount("/mnt"))fail("readonly unmount");
    printf("LINUX_MOUNTED_PASS repeated=2 inode12=640:2000:2001 inode16=604:5000:6000 neighbors=checked mount=readonly unmount=pass\n");
    for(;;)pause();
}
