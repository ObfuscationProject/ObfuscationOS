/* Linux-personality TCP and UDP through legacy socketcall(2), for guest
 * execution on i386, MIPS O32 and 32-bit PowerPC (scripts/test_net_socketcall.py).
 * Freestanding: no libc, so every socket call goes through socketcall rather
 * than through a libc that may prefer the direct calls. It connects to the
 * scripted peer's TCP echo service (192.0.2.100:7), checks SO_ERROR, SO_TYPE
 * and both names, echoes bytes with send/recv and sendto/recvfrom, shuts the
 * write side down, then checks SO_TYPE and SO_ERROR on a UDP socket. */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#if defined(__i386__)
#define SYS_exit 1
#define SYS_write 4
#define SYS_close 6
#define SYS_poll 168
#define SYS_socketcall 102
#define ARCH "i386"
static long raw(long number, long a, long b, long c)
{
    long result;
    __asm__ volatile("int $0x80" : "=a"(result) : "a"(number), "b"(a), "c"(b), "d"(c) : "memory");
    return result;
}
#elif defined(__mips__)
#define SYS_exit 4001
#define SYS_write 4004
#define SYS_close 4006
#define SYS_poll 4188
#define SYS_socketcall 4102
#define ARCH "mips"
static long raw(long number, long a, long b, long c)
{
    register long v0 __asm__("$2") = number;
    register long a0 __asm__("$4") = a;
    register long a1 __asm__("$5") = b;
    register long a2 __asm__("$6") = c;
    register long a3 __asm__("$7");
    __asm__ volatile("syscall"
                     : "+r"(v0), "=r"(a3)
                     : "r"(a0), "r"(a1), "r"(a2)
                     : "$1", "$3", "$8", "$9", "$10", "$11", "$12", "$13", "$14", "$15", "$24", "$25",
                       "hi", "lo", "memory");
    return a3 ? -v0 : v0;
}
#elif defined(__powerpc__) || defined(__PPC__)
#define SYS_exit 1
#define SYS_write 4
#define SYS_close 6
#define SYS_poll 167
#define SYS_socketcall 102
#define ARCH "ppc"
static long raw(long number, long a, long b, long c)
{
    register long r0 __asm__("r0") = number;
    register long r3 __asm__("r3") = a;
    register long r4 __asm__("r4") = b;
    register long r5 __asm__("r5") = c;
    __asm__ volatile("sc\n\tbns+ 1f\n\tneg 3,3\n1:"
                     : "+r"(r0), "+r"(r3), "+r"(r4), "+r"(r5)
                     :
                     : "r6", "r7", "r8", "r9", "r10", "r11", "r12", "cr0", "ctr", "xer", "memory");
    return r3;
}
#else
#error "socketcall probe: i386, MIPS O32 and 32-bit PowerPC only"
#endif

#if defined(__mips__)
enum { SOCK_STREAM = 2, SOCK_DGRAM = 1, SOCK_NONBLOCK = 0x80, SOL_SOCKET = 0xffff, SO_TYPE = 0x1008,
       SO_ERROR = 0x1007, EINPROGRESS = 150 };
#else
enum { SOCK_STREAM = 1, SOCK_DGRAM = 2, SOCK_NONBLOCK = 04000, SOL_SOCKET = 1, SO_TYPE = 3, SO_ERROR = 4,
       EINPROGRESS = 115 };
#endif
enum { AF_INET = 2, EAGAIN = 11, POLLIN = 1, POLLOUT = 4, MSG_NOSIGNAL = 0x4000, SHUT_WR = 1 };
enum { SC_SOCKET = 1, SC_CONNECT = 3, SC_GETSOCKNAME = 6, SC_GETPEERNAME = 7, SC_SEND = 9, SC_RECV = 10,
       SC_SENDTO = 11, SC_RECVFROM = 12, SC_SHUTDOWN = 13, SC_GETSOCKOPT = 15 };

struct address { u16 family; u8 port[2]; u8 ip[4]; u8 zero[8]; };

/* The static-exec layout has a data and a TLS segment; Linux ELF admission
 * requires both to be real, so the probe keeps one writable word in each. */
__attribute__((used)) static volatile int data_word = 1;
__attribute__((used)) static __thread int tls_word = 1;
struct pollfd { int fd; short events, revents; };

