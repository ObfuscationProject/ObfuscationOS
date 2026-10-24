#include "logging.h"
#include <errno.h>
#include <fcntl.h>
#include <ok/storage.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static int same(const struct stat *a,const struct stat *b)
{ return a->st_ino==b->st_ino && a->st_mode==b->st_mode && a->st_uid==b->st_uid && a->st_gid==b->st_gid && a->st_nlink==b->st_nlink && a->st_size==b->st_size; }
static int directory(int fd,int private)
{
    struct stat s;
    if(fstat(fd,&s)<0) return -1;
    if(!S_ISDIR(s.st_mode)||s.st_uid||s.st_gid||(s.st_mode&07022)||(private&&(s.st_mode&07777)!=0700)) { errno=EACCES; return -1; }
    return ok_sync_persistent(fd);
}
static int regular(const struct stat *s)
{
    if(!S_ISREG(s->st_mode)||(s->st_mode&07777)!=0600||s->st_uid||s->st_gid||s->st_nlink!=1||s->st_size<0||s->st_size>LG_LIMIT) { errno=EACCES; return -1; }
    return 0;
}
static int named(struct lg_store *s)
{
    struct stat a,b;
    if(fstat(s->file,&a)<0||fstatat(s->directory,LG_CURRENT,&b,AT_SYMLINK_NOFOLLOW)<0||regular(&a)<0) return -1;
    if(!same(&a,&b)||!same(&a,&s->identity)) { errno=EIO; return -1; }
    return 0;
}
void lg_store_reset(struct lg_store *s) { *s=(struct lg_store){.directory=-1,.file=-1}; }
int lg_store_close(struct lg_store *s)
{
    int failed=0,fd=s->file; s->file=-1; s->ready=0;
    if(fd>=0&&close(fd)<0) failed=1;
    fd=s->directory; s->directory=-1;
    if(fd>=0&&close(fd)<0) failed=1;
    return failed?-1:0;
}
/* No truncation, repair or unlink occurs during inspection. Both files are
 * bounded and their opened/named identities must still agree after reading. */
