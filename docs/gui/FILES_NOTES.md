# Open and edit text from Files

In Files, select a file with J/K and press Enter, or click its row. Notes opens
the selected file and shows its absolute path above the text. Ctrl+S replaces
that selected file using a synced staging file. A later complete save refreshes
the selected inode, and closing Notes then opening the file in Files reads the
saved text again. Notes' default Scratchpad remains a separate private note.

This initial path accepts at most 1023 bytes of printable English ASCII, LF and
TAB. It requires an ordinary mode 0600 file with exactly one link, owned by the
session user and group, in an owned mode 0700 folder. Files can create such a
folder with F and a file with N. Other files receive an explanatory refusal;
binary, oversized or unsupported bytes are never filtered or truncated into
editable text. Dirty Notes refuses a replacement handoff. Save or close Notes
before opening another file.

The reader verifies the displayed selection, opens relative to a checked folder
with NOFOLLOW/CLOEXEC, handles short reads with bounded interrupted retries,
checks EOF and metadata again, and closes both descriptors before changing the
document. A refused read or failed render preserves the old document and path.
A clean previous default-note load error can recover by opening a valid file
from Files. A failed or uncertain publication retains dirty text and blocks
later saves until Notes is closed and the selected file is inspected/reopened.

These controllers execute in the privileged desktop extension. SDK object
compilation and the QEMU GUI diagnostic do not qualify isolated application
execution, musl application integration, a durable home directory, device cache
durability, or atomic namespace comparison against external same-user writers.