void *memset(void *target, int value, unsigned long size)
{
    u8 *bytes = target;
    while (size--) *bytes++ = (u8)value;
    return target;
}
void *memcpy(void *target, const void *source, unsigned long size)
{
    u8 *to = target; const u8 *from = source;
    while (size--) *to++ = *from++;
    return target;
}
static unsigned long length(const char *text) { unsigned long size = 0; while (text[size]) ++size; return size; }
static void say(const char *text) { raw(SYS_write, 1, (long)text, (long)length(text)); }
static void number(long value)
{
    char digits[24]; int at = 23; int negative = value < 0;
    unsigned long magnitude = negative ? (unsigned long)-value : (unsigned long)value;
    digits[at] = 0;
    do { digits[--at] = (char)('0' + magnitude % 10); magnitude /= 10; } while (magnitude);
    if (negative) digits[--at] = '-';
    say(digits + at);
}
static __attribute__((noreturn)) void finish(int step, long value)
{
    if (step)
    {
        say("OK_NET_SOCKETCALL scope=hardware arch=" ARCH " result=fail step="); number(step);
        say(" value="); number(value); say("\n");
    }
    else say("OK_NET_SOCKETCALL scope=hardware arch=" ARCH " result=pass tcp=pass udp=pass\n");
    for (;;) raw(SYS_exit, step ? 1 : 0, 0, 0);
}
static long sc(int selector, long a, long b, long c, long d, long e, long f)
{
    long words[6] = {a, b, c, d, e, f};
    return raw(SYS_socketcall, selector, (long)words, 0);
}
static void wait_for(int fd, short events, int step)
{
    struct pollfd entry = {fd, events, 0};
    for (int attempt = 0; attempt < 200; ++attempt)
    {
        entry.revents = 0;
        const long ready = raw(SYS_poll, (long)&entry, 1, 50);
        if (ready < 0) finish(step, ready);
        if (ready == 1 && (entry.revents & events)) return;
        if (ready == 1) finish(step, 1000 + entry.revents);
    }
    finish(step, -EAGAIN);
}
static int option(int fd, int name, int expected, int step)
{
    int value = -1; u32 size = 4;
    const long result = sc(SC_GETSOCKOPT, fd, SOL_SOCKET, name, (long)&value, (long)&size, 0);
    if (result != 0 || size != 4 || value != expected) finish(step, result ? result : 2000 + value);
    return value;
}
static void echo(int fd, const char *text, int sendto, int step)
{
    const long size = (long)length(text);
    const long sent = sendto ? sc(SC_SENDTO, fd, (long)text, size, MSG_NOSIGNAL, 0, 0)
                             : sc(SC_SEND, fd, (long)text, size, 0, 0, 0);
    if (sent != size) finish(step, sent);
    char back[64]; long got = 0;
    while (got < size)
    {
        wait_for(fd, POLLIN, step + 1);
        const long part = sendto ? sc(SC_RECVFROM, fd, (long)(back + got), 64 - got, 0, 0, 0)
                                 : sc(SC_RECV, fd, (long)(back + got), 64 - got, 0, 0, 0);
        if (part == -EAGAIN) continue;
        if (part <= 0) finish(step + 2, part);
        got += part;
    }
    for (long at = 0; at < size; ++at) if (back[at] != text[at]) finish(step + 3, at);
}

static int run(void)
{
    static const struct address peer = {AF_INET, {0, 7}, {192, 0, 2, 100}, {0}};
    const long fd = sc(SC_SOCKET, AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0, 0, 0, 0);
    if (fd < 0) finish(1, fd);
    const long connecting = sc(SC_CONNECT, fd, (long)&peer, sizeof(peer), 0, 0, 0);
    if (connecting != -EINPROGRESS && connecting != 0) finish(2, connecting);
    wait_for((int)fd, POLLOUT, 3);
    option((int)fd, SO_ERROR, 0, 4);
    option((int)fd, SO_TYPE, SOCK_STREAM, 5);
    struct address name; u32 size = sizeof(name);
    memset(&name, 0, sizeof(name));
    long result = sc(SC_GETPEERNAME, fd, (long)&name, (long)&size, 0, 0, 0);
    if (result || size != 16 || name.family != AF_INET || name.port[1] != 7 || name.ip[3] != 100) finish(6, result);
    size = sizeof(name); memset(&name, 0, sizeof(name));
    result = sc(SC_GETSOCKNAME, fd, (long)&name, (long)&size, 0, 0, 0);
    if (result || size != 16 || name.family != AF_INET || name.ip[0] != 192 || name.ip[3] != 2) finish(7, result);
    echo((int)fd, "socketcall send/recv", 0, 10);
    echo((int)fd, "socketcall sendto/recvfrom", 1, 20);
    result = sc(SC_SHUTDOWN, fd, SHUT_WR, 0, 0, 0, 0);
    if (result) finish(30, result);
    raw(SYS_close, fd, 0, 0);
    const long udp = sc(SC_SOCKET, AF_INET, SOCK_DGRAM, 0, 0, 0, 0);
    if (udp < 0) finish(40, udp);
    option((int)udp, SO_TYPE, SOCK_DGRAM, 41);
    option((int)udp, SO_ERROR, 0, 42);
    raw(SYS_close, udp, 0, 0);
    return 0;
}

__attribute__((noreturn)) void _start(void) { finish(run(), 0); }