static int inspect(int dir,const char *name,uint64_t *first,uint64_t *last,struct stat *identity)
{
    unsigned char bytes[LG_LIMIT+1]; size_t used=0; struct stat before,after,path; int result=-1;
    int fd=openat(dir,name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
    *first=*last=0;
    if(fd<0) return errno==ENOENT?2:-1;
    if(fstat(fd,&before)<0||regular(&before)<0||ok_sync_persistent(fd)<0) goto done;
    while(used<sizeof(bytes)) {
        ssize_t n=read(fd,bytes+used,sizeof(bytes)-used);
        if(n<0&&errno==EINTR) continue;
        if(n<0) goto done;
        if((size_t)n>sizeof(bytes)-used) { errno=EIO; goto done; }
        if(!n) break;
        used+=(size_t)n;
    }
    if(used!=(size_t)before.st_size) { errno=EIO; goto done; }
    result=lg_scan(bytes,used,first,last);
    if(result<0) { errno=EIO; goto done; }
    if(fstat(fd,&after)<0||fstatat(dir,name,&path,AT_SYMLINK_NOFOLLOW)<0) { result=-1; goto done; }
    if(!same(&before,&after)||!same(&before,&path)) { errno=EIO; result=-1; goto done; }
    *identity=before;
done:
    { int saved=errno; if(close(fd)<0) result=-1; else errno=saved; }
    return result;
}
static int append_bytes(struct lg_store *s,const unsigned char *bytes,size_t length)
{
    size_t used=0;unsigned interruptions=0;
    while(used<length) {
        size_t offset=(size_t)s->identity.st_size+used;
        size_t chunk=1024-offset%1024;
        if(chunk>length-used) chunk=length-used;
        ssize_t count=write(s->file,bytes+used,chunk);
        if(count<0&&errno==EINTR&&++interruptions<=16) continue;
        if(count<=0||(size_t)count>chunk) {if(count>=0) errno=EIO;return -1;}
        used+=(size_t)count;
    }
    s->identity.st_size+=(off_t)length;return named(s);
}
static int create_current(struct lg_store *s)
{
    unsigned char header[33];size_t length=lg_base(s->sequence,header);
    s->file=openat(s->directory,LG_CURRENT,O_WRONLY|O_APPEND|O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC,0600);
    if(s->file<0) return -1;
    if(fstat(s->file,&s->identity)<0||regular(&s->identity)<0||s->identity.st_size||named(s)<0||
       append_bytes(s,header,length)<0||ok_sync_persistent(s->file)<0||ok_sync_persistent(s->directory)<0) return -1;
    return 0;
}
static int rotate(struct lg_store *s)
{
    struct stat previous; uint64_t first,last;
    if(named(s)<0||ok_sync_persistent(s->file)<0) return -1;
    /* Close every archive/current hold before replacement. Unsupported external
     * retained victims can make subsequent mutations busy; no retry hides it. */
    if(inspect(s->directory,LG_PREVIOUS,&first,&last,&previous)<0) return -1;
    int fd=s->file; s->file=-1;
    if(close(fd)<0) return -1;
    if(renameat(s->directory,LG_CURRENT,s->directory,LG_PREVIOUS)<0||ok_sync_persistent(s->directory)<0) return -1;
    return create_current(s);
}
int lg_store_open(struct lg_store *s)
{
    int root=-1,var=-1,status,previous,saved; uint64_t cf=0,cl=0,pf=0,pl=0; struct stat p;
    lg_store_reset(s);
    root=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(root<0||directory(root,0)<0) goto fail;
    var=openat(root,"var",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(var<0||directory(var,0)<0) goto fail;
    s->directory=openat(var,"log",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(s->directory<0||directory(s->directory,1)<0) goto fail;
    if(close(var)<0) {var=-1;goto fail;} var=-1;
    if(close(root)<0) {root=-1;goto fail;} root=-1;
    previous=inspect(s->directory,LG_PREVIOUS,&pf,&pl,&p);
    if(previous<0) goto fail;
    status=inspect(s->directory,LG_CURRENT,&cf,&cl,&s->identity);
    if(status<0) goto fail;
    if(cf&&pl>=cf) {errno=EIO;goto fail;}
    s->sequence=cl>pl?cl:pl;
    if(s->sequence==UINT64_MAX) {errno=EOVERFLOW;goto fail;}
    if(status==2) {if(create_current(s)<0) goto fail;}
    else {
        s->file=openat(s->directory,LG_CURRENT,O_WRONLY|O_APPEND|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
        if(s->file<0||named(s)<0) goto fail;
        /* Old-format partial-only files, or a cut checkpoint publication,
         * cannot replace the only surviving sequence history. Preserve both. */
        if(status==1&&cl<pl) {errno=EIO;goto fail;}
        if(status==1&&rotate(s)<0) goto fail;
    }
    s->ready=1; return 0;
fail:
    saved=errno; if(var>=0) close(var); if(root>=0) close(root); lg_store_close(s); errno=saved; return -1;
}
int lg_store_append(struct lg_store *s,uint64_t now,const struct ok_ucred *peer,
                    const unsigned char *payload,size_t size,uint64_t *sequence)
{
    unsigned char bytes[LG_RECORD]; size_t length;
    if(!s->ready||s->sequence==UINT64_MAX) {errno=EOVERFLOW;return -1;}
    length=lg_record(s->sequence+1,now,peer,payload,size,bytes);
    if(!length) {errno=EINVAL;return -1;}
    if(directory(s->directory,1)<0||named(s)<0) goto fail;
    if((size_t)s->identity.st_size+length>LG_LIMIT&&rotate(s)<0) goto fail;
    if(append_bytes(s,bytes,length)<0) goto fail;
    if(named(s)<0||ok_sync_persistent(s->file)<0||ok_sync_persistent(s->directory)<0) goto fail;
    ++s->sequence; *sequence=s->sequence; return 0;
fail:
    /* Bytes/publication may already be durable. Never acknowledge uncertainty;
     * preserve them for bounded restart inspection and supervised backoff. */
    s->ready=0; return -1;
}
