#include "../logging/logging.h"
#include <errno.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static int ready_descriptor(char **environment)
{
    const char *p=0;unsigned value=0,count=0;
    for(;environment&&*environment;++environment)
        if(!strncmp(*environment,"OK_SERVICE_READY_FD=",20)) {
            if(p) return -1;
            p=*environment+20;
        }
    if(!p||!*p) return -1;
    for(;*p;++p) {if(*p<'0'||*p>'9'||++count>2) return -1;value=value*10+(unsigned)(*p-'0');}
    return value>=3&&value<32?(int)value:-1;
}
int main(int argc,char **argv,char **environment)
{
    struct lg_store store;struct lg_server server;int ready=ready_descriptor(environment),result=1;
    (void)argv;
    lg_store_reset(&store);lg_server_reset(&server);
    if(argc!=1||getppid()!=1||geteuid()||getegid()||ready<0) {fputs("logd: invalid service launch\n",stderr);return 1;}
    if(lg_service_open(&server,&store,ready)<0) goto done;
    for(;;) {
        uint64_t now;if(lg_clock(&now)<0||lg_server_step(&server,&store,now)<0) break;
        struct pollfd wait[2]={{.fd=server.client.fd<0?server.listener:-1,.events=POLLIN},{.fd=server.client.fd,.events=server.client.reply_size?POLLOUT:POLLIN}};
        if(poll(wait,2,10)<0&&errno!=EINTR) break;
    }
done:
    /* Native TERM is fatal. Every successful reply is already persistent;
     * this cleanup is only for ordinary errors, never a signal promise. */
    perror("logd");if(lg_server_close(&server)<0) result=1;if(lg_store_close(&store)<0) result=1;return result;
}
