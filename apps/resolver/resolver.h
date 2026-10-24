#ifndef OK_RESOLVER_H
#define OK_RESOLVER_H

#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <ok/uapi/syscall.h>

#define RS_PATH "/run/resolved.sock"
#define RS_NAME "resolved.sock"
#define RS_NAME_BYTES 253u
#define RS_HOSTS_BYTES 4096u
#define RS_ALIAS_CAPACITY 64u
#define RS_REQUEST_BYTES 268u
#define RS_REPLY_BYTES 512u
#define RS_DEADLINE_MS 1000u

enum rs_operation { RS_INVALID, RS_STATUS, RS_LOOKUP, RS_ERROR };
enum rs_source { RS_NO_SOURCE, RS_NUMERIC, RS_HOSTS };
struct rs_request { enum rs_operation operation; char name[RS_NAME_BYTES + 1]; };
struct rs_reply {
    enum rs_operation operation;
    uint32_t pid, aliases, bytes;
    int error;
    enum rs_source source;
    uint8_t address[4];
    char name[RS_NAME_BYTES + 1];
};
struct rs_buffer { char bytes[RS_REPLY_BYTES]; size_t size; int failed; };
struct rs_alias { char name[RS_NAME_BYTES + 1]; uint8_t address[4]; };
struct rs_hosts { struct rs_alias aliases[RS_ALIAS_CAPACITY]; uint32_t count, bytes; };
/* The daemon owns these large objects in static storage, never on its stack. */
struct rs_workspace { char bytes[RS_HOSTS_BYTES + 1]; struct rs_hosts table; };

int rs_unsigned(const char *bytes, size_t size, uint64_t limit, uint64_t *value);
int rs_ipv4(const char *bytes, size_t size, uint8_t address[4]);
int rs_name_normalize(const char *bytes, size_t size, char name[RS_NAME_BYTES + 1]);
/* A query accepts a strict literal or a hostname. Malformed digit/dot forms fail. */
int rs_query_normalize(const char *bytes, size_t size, char name[RS_NAME_BYTES + 1]);
/* Outputs are published only after success; scratch must be a distinct table. */
int rs_hosts_parse(const char *bytes, size_t size, struct rs_hosts *hosts, struct rs_hosts *scratch);
int rs_hosts_load(struct rs_hosts *hosts, struct rs_workspace *workspace);
int rs_request_parse(const char *bytes, size_t size, struct rs_request *request);
int rs_request_encode(const struct rs_request *request, struct rs_buffer *buffer);
int rs_reply_parse(const char *bytes, size_t size, struct rs_reply *reply);
int rs_reply_encode(const struct rs_reply *reply, struct rs_buffer *buffer);
void rs_dispatch(const struct rs_request *request, const struct rs_hosts *hosts, struct rs_reply *reply);

struct rs_client {
    int fd;
    struct ok_ucred peer;
    uint64_t deadline;
    char request[RS_REQUEST_BYTES + 1];
    size_t used, sent;
    struct rs_buffer reply;
};
struct rs_server {
    int listener, run;
    struct stat socket_identity;
    struct rs_client client;
    uint64_t last;
    const struct rs_hosts *hosts;
};
int rs_clock(uint64_t *milliseconds);
void rs_server_reset(struct rs_server *server);
int rs_server_open(struct rs_server *server, const struct rs_hosts *hosts);
int rs_server_step(struct rs_server *server, uint64_t now);
int rs_server_close(struct rs_server *server);
int rs_ready_descriptor(char **environment);
int rs_service_open(struct rs_server *server, struct rs_hosts *hosts, struct rs_workspace *workspace, int ready);
/* A validated response, including ERROR, returns 0. Transport errors return -1. */
int rs_exchange(const struct rs_request *request, struct rs_buffer *wire, struct rs_reply *reply);

#endif
