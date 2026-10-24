# Default Notes save behavior

`notes /home/english.txt Updated English note.` saves the words with a final
newline. `notes /home/english.txt` opens and prints the saved text. The command
is the existing native application; the isolated graphical editor remains a
separate workstation milestone.

Saving uses an exclusive temporary in the destination directory, writes all
bytes, syncs and closes that file, renames it, then syncs and closes the parent
directory. Only a completed sequence prints `Saved`. An error before rename
preserves the original destination and attempts to remove the owned temporary.
Cleanup failure can leave a temporary for recovery. An error after rename
reports `File replaced; save completion failed.` and exits unsuccessfully;
the new contents may already be visible. Failed close calls are not retried.

This bounded lane requires a caller-owned, owner-writable directory without
group/other write permission. It accepts new files and caller-owned regular files
with one link, matching effective GID, owner write permission and no special mode
bits. It verifies that the temporary has the intended owner, group and ordinary
permissions. A restrictive umask that would change existing permissions causes
an error. Symlinks, hardlinks and unsupported metadata are rejected for save.
Read mode follows the ordinary open policy and handles interrupted and partial I/O.

Paths are limited to 255 bytes. Temporary name collisions are bounded to 32
attempts. The native stat contract has no inode/device identity: the final
destination check covers presence, permissions, UID/GID, link count and length,
not concurrent replacement or same-size concurrent editing. Same-UID writers
remain trusted and uncoordinated. ACLs, xattrs, autosave, locking and arbitrary
metadata preservation require further work.

Run hosted syscall failure controls with an unused evidence directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/test_notes_save.py --output /tmp/notes-controls
```

These controls use actual scratch host files and injected syscall errors. They
are distinct from native guest execution. File fsync/rename ordering in this
application does not prove Kernel/filesystem crash durability; journalled
create/rename, actual block FLUSH, power-cut and reboot evidence remain required.
English text/files are the initial workflow lane; UTF-8/CJK, accessibility and
the complete workstation release gates remain open.
