#include "../apps/init/service_manifest.h"
#include <assert.h>
#include <stdio.h>

static void refuse(const char *bytes, size_t size)
{
    struct service_manifest output, before;
    memset(&output, 0x5a, sizeof(output)); before = output;
    assert(sm_parse(&output, bytes, size) == -1);
    assert(!memcmp(&output, &before, sizeof(output)));
}

int main(void)
{
    const char diamond[] = "OK_SERVICE_MANIFEST 1\n# Forward names are permitted.\n"
        "service leaf notify /leaf left,right\nservice left simple /left root\n"
        "service right oneshot /right root\nservice root simple /root -\n";
    struct service_manifest manifest;
    assert(sm_parse(&manifest, diamond, sizeof(diamond) - 1) == 0);
    assert(manifest.count == 4 && manifest.records[0].dependencies == 6);
    for (unsigned i = 0; i < manifest.count; ++i)
        assert(manifest.records[i].uid == 0 && manifest.records[i].gid == 0);
    struct service_manifest copied = manifest;
    memset(&manifest, 0xee, sizeof(manifest));
    struct service_graph graph;
    assert(sm_bind(&copied, &graph) == 0);
    assert(graph.specs[0].name == copied.records[0].name && graph.specs[3].executable == copied.records[3].executable);
    assert(graph.order[0] == 3 && graph.ancestors[0] == 14);
    struct service_graph before = graph;
    copied.records[3].dependencies = 1;
    assert(sm_bind(&copied, &graph) == -1 && !memcmp(&graph, &before, sizeof(graph)));
    copied.records[3].dependencies = 0;
    copied.records[0].uid = UINT32_MAX;
    assert(sm_bind(&copied, &graph) == -1 && !memcmp(&graph, &before, sizeof(graph)));
    copied.records[0].uid = 0;
    copied.records[0].gid = UINT32_MAX;
    assert(sm_bind(&copied, &graph) == -1 && !memcmp(&graph, &before, sizeof(graph)));
    copied.records[0].gid = 0;
    memset(copied.records[0].name, 'a', sizeof(copied.records[0].name));
    assert(sm_bind(&copied, &graph) == -1 && !memcmp(&graph, &before, sizeof(graph)));
    const char *invalid[] = {
        "", "OK_SERVICE_MANIFEST 2\nservice a simple /a -\n", "OK_SERVICE_MANIFEST 1\n",
        "OK_SERVICE_MANIFEST 3\nservice a simple /a - 0 0\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a -", "OK_SERVICE_MANIFEST 1\nservice a simple /a - extra\n",
        "OK_SERVICE_MANIFEST 1\nservice  a simple /a -\n", "OK_SERVICE_MANIFEST 1\nservice a simple relative -\n",
        "OK_SERVICE_MANIFEST 1\nservice a unknown /a -\n", "OK_SERVICE_MANIFEST 1\nunknown a simple /a -\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a a\n", "OK_SERVICE_MANIFEST 1\nservice a simple /a missing\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a b,b\nservice b simple /b -\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a b,\nservice b simple /b -\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a ,b\nservice b simple /b -\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a -\nservice a notify /b -\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a b\nservice b simple /b c\nservice c simple /c a\n",
        "OK_SERVICE_MANIFEST 1\nservice - simple /a -\n", "OK_SERVICE_MANIFEST 1\n#bad\tcomment\nservice a simple /a -\n",
        "OK_SERVICE_MANIFEST 1\nservice a simple /a -\r\n"
    };
    for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) refuse(invalid[i], strlen(invalid[i]));
    const char identities[] = "OK_SERVICE_MANIFEST 2\n# Explicit permanent service identities.\n"
        "service worker notify /worker root 1001 2002\nservice root oneshot /setup - 0 0\n"
        "service boundary simple /boundary root 4294967294 4294967294\n";
    assert(!sm_parse(&manifest, identities, sizeof(identities) - 1));
    assert(manifest.count == 3 && manifest.records[0].uid == 1001 && manifest.records[0].gid == 2002);
    assert(manifest.records[0].dependencies == 2 && manifest.records[1].uid == 0 && manifest.records[1].gid == 0);
    assert(manifest.records[2].uid == UINT32_MAX - 1 && manifest.records[2].gid == UINT32_MAX - 1);
    const char *invalid_id[] = {"", "00", "01", "-1", "+1", "0x1", "1x", "4294967295", "4294967296", "999999999999999999999"};
    for (size_t i = 0; i < sizeof(invalid_id) / sizeof(invalid_id[0]); ++i) {
        char bad[256];
        int length = snprintf(bad, sizeof(bad), "OK_SERVICE_MANIFEST 2\nservice a simple /a - %s 0\n", invalid_id[i]);
        assert(length > 0 && (size_t)length < sizeof(bad)); refuse(bad, (size_t)length);
        length = snprintf(bad, sizeof(bad), "OK_SERVICE_MANIFEST 2\nservice a simple /a - 0 %s\n", invalid_id[i]);
        assert(length > 0 && (size_t)length < sizeof(bad)); refuse(bad, (size_t)length);
    }
    const char legacy_identity[] = "OK_SERVICE_MANIFEST 1\nservice a simple /a - 0 0\n";
    refuse(legacy_identity, sizeof(legacy_identity) - 1);
    const char extra_identity[] = "OK_SERVICE_MANIFEST 2\nservice a simple /a - 0 0 extra\n";
    refuse(extra_identity, sizeof(extra_identity) - 1);
    const char one[] = "OK_SERVICE_MANIFEST 1\nservice a simple /a -\n";
    for (size_t index = 0; index < sizeof(one) - 1; ++index) {
        char damaged[sizeof(one)]; memcpy(damaged, one, sizeof(one)); damaged[index] = 0;
        refuse(damaged, sizeof(one) - 1);
        damaged[index] = (char)0xff; refuse(damaged, sizeof(one) - 1);
    }
    char boundary[SM_BYTE_LIMIT + 2];
    size_t used = 0;
    used += (size_t)snprintf(boundary, sizeof(boundary), "OK_SERVICE_MANIFEST 1\n");
    for (unsigned index = 0; index < SG_CAPACITY; ++index)
        used += (size_t)snprintf(boundary + used, sizeof(boundary) - used, "service n%u simple /app -\n", index);
    assert(sm_parse(&manifest, boundary, used) == 0 && manifest.count == SG_CAPACITY);
    size_t eighth = used;
    used += (size_t)snprintf(boundary + used, sizeof(boundary) - used, "service ninth simple /app -\n");
    refuse(boundary, used); used = eighth;
    boundary[used++] = '#';
    memset(boundary + used, 'x', SM_BYTE_LIMIT - used - 1); boundary[SM_BYTE_LIMIT - 1] = '\n';
    assert(sm_parse(&manifest, boundary, SM_BYTE_LIMIT) == 0);
    boundary[SM_BYTE_LIMIT - 1] = 'x'; boundary[SM_BYTE_LIMIT] = '\n'; refuse(boundary, SM_BYTE_LIMIT + 1);
    char name[33], executable[97]; memset(name, 'a', 31); name[31] = 0;
    memset(executable, 'b', 95); executable[0] = '/'; executable[95] = 0;
    used = (size_t)snprintf(boundary, sizeof(boundary), "OK_SERVICE_MANIFEST 1\nservice %s simple %s -\n", name, executable);
    assert(sm_parse(&manifest, boundary, used) == 0);
    name[31] = 'a'; name[32] = 0;
    used = (size_t)snprintf(boundary, sizeof(boundary), "OK_SERVICE_MANIFEST 1\nservice %s simple /a -\n", name); refuse(boundary, used);
    executable[95] = 'b'; executable[96] = 0;
    used = (size_t)snprintf(boundary, sizeof(boundary), "OK_SERVICE_MANIFEST 1\nservice a simple %s -\n", executable); refuse(boundary, used);
    puts("SERVICE_MANIFEST_PARSER_HOSTED_PASS");
    return 0;
}
