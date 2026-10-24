#include "logging.h"
#include <string.h>
static const char hex[] = "0123456789abcdef";
static int nibble(unsigned char c) { return c >= '0' && c <= '9' ? c-'0' : c >= 'a' && c <= 'f' ? c-'a'+10 : -1; }
static void number(unsigned char *out, uint64_t value, unsigned digits)
{ for (unsigned i = digits; i; value >>= 4) out[--i] = (unsigned char)hex[value & 15]; }
static uint32_t check(const unsigned char *p, size_t n)
{ uint32_t h=2166136261u; for(size_t i=0;i<n;++i) h=(h^p[i])*16777619u; return h; }
int lg_request(const unsigned char *p, size_t n, size_t *length)
{
    static const char prefix[]="OKL1 ";
    if(n>LG_FRAME) return -1;
    for(size_t i=0;i<n && i<5;++i) if(p[i]!=(unsigned char)prefix[i]) return -1;
    for(size_t i=5;i<n && i<8;++i) if(p[i]<'0'||p[i]>'9') return -1;
    if(n>8 && p[8]!='\n') return -1;
    if(n<LG_HEADER) return 0;
    size_t size=(size_t)(p[5]-'0')*100+(size_t)(p[6]-'0')*10+(size_t)(p[7]-'0');
    if(!size||size>LG_PAYLOAD||n>LG_HEADER+size) return -1;
    *length=size; return n==LG_HEADER+size;
}
int lg_frame(const unsigned char *payload, size_t n, unsigned char *out)
{
    if(!n||n>LG_PAYLOAD) return -1;
    memcpy(out,"OKL1 ",5); out[5]=(unsigned char)('0'+n/100); out[6]=(unsigned char)('0'+n/10%10);
    out[7]=(unsigned char)('0'+n%10); out[8]='\n'; memcpy(out+LG_HEADER,payload,n); return (int)(LG_HEADER+n);
}
/* A persistent per-file sequence checkpoint survives rotation of a file whose
 * first unacknowledged record was interrupted before its sequence field. */
size_t lg_base(uint64_t sequence, unsigned char *out)
{
    memcpy(out,"OKLB1 ",6);number(out+6,sequence,16);
    uint32_t sum=check(out,22);out[22]=' ';out[23]='#';number(out+24,sum,8);out[32]='\n';return 33;
}
static int base(const unsigned char *p,size_t n,uint64_t *sequence)
{
    static const char prefix[]="OKLB1 ";uint64_t value=0;uint32_t sum=0;
    for(size_t i=0;i<33;++i) {
        if(i==32&&sum!=check(p,22)) return -1;
        if(i==n) return 1;
        if(i<6) {if(p[i]!=(unsigned char)prefix[i]) return -1;}
        else if(i<22) {int x=nibble(p[i]);if(x<0) return -1;value=(value<<4)|(unsigned)x;}
        else if(i==22) {if(p[i]!=' ') return -1;}
        else if(i==23) {if(p[i]!='#') return -1;}
        else if(i<32) {int x=nibble(p[i]);if(x<0) return -1;sum=(sum<<4)|(unsigned)x;}
        else if(p[i]!='\n') return -1;
    }
    if(sum!=check(p,22)) return -1;
    *sequence=value;return 0;
}
size_t lg_record(uint64_t seq, uint64_t ms, const struct ok_ucred *peer,
                 const unsigned char *payload, size_t n, unsigned char *out)
{
    size_t at=0;
    if(!seq||!n||n>LG_PAYLOAD||peer->pid<=0||peer->uid) return 0;
    memcpy(out,"OKLR1 ",6); at=6;
    number(out+at,seq,16); at+=16; out[at++]=' ';
    number(out+at,ms,16); at+=16; out[at++]=' ';
    number(out+at,(uint32_t)peer->pid,8); at+=8; out[at++]=' ';
    number(out+at,peer->uid,8); at+=8; out[at++]=' ';
    number(out+at,peer->gid,8); at+=8; out[at++]=' ';
    out[at++]=(unsigned char)('0'+n/100); out[at++]=(unsigned char)('0'+n/10%10); out[at++]=(unsigned char)('0'+n%10); out[at++]=' ';
    for(size_t i=0;i<n;++i) { out[at++]=(unsigned char)hex[payload[i]>>4]; out[at++]=(unsigned char)hex[payload[i]&15]; }
    uint32_t sum=check(out,at); out[at++]=' '; out[at++]='#'; number(out+at,sum,8); at+=8; out[at++]='\n'; return at;
}
/* Syntax is checked before classifying an EOF as an incomplete final record. */
static int record(const unsigned char *p, size_t n, size_t *used, uint64_t *seq)
{
    size_t at=0; uint64_t fields[5]={0}; static const unsigned widths[]={16,16,8,8,8};
    const char *prefix="OKLR1 ";
    for(unsigned i=0;i<6;++i) { if(at==n) return 1; if(p[at++]!=(unsigned char)prefix[i]) return -1; }
    for(unsigned f=0;f<5;++f) {
        for(unsigned i=0;i<widths[f];++i) { if(at==n) return 1; int x=nibble(p[at++]); if(x<0) return -1; fields[f]=(fields[f]<<4)|(unsigned)x; }
        if((f==0&&!fields[f])||(f==2&&(!fields[f]||fields[f]>INT32_MAX))||(f==3&&fields[f])) return -1;
        if(at==n) return 1;
        if(p[at++]!=' ') return -1;
    }
    size_t length=0;
    for(unsigned i=0;i<3;++i) { if(at==n) return 1; if(p[at]<'0'||p[at]>'9') return -1; length=length*10+(size_t)(p[at++]-'0'); }
    if(!length||length>LG_PAYLOAD) return -1;
    if(at==n) return 1;
    if(p[at++]!=' ') return -1;
    for(size_t i=0;i<2*length;++i) { if(at==n) return 1; if(nibble(p[at++])<0) return -1; }
    uint32_t expected=check(p,at), observed=0;
    if(at==n) return 1;
    if(p[at++]!=' ') return -1;
    if(at==n) return 1;
    if(p[at++]!='#') return -1;
    for(unsigned i=0;i<8;++i) { if(at==n) return 1; int x=nibble(p[at++]); if(x<0) return -1; observed=(observed<<4)|(unsigned)x; }
    if(observed!=expected) return -1;
    if(at==n) return 1;
    if(p[at++]!='\n') return -1;
    *seq=fields[0]; *used=at; return 0;
}
int lg_scan(const unsigned char *p, size_t n, uint64_t *first, uint64_t *last)
{
    size_t at=0; *first=*last=0;
    if(n>3&&p[3]=='B') {int status=base(p,n,last);if(status) return status;at=33;}
    while(at<n) { size_t used=0; uint64_t seq=0; int status=record(p+at,n-at,&used,&seq);
        if(status) return status;
        if(seq<=*last) return -1;
        if(!*first) *first=seq;
        *last=seq; at+=used;
    }
    return 0;
}
