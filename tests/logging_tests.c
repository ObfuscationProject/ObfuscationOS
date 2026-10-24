#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include <poll.h>
#include <ok/socket.h>
#include <ok/syscall.h>
#include "../apps/logging/logging.h"
/* Actual product code, deterministic syscall seam. Host filesystem operations
 * below test OS logic only; they do not qualify the native persistence provider. */
static char fixture[256];
static int calls,fail_at,injected,held,short_write,write_interrupt,read_interrupt,zero_write,oversize_write,metadata_bad;
static int file_syncs,dir_syncs,writes,renames,strict_unsupported,orphan_busy;
static char events[200000];static size_t event_count;
static int boundary_calls,retain_reader,storage_backwards,send_backwards;
static uint64_t milliseconds,storage_delay,receive_delay,receive_delay_each,send_delay,send_delay_each,eof_delay;
static void advance(uint64_t delay) {assert(milliseconds<=UINT64_MAX-delay);milliseconds+=delay;}
static int event(char what)
{
    assert(event_count<sizeof(events));events[event_count++]=what;
    ++calls;if(fail_at==calls) {injected=1;errno=EIO;return -1;}return 0;
}
static int mock_open(const char *path,int flags,...)
{
    mode_t mode=0;if(flags&O_CREAT) {va_list args;va_start(args,flags);mode=(mode_t)va_arg(args,int);va_end(args);}
    if(event('O')<0) return -1;
    int fd=open(!strcmp(path,"/")?fixture:path,flags,mode);if(fd>=0) ++held;return fd;
}
static int mock_openat(int dir,const char *path,int flags,...)
{
    mode_t mode=0;if(flags&O_CREAT) {va_list args;va_start(args,flags);mode=(mode_t)va_arg(args,int);va_end(args);}
    if(event('o')<0) return -1;
    if(orphan_busy&&(flags&O_CREAT)) {errno=EBUSY;return -1;}
    int fd=openat(dir,path,flags,mode);if(fd>=0) ++held;return fd;
}
static int mock_close(int fd)
{
    int failed=event('C');assert(held>0);--held;int result=close(fd);return failed<0?-1:result;
}
static int mock_fstat(int fd,struct stat *s)
{
    if(event('f')<0) return -1;int r=fstat(fd,s);if(!r) {s->st_uid=s->st_gid=0;if(metadata_bad&&S_ISREG(s->st_mode)) s->st_nlink=2;}return r;
}
static int mock_fstatat(int dir,const char *p,struct stat *s,int flags)
{
    if(event('n')<0) return -1;int r=fstatat(dir,p,s,flags);if(!r) s->st_uid=s->st_gid=0;return r;
}
static ssize_t mock_read(int fd,void *p,size_t n)
{
    if(event('r')<0) return -1;if(read_interrupt) {--read_interrupt;errno=EINTR;return -1;}return read(fd,p,n);
}
static ssize_t mock_write(int fd,const void *p,size_t n)
{
    if(event('w')<0) return -1;
    if(fd==30) return write(fd,p,n);
    off_t at=lseek(fd,0,SEEK_END);assert(at>=0&&n>0&&n<=1024-(size_t)at%1024);++boundary_calls;
    if(write_interrupt) {--write_interrupt;errno=EINTR;return -1;}
    if(zero_write) return 0;if(oversize_write) return (ssize_t)n+1;
    if(orphan_busy) {errno=EBUSY;return -1;}
    if(short_write&&n>(size_t)short_write) n=(size_t)short_write;
    ++writes;ssize_t result=write(fd,p,n);
    if(result>=0) {
        advance(storage_delay);storage_delay=0;
        if(storage_backwards) {assert(milliseconds>=2);milliseconds-=2;storage_backwards=0;}
    }return result;
}
int ok_sync_persistent(int fd)
{
    if(event('s')<0) return -1;if(strict_unsupported) {errno=EOPNOTSUPP;return -1;}
    struct stat s;assert(!fstat(fd,&s));if(S_ISDIR(s.st_mode)) {++dir_syncs;events[event_count-1]='D';}else {++file_syncs;events[event_count-1]='F';}return 0;
}
static int mock_renameat(int a,const char *x,int b,const char *y)
{if(event('N')<0) return -1;++renames;int result=renameat(a,x,b,y);if(!result&&retain_reader) orphan_busy=1;return result;}
#define open mock_open
#define openat mock_openat
#define close mock_close
#define fstat mock_fstat
#define fstatat mock_fstatat
#define read mock_read
#define write mock_write
#define renameat mock_renameat
#include "../apps/logging/protocol.c"
#include "../apps/logging/store.c"
#undef open
#undef openat
#undef close
#undef fstat
#undef fstatat
#undef read
#undef write
#undef renameat
static void setup(void)
{
    char pattern[]="/tmp/ok-logging-XXXXXX";char *p=mkdtemp(pattern);assert(p);strcpy(fixture,p);
    char path[300];snprintf(path,sizeof(path),"%s/var",p);assert(!mkdir(path,0755));
    snprintf(path,sizeof(path),"%s/var/log",p);assert(!mkdir(path,0700));
    snprintf(path,sizeof(path),"%s/run",p);assert(!mkdir(path,0755));
    calls=fail_at=injected=held=short_write=write_interrupt=read_interrupt=zero_write=oversize_write=metadata_bad=0;
    file_syncs=dir_syncs=writes=renames=strict_unsupported=orphan_busy=retain_reader=0;event_count=0;
    storage_delay=receive_delay=receive_delay_each=send_delay=send_delay_each=eof_delay=0;
    storage_backwards=send_backwards=0;
}
static void cleanup(void)
{
    assert(!held);char path[300];const char *names[]={"var/log/system.log","var/log/system.prev","run/logd.sock"};
    for(unsigned i=0;i<3;++i) {snprintf(path,sizeof(path),"%s/%s",fixture,names[i]);unlink(path);}
    const char *dirs[]={"var/log","var","run"};for(unsigned i=0;i<3;++i) {snprintf(path,sizeof(path),"%s/%s",fixture,dirs[i]);assert(!rmdir(path));}assert(!rmdir(fixture));
}
static void seed(const char *name,const unsigned char *bytes,size_t n)
{
    char p[300];snprintf(p,sizeof(p),"%s/var/log/%s",fixture,name);int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC,0600);assert(fd>=0);assert(write(fd,bytes,n)==(ssize_t)n);assert(!close(fd));
}
static size_t contents(const char *name,unsigned char *bytes)
{
    char p[300];snprintf(p,sizeof(p),"%s/var/log/%s",fixture,name);int fd=open(p,O_RDONLY);if(fd<0) {assert(errno==ENOENT);return 0;}ssize_t n=read(fd,bytes,LG_LIMIT+1);assert(n>=0);assert(!close(fd));return (size_t)n;
}
static const struct ok_ucred root_peer={.pid=73,.uid=0,.gid=17};
static void parser_tests(void)
{
    unsigned char frame[LG_FRAME+4],disk[LG_RECORD*2],copy[LG_RECORD*2],payload[LG_PAYLOAD];memset(payload,0xa5,sizeof(payload));
    static const unsigned char initial[]="OKLB1 0000000000000000 #077a2810\n";
    assert(lg_base(0,disk)==sizeof(initial)-1&&!memcmp(disk,initial,sizeof(initial)-1));
    for(size_t n=1;n<=LG_PAYLOAD;++n) {
        int length=lg_frame(payload,n,frame);assert(length==(int)(n+LG_HEADER));
        for(size_t at=0;at<=(size_t)length;++at) {size_t value=0;assert(lg_request(frame,at,&value)==(at==(size_t)length));if(at==(size_t)length) assert(value==n);}
        frame[length]='x';size_t value;assert(lg_request(frame,(size_t)length+1,&value)==-1);
    }
    const char *bad[]={"OKL2 001\nx","OKL1 000\n","OKL1 257\nx","OKL1 999\n","OKL1 +01\nx","OKL1 1 1\nx","OKL1 001\rx","OKL1 001\nxOKL1 001\ny"};
    for(size_t i=0;i<sizeof(bad)/sizeof(*bad);++i) {size_t value;assert(lg_request((const unsigned char *)bad[i],strlen(bad[i]),&value)<0);}
    size_t n=lg_record(1,123,&root_peer,payload,sizeof(payload),disk);assert(n<=LG_RECORD);
    for(size_t at=1;at<n;++at) {uint64_t first,last;assert(lg_scan(disk,at,&first,&last)==1);}
    uint64_t first,last;assert(!lg_scan(disk,n,&first,&last)&&first==1&&last==1);
    for(size_t at=0;at<n;++at) {memcpy(copy,disk,n);copy[at]^=0x80;assert(lg_scan(copy,n,&first,&last)<0);}
    size_t m=lg_record(2,124,&root_peer,(const unsigned char *)"\n\000x",3,disk+n);
    assert(!lg_scan(disk,n+m,&first,&last)&&first==1&&last==2);
    memcpy(disk+n,disk,n);assert(lg_scan(disk,2*n,&first,&last)<0);
}
static void storage_tests(void)
{
    struct lg_store store;uint64_t seq;unsigned char payload[LG_PAYLOAD],bytes[LG_LIMIT+1],before[LG_LIMIT+1];memset(payload,'z',sizeof(payload));
    setup();assert(!lg_store_open(&store));short_write=7;write_interrupt=2;read_interrupt=2;
    for(unsigned i=1;i<=2000;++i) {assert(!lg_store_append(&store,i,&root_peer,payload,sizeof(payload),&seq)&&seq==i);assert(store.identity.st_size<=LG_LIMIT);}
    assert(renames>=129&&boundary_calls>2000);assert(!lg_store_close(&store)&&!held);
    assert(!lg_store_open(&store)&&store.sequence==2000);assert(!lg_store_close(&store));cleanup();
    /* Every proper incomplete tail is preserved in previous; no tail truncation. */
    size_t length=lg_record(1,123,&root_peer,payload,17,bytes);
    for(size_t cut=1;cut<length;++cut) {setup();seed(LG_CURRENT,bytes,cut);assert(!lg_store_open(&store));assert(contents(LG_PREVIOUS,before)==cut&&!memcmp(before,bytes,cut));assert(store.identity.st_size==33);assert(!lg_store_close(&store));cleanup();}
    /* Complete corruption and malformed incomplete bytes refuse without erase. */
    for(size_t at=0;at<length;++at) {setup();memcpy(before,bytes,length);before[at]^=0x80;seed(LG_CURRENT,before,length);assert(lg_store_open(&store)<0&&!held);unsigned char observed[LG_LIMIT+1];assert(contents(LG_CURRENT,observed)==length&&!memcmp(before,observed,length));cleanup();}
    /* Checkpoint history survives archiving a partial first record and a second
     * restart, even when its sequence field was never fully written. */
    unsigned char checkpoint[LG_RECORD],partial[LG_RECORD*2];
    size_t base_size=lg_base(77,checkpoint),record_size=lg_record(78,124,&root_peer,payload,17,partial+33);
    memcpy(partial,checkpoint,base_size);
    for(size_t cut=1;cut<record_size;++cut) {
        setup();seed(LG_PREVIOUS,checkpoint,base_size);seed(LG_CURRENT,partial,base_size+cut);
        assert(!lg_store_open(&store)&&store.sequence==77);assert(!lg_store_close(&store));
        assert(!lg_store_open(&store)&&store.sequence==77);
        assert(!lg_store_append(&store,125,&root_peer,payload,1,&seq)&&seq==78);
        assert(!lg_store_close(&store));cleanup();
    }
    for(size_t cut=1;cut<base_size;++cut) {
        setup();seed(LG_PREVIOUS,checkpoint,base_size);seed(LG_CURRENT,checkpoint,cut);
        assert(lg_store_open(&store)<0&&!held);
        assert(contents(LG_CURRENT,before)==cut&&!memcmp(before,checkpoint,cut));
        assert(contents(LG_PREVIOUS,before)==base_size&&!memcmp(before,checkpoint,base_size));cleanup();
    }
    setup();seed(LG_PREVIOUS,checkpoint,base_size);seed(LG_CURRENT,bytes,5);
    assert(lg_store_open(&store)<0&&!held);assert(contents(LG_CURRENT,before)==5);cleanup();
    setup();seed(LG_PREVIOUS,bytes,length);assert(!lg_store_open(&store)&&store.sequence==1);assert(!lg_store_close(&store));cleanup();
    setup();seed(LG_CURRENT,bytes,0);assert(!lg_store_open(&store)&&!store.sequence);assert(!lg_store_close(&store));cleanup();
    setup();strict_unsupported=1;assert(lg_store_open(&store)<0&&errno==EOPNOTSUPP&&!held);cleanup();
    setup();seed(LG_CURRENT,bytes,length);metadata_bad=1;assert(lg_store_open(&store)<0&&!held);cleanup();
    setup();assert(!lg_store_open(&store));zero_write=1;assert(lg_store_append(&store,1,&root_peer,payload,1,&seq)<0&&!store.ready);assert(!lg_store_close(&store));cleanup();
    setup();assert(!lg_store_open(&store));oversize_write=1;assert(lg_store_append(&store,1,&root_peer,payload,1,&seq)<0&&!store.ready);assert(!lg_store_close(&store));cleanup();
    /* Inject every successful-startup operation once. Cleanup closes descriptors
     * even when close reports uncertainty; no ready state survives a failure. */
    setup();assert(!lg_store_open(&store));int startup=calls;assert(!lg_store_close(&store));cleanup();
    for(int fault=1;fault<=startup;++fault) {setup();fail_at=fault;assert(lg_store_open(&store)<0&&injected&&!store.ready&&!held);cleanup();}
    /* Exercise every append and namespace publication fault on the rotation
     * request. Successor reopen accepts reachable states or preserves evidence. */
    int operations=0;
    for(int fault=0;;++fault) {
        setup();assert(!lg_store_open(&store));
        while((size_t)store.identity.st_size+lg_record(1,1,&root_peer,payload,sizeof(payload),before)<=LG_LIMIT) assert(!lg_store_append(&store,1,&root_peer,payload,sizeof(payload),&seq));
        calls=0;fail_at=fault;int result=lg_store_append(&store,2,&root_peer,payload,sizeof(payload),&seq);
        if(!fault) {assert(!result);operations=calls;}else assert(result<0&&injected&&!store.ready);
        fail_at=0;assert(!lg_store_close(&store)&&!held);
        assert(!lg_store_open(&store));assert(!lg_store_close(&store));cleanup();
        if(fault==operations) break;
    }
    setup();assert(!lg_store_open(&store));
    while(renames<1) assert(!lg_store_append(&store,1,&root_peer,payload,sizeof(payload),&seq));
    char archive_path[300];snprintf(archive_path,sizeof(archive_path),"%s/var/log/" LG_PREVIOUS,fixture);
    int archive_reader=open(archive_path,O_RDONLY);assert(archive_reader>=0);retain_reader=1;
    while((size_t)store.identity.st_size+lg_record(1,1,&root_peer,payload,sizeof(payload),before)<=LG_LIMIT) assert(!lg_store_append(&store,1,&root_peer,payload,sizeof(payload),&seq));
    uint64_t previous_sequence=store.sequence;
    assert(lg_store_append(&store,2,&root_peer,payload,sizeof(payload),&seq)<0&&errno==EBUSY&&!store.ready);
    assert(!lg_store_close(&store)&&!held);assert(!close(archive_reader));retain_reader=orphan_busy=0;
    assert(!lg_store_open(&store)&&store.sequence==previous_sequence);
    assert(!lg_store_append(&store,3,&root_peer,payload,1,&seq)&&seq==previous_sequence+1);
    assert(!lg_store_close(&store));cleanup();
    setup();assert(!lg_store_open(&store));store.sequence=UINT64_MAX;assert(lg_store_append(&store,1,&root_peer,payload,1,&seq)<0);assert(!lg_store_close(&store));cleanup();
}
static int socket_exists,socket_owner,socket_kind,socket_mode,socket_inode,socket_swap,connect_error,listen_error,bind_error,mask_value;
static int socket_live,accept_available,peer_uid,peer_gid,peer_pid,peer_short,peer_error,accepted,unlinks;
static int recv_again,recv_interrupt,peek_interrupt,recv_flags,recv_control,recv_oversize,recv_eof,send_again,send_interrupt,send_error,send_oversize;
static size_t read_at,input_size,recv_chunk,send_chunk,output_size;static unsigned char input[600],output[600];
static int clocks,clock_error,clock_backwards,clock_overflow,clock_step,notify_bytes,notify_closed,notify_zero,notify_interrupt;
static int t_close(int fd)
{ if(fd==24||fd==25||fd==30) {int result=event('c');assert(held>0);--held;if(fd==24) socket_live=0;if(fd==30) ++notify_closed;return result;}return mock_close(fd); }
static int t_fstatat(int d,const char *name,struct stat *s,int flags)
{
    if(strcmp(name,"logd.sock")) return mock_fstatat(d,name,s,flags);
    assert(flags==AT_SYMLINK_NOFOLLOW);if(event('p')<0) return -1;
    if(!socket_exists) {errno=ENOENT;return -1;}
    memset(s,0,sizeof(*s));s->st_mode=(mode_t)(socket_kind|socket_mode);s->st_uid=(unsigned)socket_owner;s->st_gid=0;s->st_nlink=1;s->st_ino=(ino_t)socket_inode;
    if(socket_swap) {++socket_inode;socket_swap=0;}return 0;
}
static int t_unlinkat(int d,const char *name,int flags)
{(void)d;assert(!strcmp(name,"logd.sock")&&!flags);if(event('u')<0) return -1;++unlinks;socket_exists=0;return 0;}
int ok_socket(int domain,int type,int protocol)
{ assert(domain==OK_AF_UNIX&&type==(OK_SOCK_STREAM|OK_SOCK_NONBLOCK|OK_SOCK_CLOEXEC)&&!protocol);if(event('S')<0) return -1;assert(!socket_live);socket_live=1;++held;return 24; }
int ok_bind(int fd,const struct ok_sockaddr_un *a,ok_socklen_t length)
{
    assert(fd==24&&a->family==OK_AF_UNIX&&!strcmp(a->path,LG_PATH)&&length==2+sizeof(LG_PATH)&&mask_value==0177);
    if(event('B')<0) return -1;if(bind_error) {errno=bind_error;return -1;}assert(!socket_exists);socket_exists=1;return 0;
}
int ok_listen(int fd,int backlog)
{assert(fd==24&&backlog==1);if(event('L')<0) return -1;if(listen_error) {errno=listen_error;return -1;}return 0;}
int ok_connect(int fd,const struct ok_sockaddr_un *a,ok_socklen_t length)
{assert(fd==24&&a->family==OK_AF_UNIX&&!strcmp(a->path,LG_PATH)&&length==2+sizeof(LG_PATH));if(event('K')<0) return -1;if(connect_error) {errno=connect_error;return -1;}return 0;}
int ok_accept4(int fd,struct ok_sockaddr_un *a,ok_socklen_t *length,int flags)
{
    assert(fd==24&&!a&&!length&&flags==(OK_SOCK_NONBLOCK|OK_SOCK_CLOEXEC));
    if(event('a')<0) return -1;
    if(!accept_available) {errno=EAGAIN;return -1;}--accept_available;++accepted;++held;return 25;
}
int ok_getsockopt(int fd,int level,int option,void *p,ok_socklen_t *length)
{
    assert((fd==24||fd==25)&&level==OK_SOL_SOCKET&&option==OK_SO_PEERCRED&&*length==sizeof(struct ok_ucred));
    if(event('G')<0) return -1;if(peer_error) {errno=peer_error;return -1;}
    struct ok_ucred peer={.pid=peer_pid,.uid=(unsigned)peer_uid,.gid=(unsigned)peer_gid};memcpy(p,&peer,sizeof(peer));if(peer_short) --*length;return 0;
}
ssize_t ok_recvmsg(int fd,struct ok_msghdr *message,int flags)
{
    assert((fd==24||fd==25)&&!(flags&~(OK_MSG_DONTWAIT|OK_MSG_PEEK))&&(flags&OK_MSG_DONTWAIT));
    assert(!message->control&&!message->control_length&&!message->name&&message->vector_count==1);
    struct ok_iovec *v=(void *)message->vectors;if(event('v')<0) return -1;
    if((flags&OK_MSG_PEEK)&&peek_interrupt) {--peek_interrupt;errno=EINTR;return -1;}
    if(recv_interrupt) {--recv_interrupt;errno=EINTR;return -1;}
    if(recv_again) {--recv_again;errno=EAGAIN;return -1;}
    message->flags=(unsigned)recv_flags;message->control_length=(unsigned)recv_control;
    if(recv_oversize) return (ssize_t)v->length+1;
    size_t n=input_size-read_at;if(n>v->length) n=v->length;if(recv_chunk&&n>recv_chunk) n=recv_chunk;
    if(!n&&!recv_eof) {errno=EAGAIN;return -1;}
    if(!(flags&OK_MSG_PEEK)) {advance(receive_delay+receive_delay_each);receive_delay=0;if(!n) {advance(eof_delay);eof_delay=0;}}
    memcpy((void *)v->base,input+read_at,n);if(!(flags&OK_MSG_PEEK)) read_at+=n;return (ssize_t)n;
}
ssize_t ok_sendmsg(int fd,const struct ok_msghdr *message,int flags)
{
    assert((fd==24||fd==25)&&flags==(OK_MSG_DONTWAIT|OK_MSG_NOSIGNAL)&&!message->control&&!message->control_length&&message->vector_count==1);
    if(event('A')<0) return -1;
    if(send_interrupt) {--send_interrupt;errno=EINTR;return -1;}if(send_again) {--send_again;errno=EAGAIN;return -1;}if(send_error) {errno=send_error;return -1;}
    struct ok_iovec *v=(void *)message->vectors;if(send_oversize) return (ssize_t)v->length+1;
    advance(send_delay+send_delay_each);send_delay=0;
    if(send_backwards) {assert(milliseconds>=2);milliseconds-=2;send_backwards=0;}
    if(fd==25) {
        size_t w=0,f=0,d=0;for(size_t i=0;i<event_count;++i) {if(events[i]=='w') w=i;if(events[i]=='F') f=i;if(events[i]=='D') d=i;}
        assert(w<f&&f<d); /* No success bytes before record + namespace sync. */
    }
    size_t n=v->length;if(send_chunk&&n>send_chunk) n=send_chunk;assert(output_size+n<=sizeof(output));memcpy(output+output_size,(void *)v->base,n);output_size+=n;return (ssize_t)n;
}
long ok_syscall1(long nr,long arg)
{assert(nr==OK_SYS_UMASK);if(event('M')<0) return -EIO;int old=mask_value;mask_value=(int)arg;return old;}
long ok_syscall_ret(long value) {if(value<0) {errno=(int)-value;return -1;}return value;}
static uid_t t_uid(void) {return 0;}static gid_t t_gid(void) {return 0;}
static int t_clock(clockid_t id,struct timespec *out)
{
    assert(id==CLOCK_MONOTONIC);++clocks;if(clock_error) {errno=EIO;return -1;}
    uint64_t now=milliseconds;if(clock_backwards&&clocks>1) now=milliseconds-2;
    out->tv_sec=clock_overflow?INT64_MAX:(time_t)(now/1000);out->tv_nsec=(long)(now%1000)*1000000;
    milliseconds+=(unsigned)clock_step;return 0;
}
static int t_poll(struct pollfd *fds,nfds_t n,int timeout)
{assert(n==1&&fds->fd==24&&timeout==10);milliseconds+=10;return 0;}
static ssize_t t_write(int fd,const void *p,size_t n)
{
    if(fd!=30) return mock_write(fd,p,n);
    assert(n==1&&*(const char *)p=='R');if(event('R')<0) return -1;
    if(notify_interrupt) {--notify_interrupt;errno=EINTR;return -1;}if(notify_zero) return 0;++notify_bytes;return 1;
}
#define open mock_open
#define openat mock_openat
#define fstat mock_fstat
#define fstatat t_fstatat
#define unlinkat t_unlinkat
#define close t_close
#define geteuid t_uid
#define getegid t_gid
#define clock_gettime t_clock
#define poll t_poll
#define write t_write
#include "../apps/logging/transport.c"
#undef open
#undef openat
#undef fstat
#undef fstatat
#undef unlinkat
#undef close
#undef geteuid
#undef getegid
#undef clock_gettime
#undef poll
#undef write
static void transport_reset(void)
{
    socket_exists=socket_owner=socket_swap=connect_error=listen_error=bind_error=mask_value=socket_live=0;
    socket_kind=0140000;socket_mode=0600;socket_inode=99;
    accept_available=peer_uid=peer_gid=peer_short=peer_error=accepted=unlinks=0;peer_pid=73;
    recv_again=recv_interrupt=peek_interrupt=recv_flags=recv_control=recv_oversize=recv_eof=send_again=send_interrupt=send_error=send_oversize=0;
    read_at=input_size=recv_chunk=send_chunk=output_size=0;
    clocks=clock_error=clock_backwards=clock_overflow=clock_step=notify_bytes=notify_closed=notify_zero=notify_interrupt=0;milliseconds=100;
}
static void transport_start(struct lg_server *server,struct lg_store *store)
{setup();transport_reset();assert(!lg_store_open(store));assert(!lg_server_open(server));accept_available=1;}
static void transport_finish(struct lg_server *server,struct lg_store *store)
{assert(!lg_server_close(server));assert(!lg_store_close(store));cleanup();}
static int server_at(struct lg_server *server,struct lg_store *store,uint64_t now)
{milliseconds=now;return lg_server_step(server,store,now);}
static void server_tests(void)
{
    struct lg_server server;struct lg_store store;uint64_t now;const unsigned char message[]="untrusted\nuid=123\000end";
    /* Actual server sees every fragment size; credential metadata remains the
     * server snapshot and payload newline/NUL cannot forge disk boundaries. */
    for(size_t chunk=1;chunk<40;++chunk) {
        transport_start(&server,&store);input_size=(size_t)lg_frame(message,sizeof(message),input);recv_chunk=chunk;send_chunk=1;recv_interrupt=2;recv_again=2;peek_interrupt=1;send_interrupt=2;send_again=2;
        for(now=101;now<500&&server.client.fd>=0; ++now) assert(!server_at(&server,&store,now));
        /* Initial fd is absent: drive until it has been accepted and closed. */
        for(;now<900&&(!accepted||server.client.fd>=0);++now) assert(!server_at(&server,&store,now));
        assert(accepted==1&&store.sequence==1&&output_size==25&&!memcmp(output,"OKL1 OK 0000000000000001\n",25));transport_finish(&server,&store);
    }
    /* Root refusal, ancillary flags/control, malformed/coalesced frames and
     * oversized kernel transfers never reach storage or emit success. */
    for(unsigned kind=0;kind<8;++kind) {
        transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);
        if(kind==0) peer_uid=1000;if(kind==1) peer_pid=0;if(kind==2) peer_short=1;
        if(kind==3) recv_flags=1;if(kind==4) recv_control=1;if(kind==5) recv_oversize=1;
        if(kind==6) input[input_size++]='x';if(kind==7) input[0]='x';
        assert(!server_at(&server,&store,101));assert(!output_size&&!store.sequence&&server.client.fd<0);transport_finish(&server,&store);
    }
    transport_start(&server,&store);input_size=3;memcpy(input,"OKL",3);recv_eof=1;
    assert(!server_at(&server,&store,101));assert(!server_at(&server,&store,102));assert(!store.sequence&&!output_size);transport_finish(&server,&store);
    transport_start(&server,&store);input_size=3;memcpy(input,"OKL",3);
    assert(!server_at(&server,&store,101));assert(!server_at(&server,&store,1101)&&server.client.fd<0);assert(!store.sequence);transport_finish(&server,&store);
    /* Repeated progress never slides the one-second admission deadline. */
    transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);recv_chunk=1;
    for(now=101;now<1101;now+=100) assert(!server_at(&server,&store,now)&&server.client.deadline==1101);
    assert(!server_at(&server,&store,1101)&&server.client.fd<0&&!store.sequence&&!output_size);transport_finish(&server,&store);
    transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);receive_delay=1000;
    assert(!server_at(&server,&store,101)&&server.client.fd<0&&!store.sequence&&!output_size);transport_finish(&server,&store);
    /* Actual append may take tens of seconds. Its fixed persistence/reply
     * budget is granted only once, after request admission, and includes sync. */
    const uint64_t delays[]={11000,32731,59999,60000,60001};
    for(size_t i=0;i<sizeof(delays)/sizeof(*delays);++i) {
        transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);storage_delay=delays[i];
        assert(!server_at(&server,&store,101)&&store.sequence==1&&!output_size);
        assert(server.last==101+delays[i]);
        if(delays[i]<LG_PERSISTENCE_DEADLINE) {
            assert(server.client.fd>=0&&server.client.deadline==60101&&server.client.reply_size==25);
            assert(!server_at(&server,&store,101+delays[i])&&server.client.fd<0&&output_size==25);
        } else {
            assert(server.client.fd<0&&!server.client.reply_size);
            /* Unacknowledged persistent bytes survive restart; a retry is a
             * new sequence, rather than rollback or exactly-once delivery. */
            assert(!lg_store_close(&store));assert(!lg_store_open(&store)&&store.sequence==1);
            uint64_t sequence;assert(!lg_store_append(&store,milliseconds,&root_peer,message,2,&sequence)&&sequence==2);
        }
        transport_finish(&server,&store);
    }
    transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);send_chunk=1;
    assert(!server_at(&server,&store,101)&&server.client.deadline==60101);
    for(now=102;now<60101;now+=10000) assert(!server_at(&server,&store,now)&&server.client.deadline==60101);
    assert(output_size==6);assert(!server_at(&server,&store,60101)&&server.client.fd<0&&output_size==6);transport_finish(&server,&store);
    /* The first data allocation during rotation has the same budget. */
    transport_start(&server,&store);unsigned char full[LG_PAYLOAD],record[LG_RECORD];memset(full,'r',sizeof(full));uint64_t sequence;
    while((size_t)store.identity.st_size+lg_record(1,1,&root_peer,full,sizeof(full),record)<=LG_LIMIT)
        assert(!lg_store_append(&store,1,&root_peer,full,sizeof(full),&sequence));
    int rotations=renames;uint64_t prior=store.sequence;input_size=(size_t)lg_frame(full,sizeof(full),input);storage_delay=32731;
    assert(!server_at(&server,&store,101)&&store.sequence==prior+1&&renames==rotations+1&&!output_size);
    assert(!server_at(&server,&store,32832)&&output_size==25&&server.client.fd<0);transport_finish(&server,&store);
    transport_start(&server,&store);assert(server_at(&server,&store,99)<0);transport_finish(&server,&store);
    transport_start(&server,&store);assert(server_at(&server,&store,UINT64_MAX)<0);transport_finish(&server,&store);
    transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);
    assert(server_at(&server,&store,UINT64_MAX-20000)<0&&errno==EOVERFLOW&&!store.sequence&&!output_size);transport_finish(&server,&store);
    transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);clock_backwards=1;
    assert(server_at(&server,&store,101)<0&&errno==EOVERFLOW&&!store.sequence&&!output_size);transport_finish(&server,&store);
    transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);storage_backwards=1;
    assert(server_at(&server,&store,101)<0&&errno==EOVERFLOW&&store.sequence==1&&!server.client.reply_size&&!output_size);transport_finish(&server,&store);
    /* Disk failure after frame dispatch cannot produce any success byte. */
    transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);strict_unsupported=1;
    assert(server_at(&server,&store,101)<0&&!output_size&&!store.ready);strict_unsupported=0;transport_finish(&server,&store);
    /* Peer close after persistence loses only the acknowledgement, not record. */
    transport_start(&server,&store);input_size=(size_t)lg_frame(message,2,input);
    assert(!server_at(&server,&store,101)&&store.sequence==1&&!output_size);send_error=EPIPE;assert(!server_at(&server,&store,102)&&server.client.fd<0);transport_finish(&server,&store);
    /* Every actual server-open fault retains descriptor accounting. */
    setup();transport_reset();assert(!lg_server_open(&server));int open_calls=calls;assert(!lg_server_close(&server));cleanup();
    for(int fault=1;fault<=open_calls;++fault) {setup();transport_reset();fail_at=fault;assert(lg_server_open(&server)<0&&injected&&!held);cleanup();}
    /* No duplicate startup may steal a live or full-backlog endpoint. Only an
     * unchanged owned ECONNREFUSED socket is reclaimed. */
    for(unsigned kind=0;kind<8;++kind) {
        setup();transport_reset();socket_exists=1;
        if(kind==1) connect_error=EAGAIN;if(kind>=2) connect_error=ECONNREFUSED;
        if(kind==3) socket_owner=1000;if(kind==4) socket_kind=S_IFREG;if(kind==5) socket_kind=S_IFLNK;if(kind==6) socket_mode=0666;if(kind==7) socket_swap=1;
        int result=lg_server_open(&server);assert((kind==2)==(result==0));assert(unlinks==(kind==2));assert(!lg_server_close(&server));cleanup();
    }
    setup();transport_reset();++held;lg_store_reset(&store);lg_server_reset(&server);
    assert(!lg_service_open(&server,&store,30)&&notify_bytes==1&&notify_closed==1);
    size_t ready_event=0,listener_event=0,last_directory=0;
    for(size_t i=0;i<event_count;++i) {if(events[i]=='R') ready_event=i;if(events[i]=='L') listener_event=i;if(events[i]=='D') last_directory=i;}
    assert(last_directory<listener_event&&listener_event<ready_event);transport_finish(&server,&store);
    setup();transport_reset();++held;strict_unsupported=1;lg_store_reset(&store);lg_server_reset(&server);
    assert(lg_service_open(&server,&store,30)<0&&!notify_bytes&&notify_closed==1);strict_unsupported=0;transport_finish(&server,&store);
    /* Keep PID1 readiness policy unchanged: an eleven-second startup write
     * cannot emit a late R even though the checkpoint became persistent. */
    setup();transport_reset();++held;storage_delay=11000;lg_store_reset(&store);lg_server_reset(&server);
    assert(lg_service_open(&server,&store,30)<0&&errno==EAGAIN&&!notify_bytes&&notify_closed==1);
    assert(milliseconds==11100);transport_finish(&server,&store);
    setup();transport_reset();unsigned char checkpoint[33];assert(lg_base(0,checkpoint)==sizeof(checkpoint));seed(LG_CURRENT,checkpoint,sizeof(checkpoint));
    ++held;storage_delay=11000;lg_store_reset(&store);lg_server_reset(&server);
    assert(!lg_service_open(&server,&store,30)&&notify_bytes==1&&notify_closed==1);
    assert(milliseconds==100&&storage_delay==11000&&!writes);storage_delay=0;transport_finish(&server,&store);
    setup();transport_reset();++held;notify_interrupt=2;assert(!lg_notify(30)&&notify_bytes==1&&notify_closed==1&&!held);cleanup();
    setup();transport_reset();++held;notify_zero=1;assert(lg_notify(30)<0&&!notify_bytes&&notify_closed==1&&!held);cleanup();
}
static void client_tests(void)
{
    uint64_t seq;
    for(size_t chunk=1;chunk<=26;++chunk) {
        setup();transport_reset();socket_exists=1;input_size=25;memcpy(input,"OKL1 OK 0000000000000001\n",25);recv_eof=1;recv_chunk=chunk;send_chunk=chunk;send_interrupt=2;send_again=2;recv_interrupt=2;recv_again=2;
        assert(!lg_exchange((const unsigned char *)"abc",3,&seq)&&seq==1&&output_size==12&&!held);cleanup();
    }
    for(unsigned kind=0;kind<11;++kind) {
        setup();transport_reset();socket_exists=1;input_size=25;memcpy(input,"OKL1 OK 0000000000000001\n",25);recv_eof=1;clock_step=1;
        if(kind==0) peer_uid=1000;if(kind==1) peer_gid=1;if(kind==2) peer_pid=0;if(kind==3) peer_short=1;
        if(kind==4) input[23]='0';if(kind==5) input[input_size++]='x';if(kind==6) recv_flags=1;if(kind==7) recv_control=1;
        if(kind==8) recv_oversize=1;if(kind==9) {recv_eof=0;input_size=0;}if(kind==10) send_oversize=1;
        assert(lg_exchange((const unsigned char *)"abc",3,&seq)<0&&!held);cleanup();
    }
    setup();transport_reset();clock_overflow=1;assert(lg_exchange((const unsigned char *)"a",1,&seq)<0&&!held);cleanup();
    setup();transport_reset();socket_exists=1;clock_backwards=1;assert(lg_exchange((const unsigned char *)"a",1,&seq)<0&&!held);cleanup();
    /* Partial sends retain one fixed second; progress cannot renew it or
     * start another send at the exact admission boundary. */
    for(unsigned kind=0;kind<2;++kind) {
        setup();transport_reset();socket_exists=1;input_size=25;memcpy(input,"OKL1 OK 0000000000000001\n",25);recv_eof=1;
        send_chunk=1;if(kind==0) send_delay=1000;else send_delay_each=100;
        assert(lg_exchange((const unsigned char *)"abc",3,&seq)<0&&errno==EAGAIN&&read_at==0&&output_size==(kind==0?1u:10u)&&!held);cleanup();
    }
    /* A complete send selects a fixed 60 s deadline anchored immediately
     * before that call. Time spent returning from it consumes the same cap. */
    const uint64_t send_delays[]={1000,11000,59999,60000,60001};
    for(size_t i=0;i<sizeof(send_delays)/sizeof(*send_delays);++i) {
        setup();transport_reset();socket_exists=1;input_size=25;memcpy(input,"OKL1 OK 0000000000000001\n",25);recv_eof=1;send_delay=send_delays[i];
        int result=lg_exchange((const unsigned char *)"abc",3,&seq);
        assert((result==0)==(send_delays[i]<LG_PERSISTENCE_DEADLINE));
        assert(output_size==12&&!held);if(!result) assert(seq==1&&read_at==25);else assert(errno==EAGAIN&&!read_at);cleanup();
    }
    /* Neither reply nor EOF starts a fresh budget after a delayed full send. */
    for(unsigned eof=0;eof<2;++eof) for(unsigned expired=0;expired<2;++expired) {
        setup();transport_reset();socket_exists=1;input_size=25;memcpy(input,"OKL1 OK 0000000000000001\n",25);recv_eof=1;send_delay=11000;
        if(eof) eof_delay=48999+expired;else receive_delay=48999+expired;
        int result=lg_exchange((const unsigned char *)"abc",3,&seq);
        assert((result==0)==!expired&&milliseconds==60099+expired&&output_size==12&&!held);
        if(!result) assert(seq==1);else assert(errno==EAGAIN);cleanup();
    }
    /* The anchor is the final successful send, after earlier fragments, rather
     * than exchange start or return from that final send. */
    for(unsigned expired=0;expired<2;++expired) {
        setup();transport_reset();socket_exists=1;input_size=25;memcpy(input,"OKL1 OK 0000000000000001\n",25);recv_eof=1;
        send_chunk=6;send_delay_each=400;receive_delay=59599+expired;
        int result=lg_exchange((const unsigned char *)"abc",3,&seq);
        assert((result==0)==!expired&&milliseconds==60499+expired&&output_size==12&&!held);
        if(!result) assert(seq==1);else assert(errno==EAGAIN);cleanup();
    }
    setup();transport_reset();socket_exists=1;send_backwards=1;
    assert(lg_exchange((const unsigned char *)"abc",3,&seq)<0&&errno==EOVERFLOW&&output_size==12&&!read_at&&!held);cleanup();
    /* Both reply and EOF must fit one fixed 60 s cap, including time spent
     * inside a slow receive/EOF syscall and partial reply progress. */
    const uint64_t delays[]={11000,32731,59999,60000,60001};
    for(size_t i=0;i<sizeof(delays)/sizeof(*delays);++i) {
        for(unsigned eof=0;eof<2;++eof) {
            setup();transport_reset();socket_exists=1;input_size=25;memcpy(input,"OKL1 OK 0000000000000001\n",25);recv_eof=1;
            if(eof) eof_delay=delays[i];else receive_delay=delays[i];
            int result=lg_exchange((const unsigned char *)"abc",3,&seq);
            assert((result==0)==(delays[i]<LG_PERSISTENCE_DEADLINE));
            if(!result) assert(seq==1);else assert(errno==EAGAIN);assert(!held);cleanup();
        }
    }
    setup();transport_reset();socket_exists=1;input_size=25;memcpy(input,"OKL1 OK 0000000000000001\n",25);recv_eof=1;recv_chunk=1;receive_delay_each=3000;
    assert(lg_exchange((const unsigned char *)"abc",3,&seq)<0&&errno==EAGAIN&&read_at==20&&!held);cleanup();
    setup();transport_reset();socket_exists=1;milliseconds=UINT64_MAX-20000;
    assert(lg_exchange((const unsigned char *)"a",1,&seq)<0&&errno==EOVERFLOW&&output_size==10&&!held);cleanup();
}
int main(void)
{
    parser_tests();storage_tests();server_tests();client_tests();
    puts("logging actual parser/storage/server/client fault controls passed (hosted syscall seam, not native execution)");return 0;
}
