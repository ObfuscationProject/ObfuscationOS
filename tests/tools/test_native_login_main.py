"""Hosted login control flow with injected OS/store boundaries and real PBKDF2.

The store, input, process, entropy and exec backends are deterministic stand-ins.
These tests do not establish guest execution, storage recovery or durability.
"""
from pathlib import Path
import ctypes
import hashlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

BACKEND = r'''
#include "accounts.h"
#include "input.h"
#include "store.h"
#include "users_store.h"
#include "home.h"
#include <errno.h>
#include <fcntl.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <time.h>

enum {
 RANDOM_INTERRUPTED_PARTIAL = 1, RANDOM_UNAVAILABLE = 2, RANDOM_PARTIAL_ERROR = 4,
 RANDOM_ZERO = 8, VERIFY_ERROR = 16, DERIVE_ERROR = 32, PENDING_ERROR = 64,
 ACTIVE_ERROR = 128, RECOVER_ERROR = 256, STORE_CLOSE_ERROR = 512,
 HOME_OPEN_ERROR = 1024, HOME_MODE_ERROR = 2048, HOME_CHDIR_ERROR = 4096,
 HOME_CLOSE_ERROR = 8192, FINAL_FLUSH_ERROR = 16384, EXEC_ERROR = 32768,
 PID_ERROR = 65536, CREDENTIAL_ERROR = 131072, STDIO_ERROR = 262144,
 CLOCK_ERROR = 524288, SLEEP_ERROR = 1048576, SLEEP_INTERRUPTED = 2097152,
 ROTATE_ERROR = 4194304, RANDOM_OVERCOUNT = 8388608, VERIFY_NONBOOLEAN = 16777216,
 FINAL_IDENTITY_ERROR = 33554432, RECOVER_SELECTED_B = 67108864
};
static unsigned options;
static int user_mode, user_failures, users_live;
static uint32_t session_uid;
enum { USERS_OPEN_ERROR=1, USERS_STAGE_ERROR=2, USERS_HOME_ERROR=4,
 USERS_RECOVER_ERROR=8, USERS_ROTATE_ERROR=16, USERS_CLOSE_ERROR=32,
 USERS_ENTER_ERROR=64, USERS_UID_ERROR=128, USERS_AVAILABLE_ERROR=256 };
void login_main_users(int mode, int failures) { user_mode=mode; user_failures=failures; }

static int initial_state, initial_recovering, opening_error;
static unsigned char expected[32];
static unsigned char rotation_salt[16], rotation_verifier[32], rotated_salt[16], rotated_verifier[32];
static char events[1024], output[8192], names[64], shell_env[256], prompts[4096], failed_write[256];
static size_t event_count, output_count, input_index, input_count, random_used;
static size_t prompt_count;
static int random_calls, verify_calls, derives, commits, recoveries, rotations, close_calls;
static int sleep_calls, exec_calls, backend_bad, store_live, home_entered, identity_calls;
static int console_failures, session_ready, console_attached, terminal_sid_calls, terminal_group_calls;
static const unsigned char *lines[64];
static size_t sizes[64];
static int statuses[64];
static struct { uintptr_t address; size_t size; int cleared; } buffers[64];
static size_t buffer_count;
static uintptr_t candidate_address;
static int candidate_cleared;
static jmp_buf execution;

int login_application_main(int, char **, char **);
static void event(char c) { if (event_count + 1 < sizeof(events)) events[event_count++] = c; else backend_bad = 1; }
static void check(int condition) { if (!condition) backend_bad = 1; }

void login_main_begin(int state, int recovering, unsigned flags, int store_error, const unsigned char *verifier)
{
 user_mode = user_failures = users_live = session_uid = 0;
 initial_state = state; initial_recovering = recovering; options = flags; opening_error = store_error;
 memcpy(expected, verifier, 32);
 memset(events, 0, sizeof(events)); memset(output, 0, sizeof(output));
 memset(names, 0, sizeof(names)); memset(shell_env, 0, sizeof(shell_env));
 memset(prompts, 0, sizeof(prompts)); memset(failed_write, 0, sizeof(failed_write));
 memset(rotated_salt, 0, sizeof(rotated_salt)); memset(rotated_verifier, 0, sizeof(rotated_verifier));
 memset(buffers, 0, sizeof(buffers)); buffer_count = 0;
 candidate_address = 0; candidate_cleared = 0;
 event_count = output_count = input_index = input_count = random_used = prompt_count = 0;
 random_calls = verify_calls = derives = commits = recoveries = rotations = close_calls = 0;
 sleep_calls = exec_calls = backend_bad = store_live = home_entered = identity_calls = 0;
 console_failures = session_ready = console_attached = terminal_sid_calls = terminal_group_calls = 0;
}
void login_main_console_failures(int failures) { console_failures = failures; }
void login_main_rotation(const unsigned char *salt, const unsigned char *verifier)
{ memcpy(rotation_salt, salt, 16); memcpy(rotation_verifier, verifier, 32); }
void login_main_fail_write(const char *text)
{ check(strlen(text) < sizeof(failed_write)); strcpy(failed_write, text); }
void login_main_line(const unsigned char *data, size_t size, int status)
{
 if (input_count == 64) { backend_bad = 1; return; }
 lines[input_count] = data; sizes[input_count] = size; statuses[input_count++] = status;
}
int login_main_run(char **environment)
{
 char *arguments[] = {"/bin/login", 0};
 if (setjmp(execution)) return 0;
 return login_application_main(1, arguments, environment);
}
const char *login_main_events(void) { return events; }
const char *login_main_output(void) { return output; }
const char *login_main_environment(void) { return shell_env; }
const char *login_main_prompts(void) { return prompts; }
const unsigned char *login_main_rotated_salt(void) { return rotated_salt; }
const unsigned char *login_main_rotated_verifier(void) { return rotated_verifier; }
int login_main_bad(void) { return backend_bad; }
int login_main_execs(void) { return exec_calls; }
int login_main_verifies(void) { return verify_calls; }
int login_main_derives(void) { return derives; }
int login_main_commits(void) { return commits; }
int login_main_recovers(void) { return recoveries; }
int login_main_rotates(void) { return rotations; }
int login_main_closes(void) { return close_calls; }
int login_main_inputs(void) { return (int)input_index; }
int login_main_random_calls(void) { return random_calls; }
int login_main_sleeps(void) { return sleep_calls; }
int login_main_uncleared(void)
{
 int count = candidate_address && !candidate_cleared;
 for (size_t i = 0; i < buffer_count; ++i) count += !buffers[i].cleared;
 return count;
}
void test_password_clear(void *buffer, size_t size)
{
 ok_password_clear(buffer, size);
 for (size_t i = 0; i < size; ++i) check(!((unsigned char *)buffer)[i]);
 uintptr_t address = (uintptr_t)buffer;
 for (size_t i = 0; i < buffer_count; ++i)
  if (address <= buffers[i].address && size >= buffers[i].size &&
      buffers[i].address - address <= size - buffers[i].size) buffers[i].cleared = 1;
 if (candidate_address == address && size == sizeof(struct ok_account)) candidate_cleared = 1;
}

pid_t test_getpid(void)
{ ++identity_calls; return (options & PID_ERROR) || ((options & FINAL_IDENTITY_ERROR) && identity_calls > 1) ? 1 : 7; }
pid_t test_getppid(void) { return 1; }
pid_t test_setsid(void)
{
 event('s'); check(!store_live && !users_live && !session_uid && (verify_calls || commits));
 if (console_failures & 1) { errno = EPERM; return -1; }
 session_ready = 1; return console_failures & 2 ? 8 : 7;
}
pid_t test_getsid(pid_t pid) { check(session_ready && (pid == 0 || pid == 7)); return 7; }
pid_t test_getpgid(pid_t pid) { check(session_ready && (pid == 0 || pid == 7)); return 7; }
pid_t test_getpgrp(void) { check(session_ready); return 7; }
int test_ioctl(int fd, unsigned long request, ...)
{
 event('t'); check(fd == 0 && request == TIOCSCTTY && session_ready && !session_uid && !console_attached);
 va_list arguments; va_start(arguments, request); check(va_arg(arguments, int) == 0); va_end(arguments);
 if (console_failures & 4) { errno = EACCES; return -1; }
 console_attached = 1; return 0;
}
pid_t test_tcgetsid(int fd)
{
 event('j'); check(fd == 0 && console_attached); ++terminal_sid_calls;
 return (console_failures & 8) || ((console_failures & 32) && terminal_sid_calls > 1) ? 8 : 7;
}
pid_t test_tcgetpgrp(int fd)
{
 event('g'); check(fd == 0 && console_attached); ++terminal_group_calls;
 return (console_failures & 16) || ((console_failures & 64) && terminal_group_calls > 1) ? 8 : 7;
}
int test_getresuid(uid_t *real, uid_t *effective, uid_t *saved)
{ *real = *effective = session_uid; *saved = options & CREDENTIAL_ERROR ? 1 : session_uid; return 0; }
int test_getresgid(gid_t *real, gid_t *effective, gid_t *saved)
{ *real = *effective = *saved = session_uid; return 0; }
int test_fcntl(int descriptor, int command, ...)
{
 check(descriptor >= 0 && descriptor < 3);
 if (command == F_GETFD) return options & STDIO_ERROR ? FD_CLOEXEC : 0;
 check(command == F_GETFL);
 return descriptor ? O_WRONLY : O_RDONLY;
}
int test_fstat(int descriptor, struct stat *info)
{
 memset(info, 0, sizeof(*info)); info->st_nlink = 1;
 if (descriptor >= 0 && descriptor < 3) info->st_mode = S_IFCHR | 0600;
 else if (descriptor == 11) info->st_mode = S_IFDIR | 0755;
 else if (descriptor == 12) info->st_mode = S_IFDIR | (options & HOME_MODE_ERROR ? 0755 : 0700);
 else { backend_bad = 1; errno = EBADF; return -1; }
 return 0;
}
int test_open(const char *path, int flags, ...)
{
 event('o'); check(!strcmp(path, "/"));
 check(flags == (O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
 return 11;
}
int test_openat(int directory, const char *name, int flags, ...)
{
 event('h'); check(directory == 11 && !strcmp(name, "root"));
 check(flags == (O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
 if (options & HOME_OPEN_ERROR) { errno = EIO; return -1; }
 return 12;
}
int test_close(int descriptor)
{
 event('c'); check(descriptor == 11 || descriptor == 12);
 if (descriptor == 12 && (options & HOME_CLOSE_ERROR)) { errno = EIO; return -1; }
 return 0;
}
long test_syscall1(long number, long descriptor)
{
 event('H'); check(number == 81 && descriptor == 12);
 if (options & HOME_CHDIR_ERROR) return -EIO;
 home_entered = 1; return 0;
}
long test_syscall_ret(long result)
{ if (result < 0) { errno = (int)-result; return -1; } return result; }
int test_clock_gettime(clockid_t clock, struct timespec *now)
{
 check(clock == CLOCK_MONOTONIC);
 if (options & CLOCK_ERROR) { errno = EIO; return -1; }
 *now = (struct timespec){.tv_sec = 123, .tv_nsec = 456}; return 0;
}
int test_clock_nanosleep(clockid_t clock, int flags, const struct timespec *deadline, struct timespec *remaining)
{
 event('Z'); ++sleep_calls;
 check(clock == CLOCK_MONOTONIC && flags == TIMER_ABSTIME && !remaining);
 check(deadline->tv_sec == 124 && deadline->tv_nsec == 456);
 if ((options & SLEEP_INTERRUPTED) && sleep_calls == 1) return EINTR;
 return options & SLEEP_ERROR ? EIO : 0;
}
ssize_t test_getrandom(void *buffer, size_t size, unsigned flags)
{
 event('G'); ++random_calls; check(!flags && size == 16 - random_used);
 if ((options & RANDOM_INTERRUPTED_PARTIAL) && random_calls == 1) { errno = EINTR; return -1; }
 if (options & RANDOM_UNAVAILABLE) { errno = EAGAIN; return -1; }
 if ((options & RANDOM_PARTIAL_ERROR) && random_used) { errno = EIO; return -1; }
 if (options & RANDOM_ZERO) return 0;
 if (options & RANDOM_OVERCOUNT) return (ssize_t)size + 1;
 if (((options & RANDOM_INTERRUPTED_PARTIAL) || (options & RANDOM_PARTIAL_ERROR)) && !random_used) size = 5;
 for (size_t i = 0; i < size; ++i)
  ((unsigned char *)buffer)[i] = (unsigned char)(random_used + i + (initial_state ? 16 : 0));
 random_used += size; return (ssize_t)size;
}
int test_console_flush(uint32_t epoch)
{
 event('F'); check(epoch == 17);
 if (options & FINAL_FLUSH_ERROR) { errno = EACCES; return -1; }
 return 0;
}
int test_write(int descriptor, const char *text)
{
 check(descriptor == 1 || descriptor == 2);
 if (failed_write[0] && !strcmp(text, failed_write)) { errno = EIO; return -1; }
 if (!strcmp(text, "Password changed.\n")) event('S');
 if (!strcmp(text, "If saving is interrupted, the next sign-in may require the new password.\n")) event('W');
 size_t size = strlen(text);
 if (size + output_count + 1 > sizeof(output)) { backend_bad = 1; return -1; }
 memcpy(output + output_count, text, size); output_count += size; return 0;
}
int test_read_line(uint32_t epoch, const char *prompt, unsigned char *buffer, size_t capacity, size_t *length)
{
 event('I'); check(epoch == 17 && prompt && buffer && length);
 size_t prompt_size = strlen(prompt);
 check(prompt_count + prompt_size + 2 < sizeof(prompts));
 if (prompt_count + prompt_size + 2 >= sizeof(prompts)) return -1;
 memcpy(prompts + prompt_count, prompt, prompt_size); prompt_count += prompt_size;
 prompts[prompt_count++] = '\n';
 memset(buffer, 0, capacity); *length = 0;
 size_t tracked;
 for (tracked = 0; tracked < buffer_count; ++tracked)
  if (buffers[tracked].address == (uintptr_t)buffer && buffers[tracked].size == capacity) break;
 if (tracked == buffer_count) {
  check(buffer_count < 64); if (buffer_count == 64) return -1;
  buffers[buffer_count].address = (uintptr_t)buffer; buffers[buffer_count++].size = capacity;
 }
 buffers[tracked].cleared = 1;
 if (input_index == input_count) { errno = EIO; return -1; }
 size_t index = input_index++;
 if (statuses[index]) return statuses[index];
 if (sizes[index] >= capacity) return 1;
 memcpy(buffer, lines[index], sizes[index]); *length = sizes[index];
 buffers[tracked].cleared = !sizes[index];
 if (!strcmp(prompt, "Login: ") || !strcmp(prompt, "Account name: ")) {
   memset(names, 0, sizeof(names)); memcpy(names, buffer, sizes[index]);
 }
 return 0;
}
int test_password_verify(const void *password, size_t size, const unsigned char *salt, const unsigned char *verifier)
{
 event('V'); ++verify_calls;
 if (options & VERIFY_ERROR) return -1;
 if (options & VERIFY_NONBOOLEAN) return 2;
 return ok_password_verify(password, size, salt, verifier);
}
int test_password_derive(const void *password, size_t size, const unsigned char *salt, unsigned char *verifier)
{
 event('D'); ++derives;
 if (options & DERIVE_ERROR) return -1;
 return ok_password_derive(password, size, salt, verifier);
}
int ok_account_store_open(struct ok_account_store *store)
{
 event('O'); *store = (struct ok_account_store){.directory = -1};
 if (opening_error) { errno = opening_error; return -1; }
 store->directory = 10; store->ready = store_live = 1; store->recovering = initial_recovering;
 store->account.state = initial_state;
 if (initial_state) {
  strcpy(store->account.name, "chosen_admin");
  for (size_t i = 0; i < 16; ++i) store->account.salt[i] = (unsigned char)i;
  memcpy(store->account.verifier, expected, 32);
 }
 store->observed = store->account;
 if (options & RECOVER_SELECTED_B) {
  check(initial_state == OK_ACCOUNT_ACTIVE && initial_recovering);
  memcpy(store->account.salt, rotation_salt, 16); memcpy(store->account.verifier, rotation_verifier, 32);
 }
 return 0;
}
int ok_account_store_commit(struct ok_account_store *store, const struct ok_account *next)
{
 event(next->state == OK_ACCOUNT_PENDING ? 'p' : 'a'); ++commits;
 check(store_live && store->ready && !store->recovering);
 check(!strcmp(next->name, "chosen_admin") && !memcmp(next->verifier, expected, 32));
 check((store->account.state == 0 && next->state == 1) || (store->account.state == 1 && next->state == 2));
 if ((next->state == 1 && (options & PENDING_ERROR)) || (next->state == 2 && (options & ACTIVE_ERROR))) {
  store->ready = 0; errno = EIO; return -2;
 }
 store->observed = store->account = *next; return 0;
}
int ok_account_store_recover(struct ok_account_store *store)
{
 event('r'); ++recoveries; check(store_live && store->ready && store->recovering);
 check(verify_calls > 0 && !strcmp(names, "chosen_admin"));
 if (options & RECOVER_ERROR) { store->ready = 0; errno = EIO; return -2; }
 store->recovering = 0; store->observed = store->account; return 0;
}
int ok_account_store_rotate(struct ok_account_store *store, const struct ok_account *next)
{
 event('R'); ++rotations;
 check(store_live && store->ready && !store->recovering && verify_calls > 0);
 check(store->observed.state == OK_ACCOUNT_ACTIVE && store->account.state == OK_ACCOUNT_ACTIVE);
 check(next->state == OK_ACCOUNT_ACTIVE && !memcmp(next->name, store->account.name, sizeof(next->name)));
 check(!memcmp(store->observed.verifier, expected, 32));
 check(!memcmp(next->salt, rotation_salt, 16) && !memcmp(next->verifier, rotation_verifier, 32));
 check(memcmp(next->salt, store->observed.salt, 16) && random_used == 16);
 for (size_t i = 0; i < buffer_count; ++i) check(buffers[i].cleared);
 candidate_address = (uintptr_t)next; candidate_cleared = 0;
 memcpy(rotated_salt, next->salt, 16); memcpy(rotated_verifier, next->verifier, 32);
 if (options & ROTATE_ERROR) { store->ready = 0; errno = EIO; return -2; }
 store->observed = store->account = *next; return 0;
}
int ok_account_store_close(struct ok_account_store *store)
{
 if (store->directory >= 0) { event('C'); ++close_calls; store_live = 0; }
 else event('q');
 memset(store, 0, sizeof(*store)); store->directory = -1;
 if (close_calls && (options & STORE_CLOSE_ERROR)) { errno = EIO; return -1; }
 return 0;
}

static void prepare_user(struct ok_user *user, const char *name, uint32_t uid)
{
 memset(user,0,sizeof(*user)); strcpy(user->name,name); user->uid=user->gid=uid;
 for(size_t i=0;i<16;++i) user->salt[i]=(unsigned char)i;
 memcpy(user->verifier,expected,32);
}
int ok_users_store_open(struct ok_users_store *store,const char *administrator)
{
 *store=(struct ok_users_store){.directory=-1};
 if(user_failures&USERS_OPEN_ERROR) { errno=EIO; return -1; }
 store->directory=13; store->ready=users_live=1; strcpy(store->administrator,administrator);
 if(user_mode) {
  store->users.count=2;
  prepare_user(&store->users.entries[0],"alice",1000);
  prepare_user(&store->users.entries[1],"bob",1001);
 }
 store->observed=store->users;
 if(user_mode==2) { store->recovering=1;store->recovery_kind=OK_USERS_ADD;
  store->change_index=1; store->observed.count=1; }
 if(user_mode==3) { store->recovering=1;store->recovery_kind=OK_USERS_ROTATE;
  store->change_index=0; memcpy(store->users.entries[0].salt,rotation_salt,16);
  memcpy(store->users.entries[0].verifier,rotation_verifier,32); }
 return 0;
}
int ok_users_store_close(struct ok_users_store *store)
{
 int live=store->directory>=0;
 if(live && user_mode) event('Q');
 users_live=0; memset(store,0,sizeof(*store));store->directory=-1;
 if(live && (user_failures&USERS_CLOSE_ERROR)) {errno=EIO;return -1;} return 0;
}
int ok_users_store_stage_add(struct ok_users_store *store,const struct ok_user *user)
{
 event('T');check(users_live && store->ready && !store->recovering && verify_calls && !strcmp(names,"chosen_admin"));
 check(user->uid==1002 && user->gid==1002 && !strcmp(user->name,"carol"));
 if(user_failures&USERS_STAGE_ERROR) {store->ready=0;errno=EIO;return -2;}
 store->change_index=store->users.count;store->users.entries[store->users.count++]=*user;
 store->recovering=1;store->recovery_kind=OK_USERS_ADD;return 0;
}
int ok_users_store_recover(struct ok_users_store *store)
{
 event('Y');check(users_live && store->ready && store->recovering && verify_calls);
 check(store->recovery_kind==OK_USERS_ADD ? !strcmp(names,"chosen_admin") : !strcmp(names,"alice"));
 if(user_failures&USERS_RECOVER_ERROR) {store->ready=0;errno=EIO;return -2;}
 store->recovering=0;store->observed=store->users;return 0;
}
int ok_users_store_rotate(struct ok_users_store *store,const struct ok_user *user)
{
 event('U');check(users_live && store->ready && !store->recovering && verify_calls);
 check(!strcmp(names,"alice") && user->uid==1000 && user->gid==1000);
 check(!memcmp(user->salt,rotation_salt,16) && !memcmp(user->verifier,rotation_verifier,32));
 if(user_failures&USERS_ROTATE_ERROR){store->ready=0;errno=EIO;return -2;}
 store->observed.entries[0]=store->users.entries[0]=*user;return 0;
}
int ok_login_user_next_uid(const struct ok_users *users,uint32_t *uid)
{ event('N');check(users->count==2); if(user_failures&USERS_UID_ERROR){errno=EIO;return -1;}*uid=1002;return 0; }
int ok_login_home_available(const struct ok_user *user)
{event('A');check(!strcmp(user->name,"carol"));if(user_failures&USERS_AVAILABLE_ERROR){errno=EEXIST;return -1;}return 0;}
int ok_login_home_prepare(const struct ok_user *user)
{event('B');check(!strcmp(user->name,user_mode==2?"bob":"carol"));if(user_failures&USERS_HOME_ERROR){errno=EIO;return -1;}return 0;}
int ok_login_home_enter(const char *name,uint32_t uid,uint32_t gid)
{
 event('E');check(console_attached&&!users_live&&!store_live&&((!strcmp(name,"alice")&&uid==1000&&gid==1000)||(!strcmp(name,"bob")&&uid==1001&&gid==1001)));
 if(user_failures&USERS_ENTER_ERROR){errno=EACCES;return -1;}
 session_uid=uid;home_entered=1;return 0;
}

int test_execve(const char *path, char *const arguments[], char *const environment[])
{
 event('X'); ++exec_calls;
 check(!store_live && !users_live && home_entered && console_attached && terminal_sid_calls == 2 && terminal_group_calls == 2);
 check(!strcmp(path, "/bin/oksh") && !strcmp(arguments[0], path) && !arguments[1]);
 const char *wanted[] = {"HOME=/root", "PATH=/bin", "USER=chosen_admin", "LOGNAME=chosen_admin", "OK_CONSOLE_EPOCH=17", 0};
 const char *ordinary[] = {"HOME=/home/alice", "PATH=/bin", "USER=alice", "LOGNAME=alice", "OK_CONSOLE_EPOCH=17", 0};
 const char *bob[] = {"HOME=/home/bob", "PATH=/bin", "USER=bob", "LOGNAME=bob", "OK_CONSOLE_EPOCH=17", 0};
 if (session_uid) for (size_t i=0; i<5; ++i) wanted[i]=session_uid==1001 ? bob[i] : ordinary[i];
 size_t offset = 0;
 for (size_t i = 0; wanted[i]; ++i) {
  check(environment[i] && !strcmp(environment[i], wanted[i]));
  if (environment[i] && strlen(environment[i]) + offset + 2 < sizeof(shell_env)) {
    strcpy(shell_env + offset, environment[i]); offset += strlen(environment[i]); shell_env[offset++] = '\n';
  }
 }
 check(!environment[5]);
 if (options & EXEC_ERROR) { errno = ENOENT; return -1; }
 longjmp(execution, 1);
}
'''


