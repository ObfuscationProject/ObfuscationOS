#ifndef OK_NATIVE_CONTROL_CLIENT_H
#define OK_NATIVE_CONTROL_CLIENT_H
#include "native_control_protocol.h"
/* 0: validated success, 1: validated server error, -1: transport/auth/protocol.
 * A fixed monotonic deadline covers connection, request and complete EOF reply. */
int nc_exchange(const char *request, size_t size, struct nc_buffer *reply);
#endif
