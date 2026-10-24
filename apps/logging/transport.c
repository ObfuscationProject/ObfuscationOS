#include "logging.h"
#include <errno.h>
#include <fcntl.h>
#include <ok/socket.h>
#include <ok/syscall.h>
#include <poll.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
int lg_clock(uint64_t *value)
{
    struct timespec now;
    if(clock_gettime(CLOCK_MONOTONIC,&now)<0) return -1;
    if(now.tv_sec<0||now.tv_nsec<0||now.tv_nsec>=1000000000||(uint64_t)now.tv_sec>(UINT64_MAX-999)/1000) {errno=EOVERFLOW;return -1;}
    *value=(uint64_t)now.tv_sec*1000+(uint64_t)now.tv_nsec/1000000; return 0;
}
static int same_socket(const struct stat *a,const struct stat *b)
{ return a->st_ino==b->st_ino&&a->st_mode==b->st_mode&&a->st_uid==b->st_uid&&a->st_gid==b->st_gid&&a->st_nlink==b->st_nlink; }
static int socket_metadata(const struct stat *s)
{
    /* Native pathname sockets use the Linux type encoding 0140000. */
    if((s->st_mode&0170000)!=0140000||(s->st_mode&07777)!=0600||s->st_uid||s->st_gid||s->st_nlink!=1) {errno=EACCES;return -1;}
    return 0;
}
static int protected_dir(int fd)
{
    struct stat s; if(fstat(fd,&s)<0) return -1;
    if(!S_ISDIR(s.st_mode)||s.st_uid||s.st_gid||(s.st_mode&07022)) {errno=EACCES;return -1;} return 0;
}
static int open_run(void)
{
    int root=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC),run=-1,error;
    if(root<0) return -1;
    if(protected_dir(root)<0) goto done;
    run=openat(root,"run",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(run>=0&&protected_dir(run)<0) {error=errno;close(run);run=-1;errno=error;}
 done:
    error=errno; if(close(root)<0) {if(run>=0) close(run);return -1;} errno=error;return run;
}
static struct ok_sockaddr_un address(void)
{ struct ok_sockaddr_un a={.family=OK_AF_UNIX};memcpy(a.path,LG_PATH,sizeof(LG_PATH));return a; }
static int connect_socket(int fd)
{ struct ok_sockaddr_un a=address();return ok_connect(fd,&a,(ok_socklen_t)(2+sizeof(LG_PATH))); }
static int new_socket(void) {return ok_socket(OK_AF_UNIX,OK_SOCK_STREAM|OK_SOCK_NONBLOCK|OK_SOCK_CLOEXEC,0);}
void lg_server_reset(struct lg_server *s)
{ *s=(struct lg_server){.listener=-1,.run=-1,.client={.fd=-1}}; }
static int drop(struct lg_client *c) {int fd=c->fd;c->fd=-1;return fd<0?0:close(fd);}
int lg_server_close(struct lg_server *s)
{
    int failed=drop(&s->client)<0,fd=s->listener;s->listener=-1;
    if(fd>=0&&close(fd)<0) failed=1;
    fd=s->run;s->run=-1;if(fd>=0&&close(fd)<0) failed=1;
    /* A stale name is intentionally left for checked restart. */
    return failed?-1:0;
}
int lg_server_open(struct lg_server *s)
{
    struct stat before,after; uint64_t start,end; int probe=-1,error,bound;
    lg_server_reset(s);
    if(geteuid()||getegid()) {errno=EPERM;return -1;}
    if(lg_clock(&start)<0) return -1;
    if(start>UINT64_MAX-LG_DEADLINE) {errno=EOVERFLOW;return -1;}
    s->run=open_run();if(s->run<0) goto fail;
    if(!fstatat(s->run,"logd.sock",&before,AT_SYMLINK_NOFOLLOW)) {
        if(socket_metadata(&before)<0) goto fail;
        probe=new_socket();if(probe<0) goto fail;
        int result=connect_socket(probe);error=errno;
        if(close(probe)<0) {probe=-1;goto fail;} probe=-1;
        /* Success and full backlog both denote a live/contended listener. */
        if(result>=0||error!=ECONNREFUSED) {errno=result>=0?EADDRINUSE:error;goto fail;}
        if(lg_clock(&end)<0||end<start||end-start>=LG_DEADLINE) {errno=EAGAIN;goto fail;}
        if(fstatat(s->run,"logd.sock",&after,AT_SYMLINK_NOFOLLOW)<0||socket_metadata(&after)<0) goto fail;
        if(!same_socket(&before,&after)) {errno=EIO;goto fail;}
        if(unlinkat(s->run,"logd.sock",0)<0) goto fail;
    } else if(errno!=ENOENT) goto fail;
    s->listener=new_socket();if(s->listener<0) goto fail;
    struct ok_sockaddr_un a=address();
    long mask=ok_syscall_ret(ok_syscall1(OK_SYS_UMASK,0177));if(mask<0) goto fail;
    bound=ok_bind(s->listener,&a,(ok_socklen_t)(2+sizeof(LG_PATH)));error=errno;
    long restored=ok_syscall_ret(ok_syscall1(OK_SYS_UMASK,mask));
    if(bound<0||restored<0) {if(restored>=0) errno=error;goto fail;}
    if(fstatat(s->run,"logd.sock",&s->socket_identity,AT_SYMLINK_NOFOLLOW)<0||socket_metadata(&s->socket_identity)<0||ok_listen(s->listener,1)<0) goto fail;
    if(lg_clock(&end)<0||end<start||end-start>=LG_DEADLINE) {errno=EAGAIN;goto fail;}
    s->last=end;return 0;
fail:
    error=errno;if(probe>=0) close(probe);lg_server_close(s);errno=error;return -1;
}
static ssize_t receive(int fd,void *bytes,size_t size,int peek,int *invalid)
{
    struct ok_iovec vector={(uintptr_t)bytes,size};struct ok_msghdr message={0};
    message.vectors=(uintptr_t)&vector;message.vector_count=1;
    ssize_t count=ok_recvmsg(fd,&message,OK_MSG_DONTWAIT|(peek?OK_MSG_PEEK:0));
    *invalid=message.flags||message.control_length||(count>0&&(size_t)count>size);
    return count;
}
static ssize_t send_bytes(int fd,const void *bytes,size_t size)
{
    struct ok_iovec vector={(uintptr_t)bytes,size};struct ok_msghdr message={0};
    message.vectors=(uintptr_t)&vector;message.vector_count=1;
    return ok_sendmsg(fd,&message,OK_MSG_DONTWAIT|OK_MSG_NOSIGNAL);
}
static void reply(struct lg_client *c,uint64_t seq)
{
    static const char digits[]="0123456789abcdef";
    memcpy(c->reply,"OKL1 OK ",8);
    for(unsigned i=24;i>8;seq>>=4) c->reply[--i]=digits[seq&15];
    c->reply[24]='\n';c->reply_size=25;
}
static int budget(uint64_t deadline,uint64_t *last)
{
    uint64_t now;if(lg_clock(&now)<0) return -1;
    if(now<*last) {errno=EOVERFLOW;return -1;} *last=now;
    if(now>=deadline) {errno=EAGAIN;return -1;} return 0;
}
int lg_server_step(struct lg_server *s,struct lg_store *store,uint64_t now)
{
    struct lg_client *c=&s->client;
    if(now<s->last) {errno=EOVERFLOW;return -1;} s->last=now;
    if(c->fd>=0&&now>=c->deadline) return drop(c);
    if(c->fd<0) {
        if(now>UINT64_MAX-LG_DEADLINE) {errno=EOVERFLOW;return -1;}
        int fd=ok_accept4(s->listener,0,0,OK_SOCK_NONBLOCK|OK_SOCK_CLOEXEC);
        if(fd<0) return errno==EINTR||errno==EAGAIN||errno==EMFILE||errno==ENFILE?0:-1;
        *c=(struct lg_client){.fd=fd,.deadline=now+LG_DEADLINE};
        ok_socklen_t length=sizeof(c->peer);
        if(ok_getsockopt(fd,OK_SOL_SOCKET,OK_SO_PEERCRED,&c->peer,&length)<0||length!=sizeof(c->peer)||c->peer.pid<=0||c->peer.uid) return drop(c);
    }
    if(c->reply_size) {
        if(budget(c->deadline,&s->last)<0) return errno==EAGAIN?drop(c):-1;
        ssize_t count=send_bytes(c->fd,c->reply+c->sent,c->reply_size-c->sent);
        if(count<0&&(errno==EINTR||errno==EAGAIN)) return 0;
        if(count<=0) return drop(c);
        if((size_t)count>c->reply_size-c->sent) {errno=EIO;return -1;}
        c->sent+=(size_t)count;
        return c->sent==c->reply_size?drop(c):0;
    }
    size_t payload=0;int parsed=lg_request(c->request,c->used,&payload),invalid=0;ssize_t count;
    if(parsed<0) return drop(c);
    if(!parsed) {
        count=receive(c->fd,c->request+c->used,sizeof(c->request)-c->used,0,&invalid);
        if(count<0&&(errno==EINTR||errno==EAGAIN)&&!invalid) return 0;
        if(invalid||count<=0) return drop(c);
        c->used+=(size_t)count;
        parsed=lg_request(c->request,c->used,&payload);
        if(parsed<0) return drop(c);
        if(!parsed) return 0;
    }
    /* Reject an already-buffered suffix without treating stream packets as
     * framing. Bytes arriving after this dispatch are never another request. */
    unsigned char extra;count=receive(c->fd,&extra,1,1,&invalid);
    if(invalid||count>0||(count<0&&errno!=EAGAIN&&errno!=EINTR)) return drop(c);
    if(count<0&&errno==EINTR) return 0;
    /* Only a complete validated frame earns a separate, fixed persistence and
     * reply budget. Fragment arrival never extends admission. */
    if(budget(c->deadline,&s->last)<0) return errno==EAGAIN?drop(c):-1;
    if(s->last>UINT64_MAX-LG_PERSISTENCE_DEADLINE) {errno=EOVERFLOW;return -1;}
    c->deadline=s->last+LG_PERSISTENCE_DEADLINE;
    uint64_t sequence;
    if(lg_store_append(store,s->last,&c->peer,c->request+LG_HEADER,payload,&sequence)<0) return -1;
    /* Native storage is synchronous. A late durable write may survive, but it
     * must not prepare an acknowledgement after this fixed budget expires. */
    if(budget(c->deadline,&s->last)<0) return errno==EAGAIN?drop(c):-1;
    reply(c,sequence);return 0;
}
int lg_notify(int descriptor)
{
    ssize_t count;unsigned attempts=0;
    if(descriptor<3||descriptor>=32) {errno=EINVAL;return -1;}
    do {count=write(descriptor,"R",1);} while(count<0&&errno==EINTR&&++attempts<16);
    int error=errno,status=close(descriptor);
    if(count!=1) {errno=count<0?error:EIO;return -1;}
    return status;
}
int lg_service_open(struct lg_server *server,struct lg_store *store,int ready)
{
    uint64_t start,end;int error;
    if(lg_clock(&start)<0||lg_store_open(store)<0||lg_server_open(server)<0||lg_clock(&end)<0) goto fail;
    if(end<start||end-start>=2500) {errno=EAGAIN;goto fail;}
    return lg_notify(ready);
fail:
    error=errno;if(close(ready)<0) return -1;errno=error;return -1;
}
int lg_exchange(const unsigned char *payload,size_t size,uint64_t *sequence)
{
    unsigned char frame[LG_FRAME],response[26];size_t sent=0,used=0;
    int length=lg_frame(payload,size,frame),fd=-1,run=-1,status=-1,error;uint64_t start,last,deadline;struct stat before,after;
    if(length<0) {errno=EINVAL;return -1;}
    if(geteuid()) {errno=EPERM;return -1;}
    if(lg_clock(&start)<0) return -1;
    if(start>UINT64_MAX-LG_DEADLINE) {errno=EOVERFLOW;return -1;}
    last=start;deadline=start+LG_DEADLINE;
    run=open_run();if(run<0) goto done;
    if(fstatat(run,"logd.sock",&before,AT_SYMLINK_NOFOLLOW)<0||socket_metadata(&before)<0) goto done;
    fd=new_socket();if(fd<0||connect_socket(fd)<0) goto done;
    if(fstatat(run,"logd.sock",&after,AT_SYMLINK_NOFOLLOW)<0||!same_socket(&before,&after)) {errno=EIO;goto done;}
    struct ok_ucred peer={0};ok_socklen_t peer_size=sizeof(peer);
    if(ok_getsockopt(fd,OK_SOL_SOCKET,OK_SO_PEERCRED,&peer,&peer_size)<0) goto done;
    if(peer_size!=sizeof(peer)||peer.pid<=0||peer.uid||peer.gid) {errno=EACCES;goto done;}
    for(;;) {
        if(budget(deadline,&last)<0) goto done;
        ssize_t count;int invalid=0;
        if(sent<(size_t)length) {
            uint64_t send_started=last;
            count=send_bytes(fd,frame+sent,(size_t)length-sent);
            if(count>0&&(size_t)count<=(size_t)length-sent) {
                sent+=(size_t)count;
                if(sent==(size_t)length) {
                    /* Scheduling while the final send returns consumes the
                     * same fixed completion budget, never a renewed one. */
                    if(send_started>UINT64_MAX-LG_PERSISTENCE_DEADLINE) {errno=EOVERFLOW;goto done;}
                    deadline=send_started+LG_PERSISTENCE_DEADLINE;
                    if(budget(deadline,&last)<0) goto done;
                }
                continue;
            }
        } else {
            count=receive(fd,response+used,sizeof(response)-used,0,&invalid);
            if(invalid) {errno=EIO;goto done;}
            if(count>0) {used+=(size_t)count;if(used>=sizeof(response)) {errno=EIO;goto done;}continue;}
            if(!count) {
                if(budget(deadline,&last)<0) goto done;
                if(used!=25||memcmp(response,"OKL1 OK ",8)||response[24]!='\n') {errno=EIO;goto done;}
                uint64_t value=0;
                for(unsigned i=8;i<24;++i) {unsigned char c=response[i];int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;if(n<0) {errno=EIO;goto done;}value=(value<<4)|(unsigned)n;}
                if(!value) {errno=EIO;goto done;} *sequence=value;status=0;goto done;
            }
        }
        if(count>=0) {errno=EIO;goto done;}
        if(errno!=EAGAIN&&errno!=EINTR) goto done;
        struct pollfd wait={.fd=fd,.events=sent<(size_t)length?POLLOUT:POLLIN};
        if(poll(&wait,1,10)<0&&errno!=EINTR) goto done;
    }
done:
    error=errno;if(fd>=0&&close(fd)<0) {error=errno;status=-1;}
    if(run>=0&&close(run)<0) {error=errno;status=-1;}errno=error;return status;
}
