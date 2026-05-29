#ifndef APPS_COMMANDS_H
#define APPS_COMMANDS_H

struct command_entry {
    const char *name;
    int (*run)(int argc, char **argv);
    const char *summary;
};

int cmd_hello(int argc, char **argv);
int cmd_cat(int argc, char **argv);
int cmd_ls(int argc, char **argv);
int cmd_stat(int argc, char **argv);
int cmd_mkdir(int argc, char **argv);
int cmd_rm(int argc, char **argv);
int cmd_echo(int argc, char **argv);
int cmd_pwd(int argc, char **argv);
int cmd_cd(int argc, char **argv);
int cmd_whoami(int argc, char **argv);
int cmd_uname(int argc, char **argv);
int cmd_uptime(int argc, char **argv);
int cmd_touch(int argc, char **argv);
int cmd_help(int argc, char **argv);

const struct command_entry *commands_table(void);
const struct command_entry *find_command(const char *name);

#endif
