#ifndef OKCRT_SOCKET_H
#define OKCRT_SOCKET_H
#include <ok/uapi/syscall.h>
#include <sys/types.h>
#ifdef __cplusplus
extern "C" {
#endif
int ok_socket(int domain, int type, int protocol);
int ok_bind(int fd, const struct ok_sockaddr_un *address, ok_socklen_t length);
int ok_listen(int fd, int backlog);
int ok_connect(int fd, const struct ok_sockaddr_un *address, ok_socklen_t length);
int ok_accept4(int fd, struct ok_sockaddr_un *address, ok_socklen_t *length, int flags);
int ok_getsockopt(int fd, int level, int option, void *value, ok_socklen_t *length);
int ok_socketpair(int domain, int type, int protocol, int descriptors[2]);
ssize_t ok_sendmsg(int fd, const struct ok_msghdr *message, int flags);
ssize_t ok_recvmsg(int fd, struct ok_msghdr *message, int flags);
#ifdef __cplusplus
}
#endif
#endif
