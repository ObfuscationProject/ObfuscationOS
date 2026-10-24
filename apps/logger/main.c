#include "../logging/logging.h"
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv)
{
    unsigned char payload[LG_PAYLOAD];size_t used=0;
    if(argc<2) {fputs("usage: logger MESSAGE...\n",stderr);return 2;}
    for(int i=1;i<argc;++i) {
        size_t n=strlen(argv[i]);
        if((i>1&&used==sizeof(payload))||n>sizeof(payload)-used-(i>1?1u:0u)) {fputs("logger: message exceeds 256 bytes\n",stderr);return 2;}
        if(i>1) payload[used++]=' ';
        memcpy(payload+used,argv[i],n);used+=n;
    }
    uint64_t sequence;if(!used||lg_exchange(payload,used,&sequence)<0) {perror("logger");return 1;}
    /* Native minimal printf does not distinguish long from long long on the
     * 32-bit profiles. Encode the complete 64-bit sequence explicitly. */
    char decimal[22];size_t at=sizeof(decimal)-1;decimal[at]='\0';decimal[--at]='\n';
    do {decimal[--at]=(char)('0'+sequence%10);sequence/=10;} while(sequence);
    if(fputs("logger: persisted sequence=",stdout)<0||fputs(decimal+at,stdout)<0) return 1;
    return 0;
}
