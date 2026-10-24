#ifndef OK_TIME_SERVICE_H
#define OK_TIME_SERVICE_H

#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <ok/uapi/syscall.h>

#define TS_PATH "/run/timed.sock"
#define TS_NAME "timed.sock"
#define TS_REQUEST_BYTES 64u
#define TS_REPLY_BYTES 384u
#define TS_DEADLINE_MS 1000u
#define TS_MAX_SECONDS 8277292036ULL

enum ts_operation { TS_INVALID, TS_STATUS, TS_SET, TS_ERROR };
struct ts_request { enum ts_operation operation; int64_t seconds; uint32_t nanoseconds; };
struct ts_reply {
    enum ts_operation operation;
    uint32_t pid;
    uint64_t manual_updates;
    int error, realtime_error;
    int64_t realtime_seconds, monotonic_seconds;
    uint32_t realtime_nanoseconds, monotonic_nanoseconds;
};
struct ts_buffer { char bytes[TS_REPLY_BYTES]; size_t size; int failed; };

/* Canonical unsigned decimal, without signs, padding or leading zeroes. */
int ts_unsigned(const char *bytes, size_t size, uint64_t limit, uint64_t *value);
/* Return 1 complete, 0 incomplete, -1 malformed or a buffered suffix. */
int ts_request_parse(const char *bytes, size_t size, struct ts_request *request);
int ts_request_encode(const struct ts_request *request, struct ts_buffer *buffer);
int ts_reply_parse(const char *bytes, size_t size, struct ts_reply *reply);
int ts_reply_encode(const struct ts_reply *reply, struct ts_buffer *buffer);
/* manual_updates counts successful kernel commits in this daemon process only. */
void ts_dispatch(const struct ts_request *request, const struct ok_ucred *peer,
                 uint64_t *manual_updates, struct ts_reply *reply);

struct ts_client {
    int fd;
    struct ok_ucred peer;
    uint64_t deadline;
    char request[TS_REQUEST_BYTES + 1];
    size_t used, sent;
    struct ts_buffer reply;
};
struct ts_server {
    int listener, run;
    struct stat socket_identity;
    struct ts_client client;
    uint64_t last, manual_updates;
};
int ts_clock(uint64_t *milliseconds);
void ts_server_reset(struct ts_server *server);
int ts_server_open(struct ts_server *server);
int ts_server_step(struct ts_server *server, uint64_t now);
int ts_server_close(struct ts_server *server);
int ts_ready_descriptor(char **environment);
int ts_service_open(struct ts_server *server, int ready);
/* Complete validated response, including ERROR, returns 0. Transport errors -1. */
int ts_exchange(const struct ts_request *request, struct ts_buffer *wire, struct ts_reply *reply);

#endif
