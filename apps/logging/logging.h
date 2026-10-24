#ifndef OK_LOGGING_H
#define OK_LOGGING_H
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <ok/uapi/syscall.h>
#define LG_PATH "/run/logd.sock"
#define LG_PAYLOAD 256u
#define LG_HEADER 9u
#define LG_FRAME (LG_HEADER + LG_PAYLOAD)
#define LG_RECORD 640u
#define LG_LIMIT 8192u
#define LG_DEADLINE 1000u
#define LG_PERSISTENCE_DEADLINE 60000u
#define LG_CURRENT "system.log"
#define LG_PREVIOUS "system.prev"
/* Return 1 complete, 0 incomplete, -1 malformed, including extra frames. */
int lg_request(const unsigned char *bytes, size_t size, size_t *payload);
int lg_frame(const unsigned char *payload, size_t size, unsigned char *out);
size_t lg_base(uint64_t sequence, unsigned char *out);
size_t lg_record(uint64_t sequence, uint64_t monotonic_ms, const struct ok_ucred *peer,
                 const unsigned char *payload, size_t size, unsigned char *out);
/* Parse complete records and a syntactically valid incomplete final record.
 * Returns 0 complete, 1 incomplete tail, -1 corruption. */
int lg_scan(const unsigned char *bytes, size_t size, uint64_t *first, uint64_t *last);
struct lg_store { int directory, file, ready; uint64_t sequence; struct stat identity; };
void lg_store_reset(struct lg_store *store);
int lg_store_open(struct lg_store *store);
int lg_store_append(struct lg_store *store, uint64_t now, const struct ok_ucred *peer,
                    const unsigned char *payload, size_t size, uint64_t *sequence);
int lg_store_close(struct lg_store *store);
struct lg_client {
    int fd; struct ok_ucred peer; uint64_t deadline;
    unsigned char request[LG_FRAME + 1]; size_t used, sent, reply_size; char reply[48];
};
struct lg_server { int listener, run; struct stat socket_identity; struct lg_client client; uint64_t last; };
int lg_clock(uint64_t *now);
void lg_server_reset(struct lg_server *server);
int lg_server_open(struct lg_server *server);
int lg_server_step(struct lg_server *server, struct lg_store *store, uint64_t now);
int lg_server_close(struct lg_server *server);
int lg_notify(int descriptor);
int lg_service_open(struct lg_server *server, struct lg_store *store, int ready);
int lg_exchange(const unsigned char *payload, size_t size, uint64_t *sequence);
#endif
