#include "../include/obflib.h"
#include <stdint.h>

// 实现基本的内存操作函数
void *memset(void *ptr, int value, size_t num)
{
    unsigned char *p = (unsigned char *)ptr;
    for (size_t i = 0; i < num; i++)
    {
        p[i] = (unsigned char)value;
    }
    return ptr;
}

void *memcpy(void *dest, const void *src, size_t num)
{
    unsigned char *d = (unsigned char *)dest;
    const unsigned char *s = (const unsigned char *)src;
    for (size_t i = 0; i < num; i++)
    {
        d[i] = s[i];
    }
    return dest;
}

int memcmp(const void *ptr1, const void *ptr2, size_t num)
{
    const unsigned char *p1 = (const unsigned char *)ptr1;
    const unsigned char *p2 = (const unsigned char *)ptr2;
    for (size_t i = 0; i < num; i++)
    {
        if (p1[i] < p2[i])
            return -1;
        if (p1[i] > p2[i])
            return 1;
    }
    return 0;
}