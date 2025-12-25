#ifndef OBFLIB_H
#define OBFLIB_H

// 基础类型定义
#include <stddef.h>
#include <stdint.h>

// 基础类型定义
using byte = uint8_t;
using word = uint16_t;
using dword = uint32_t;
using qword = uint64_t;

// 基础函数声明
void *memset(void *ptr, int value, size_t num);
void *memcpy(void *dest, const void *src, size_t num);
int memcmp(const void *ptr1, const void *ptr2, size_t num);

// 内存分配相关
void *malloc(size_t size);
void free(void *ptr);

#endif // OBFLIB_H