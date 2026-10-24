# Native shell execution

`oksh` launches native user programs with `fork`, `pipe`, `dup2`, `execve` and
`waitpid`. Foreground pipelines may contain up to 16 commands; every stage is
created before execution starts, and stages execute concurrently. The pipeline
status is the last command's exit status, or 128 plus its terminating signal.
All children are reaped, including after a partial pipe/fork failure. A shared
launch barrier prevents already-created children from executing when construction
of a later stage fails.

Supported forms include:

```
hello | cat | cat
cat < input > output
echo another >> output
program 2> errors
program 2>> errors
program > combined 2>&1
program 2>&1 > output | cat > errors
echo first; echo next
program | cat && echo success || echo failure
cd /tmp && echo result > output; cat < /tmp/output
```

Sequential lists support `;`, `&&` and `||`, including adjacent operators and a
final `;`. Pipelines bind more tightly than list operators. `&&` and `||` have
equal precedence and associate left to right: `echo first || echo skipped &&
echo last` prints `first` and `last`. Each conditional tests the status of the
last executed pipeline; skipped pipelines neither open files nor create children
nor run parent builtins. `;` runs the next pipeline regardless of status. The
list returns the last executed pipeline's status.

Redirections apply after pipeline connections, in source order. Descriptors 0,
1 and 2 can be duplicated with `<&` or `>&`, or closed with `<&-` and `>&-`.
Single/double quotes, empty quoted arguments and backslash quoting preserve words
containing spaces or operators. Redirections need no surrounding spaces.

`cd`, `exit`, `echo` and `help` run in the parent for standalone commands, with
standard descriptors saved and restored around redirections. In a pipeline they
run in a child, so a piped `cd` cannot change the parent directory. `exit` without
an argument and end of input return the previous command status. Missing programs
return 127, other exec failures 126, syntax/limit errors 2, and setup failures 1.
An executed parent `exit` stops the rest of its list and the interactive shell.
An `exit` in a pipeline only terminates that stage.

The bounded command format allows 1,023 input bytes, 31 arguments per command,
16 commands in total across up to 16 list elements, and 32 redirections in total
per input line. A single pipeline can still use all 16 command slots. The shared
command storage bounds stack use rather than allocating a full command array for
every list element. Oversized interactive lines are drained and rejected as a
unit. The whole line, including skipped branches and text after `exit`, is checked
for syntax and capacity errors before files are opened or children are created.

This is a bounded foreground pipeline, list and redirection substrate. Variables,
substitutions, globbing, functions, scripts, shell control structures, job control
and terminal ownership are not implemented. In particular `$name` and wildcard
characters remain literal arguments. Background `&` and grouping are rejected.
PTY and controlling-terminal support are prerequisites for job control and require
separate native acceptance.
This implementation does not close the complete M5/POSIX shell milestone.

`tests/tools/test_oksh.py` runs hosted process/file tests and injected resource
failures, including short-circuit side effects, equal left-associative precedence,
parent state/descriptor restoration, exit propagation and repeated list cleanup.
`tests/native/oksh_pipeline.c`, packaged explicitly as
`/bin/oksh-acceptance`, runs the native execution suite. The independent observer
`tools/qualify_oksh_guest.py` records its actual QEMU output; hosted success is not
native execution evidence.

The SDK-only service-graph qualifier can package and run the same fixture with
`--shell-acceptance`. Its x86_64 Debug and Release adoption lanes run the current
signal-enabled native init/okcrt composition. They pass the large stream,
redirection/status checks and twenty repeated pipelines, followed by a fresh
interactive pipeline. Other native architectures retain compile coverage for
this suite; these two guests do not establish its execution on all ten profiles.
The later `--shell-acceptance --shell-lists` lane requires the extended fixture's
complete `OKSH_LISTS` record before final shell success. Fresh x86_64 Debug and
Release guests pass sequential/conditional lists, skipped side effects,
left-associative precedence, builtin/exit behavior, whole-line syntax rejection
and repeated pipeline/list combinations. Retained results are under workspace
`build/qualification/native-m7-shell-lists-{debug,release}-v1/`; separate strict
readbacks and read-only fsck checks are in
`native-m7-shell-lists-readback-v1/{debug,release}/`. These guests are host-retired
after shell sync and do not establish synchronized guest shutdown. The later
shell and expanded fixture also compile on all ten native profiles with Debug
and Release flags. Separate readback of the forty objects is retained in
`build/qualification/oksh-lists-cross-v1/readback/`; its original path-only
finalizer failure remains failed, and no successful compile was replayed.