class NativeLoginMainTests(unittest.TestCase):
    RANDOM_INTERRUPTED_PARTIAL = 1
    RANDOM_UNAVAILABLE = 2
    RANDOM_PARTIAL_ERROR = 4
    RANDOM_ZERO = 8
    VERIFY_ERROR = 16
    DERIVE_ERROR = 32
    PENDING_ERROR = 64
    ACTIVE_ERROR = 128
    RECOVER_ERROR = 256
    STORE_CLOSE_ERROR = 512
    HOME_OPEN_ERROR = 1024
    HOME_MODE_ERROR = 2048
    HOME_CHDIR_ERROR = 4096
    HOME_CLOSE_ERROR = 8192
    FINAL_FLUSH_ERROR = 16384
    EXEC_ERROR = 32768
    PID_ERROR = 65536
    CREDENTIAL_ERROR = 131072
    STDIO_ERROR = 262144
    CLOCK_ERROR = 524288
    SLEEP_ERROR = 1048576
    SLEEP_INTERRUPTED = 2097152
    ROTATE_ERROR = 4194304
    RANDOM_OVERCOUNT = 8388608
    VERIFY_NONBOOLEAN = 16777216
    FINAL_IDENTITY_ERROR = 33554432
    RECOVER_SELECTED_B = 67108864

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-login-main-host-')
        temporary = Path(cls.directory.name)
        (temporary / 'ok/uapi').mkdir(parents=True)
        shutil.copyfile(ROOT / 'sdk/include/ok/console.h', temporary / 'ok/console.h')
        shutil.copyfile(ROOT / 'lib/okcrt/include/ok/syscall.h', temporary / 'ok/syscall.h')
        (temporary / 'ok/uapi/syscall.h').write_text(
            '#define OK_SYS_FCHDIR 81ULL\n#define OK_MODE_CHARACTER_DEVICE 0020000U\n')
        (temporary / 'backend.c').write_text(BACKEND)
        common = ['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fPIC',
                  '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-D_GNU_SOURCE',
                  '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(temporary),
                  '-I', str(ROOT / 'apps/login'), '-include', 'termios.h']
        substitutions = {
            'main': 'login_application_main', 'getpid': 'test_getpid', 'getppid': 'test_getppid',
            'setsid': 'test_setsid', 'getsid': 'test_getsid', 'getpgid': 'test_getpgid',
            'getpgrp': 'test_getpgrp', 'ioctl': 'test_ioctl', 'tcgetsid': 'test_tcgetsid',
            'tcgetpgrp': 'test_tcgetpgrp',
            'getresuid': 'test_getresuid', 'getresgid': 'test_getresgid', 'fcntl': 'test_fcntl',
            'fstat': 'test_fstat', 'open': 'test_open', 'openat': 'test_openat', 'close': 'test_close',
            'clock_gettime': 'test_clock_gettime', 'clock_nanosleep': 'test_clock_nanosleep',
            'getrandom': 'test_getrandom', 'execve': 'test_execve', 'ok_syscall1': 'test_syscall1',
            'ok_syscall_ret': 'test_syscall_ret', 'ok_console_flush': 'test_console_flush',
            'ok_login_write': 'test_write', 'ok_login_read_line': 'test_read_line',
            'ok_password_verify': 'test_password_verify', 'ok_password_derive': 'test_password_derive',
            'ok_password_clear': 'test_password_clear'}
        application = temporary / 'main.o'
        subprocess.run(common + [f'-D{key}={value}' for key, value in substitutions.items()] +
                       ['-c', str(ROOT / 'apps/login/main.c'), '-o', str(application)], check=True)
        output = temporary / 'login-main.so'
        subprocess.run(common + ['-shared', '-Dok_console_flush=test_console_flush', str(application),
            str(ROOT / 'apps/login/input.c'), str(ROOT / 'apps/login/accounts.c'),
            str(ROOT / 'apps/login/password.c'), str(ROOT / 'apps/login/users.c'), str(temporary / 'backend.c'), '-o', str(output)], check=True)
        cls.lib = ctypes.CDLL(str(output), use_errno=True)
        cls.lib.login_main_begin.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint,
                                            ctypes.c_int, ctypes.c_void_p]
        cls.lib.login_main_line.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
        cls.lib.login_main_rotation.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cls.lib.login_main_fail_write.argtypes = [ctypes.c_char_p]
        cls.lib.login_main_run.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
        for name in ('events', 'output', 'environment', 'prompts'):
            getattr(cls.lib, 'login_main_' + name).restype = ctypes.c_char_p
        for name in ('rotated_salt', 'rotated_verifier'):
            getattr(cls.lib, 'login_main_' + name).restype = ctypes.c_void_p
        cls.verifier = hashlib.pbkdf2_hmac('sha256', b'secret', bytes(range(16)), 600000, 32)
        cls.rotation_verifiers = {}

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_login(self, state=2, recovering=False, flags=0, lines=None, store_error=0,
                  environment=None, new_password=b'new-secret', fail_write=None, user_mode=0, user_failures=0,
                  console_failures=0):
        if lines is None:
            lines = [b'chosen_admin', b'secret'] if state else [b'chosen_admin', b'secret', b'secret']
        self.lib.login_main_begin(state, int(recovering), flags, store_error, self.verifier)
        self.lib.login_main_console_failures(console_failures)
        if new_password not in self.rotation_verifiers:
            self.rotation_verifiers[new_password] = hashlib.pbkdf2_hmac(
                'sha256', new_password, bytes(range(16, 32)), 600000, 32)
        self.lib.login_main_rotation(bytes(range(16, 32)), self.rotation_verifiers[new_password])
        self.lib.login_main_users(user_mode, user_failures)
        if fail_write is not None:
            self.lib.login_main_fail_write(fail_write)
        held = []
        for item in lines:
            data, status = item if isinstance(item, tuple) else (item, 0)
            held.append(ctypes.create_string_buffer(data))
            self.lib.login_main_line(held[-1], len(data), status)
        if environment is None:
            environment = [b'PATH=/evil', b'HOME=/elsewhere', b'LD_PRELOAD=untrusted', b'OK_CONSOLE_EPOCH=17']
        env = (ctypes.c_char_p * (len(environment) + 1))(*environment, None)
        result = self.lib.login_main_run(env)
        self.assertEqual(self.lib.login_main_bad(), 0, self.lib.login_main_events())
        self.assertEqual(self.lib.login_main_uncleared(), 0, self.lib.login_main_events())
        return result, self.lib.login_main_events()

    @staticmethod
    def rotation_lines(new_password=b'new-secret'):
        return [b':passwd', b'chosen_admin', b'secret', new_password, new_password]

    def assert_no_rotation(self, events):
        self.assertEqual(self.lib.login_main_rotates(), 0)
        self.assertNotIn(b'R', events)
        self.assertNotIn(b'Password changed.', self.lib.login_main_output())

    def test_enrollment_requires_pending_then_active_with_selected_name(self):
        result, events = self.run_login(state=0)
        self.assertEqual(result, 0)
        self.assertLess(events.index(b'p'), events.index(b'a'))
        self.assertEqual(self.lib.login_main_commits(), 2)
        self.assertEqual(self.lib.login_main_derives(), 1)
        self.assertEqual(self.lib.login_main_verifies(), 0)
        self.assertLess(events.index(b'C'), events.index(b'H'))
        self.assertTrue(events.endswith(b'FX'))

    def test_console_attachment_follows_authentication_and_precedes_credential_drop(self):
        for ordinary in (False, True):
            with self.subTest(ordinary=ordinary):
                result, events = self.run_login(user_mode=int(ordinary),
                                                lines=[b'alice' if ordinary else b'chosen_admin', b'secret'])
                self.assertEqual(result, 0)
                order = [events.index(marker) for marker in (b'V', b'C', b's', b't', b'j', b'g',
                                                              b'E' if ordinary else b'H')]
                self.assertEqual(order, sorted(order))
                self.assertEqual(events.count(b't'), 1)
                self.assertEqual(events.count(b'j'), 2)
                self.assertEqual(events.count(b'g'), 2)
                self.assertLess(events.rindex(b'g'), events.rindex(b'F'))

    def test_console_attachment_and_both_identity_checks_fail_closed(self):
        for failure in (1, 2, 4, 8, 16, 32, 64):
            with self.subTest(failure=failure):
                result, events = self.run_login(user_mode=1, lines=[b'alice', b'secret'],
                                                console_failures=failure)
                self.assertEqual(result, 1)
                self.assertNotIn(b'X', events)
                if failure <= 16:
                    self.assertNotIn(b'E', events)
                else:
                    self.assertIn(b'E', events)
                    self.assertNotIn(b'F', events[events.index(b'E'):])
                if failure <= 2:
                    self.assertNotIn(b't', events)

    def test_pending_activates_only_after_password_authentication(self):
        result, events = self.run_login(state=1)
        self.assertEqual(result, 0)
        self.assertLess(events.index(b'V'), events.index(b'a'))
        self.assertNotIn(b'p', events)
        self.assertEqual(self.lib.login_main_commits(), 1)

    def test_staged_recovery_waits_for_authentication_then_pending_activation(self):
        for state in (1, 2):
            with self.subTest(state=state):
                result, events = self.run_login(state=state, recovering=True)
                self.assertEqual(result, 0)
                self.assertLess(events.index(b'V'), events.index(b'r'))
                self.assertEqual(self.lib.login_main_recovers(), 1)
                self.assertEqual(self.lib.login_main_commits(), state == 1)

    def test_wrong_password_and_name_pay_kdf_then_monotonic_delay(self):
        for first in ([b'chosen_admin', b'wrong'], [b'wrong_name', b'secret'],
                      [(b'', 1), b'secret'], [b'chosen_admin', b'']):
            with self.subTest(first=first):
                result, events = self.run_login(recovering=True, lines=first + [b'chosen_admin', b'secret'])
                self.assertEqual(result, 0)
                self.assertEqual(self.lib.login_main_verifies(), 2)
                self.assertEqual(self.lib.login_main_sleeps(), 1)
                self.assertTrue(events.startswith(b'OIIVZ'))
                self.assertGreater(events.index(b'r'), events.rindex(b'V'))
                self.assertIn(b'Login incorrect.', self.lib.login_main_output())

    def test_negative_verifier_result_is_fatal_and_never_recovers(self):
        result, events = self.run_login(recovering=True, flags=self.VERIFY_ERROR)
        self.assertEqual(result, 1)
        self.assertIn(b'V', events)
        self.assertNotIn(b'r', events)
        self.assertNotIn(b'X', events)
        self.assertEqual(self.lib.login_main_commits(), 0)

    def test_entropy_eintr_and_partial_reads_provide_exact_salt(self):
        result, events = self.run_login(state=0, flags=self.RANDOM_INTERRUPTED_PARTIAL)
        self.assertEqual(result, 0)
        self.assertEqual(self.lib.login_main_random_calls(), 3)
        self.assertEqual(events.count(b'G'), 3)
        self.assertLess(events.rindex(b'G'), events.index(b'D'))

    def test_entropy_failure_never_falls_back_or_publishes(self):
        for flags in (self.RANDOM_UNAVAILABLE, self.RANDOM_PARTIAL_ERROR, self.RANDOM_ZERO):
            with self.subTest(flags=flags):
                result, events = self.run_login(state=0, flags=flags)
                self.assertEqual(result, 1)
                self.assertNotIn(b'D', events)
                self.assertNotIn(b'p', events)
                self.assertNotIn(b'X', events)

    def test_missing_malformed_and_unsupported_store_never_enroll(self):
        for error in (2, 5, 95):
            with self.subTest(error=error):
                result, events = self.run_login(state=0, store_error=error)
                self.assertEqual(result, 1)
                self.assertEqual(self.lib.login_main_inputs(), 0)
                self.assertNotIn(b'G', events)
                self.assertNotIn(b'p', events)
                self.assertNotIn(b'X', events)

    def test_input_error_and_kdf_error_never_publish(self):
        for lines, flags in [([(b'', -1)], 0), ([b'chosen_admin', (b'', -1)], 0),
                             ([b'chosen_admin', b'secret', (b'', -1)], 0),
                             ([b'chosen_admin', b'secret', b'secret'], self.DERIVE_ERROR)]:
            with self.subTest(lines=lines, flags=flags):
                result, events = self.run_login(state=0, flags=flags, lines=lines)
                self.assertEqual(result, 1)
                self.assertEqual(self.lib.login_main_commits(), 0)
                self.assertNotIn(b'X', events)

    def test_invalid_enrollment_inputs_repeat_without_mutating_credentials(self):
        lines = [b'Bad_Name', b'chosen_admin', b'', b'secret', b'different', b'secret', b'secret']
        result, events = self.run_login(state=0, lines=lines)
        self.assertEqual(result, 0)
        self.assertEqual(events.count(b'I'), len(lines))
        self.assertEqual(self.lib.login_main_derives(), 1)
        self.assertEqual(self.lib.login_main_commits(), 2)

    def test_any_store_mutation_error_is_fatal_without_enrollment_retry(self):
        for state, recovering, flags, count in [(0, False, self.PENDING_ERROR, 1),
                (0, False, self.ACTIVE_ERROR, 2), (1, False, self.ACTIVE_ERROR, 1),
                (1, True, self.RECOVER_ERROR, 0)]:
            with self.subTest(state=state, flags=flags):
                result, events = self.run_login(state=state, recovering=recovering, flags=flags)
                self.assertEqual(result, 1)
                self.assertEqual(self.lib.login_main_commits(), count)
                self.assertNotIn(b'X', events)

    def test_shell_gets_only_exact_safe_environment_and_direct_argv(self):
        result, events = self.run_login()
        self.assertEqual(result, 0)
        self.assertEqual(self.lib.login_main_execs(), 1)
        self.assertEqual(self.lib.login_main_environment(), b'HOME=/root\nPATH=/bin\nUSER=chosen_admin\n'
                         b'LOGNAME=chosen_admin\nOK_CONSOLE_EPOCH=17\n')
        self.assertNotIn(b'secret', self.lib.login_main_output())
        self.assertLess(events.index(b'C'), events.index(b'X'))

    def test_close_home_and_flush_errors_prevent_exec(self):
        for flags in (self.STORE_CLOSE_ERROR, self.HOME_OPEN_ERROR, self.HOME_MODE_ERROR,
                      self.HOME_CHDIR_ERROR, self.HOME_CLOSE_ERROR, self.FINAL_FLUSH_ERROR):
            with self.subTest(flags=flags):
                result, events = self.run_login(flags=flags)
                self.assertEqual(result, 1)
                self.assertNotIn(b'X', events)
                self.assertIn(b'unable to establish', self.lib.login_main_output())

    def test_exec_error_fails_after_attempt_without_retrying_authentication(self):
        result, events = self.run_login(flags=self.EXEC_ERROR)
        self.assertEqual(result, 1)
        self.assertEqual(self.lib.login_main_execs(), 1)
        self.assertEqual(events.count(b'V'), 1)
        self.assertEqual(self.lib.login_main_commits(), 0)

    def test_identity_and_epoch_errors_prevent_store_and_input(self):
        for flags, environment in [(self.PID_ERROR, None), (self.CREDENTIAL_ERROR, None),
                                   (self.STDIO_ERROR, None), (0, []), (0, [b'OK_CONSOLE_EPOCH=01'])]:
            with self.subTest(flags=flags, environment=environment):
                result, events = self.run_login(flags=flags, environment=environment)
                self.assertEqual(result, 1)
                self.assertNotIn(b'O', events)
                self.assertNotIn(b'I', events)
                self.assertNotIn(b'X', events)

    def test_delay_retries_eintr_but_other_time_errors_are_fatal(self):
        lines = [b'chosen_admin', b'wrong', b'chosen_admin', b'secret']
        result, events = self.run_login(flags=self.SLEEP_INTERRUPTED, lines=lines)
        self.assertEqual(result, 0)
        self.assertEqual(self.lib.login_main_sleeps(), 2)
        for flags in (self.CLOCK_ERROR, self.SLEEP_ERROR):
            result, events = self.run_login(flags=flags, lines=lines)
            self.assertEqual(result, 1)
            self.assertEqual(events.count(b'V'), 1)
            self.assertNotIn(b'X', events)

    def test_rotation_authenticates_then_uses_fresh_salt_and_one_separate_store_operation(self):
        result, events = self.run_login(lines=self.rotation_lines())
        self.assertEqual(result, 0)
        self.assertEqual(self.lib.login_main_prompts(), b'Login: \nLogin: \nPassword: \n'
                         b'New password: \nRepeat new password: \n')
        self.assertEqual(self.lib.login_main_verifies(), 1)
        self.assertEqual(self.lib.login_main_derives(), 1)
        self.assertEqual(self.lib.login_main_rotates(), 1)
        self.assertEqual(self.lib.login_main_commits(), 0)
        self.assertEqual(self.lib.login_main_recovers(), 0)
        self.assertEqual(self.lib.login_main_closes(), 1)
        order = [events.index(marker) for marker in (b'V', b'W', b'G', b'D', b'R', b'C', b'H', b'F', b'S', b'X')]
        self.assertEqual(order, sorted(set(order)))
        self.assertEqual(ctypes.string_at(self.lib.login_main_rotated_salt(), 16), bytes(range(16, 32)))
        self.assertEqual(ctypes.string_at(self.lib.login_main_rotated_verifier(), 32),
                         self.rotation_verifiers[b'new-secret'])
        self.assertTrue(events.endswith(b'FSX'))

    def test_selector_is_exact_complete_login_line_and_not_a_password_escape(self):
        for selector in (b':passwdx', b' :passwd', b':passwd ', b':PASSWD',
                         (b':passwd', 1), b':passwd\0'):
            with self.subTest(selector=selector):
                lines = [selector, b'secret', b'chosen_admin', b'secret']
                result, events = self.run_login(lines=lines)
                self.assertEqual(result, 0)
                self.assert_no_rotation(events)
                self.assertEqual(self.lib.login_main_verifies(), 2)
                self.assertEqual(self.lib.login_main_sleeps(), 1)
                self.assertNotIn(b'New password:', self.lib.login_main_prompts())
        result, events = self.run_login(lines=[b'chosen_admin', b':passwd', b'chosen_admin', b'secret'])
        self.assertEqual(result, 0)
        self.assert_no_rotation(events)
        self.assertEqual(self.lib.login_main_verifies(), 2)

    def test_rotation_selector_cannot_bypass_enrollment_activation_or_recovery(self):
        result, events = self.run_login(state=0, lines=[b':passwd', b'chosen_admin', b'secret', b'secret'])
        self.assertEqual(result, 0)
        self.assert_no_rotation(events)
        self.assertEqual(self.lib.login_main_commits(), 2)
        self.assertEqual(self.lib.login_main_verifies(), 0)
        self.assertEqual(self.lib.login_main_prompts().count(b'Account name:'), 2)
        for state, recovering in ((1, False), (1, True), (2, True)):
            with self.subTest(state=state, recovering=recovering):
                result, events = self.run_login(state=state, recovering=recovering,
                    lines=[b':passwd', b'chosen_admin', b'secret'])
                self.assertEqual(result, 0)
                self.assert_no_rotation(events)
                self.assertEqual(self.lib.login_main_verifies(), 1)
                self.assertEqual(self.lib.login_main_prompts(), b'Login: \nLogin: \nPassword: \n')
                self.assertIn(b'Complete account activation or recovery', self.lib.login_main_output())
                self.assertNotIn(b'Enter :passwd', self.lib.login_main_output())

    def test_selected_staged_b_must_authenticate_before_recovery_and_cannot_rotate(self):
        for lines, success in (([b':passwd', b'chosen_admin', b'secret'], False),
                ([b':passwd', b'chosen_admin', b'secret', b'chosen_admin', b'new-secret'], True)):
            with self.subTest(success=success):
                result, events = self.run_login(recovering=True, flags=self.RECOVER_SELECTED_B, lines=lines)
                self.assertEqual(result, 0 if success else 1)
                self.assert_no_rotation(events)
                self.assertEqual(self.lib.login_main_recovers(), int(success))
                self.assertEqual(self.lib.login_main_commits(), 0)
                self.assertNotIn(b'G', events)
                if success:
                    self.assertGreater(events.index(b'r'), events.rindex(b'V'))
                else:
                    self.assertNotIn(b'X', events)

    def test_rotation_request_survives_wrong_name_and_password_with_retry_delay(self):
        lines = [b':passwd', b'other_admin', b'secret', b'chosen_admin', b'wrong-current',
                 b'chosen_admin', b'secret', b'new-secret', b'new-secret']
        result, events = self.run_login(lines=lines, flags=self.SLEEP_INTERRUPTED)
        self.assertEqual(result, 0)
        self.assertEqual(self.lib.login_main_verifies(), 3)
        self.assertEqual(self.lib.login_main_sleeps(), 3)
        self.assertEqual(events.count(b'R'), 1)
        self.assertGreater(events.index(b'R'), events.rindex(b'V'))
        self.assertEqual(self.lib.login_main_output().count(b'Login incorrect.'), 2)
        for flags in (self.CLOCK_ERROR, self.SLEEP_ERROR):
            with self.subTest(flags=flags):
                result, events = self.run_login(lines=lines, flags=flags)
                self.assertEqual(result, 1)
                self.assertEqual(self.lib.login_main_verifies(), 1)
                self.assert_no_rotation(events)
                self.assertNotIn(b'G', events)

    def test_rotation_verifier_error_or_nonboolean_success_never_authorizes_update(self):
        for flags in (self.VERIFY_ERROR, self.VERIFY_NONBOOLEAN):
            with self.subTest(flags=flags):
                result, events = self.run_login(lines=self.rotation_lines()[:3], flags=flags)
                self.assertEqual(result, 1)
                self.assert_no_rotation(events)
                self.assertNotIn(b'G', events)
                self.assertNotIn(b'X', events)

    def test_rotation_rejects_invalid_or_mismatching_new_lines_before_one_update(self):
        attempts = ([b''], [(b'invalid-prefix', 1)], [b'x' * 129], [(b'new\0secret', 1)],
                    [b'candidate-one', b'candidate-two'], [b'candidate-one', b''],
                    [b'candidate-one', (b'invalid-confirmation', 1)],
                    [b'candidate-one', b'x' * 129])
        for attempt in attempts:
            with self.subTest(attempt=attempt):
                lines = self.rotation_lines()[:3] + attempt + [b'new-secret', b'new-secret']
                result, events = self.run_login(lines=lines)
                self.assertEqual(result, 0)
                self.assertEqual(self.lib.login_main_inputs(), len(lines))
                self.assertEqual(self.lib.login_main_derives(), 1)
                self.assertEqual(self.lib.login_main_rotates(), 1)
                self.assertEqual(self.lib.login_main_commits(), 0)
                self.assertEqual(self.lib.login_main_random_calls(), 1)

    def test_rotation_accepts_128_bytes_and_same_plaintext_with_fresh_entropy(self):
        for password in (b'boundary-password-' + b'x' * 110, b'secret'):
            with self.subTest(length=len(password)):
                self.assertIn(len(password), (128, 6))
                result, events = self.run_login(lines=self.rotation_lines(password), new_password=password)
                self.assertEqual(result, 0)
                self.assertEqual(self.lib.login_main_rotates(), 1)
                self.assertEqual(self.lib.login_main_random_calls(), 1)
                self.assertNotEqual(ctypes.string_at(self.lib.login_main_rotated_salt(), 16), bytes(range(16)))
                self.assertEqual(ctypes.string_at(self.lib.login_main_rotated_verifier(), 32),
                                 self.rotation_verifiers[password])

    def test_rotation_input_failure_at_every_prompt_clears_and_never_updates(self):
        for index in range(5):
            with self.subTest(prompt=index):
                lines = self.rotation_lines()[:index] + [(b'unaccepted-secret-prefix', -1)]
                result, events = self.run_login(lines=lines)
                self.assertEqual(result, 1)
                self.assert_no_rotation(events)
                self.assertEqual(self.lib.login_main_commits(), 0)
                self.assertNotIn(b'G', events)
                self.assertNotIn(b'X', events)

    def test_rotation_entropy_partial_eintr_is_fresh_and_errors_never_stage(self):
        result, events = self.run_login(lines=self.rotation_lines(), flags=self.RANDOM_INTERRUPTED_PARTIAL)
        self.assertEqual(result, 0)
        self.assertEqual(self.lib.login_main_random_calls(), 3)
        self.assertEqual(self.lib.login_main_rotates(), 1)
        for flags in (self.RANDOM_UNAVAILABLE, self.RANDOM_PARTIAL_ERROR,
                      self.RANDOM_ZERO, self.RANDOM_OVERCOUNT):
            with self.subTest(flags=flags):
                result, events = self.run_login(lines=self.rotation_lines(), flags=flags)
                self.assertEqual(result, 1)
                self.assert_no_rotation(events)
                self.assertEqual(self.lib.login_main_derives(), 0)
                self.assertEqual(self.lib.login_main_commits(), 0)
                self.assertNotIn(b'X', events)

    def test_rotation_derive_or_uncertain_store_failure_exits_without_retry_or_success(self):
        for flags, expected_rotations in ((self.DERIVE_ERROR, 0), (self.ROTATE_ERROR, 1)):
            with self.subTest(flags=flags):
                result, events = self.run_login(lines=self.rotation_lines(), flags=flags)
                self.assertEqual(result, 1)
                self.assertEqual(self.lib.login_main_derives(), 1)
                self.assertEqual(self.lib.login_main_rotates(), expected_rotations)
                self.assertEqual(self.lib.login_main_commits(), 0)
                self.assertEqual(self.lib.login_main_inputs(), 5)
                self.assertEqual(self.lib.login_main_closes(), 1)
                self.assertNotIn(b'S', events)
                self.assertNotIn(b'X', events)

    def test_rotation_final_checks_precede_success_and_consume_store_once(self):
        for flags in (self.STORE_CLOSE_ERROR, self.HOME_OPEN_ERROR, self.HOME_MODE_ERROR,
                      self.HOME_CHDIR_ERROR, self.HOME_CLOSE_ERROR, self.FINAL_IDENTITY_ERROR,
                      self.FINAL_FLUSH_ERROR):
            with self.subTest(flags=flags):
                result, events = self.run_login(lines=self.rotation_lines(), flags=flags)
                self.assertEqual(result, 1)
                self.assertEqual(self.lib.login_main_rotates(), 1)
                self.assertEqual(self.lib.login_main_closes(), 1)
                self.assertNotIn(b'S', events)
                self.assertNotIn(b'X', events)
        result, events = self.run_login(lines=self.rotation_lines(), flags=self.EXEC_ERROR)
        self.assertEqual(result, 1)
        self.assertTrue(events.endswith(b'SXq'))
        self.assertEqual(self.lib.login_main_execs(), 1)
        self.assertEqual(self.lib.login_main_rotates(), 1)

    def test_rotation_output_errors_never_retry_mutation_or_exec(self):
        cases = [(b'Enter :passwd at Login to change an account password.\n', self.rotation_lines(), 0),
                 (b'Authenticate the current account password.\n', self.rotation_lines(), 0),
                 (b'If saving is interrupted, the next sign-in may require the new password.\n', self.rotation_lines(), 0),
                 (b'Use a nonempty password of at most 128 bytes.\n', self.rotation_lines()[:3] + [b''], 0),
                 (b'Passwords did not match.\n', self.rotation_lines()[:3] + [b'one', b'two'], 0),
                 (b'Password changed.\n', self.rotation_lines(), 1)]
        for message, lines, expected_rotations in cases:
            with self.subTest(message=message):
                result, events = self.run_login(lines=lines, fail_write=message)
                self.assertEqual(result, 1)
                self.assertEqual(self.lib.login_main_rotates(), expected_rotations)
                self.assertNotIn(b'S', events)
                self.assertNotIn(b'X', events)

    def test_rotation_never_exposes_secrets_in_output_argv_or_fixed_environment(self):
        password = b'NewCredential-Q7-WholeSecret-9p4'
        result, events = self.run_login(lines=self.rotation_lines(password), new_password=password)
        self.assertEqual(result, 0)
        output = self.lib.login_main_output()
        environment = self.lib.login_main_environment()
        self.assertNotIn(b'secret', output)
        self.assertNotIn(b'secret', environment)
        for start in range(len(password) - 7):
            self.assertNotIn(password[start:start + 8], output)
            self.assertNotIn(password[start:start + 8], environment)
        self.assertEqual(output.count(b'Password changed.'), 1)
        self.assertEqual(environment, b'HOME=/root\nPATH=/bin\nUSER=chosen_admin\n'
                         b'LOGNAME=chosen_admin\nOK_CONSOLE_EPOCH=17\n')
        self.assertTrue(events.endswith(b'FSX'))


    def test_ordinary_authentication_drops_before_fixed_environment_exec(self):
        result, events = self.run_login(user_mode=1, lines=[b'alice', b'secret'])
        self.assertEqual(result, 0)
        self.assertLess(events.index(b'V'), events.index(b'Q'))
        self.assertLess(events.index(b'Q'), events.index(b'E'))
        self.assertLess(events.index(b'C'), events.index(b'E'))
        self.assertTrue(events.endswith(b'EjgFX'))
        self.assertEqual(self.lib.login_main_environment(),
                         b'HOME=/home/alice\nPATH=/bin\nUSER=alice\nLOGNAME=alice\nOK_CONSOLE_EPOCH=17\n')
        self.assertEqual(self.lib.login_main_commits(), 0)
        self.assertEqual(self.lib.login_main_rotates(), 0)

    def test_ordinary_wrong_or_unknown_name_pays_kdf_delay_without_drop(self):
        for attempt in ([b'alice', b'wrong'], [b'unknown', b'secret']):
            with self.subTest(attempt=attempt):
                result, events = self.run_login(user_mode=1, lines=attempt+[b'alice', b'secret'])
                self.assertEqual(result, 0)
                self.assertEqual(self.lib.login_main_verifies(), 2)
                self.assertEqual(self.lib.login_main_sleeps(), 1)
                self.assertGreater(events.index(b'E'), events.rindex(b'V'))

    @staticmethod
    def add_lines():
        return [b':useradd', b'chosen_admin', b'secret', b'carol', b'new-secret', b'new-secret']

    def test_add_authenticates_admin_stages_then_prepares_then_publishes(self):
        result, events = self.run_login(user_mode=1, lines=self.add_lines())
        self.assertEqual(result, 0)
        for left, right in ((b'V',b'N'),(b'N',b'A'),(b'A',b'T'),(b'T',b'B'),(b'B',b'Y'),(b'Y',b'Q')):
            self.assertLess(events.index(left),events.index(right))
        self.assertNotIn(b'E',events)
        self.assertIn(b'Account created.',self.lib.login_main_output())
        self.assertNotIn(b'new-secret',self.lib.login_main_output())

    def test_ordinary_credentials_cannot_authorize_add(self):
        result, events = self.run_login(user_mode=1,
            lines=[b':useradd',b'alice',b'secret',b'chosen_admin',b'secret',b'carol',b'new-secret',b'new-secret'])
        self.assertEqual(result,0)
        self.assertEqual(self.lib.login_main_verifies(),2)
        self.assertEqual(self.lib.login_main_sleeps(),1)
        self.assertGreater(events.index(b'T'),events.rindex(b'V'))

    def test_add_failure_never_publishes_before_home_or_executes(self):
        for failure, absent in ((128,b'T'),(256,b'T'),(2,b'B'),(4,b'Y'),(8,b'X'),(32,b'X')):
            with self.subTest(failure=failure):
                result, events = self.run_login(user_mode=1,user_failures=failure,lines=self.add_lines())
                self.assertEqual(result,1)
                self.assertNotIn(absent,events)
                self.assertNotIn(b'Account created.',self.lib.login_main_output())
                self.assertNotIn(b'X',events)

    def test_staged_add_rejects_ordinary_then_admin_completes_home_and_registry(self):
        result, events = self.run_login(user_mode=2,
            lines=[b'alice',b'secret',b'chosen_admin',b'secret'])
        self.assertEqual(result,0)
        self.assertEqual(self.lib.login_main_verifies(),2)
        self.assertLess(events.rindex(b'V'),events.index(b'B'))
        self.assertLess(events.index(b'B'),events.index(b'Y'))
        self.assertNotIn(b'T',events)
        self.assertNotIn(b'E',events)

    def test_staged_add_home_failure_leaves_registry_unpublished(self):
        result,events=self.run_login(user_mode=2,user_failures=4)
        self.assertEqual(result,1)
        self.assertIn(b'B',events)
        self.assertNotIn(b'Y',events)
        self.assertNotIn(b'X',events)

    def test_ordinary_cannot_login_during_administrator_activation_or_recovery(self):
        for state,recovering in ((1,False),(2,True)):
            with self.subTest(state=state,recovering=recovering):
                result,events=self.run_login(state=state,recovering=recovering,user_mode=1,
                    lines=[b'alice',b'secret',b'chosen_admin',b'secret'])
                self.assertEqual(result,0)
                self.assertEqual(self.lib.login_main_verifies(),2)
                self.assertNotIn(b'E',events)

    def test_ordinary_rotation_updates_only_selected_user(self):
        result,events=self.run_login(user_mode=1,
            lines=[b':passwd',b'alice',b'secret',b'new-secret',b'new-secret'])
        self.assertEqual(result,0)
        self.assertLess(events.index(b'V'),events.index(b'U'))
        self.assertLess(events.index(b'U'),events.index(b'E'))
        self.assertNotIn(b'R',events)
        self.assertEqual(self.lib.login_main_rotates(),0)
        self.assertIn(b'Password changed.',self.lib.login_main_output())

    def test_staged_rotation_recovers_only_matching_new_credentials(self):
        result,events=self.run_login(user_mode=3,
            lines=[b'alice',b'secret',b'alice',b'new-secret'])
        self.assertEqual(result,0)
        self.assertEqual(self.lib.login_main_verifies(),2)
        self.assertGreater(events.index(b'Y'),events.rindex(b'V'))
        self.assertLess(events.index(b'Y'),events.index(b'E'))
        result,events=self.run_login(user_mode=3)
        self.assertEqual(result,0)
        self.assertNotIn(b'Y',events)
        self.assertNotIn(b'E',events)

    def test_registry_open_close_and_home_entry_fail_closed(self):
        for failure in (1,32,64):
            with self.subTest(failure=failure):
                result,events=self.run_login(user_mode=1,user_failures=failure,lines=[b'alice',b'secret'])
                self.assertEqual(result,1)
                self.assertNotIn(b'X',events)
        result,events=self.run_login(user_mode=1,user_failures=16,
            lines=[b':passwd',b'alice',b'secret',b'new-secret',b'new-secret'])
        self.assertEqual(result,1)
        self.assertIn(b'U',events)
        self.assertNotIn(b'E',events)
        self.assertNotIn(b'X',events)


    def test_unrelated_ordinary_login_preserves_staged_rotation(self):
        result, events = self.run_login(user_mode=3, lines=[b'bob', b'secret'])
        self.assertEqual(result, 0)
        self.assertNotIn(b'Y', events)
        self.assertNotIn(b'U', events)
        self.assertIn(b'E', events)
        self.assertEqual(self.lib.login_main_environment(),
                         b'HOME=/home/bob\nPATH=/bin\nUSER=bob\nLOGNAME=bob\nOK_CONSOLE_EPOCH=17\n')
        result, events = self.run_login(user_mode=3,
            lines=[b':passwd', b'bob', b'secret', b'new-secret', b'new-secret'])
        self.assertEqual(result, 1)
        self.assertNotIn(b'Y', events)
        self.assertNotIn(b'U', events)
        self.assertNotIn(b'E', events)
        self.assertNotIn(b'X', events)

if __name__ == '__main__':
    unittest.main()
