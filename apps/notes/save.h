#ifndef OK_NOTES_SAVE_H
#define OK_NOTES_SAVE_H

#include <stddef.h>

enum notes_save_result {
    NOTES_SAVE_FAILED = -1,
    NOTES_SAVE_DONE = 0,
    NOTES_SAVE_REPLACED_ERROR = 1
};

int notes_write_all(int fd, const char *bytes, size_t size);
enum notes_save_result notes_save_words(const char *path, int count, char *const words[]);

#endif
