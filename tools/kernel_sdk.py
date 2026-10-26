#!/usr/bin/env python3
"""Validate or assemble an image from an exported ObfuscationKernel SDK."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import struct
import subprocess
from pathlib import Path

ARCH_TRIPLES = {
    "i386": "i386-elf", "x86_64": "x86_64-elf", "aarch64": "aarch64-elf",
    "arm32": "arm-none-eabi", "rv64": "riscv64-elf", "rv32": "riscv32-elf",
    "loongarch64": "loongarch64-elf", "mips": "mips-elf", "mips64": "mips64-elf", "ppc": "powerpc-eabi",
}
LEGACY_BIOS_PAYLOAD_CAPACITY = 256 * 32 * 512
EXTENDED_BIOS_PAYLOAD_CAPACITY = 512 * 32 * 512
COMMON_PROFILE = "serialized-common-eight-family-directory-create-ordered-free-init-zero-refill-optional-revoke-legacy-v4"
NATIVE_TERMINATION_PROFILE = "bootcpu-positive-pid-probe-term-kill-deferred-v1"


BOOT_ARCHIVE_DIRECTORY_PROFILE = "root-owned-ram-exact-sticky-sgid-v1"
NATIVE_CONSOLE_INPUT_PROFILE = "pid1-issued-epoch-fork-exec-leader-revoke-noecho-v1"
NATIVE_CONSOLE_INPUT_PROFILE_HEADER = "ok/sched/console_input_profile.hpp"
NATIVE_CONSOLE_INPUT_HEADERS = (
    NATIVE_CONSOLE_INPUT_PROFILE_HEADER, "ok/sched/console_input.hpp",
    "ok/sched/scheduler.hpp", "ok/uapi/syscall.h", "ok/core/types.hpp",
)
NATIVE_CONSOLE_INPUT_DEFINES = {
    "OK_NATIVE_CONSOLE_LEASE_VERSION": "1", "OK_CONSOLE_EPOCH_MAX": "0x3fffffffU",
    "OK_SYS_CONSOLE_CLAIM": "1028ULL", "OK_SYS_CONSOLE_REVOKE": "1029ULL",
    "OK_SYS_CONSOLE_FLUSH": "1030ULL",
}

NATIVE_PERSISTENT_SYNC_PROFILE = "retained-linked-mounted-ordered-journal-device-flush-v1"
NATIVE_PERSISTENT_SYNC_PROFILE_HEADER = "ok/fs/persistent_sync_profile.hpp"
NATIVE_PERSISTENT_SYNC_HEADERS = (
    NATIVE_PERSISTENT_SYNC_PROFILE_HEADER, "ok/fs/vfs.hpp", "ok/fs/ext4_mounted_metadata.hpp",
    "ok/posix/posix.hpp", "ok/uapi/syscall.h", "ok/core/types.hpp",
)
NATIVE_PERSISTENT_SYNC_DEFINES = {
    "OK_NATIVE_PERSISTENT_SYNC_VERSION": "1", "OK_SYS_SYNC_PERSISTENT": "1031ULL",
}

NATIVE_MOUNT_INFO_PROFILE = "global-nine-slot-read-only-derived-generation-v1"
NATIVE_MOUNT_INFO_PROFILE_HEADER = "ok/fs/mount_snapshot_profile.hpp"
NATIVE_MOUNT_INFO_HEADERS = (NATIVE_MOUNT_INFO_PROFILE_HEADER, "ok/fs/mount_snapshot.hpp",
                             "ok/user/native_mount_info.hpp", "ok/fs/vfs.hpp", "ok/uapi/syscall.h")
NATIVE_MOUNT_INFO_DEFINES = {
    "OK_NATIVE_MOUNT_INFO_VERSION": "1", "OK_SYS_MOUNT_INFO": "1034ULL",
    "OK_MOUNT_INFO_CAPACITY": "9U", "OK_MOUNT_INFO_PATH_CAPACITY": "256U",
    "OK_MOUNT_STATE_UNUSED": "0U", "OK_MOUNT_STATE_UNDERLYING_RAM": "1U",
    "OK_MOUNT_STATE_BORROWED": "2U", "OK_MOUNT_STATE_OWNED_PROVIDER": "3U",
    "OK_MOUNT_STATE_OWNED_RAM": "4U", "OK_MOUNT_STATE_DETACHED": "5U",
}


def validate_native_mount_info_profile(headers: Path) -> None:
    """Admit the exact bounded, pointer-free, observational native inventory."""
    for name in NATIVE_MOUNT_INFO_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK mount inventory header missing: " + name)
    source = (headers / NATIVE_MOUNT_INFO_PROFILE_HEADER).read_text()
    if not source.isascii() or any(token in source for token in ('\\', '??', '%:')):
        raise ValueError("kernel SDK mount inventory profile syntax mismatch")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = ["#pragma once", '#include "ok/core/types.hpp"', "#include <string_view>",
                "namespace ok::fs", "{",
                'inline constexpr std::string_view native_mount_snapshot_profile = "global-nine-slot-read-only-derived-generation-v1";',
                "inline constexpr u32 native_mount_snapshot_version = 1;",
                "inline constexpr u32 native_mount_snapshot_slots = 9;",
                "inline constexpr u32 native_mount_snapshot_path_bytes = 256;",
                "inline constexpr u32 native_mount_snapshot_wire_bytes = 288;", "} // namespace ok::fs"]
    if lines != expected:
        raise ValueError("kernel SDK mount inventory profile mismatch")
    validate_native_credentials_profile(headers)
    validate_uapi_version(headers / "ok/uapi/syscall.h")
    source = (headers / "ok/uapi/syscall.h").read_text()
    if not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source):
        raise ValueError("kernel SDK mount inventory UAPI syntax mismatch")
    source = re.sub(r"/\*.*?\*/|//[^\n]*", lambda match: re.sub(r"[^\n]", " ", match[0]),
                    source, flags=re.DOTALL)
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    for line in directives:
        if line.startswith("#define ") and not re.match(r"#define OK_[A-Z0-9_]+(?:\s|\(|$)", line):
            raise ValueError("kernel SDK mount inventory UAPI local macro mismatch")
    for name, value in NATIVE_MOUNT_INFO_DEFINES.items():
        definitions = [line for line in directives if re.match(r"#define " + name + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value]:
            raise ValueError("kernel SDK mount inventory UAPI mismatch: " + name)
    code = re.sub(r"^[ \t]*#.*$", "", source, flags=re.MULTILINE)
    records = re.findall(r"\bstruct\s+ok_mount_info\s*\{([^{}]*)\}\s*;", code)
    fields = ("uint32_t version; uint32_t size; uint32_t generation; uint32_t slot; "
              "uint32_t capacity; uint32_t state; uint32_t parent_id; uint32_t path_length; char path[OK_MOUNT_INFO_PATH_CAPACITY];")
    normalize = lambda value: re.findall(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\s]", value)
    if (len(records) != 1 or normalize(records[0]) != normalize(fields) or
            len(re.findall(r"\bok_mount_info\b", code)) != 1):
        raise ValueError("kernel SDK mount inventory wire layout mismatch")


NATIVE_SESSIONS_PROFILE = "bootcpu-serialized-process-group-session-console-lifecycle-v3"
NATIVE_SESSIONS_PROFILE_HEADER = "ok/user/native_sessions_profile.hpp"
NATIVE_SESSIONS_HEADERS = (
    NATIVE_SESSIONS_PROFILE_HEADER, "ok/sched/resources.hpp", "ok/sched/scheduler.hpp",
    "ok/posix/posix.hpp", "ok/syscall/syscall.hpp", "ok/uapi/syscall.h",
    "ok/core/module.hpp", "ok/core/types.hpp", "ok/user/linux_bootstrap.hpp",
    "ok/abi/linux_profile_data.hpp",
)
NATIVE_SESSIONS_DEFINES = {
    "OK_NATIVE_SESSIONS_VERSION": "3", "OK_SYS_SETPGID": "109ULL",
    "OK_SYS_GETPGRP": "111ULL", "OK_SYS_SETSID": "112ULL",
    "OK_SYS_GETPGID": "121ULL", "OK_SYS_GETSID": "124ULL", "OK_ESRCH": "3",
}


def validate_native_sessions_profile(headers: Path) -> None:
    """Admit bounded process membership with explicit single-console ownership."""
    for name in NATIVE_SESSIONS_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK native sessions header missing: " + name)
    source = (headers / NATIVE_SESSIONS_PROFILE_HEADER).read_text()
    if (not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source) or
            any(token in source for token in ('\\', '??', '%:'))):
        raise ValueError("kernel SDK native sessions profile requires canonical ASCII lines")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = [
        '#pragma once',
        '#include "ok/core/types.hpp"',
        '#include <string_view>',
        'namespace ok::user',
        '{',
        'inline constexpr std::string_view native_sessions_profile = "bootcpu-serialized-process-group-session-console-lifecycle-v3";',
        'inline constexpr u32 native_sessions_version = 3;',
        'inline constexpr u32 native_sessions_module_abi = 75;',
        'inline constexpr u32 native_sessions_pid_bits = 32;',
        'inline constexpr u32 native_sessions_process_capacity = 64;',
        'inline constexpr u32 native_sessions_fork_inherits = 1;',
        'inline constexpr u32 native_sessions_exec_preserves = 1;',
        'inline constexpr u32 native_sessions_reparent_preserves = 1;',
        'inline constexpr u32 native_sessions_controlling_tty = 1;',
        'inline constexpr u32 native_sessions_pty = 0;',
        'inline constexpr u32 native_sessions_job_control = 0;',
        '} // namespace ok::user',
    ]
    if lines != expected:
        raise ValueError("kernel SDK native sessions profile mismatch")
    validate_module_abi(headers / "ok/core/module.hpp")
    validate_uapi_version(headers / "ok/uapi/syscall.h")
    validate_native_credentials_profile(headers)
    source = (headers / "ok/uapi/syscall.h").read_text()
    source = re.sub(r"/\*.*?\*/|//[^\n]*", lambda match: re.sub(r"[^\n]", " ", match[0]),
                    source, flags=re.DOTALL)
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    for name, value in NATIVE_SESSIONS_DEFINES.items():
        definitions = [line for line in directives if re.match(r"#define " + re.escape(name) + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value]:
            raise ValueError("kernel SDK native sessions UAPI mismatch: " + name)


NATIVE_GROUP_SIGNAL_PROFILE = 'bootcpu-signed32-current-negative-pgid-probe-term-kill-deferred-partial-v2'
NATIVE_GROUP_SIGNAL_PROFILE_HEADER = "ok/user/native_group_signal_profile.hpp"
NATIVE_GROUP_SIGNAL_HEADERS = (
    NATIVE_GROUP_SIGNAL_PROFILE_HEADER, "ok/user/native_signal_target.hpp",
    "ok/user/native_process_group_signal.hpp",
    "ok/sched/resources.hpp", "ok/sched/scheduler.hpp", "ok/uapi/signal.h",
    "ok/uapi/syscall.h", "ok/core/module.hpp", "ok/core/types.hpp",
)


def validate_native_group_signal_profile(headers: Path) -> None:
    """Admit only serialized group probes and deferred TERM/KILL selection."""
    for name in NATIVE_GROUP_SIGNAL_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK native group signal header missing: " + name)
    source = (headers / NATIVE_GROUP_SIGNAL_PROFILE_HEADER).read_text()
    if (not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source) or
            any(token in source for token in (chr(92), "??", "%:"))):
        raise ValueError("kernel SDK native group signal profile requires canonical ASCII lines")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = [
        '#pragma once',
        '#include "ok/core/types.hpp"',
        '#include <string_view>',
        'namespace ok::user',
        '{',
        'inline constexpr std::string_view native_group_signal_profile = "bootcpu-signed32-current-negative-pgid-probe-term-kill-deferred-partial-v2";',
        'inline constexpr u32 native_group_signal_version = 2;',
        'inline constexpr u32 native_group_signal_module_abi = 75;',
        'inline constexpr u32 native_group_signal_pid_bits = 32;',
        'inline constexpr u32 native_group_signal_process_capacity = 64;',
        'inline constexpr u32 native_group_signal_current_group = 1;',
        'inline constexpr u32 native_group_signal_negative_group = 1;',
        'inline constexpr u32 native_group_signal_probe = 1;',
        'inline constexpr u32 native_group_signal_term = 15;',
        'inline constexpr u32 native_group_signal_kill = 9;',
        'inline constexpr u32 native_group_signal_deferred_fatal = 1;',
        'inline constexpr u32 native_group_signal_partial_success = 1;',
        'inline constexpr u32 native_group_signal_broadcast = 0;',
        'inline constexpr u32 native_group_signal_stop_continue = 0;',
        'inline constexpr u32 native_group_signal_controlling_tty = 1;',
        'inline constexpr u32 native_group_signal_job_control = 0;',
        'inline constexpr u32 native_group_signal_smp = 0;',
        '} // namespace ok::user',
    ]
    if lines != expected:
        raise ValueError("kernel SDK native group signal profile mismatch")
    validate_native_sessions_profile(headers)
    validate_native_termination_profile(headers)


NATIVE_CONSOLE_CONTROL_PROFILE = "bootcpu-lease-epoch-explicit-session-foreground-eio-pid32-ioctl-v1"
NATIVE_CONSOLE_CONTROL_PROFILE_HEADER = "ok/user/native_console_control_profile.hpp"
# Each implementation boundary used by this capability is explicitly hashed.
# The OS still links the exported library and never compiles kernel sources.
NATIVE_CONSOLE_CONTROL_HEADERS = (
    NATIVE_CONSOLE_CONTROL_PROFILE_HEADER, "ok/sched/console_control.hpp",
    "ok/sched/console_input.hpp", "ok/sched/console_input_profile.hpp",
    "ok/sched/resources.hpp", "ok/sched/scheduler.hpp", "ok/posix/posix.hpp",
    "ok/syscall/syscall.hpp", "ok/syscall/linux.hpp", "ok/user/console_control_dispatch.hpp",
    "ok/user/linux_bootstrap.hpp", "ok/abi/linux_console_ioctl.hpp",
    "ok/abi/linux_user.hpp", "ok/abi/linux_profile_data.hpp",
    "ok/user/native_sessions_profile.hpp", "ok/user/native_group_signal_profile.hpp",
    "ok/uapi/syscall.h", "ok/core/module.hpp", "ok/core/types.hpp",
)
NATIVE_CONSOLE_CONTROL_DEFINES = {
    "OK_NATIVE_CONSOLE_CONTROL_VERSION": "1", "OK_SYS_IOCTL": "16ULL",
    "OK_TIOCSCTTY": "0x540eU", "OK_TIOCGSID": "0x5429U",
    "OK_TIOCGPGRP": "0x540fU", "OK_TIOCSPGRP": "0x5410U",
    "OK_EBADF": "9", "OK_EACCES": "13", "OK_EFAULT": "14", "OK_EIO": "5",
    "OK_EPERM": "1", "OK_ESRCH": "3", "OK_ENOTTY": "25", "OK_EOPNOTSUPP": "95",
}


def validate_native_console_control_profile(headers: Path) -> None:
    """Admit explicit one-console foreground control, without full job control."""
    for name in NATIVE_CONSOLE_CONTROL_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK native console control header missing: " + name)
    source = (headers / NATIVE_CONSOLE_CONTROL_PROFILE_HEADER).read_text()
    if (not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source) or
            any(token in source for token in (chr(92), "??", "%:"))):
        raise ValueError("kernel SDK native console control profile requires canonical ASCII lines")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = [
        '#pragma once',
        '#include "ok/core/types.hpp"',
        '#include <string_view>',
        'namespace ok::user',
        '{',
        'inline constexpr std::string_view native_console_control_profile = "bootcpu-lease-epoch-explicit-session-foreground-eio-pid32-ioctl-v1";',
        'inline constexpr u32 native_console_control_version = 1;',
        'inline constexpr u32 native_console_control_module_abi = 75;',
        'inline constexpr u32 native_console_control_serialized_boot_cpu = 1;',
        'inline constexpr u32 native_console_control_lease_epoch = 1;',
        'inline constexpr u32 native_console_control_explicit_acquire = 1;',
        'inline constexpr u32 native_console_control_original_lease_session_leader = 1;',
        'inline constexpr u32 native_console_control_foreground_read = 1;',
        'inline constexpr u32 native_console_control_background_eio = 1;',
        'inline constexpr u32 native_console_control_same_session_background_control = 1;',
        'inline constexpr u32 native_console_control_zombie_group_until_reap = 1;',
        'inline constexpr u32 native_console_control_pid_bytes = 4;',
        'inline constexpr u32 native_console_control_native_uniform_requests = 1;',
        'inline constexpr u32 native_console_control_linux_generated_requests = 1;',
        'inline constexpr u32 native_console_control_auto_open_acquire = 0;',
        'inline constexpr u32 native_console_control_force_steal = 0;',
        'inline constexpr u32 native_console_control_empty_foreground_replaced = 0;',
        'inline constexpr u32 native_console_control_pty = 0;',
        'inline constexpr u32 native_console_control_termios = 0;',
        'inline constexpr u32 native_console_control_stop_continue = 0;',
        'inline constexpr u32 native_console_control_job_control = 0;',
        'inline constexpr u32 native_console_control_smp = 0;',
        '} // namespace ok::user',
    ]
    if lines != expected:
        raise ValueError("kernel SDK native console control profile mismatch")
    validate_native_sessions_profile(headers)
    validate_native_group_signal_profile(headers)
    validate_native_console_input_profile(headers)
    source = (headers / "ok/uapi/syscall.h").read_text()
    source = re.sub(r"/\*.*?\*/|//[^\n]*", lambda match: re.sub(r"[^\n]", " ", match[0]),
                    source, flags=re.DOTALL)
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    for name, value in NATIVE_CONSOLE_CONTROL_DEFINES.items():
        definitions = [line for line in directives if re.match(r"#define " + re.escape(name) + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value]:
            raise ValueError("kernel SDK native console control UAPI mismatch: " + name)


NATIVE_PTY_PROFILE = "bootcpu-native-raw-pair-ofd-waits-drain-eof-eio-v1"
NATIVE_PTY_PROFILE_HEADER = "ok/user/native_pty_profile.hpp"
# Hash each owner, reservation and publication boundary; these are admission
# dependencies, not evidence that a target executed the transport.
NATIVE_PTY_HEADERS = (
    NATIVE_PTY_PROFILE_HEADER, "ok/sched/raw_pty_transport.hpp",
    "ok/sched/pty_pair.hpp", "ok/sched/resources.hpp", "ok/sched/scheduler.hpp",
    "ok/sched/descriptor_reservation.hpp", "ok/user/native_pty_pair_dispatch.hpp",
    "ok/syscall/syscall.hpp", "ok/uapi/syscall.h", "ok/core/module.hpp", "ok/core/types.hpp",
)
NATIVE_PTY_DEFINES = {
    "OK_SYS_PTY_PAIR": "1035ULL", "OK_NATIVE_PTY_PAIR_VERSION": "1U",
    "OK_NATIVE_PTY_NONBLOCK": "0x0800U", "OK_NATIVE_PTY_CLOEXEC": "0x080000U",
}


def validate_native_pty_profile(headers: Path) -> None:
    """Admit only the bounded native raw pair, without terminal policy claims."""
    for name in NATIVE_PTY_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK native PTY header missing: " + name)
    source = (headers / NATIVE_PTY_PROFILE_HEADER).read_text()
    if (not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source) or
            any(token in source for token in (chr(92), "??", "%:"))):
        raise ValueError("kernel SDK native PTY profile requires canonical ASCII lines")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = [
        '#pragma once',
        '#include "ok/core/types.hpp"',
        '#include <string_view>',
        'namespace ok::user',
        '{',
        'inline constexpr std::string_view native_pty_profile = "bootcpu-native-raw-pair-ofd-waits-drain-eof-eio-v1";',
        'inline constexpr u32 native_pty_version = 1;',
        'inline constexpr u32 native_pty_module_abi = 75;',
        'inline constexpr u32 native_pty_pair_capacity = 8;',
        'inline constexpr u32 native_pty_queue_capacity = 4096;',
        'inline constexpr u32 native_pty_generation_bits = 64;',
        'inline constexpr u32 native_pty_descriptor_bytes = 4;',
        'inline constexpr u32 native_pty_pair_output_bytes = 8;',
        'inline constexpr u32 native_pty_serialized_boot_cpu = 1;',
        'inline constexpr u32 native_pty_raw = 1;',
        'inline constexpr u32 native_pty_retained_ofd_waits = 1;',
        'inline constexpr u32 native_pty_unconditional_hangup = 1;',
        'inline constexpr u32 native_pty_slave_master_closed_poll_error = 1;',
        'inline constexpr u32 native_pty_master_slave_closed_poll_error = 0;',
        'inline constexpr u32 native_pty_scm_rights = 0;',
        'inline constexpr u32 native_pty_linux_creation = 0;',
        'inline constexpr u32 native_pty_slave_reopen = 0;',
        'inline constexpr u32 native_pty_termios = 0;',
        'inline constexpr u32 native_pty_controlling_terminal = 0;',
        'inline constexpr u32 native_pty_terminal_signals = 0;',
        'inline constexpr u32 native_pty_job_control = 0;',
        'inline constexpr u32 native_pty_devpts = 0;',
        'inline constexpr u32 native_pty_smp = 0;',
        '} // namespace ok::user',
    ]
    if lines != expected:
        raise ValueError("kernel SDK native PTY profile mismatch")
    validate_module_abi(headers / "ok/core/module.hpp")
    validate_uapi_version(headers / "ok/uapi/syscall.h")
    source = (headers / "ok/uapi/syscall.h").read_text()
    if not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source):
        raise ValueError("kernel SDK native PTY UAPI requires canonical ASCII lines")
    source = re.sub(r"/\*.*?\*/|//[^\n]*", lambda match: re.sub(r"[^\n]", " ", match[0]),
                    source, flags=re.DOTALL)
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    conditions = [line for line in directives if re.match(r"#\s*(?:if|ifdef|ifndef|elif|else|endif)\b", line)]
    if conditions != ["#ifndef OK_UAPI_SYSCALL_H", "#endif"]:
        raise ValueError("kernel SDK native PTY UAPI must be unconditional within its include guard")
    if directives[:2] != ["#ifndef OK_UAPI_SYSCALL_H", "#define OK_UAPI_SYSCALL_H"] or directives[-1:] != ["#endif"]:
        raise ValueError("kernel SDK native PTY UAPI requires its canonical include guard")
    for name, value in NATIVE_PTY_DEFINES.items():
        definitions = [line for line in directives if re.match(r"#\s*define\s+" + re.escape(name) + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value] or any(
                re.match(r"#\s*undef\s+" + re.escape(name) + r"(?:\s|$)", line) for line in directives):
            raise ValueError("kernel SDK native PTY UAPI mismatch: " + name)


NATIVE_METADATA_PROFILE = "checked-mode-root-owner-u32-v1"
NATIVE_METADATA_PROFILE_HEADER = "ok/user/native_metadata_profile.hpp"
NATIVE_METADATA_HEADERS = (NATIVE_METADATA_PROFILE_HEADER, "ok/user/native_metadata.hpp",
                           "ok/fs/mode_change.hpp", "ok/fs/vfs.hpp", "ok/posix/posix.hpp",
                           "ok/syscall/linux.hpp", "ok/syscall/syscall.hpp", "ok/uapi/syscall.h",
                           "ok/core/types.hpp", "ok/core/module.hpp")
NATIVE_METADATA_DEFINES = {
    "OK_NATIVE_METADATA_VERSION": "1", "OK_SYS_CHMOD": "90ULL", "OK_SYS_FCHMOD": "91ULL",
    "OK_SYS_CHOWN": "92ULL", "OK_SYS_FCHOWN": "93ULL", "OK_SYS_FCHOWNAT": "260ULL",
    "OK_SYS_FCHMODAT": "268ULL", "OK_AT_EMPTY_PATH": "0x1000U", "OK_AT_SYMLINK_NOFOLLOW": "0x0100U",
}


def validate_native_metadata_profile(headers: Path) -> None:
    """Require the checked provider-result boundary, not a hardware claim."""
    for name in NATIVE_METADATA_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK native metadata header missing: " + name)
    source = (headers / NATIVE_METADATA_PROFILE_HEADER).read_text()
    if (not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source) or
            any(token in source for token in ('\\', '??', '%:'))):
        raise ValueError("kernel SDK native metadata profile requires canonical ASCII lines")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = ["#pragma once", '#include "ok/core/types.hpp"', "#include <string_view>",
                "namespace ok::user", "{",
                'inline constexpr std::string_view native_metadata_profile = "checked-mode-root-owner-u32-v1";',
                "inline constexpr u32 native_metadata_version = 1;",
                "inline constexpr u32 native_metadata_module_abi = 75;", "} // namespace ok::user"]
    if lines != expected:
        raise ValueError("kernel SDK native metadata profile mismatch")
    validate_module_abi(headers / "ok/core/module.hpp")
    validate_native_credentials_profile(headers)
    validate_uapi_version(headers / "ok/uapi/syscall.h")
    source = (headers / "ok/uapi/syscall.h").read_text()
    source = re.sub(r"/\*.*?\*/|//[^\n]*", lambda match: re.sub(r"[^\n]", " ", match[0]),
                    source, flags=re.DOTALL)
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    for name, value in NATIVE_METADATA_DEFINES.items():
        definitions = [line for line in directives if re.match(r"#define " + re.escape(name) + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value]:
            raise ValueError("kernel SDK native metadata UAPI mismatch: " + name)


NATIVE_POWER_PROFILE = "original-init-scalar-prepare-queued-commit-v1"
NATIVE_POWER_PROFILE_HEADER = "ok/user/native_power_profile.hpp"
NATIVE_POWER_HEADERS = (NATIVE_POWER_PROFILE_HEADER, "ok/uapi/syscall.h", "ok/core/types.hpp")
NATIVE_POWER_DEFINES = {
    "OK_NATIVE_POWER_VERSION": "1", "OK_POWER_TOKEN_MAX": "0x3fffffffU",
    "OK_POWER_HALT": "1U", "OK_POWER_REBOOT": "2U", "OK_POWER_POWEROFF": "3U",
    "OK_SYS_POWER_PREPARE": "1032ULL", "OK_SYS_POWER_COMMIT": "1033ULL",
}


def validate_native_power_profile(headers: Path) -> None:
    """Require scalar selectors and queued commit; this is not backend support."""
    for name in NATIVE_POWER_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK native power header missing: " + name)
    source = (headers / NATIVE_POWER_PROFILE_HEADER).read_text()
    if (not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source) or
            "\\" in source or "??" in source):
        raise ValueError("kernel SDK native power profile requires canonical ASCII lines")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = ["#pragma once", '#include "ok/core/types.hpp"', "#include <string_view>",
                "namespace ok::user", "{",
                'inline constexpr std::string_view native_power_profile = "original-init-scalar-prepare-queued-commit-v1";',
                "inline constexpr u32 native_power_version = 1;",
                "inline constexpr u32 native_power_token_limit = 0x3fffffff;", "} // namespace ok::user"]
    if lines != expected:
        raise ValueError("kernel SDK native power profile mismatch")
    validate_native_console_input_profile(headers)
    validate_uapi_version(headers / "ok/uapi/syscall.h")
    source = (headers / "ok/uapi/syscall.h").read_text()
    source = re.sub(r"/\*.*?\*/|//[^\n]*", lambda m: re.sub(r"[^\n]", " ", m.group()), source, flags=re.DOTALL)
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    for name, value in NATIVE_POWER_DEFINES.items():
        definitions = [line for line in directives if re.match(r"#define " + re.escape(name) + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value]:
            raise ValueError("kernel SDK native power UAPI mismatch: " + name)


def validate_native_persistent_sync_profile(headers: Path) -> None:
    """Require explicit retained mounted-provider synchronization capability."""
    for name in NATIVE_PERSISTENT_SYNC_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK persistent sync header missing: " + name)
    source = (headers / NATIVE_PERSISTENT_SYNC_PROFILE_HEADER).read_text()
    if (not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source) or
            "\\" in source or "??" in source):
        raise ValueError("kernel SDK persistent sync profile requires canonical ASCII lines")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = ["#pragma once", '#include "ok/core/types.hpp"', "#include <string_view>",
                "namespace ok::fs", "{",
                'inline constexpr std::string_view native_persistent_sync_profile = "retained-linked-mounted-ordered-journal-device-flush-v1";',
                "inline constexpr u32 native_persistent_sync_version = 1;", "} // namespace ok::fs"]
    if lines != expected:
        raise ValueError("kernel SDK persistent sync profile mismatch")
    validate_native_console_input_profile(headers)
    source = (headers / "ok/uapi/syscall.h").read_text()
    source = re.sub(r"/\*.*?\*/|//[^\n]*",
                    lambda m: re.sub(r"[^\n]", " ", m.group()), source, flags=re.DOTALL)
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    for name, value in NATIVE_PERSISTENT_SYNC_DEFINES.items():
        definitions = [line for line in directives
                       if re.match(r"#define " + re.escape(name) + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value]:
            raise ValueError("kernel SDK persistent sync UAPI mismatch: " + name)


def validate_native_console_input_profile(headers: Path) -> None:
    """Require explicit epoch-bound console authority and its native UAPI."""
    for name in NATIVE_CONSOLE_INPUT_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK native console input header missing: " + name)
    source = (headers / NATIVE_CONSOLE_INPUT_PROFILE_HEADER).read_text()
    if not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source):
        raise ValueError("kernel SDK native console input profile requires ASCII source lines")
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = ["#pragma once", '#include "ok/core/types.hpp"', "#include <string_view>",
                "namespace ok::sched", "{",
                'inline constexpr std::string_view native_console_input_profile = "pid1-issued-epoch-fork-exec-leader-revoke-noecho-v1";',
                "inline constexpr u32 native_console_epoch_limit = 0x3fffffff;",
                "} // namespace ok::sched"]
    if lines != expected:
        raise ValueError("kernel SDK native console input profile mismatch")
    # The existing unconditional UAPI checks reject literals and directives that
    # can hide definitions. Preserve token boundaries when erasing comments.
    validate_native_credentials_profile(headers)
    source = (headers / "ok/uapi/syscall.h").read_text()
    if not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source):
        raise ValueError("kernel SDK native console input UAPI requires ASCII source lines")
    source = re.sub(r"/\*.*?\*/|//[^\n]*",
                    lambda match: re.sub(r"[^\n]", " ", match.group()), source, flags=re.DOTALL)
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    for name, value in NATIVE_CONSOLE_INPUT_DEFINES.items():
        definitions = [line for line in directives
                       if re.match(r"#define " + re.escape(name) + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value]:
            raise ValueError("kernel SDK native console input UAPI mismatch: " + name)


BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADER = "ok/fs/archive_directory_profile.hpp"
BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADERS = (
    BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADER, "ok/fs/archive.hpp", "ok/fs/vfs.hpp",
    "ok/core/types.hpp",
)


def validate_boot_archive_directory_profile(headers: Path) -> None:
    """Require the exact bounded RAM-directory mode capability declaration."""
    for name in BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK boot archive directory header missing: " + name)
    source = (headers / BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADER).read_text()
    if not source.isascii() or any(ord(c) < 32 and c not in "\t\n" for c in source):
        raise ValueError("kernel SDK boot archive directory profile requires ASCII source lines")
    if "\\" in source or "??" in source:
        raise ValueError("kernel SDK boot archive directory profile rejects line splicing")
    # Admit this canonical header verbatim; regex comment removal can alter
    # string literals or join distinct preprocessing tokens.
    lines = [" ".join(line.split()) for line in source.split("\n") if line.strip()]
    expected = ["#pragma once", '#include "ok/core/types.hpp"', "#include <string_view>",
                "namespace ok::fs", "{",
                'inline constexpr std::string_view boot_archive_directory_profile = "root-owned-ram-exact-sticky-sgid-v1";',
                "inline constexpr u32 boot_archive_directory_mode_mask = 03777;",
                "inline constexpr u32 boot_archive_regular_mode_mask = 0777;", "} // namespace ok::fs"]
    if lines != expected:
        raise ValueError("kernel SDK boot archive directory profile mismatch")


NATIVE_CREDENTIALS_PROFILE = "bootcpu-single-live-thread-real-effective-saved-v1"
NATIVE_CREDENTIALS_HEADERS = (
    "ok/uapi/syscall.h", "ok/user/native_credentials.hpp",
    "ok/user/credential_change.hpp", "ok/user/linux_credentials.hpp",
    "ok/sched/scheduler.hpp",
)
NATIVE_CREDENTIALS_DEFINES = {
    "OK_NATIVE_CREDENTIALS_VERSION": "1", "OK_SYS_SETUID": "105ULL",
    "OK_SYS_SETGID": "106ULL", "OK_SYS_SETREUID": "113ULL",
    "OK_SYS_SETREGID": "114ULL", "OK_SYS_SETRESUID": "117ULL",
    "OK_SYS_GETRESUID": "118ULL", "OK_SYS_SETRESGID": "119ULL",
    "OK_SYS_GETRESGID": "120ULL", "OK_ID_UNCHANGED": "UINT32_C(0xffffffff)",
}


def validate_native_credentials_profile(headers: Path) -> None:
    """Require an unconditional fixed-width additive native credential UAPI."""
    for name in NATIVE_CREDENTIALS_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("kernel SDK native credentials header missing: " + name)
    source = (headers / "ok/uapi/syscall.h").read_text()
    if "\\" in source or "??" in source:
        raise ValueError("kernel SDK native credentials UAPI rejects line splicing")
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    # This C UAPI has one include guard and no conditional feature sections.
    # Reject local directives, line splicing and literal impersonations.
    if any(token in source for token in ('\\', '"', "'", '%:', '??')):
        raise ValueError("kernel SDK native credentials UAPI has unsupported syntax")
    directives = [" ".join(line.split()) for line in source.splitlines()
                  if line.lstrip().startswith("#")]
    if (directives[:2] != ["#ifndef OK_UAPI_SYSCALL_H", "#define OK_UAPI_SYSCALL_H"] or
            not directives or directives[-1] != "#endif" or
            any(not (line.startswith("#define ") or line == "#include <stdint.h>")
                for line in directives[2:-1])):
        raise ValueError("kernel SDK native credentials UAPI must be unconditional")
    if [line for line in directives if re.match(r"#define OK_UAPI_SYSCALL_H(?:\s|\(|$)", line)] != ["#define OK_UAPI_SYSCALL_H"]:
        raise ValueError("kernel SDK native credentials UAPI redefines its guard")
    if any(re.match(r"#define UINT32_C(?:\s|\(|$)", line) for line in directives):
        raise ValueError("kernel SDK native credentials UAPI redefines UINT32_C")
    for name, value in NATIVE_CREDENTIALS_DEFINES.items():
        definitions = [line for line in directives
                       if re.match(r"#define " + re.escape(name) + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + value]:
            raise ValueError("kernel SDK native credentials UAPI mismatch: " + name)


def validate_native_termination_profile(headers: Path) -> None:
    """Pin the complete bounded C UAPI, including its unconditional definitions."""
    path = headers / "ok/uapi/signal.h"
    if not path.is_file():
        raise ValueError("kernel SDK native termination UAPI is missing")
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(), flags=re.DOTALL)
    lines = [" ".join(line.split()) for line in source.splitlines() if line.strip()]
    expected = ["#ifndef OK_UAPI_SIGNAL_H", "#define OK_UAPI_SIGNAL_H",
                "#define OK_SIGKILL 9", "#define OK_SIGTERM 15",
                "#define OK_NATIVE_SIGNAL_MAX 64", "#define OK_NATIVE_TERMINATION_VERSION 1", "#endif"]
    if lines != expected:
        raise ValueError("kernel SDK native termination UAPI mismatch")


COMMON_HEADERS = (
    "include/ok/fs/ext4_mounted_common_profile.hpp",
    "include/ok/fs/ext4_mounted_metadata.hpp",
    "include/ok/fs/ext4_mounted_common_opening_budget.hpp",
    "include/ok/block/session_counters.hpp",
)


DIRECTORY_CREATE_PROFILE_HEADER = "ok/fs/ext4_directory_create_sdk_profile.hpp"
DIRECTORY_CREATE_PROFILE = "bounded-journalled-single-block-directory-create-ordered-free-init-v2"
DIRECTORY_CREATE_PROFILE_HEADERS = (
    DIRECTORY_CREATE_PROFILE_HEADER, "ok/fs/ext4_directory_create_plan.hpp",
    "ok/fs/ext4_directory_create_witness.hpp", "ok/fs/ext4_create_transaction.hpp",
    "ok/fs/ext4_owned_transaction.hpp", "ok/fs/ext4_directory_initialization_budget.hpp",
    "ok/fs/ext4_replay_view.hpp",
    "ok/fs/ext4_completion.hpp", "ok/fs/ext4_recovery.hpp",
    "ok/fs/ext4_replay_shape.hpp", "ok/fs/ext4_mounted_metadata.hpp",
    "ok/fs/ext4_mounted_startup_port.inc",
)


def validate_directory_create_profile(headers: Path) -> None:
    """Require the explicit bounded directory producer/consumer contract."""
    for name in DIRECTORY_CREATE_PROFILE_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("SDK75 directory-create contract header is missing: " + name)
    source = shared_file_contract_code((headers / DIRECTORY_CREATE_PROFILE_HEADER).read_text())
    name = "ext4_directory_create_profile"
    pattern = rf'^[ \t]*inline[ \t]+constexpr[ \t]+std::string_view[ \t]+{name}[ \t]*=[ \t]*"([^"\n]+)"[ \t]*;[ \t]*$'
    if contract_declaration_values(source, name, pattern) != [DIRECTORY_CREATE_PROFILE]:
        raise ValueError("SDK75 directory-create profile mismatch")
    for name, kind, expected in (("ext4_directory_create_module_abi", "u32", "75"),
                                 ("ext4_directory_create_home_capacity", "usize", "8"),
                                 ("ext4_directory_create_owner_buffers", "usize", "9")):
        pattern = rf"^[ \t]*inline[ \t]+constexpr[ \t]+{kind}[ \t]+{name}[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 directory-create contract mismatch: " + name)


UNIX_PATHNAME_PROFILE_HEADER = "ok/sched/unix_pathname_sdk_profile.hpp"
UNIX_PATHNAME_PROFILE = "bootcpu-ram-pathname-stream-owned-queue-direct-v1"
UNIX_PATHNAME_PROFILE_HEADERS = (
    UNIX_PATHNAME_PROFILE_HEADER, "ok/sched/unix_rights.hpp", "ok/sched/resources.hpp",
    "ok/fs/vfs.hpp", "ok/abi/linux_unix_pathname.hpp", "ok/user/unix_pathname.hpp",
    "ok/user/unix_original_ofd.hpp", "ok/user/unix_pathname_operation.hpp",
)


def validate_unix_pathname_profile(headers: Path) -> None:
    for name in UNIX_PATHNAME_PROFILE_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("SDK75 UNIX pathname contract header is missing: " + name)
    source = shared_file_contract_code((headers / UNIX_PATHNAME_PROFILE_HEADER).read_text())
    for name in ("native_unix_pathname_profile", "linux_unix_pathname_profile"):
        pattern = rf'^[ \t]*inline[ \t]+constexpr[ \t]+std::string_view[ \t]+{name}[ \t]*=[ \t]*"([^"\n]+)"[ \t]*;[ \t]*$'
        if contract_declaration_values(source, name, pattern) != [UNIX_PATHNAME_PROFILE]:
            raise ValueError("SDK75 UNIX pathname profile mismatch: " + name)
    for name, kind, expected in (("unix_pathname_module_abi", "u32", "75"),
            ("unix_pathname_endpoint_capacity", "usize", "32"),
            ("unix_pathname_backlog_capacity", "usize", "4"),
            ("unix_pathname_address_capacity", "usize", "110"),
            ("unix_pathname_text_capacity", "usize", "107"),
            ("unix_pathname_peer_credentials_bytes", "usize", "12")):
        pattern = rf"^[ \t]*inline[ \t]+constexpr[ \t]+{kind}[ \t]+{name}[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 UNIX pathname contract mismatch: " + name)


UDP_PROFILE_HEADER = "ok/net/native_udp_sdk_profile.hpp"
NATIVE_UDP_PROFILE = "bootcpu-static-peer-ipv4-polling-captured-connected-zero-send-v3"
LINUX_UDP_PROFILE = "bootcpu-static-peer-ipv4-captured-connected-zero-send-v3"
CONNECTED_UDP_PROFILE = "bounded-static-peer-association-zero-destination-output-v2"
UDP_PROFILE_HEADERS = (
    UDP_PROFILE_HEADER, "ok/net/wire.hpp", "ok/net/native_udp.hpp", "ok/net/native_udp_executor.hpp",
    "ok/net/native_udp_poll.hpp", "ok/net/native_udp_readiness_sequence.hpp",
    "ok/abi/linux_udp_address.hpp", "ok/abi/linux_udp_call.hpp", "ok/abi/linux_udp_data.hpp",
    "ok/abi/linux_udp_name_data.hpp", "ok/abi/linux_udp_connected_data.hpp",
)


SHARED_FILE_PROFILE_HEADER = "ok/user/native_shared_files_sdk_profile.hpp"
NATIVE_SHARED_FILE_PROFILE = "bootcpu-volatile-sealed-size-write-eager-pages-v2"
LINUX_SHARED_FILE_PROFILE = "bootcpu-volatile-sealed-size-write-eager-pages-v2"
SHARED_FILE_PROFILE_HEADERS = (
    SHARED_FILE_PROFILE_HEADER, "ok/user/native_shared_files.hpp",
    "ok/user/native_shared_file_handle.hpp", "ok/user/native_mapping_pages.hpp",
    "ok/user/native_page_pool.hpp", "ok/abi/linux_memfd.hpp",
)


FUTEX_WAKE_OPERATION_PROFILE_HEADER = "ok/user/native_futex_wake_operation_sdk_profile.hpp"
FUTEX_WAKE_OPERATION_PROFILE = "bootcpu-serialized-two-key-private-anonymous-shared-signed-wrap-legacy-count-v1"
FUTEX_WAKE_OPERATION_PROFILE_HEADERS = (
    FUTEX_WAKE_OPERATION_PROFILE_HEADER, "ok/user/native_futex.hpp",
    "ok/abi/linux_futex_wake_operation.hpp", "ok/user/linux_bootstrap.hpp",
    "ok/user/native_mapping_pages.hpp", "ok/user/native_page_pool.hpp",
    "ok/sched/scheduler.hpp", "ok/sched/resources.hpp",
)


def validate_futex_wake_operation_profile(headers: Path) -> None:
    """Require the explicit serialized two-key contract, without claiming execution."""
    for name in FUTEX_WAKE_OPERATION_PROFILE_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("SDK75 futex wake-operation contract header is missing: " + name)
    source = shared_file_contract_code((headers / FUTEX_WAKE_OPERATION_PROFILE_HEADER).read_text())
    for name in ("native_futex_wake_operation_profile", "linux_futex_wake_operation_profile"):
        pattern = rf'^[ \t]*inline[ \t]+constexpr[ \t]+std::string_view[ \t]+{name}[ \t]*=[ \t]*"([^"\n]+)"[ \t]*;[ \t]*$'
        if contract_declaration_values(source, name, pattern) != [FUTEX_WAKE_OPERATION_PROFILE]:
            raise ValueError("SDK75 futex wake-operation profile mismatch: " + name)
    for name, kind, expected in (
            ("native_futex_wake_operation_module_abi", "u32", "75"),
            ("native_futex_wake_operation_word_bits", "usize", "32"),
            ("native_futex_wake_operation_operand_bits", "usize", "12"),
            ("native_futex_wake_operation_shift_bits", "usize", "5"),
            ("native_futex_wake_operation_arithmetic_count", "usize", "5"),
            ("native_futex_wake_operation_comparison_count", "usize", "6"),
            ("native_futex_wake_operation_wake_passes", "usize", "2"),
            ("native_futex_wake_operation_key_domains", "usize", "2"),
            ("native_futex_wake_operation_nonpositive_wake_minimum", "usize", "1"),
            ("native_futex_wake_operation_smp_atomic", "u32", "0"),
            ("native_futex_wake_operation_file_backed", "u32", "0"),
            ("native_futex_wake_operation_cross_process_clone_vm", "u32", "0")):
        pattern = rf"^[ \t]*inline[ \t]+constexpr[ \t]+{kind}[ \t]+{name}[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 futex wake-operation contract mismatch: " + name)


FUTEX_REQUEUE_PROFILE_HEADER = "ok/user/native_futex_requeue_sdk_profile.hpp"
FUTEX_REQUEUE_PROFILE = "bootcpu-nonpi-read-keys-signed-counts-exact-origin-ticket-sequence-owned-transfer-v1"
FUTEX_REQUEUE_PROFILE_HEADERS = (
    FUTEX_REQUEUE_PROFILE_HEADER, "ok/user/native_futex.hpp", "ok/user/linux_bootstrap.hpp",
    "ok/user/native_page_pool.hpp", "ok/user/native_mapping_pages.hpp",
    "ok/sched/scheduler.hpp", "ok/sched/resources.hpp",
)


def validate_futex_requeue_profile(headers: Path) -> None:
    """Require the exact implemented source slice; metadata is not execution."""
    for name in FUTEX_REQUEUE_PROFILE_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("SDK75 futex requeue contract header is missing: " + name)
    source = shared_file_contract_code((headers / FUTEX_REQUEUE_PROFILE_HEADER).read_text())
    for name in ("native_futex_requeue_profile", "linux_futex_requeue_profile"):
        pattern = rf'^[ \t]*inline[ \t]+constexpr[ \t]+std::string_view[ \t]+{name}[ \t]*=[ \t]*"([^"\n]+)"[ \t]*;[ \t]*$'
        if contract_declaration_values(source, name, pattern) != [FUTEX_REQUEUE_PROFILE]:
            raise ValueError("SDK75 futex requeue profile mismatch: " + name)
    for name, kind, expected in (
            ("native_futex_requeue_module_abi", "u32", "75"),
            ("native_futex_requeue_word_bits", "usize", "32"),
            ("native_futex_requeue_operation_count", "usize", "2"),
            ("native_futex_requeue_linux_operation", "usize", "3"),
            ("native_futex_cmp_requeue_linux_operation", "usize", "4"),
            ("native_futex_requeue_private_flag", "usize", "128"),
            ("native_futex_requeue_key_domains", "usize", "2"),
            ("native_futex_requeue_waiter_capacity", "usize", "64"),
            ("native_futex_requeue_sequence_bits", "usize", "64"),
            ("native_futex_requeue_original_continuation_preserved", "u32", "1"),
            ("native_futex_requeue_same_key_sequence_preserved", "u32", "1"),
            ("native_futex_requeue_zero_wake_minimum", "u32", "0"),
            ("native_futex_requeue_signed_negative_counts_rejected", "u32", "1"),
            ("native_futex_requeue_transfer_pin_owners_retained", "u32", "1"),
            ("native_futex_requeue_smp_atomic", "u32", "0"),
            ("native_futex_requeue_priority_inheritance", "u32", "0"),
            ("native_futex_requeue_realtime_priority", "u32", "0"),
            ("native_futex_requeue_file_backed", "u32", "0"),
            ("native_futex_requeue_cross_process_clone_vm", "u32", "0"),
    ):
        pattern = rf"^[ \t]*inline[ \t]+constexpr[ \t]+{kind}[ \t]+{name}[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 futex requeue contract mismatch: " + name)


def shared_file_contract_code(source: str, preserve_strings: bool = True) -> str:
    """Read unconditional marker code, masking comments and C++ raw literals.

    The native marker headers are canonical, unconditional contracts. Do
    not infer a compiler's macro state or accept conditional marker headers.
    These headers use no physical line continuations. Refuse them rather than
    approximating C++ raw-string restoration of preprocessing transformations.
    """
    if re.search(r"\\[ \t]*\r?\n", source):
        raise ValueError("SDK75 contract markers cannot use physical line continuations")
    output: list[str] = []
    index = 0
    raw_start = re.compile(r'(?:u8|[uUL])?R"([^ ()\\\t\v\f\r\n]{0,16})\(')

    def mask(value: str) -> str:
        return re.sub(r"[^\n]", " ", value)

    while index < len(source):
        if source.startswith("//", index):
            end = source.find("\n", index)
            end = len(source) if end < 0 else end
            output.append(mask(source[index:end]))
            index = end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise ValueError("SDK75 contract has an unterminated comment")
            end += 2
            output.append(mask(source[index:end]))
            index = end
            continue
        boundary = index == 0 or not (source[index - 1].isalnum() or source[index - 1] == "_")
        raw = raw_start.match(source, index) if boundary else None
        if raw:
            end_token = ")" + raw[1] + '"'
            end = source.find(end_token, raw.end())
            if end < 0:
                raise ValueError("SDK75 contract has an unterminated raw string")
            end += len(end_token)
            output.append(mask(source[index:end]))
            index = end
            continue
        if source[index] in ('"', "'"):
            quote = source[index]
            end = index + 1
            while end < len(source) and source[end] != quote:
                if source[end] == "\n":
                    raise ValueError("SDK75 contract has an invalid multiline quoted literal")
                end += 2 if source[end] == "\\" else 1
            if end >= len(source):
                raise ValueError("SDK75 contract has an unterminated quoted literal")
            end += 1
            value = source[index:end]
            output.append(value if preserve_strings and quote == '"' else mask(value))
            index = end
            continue
        output.append(source[index])
        index += 1
    code = "".join(output)
    if re.search(r"^[ \t\v\f]*(?:#|%:)[ \t\v\f]*(?:if|ifdef|ifndef|elif|else|endif|define|undef)\b", code, re.MULTILINE):
        raise ValueError("SDK75 contract markers must be unconditional and free of local macros")
    return code


def contract_declaration_values(source: str, name: str, pattern: str) -> list[str]:
    """Require one canonical marker statement and bound its other permitted uses.

    These marker headers use their declared fields only in static assertions;
    the native module manifest also defaults its ABI member to the marker.
    Refuse every other marker-bearing statement instead of guessing arbitrary
    C++ declarator syntax from the punctuation immediately after a name.
    """
    matches = list(re.finditer(pattern, source, re.MULTILINE))
    if len(matches) != 1:
        return []
    code = shared_file_contract_code(source, preserve_strings=False)
    marker = re.escape(name)
    canonical = matches[0]
    covered_end = 0
    for statement in re.finditer(r"[^;]*;", code):
        covered_end = statement.end()
        value = statement[0][:-1]
        if not re.search(rf"\b{marker}\b", value):
            continue
        if statement.start() <= canonical.start() < statement.end():
            if len(re.findall(rf"\b{marker}\b", value)) != 1 or canonical.end() > statement.end():
                return []
            continue
        if re.match(r"^[ \t\r\n]*static_assert[ \t\r\n]*\(", value) and not re.search(
                r"\b(?:constexpr|extern|constinit)\b", value):
            continue
        if name == "kernel_module_abi_version" and re.fullmatch(
                r"[ \t\r\n]*u32[ \t]+abi_version[ \t]*\{[ \t]*kernel_module_abi_version[ \t]*\}[ \t\r\n]*", value):
            continue
        return []
    if re.search(rf"\b{marker}\b", code[covered_end:]):
        return []
    return [canonical[1]]


def validate_shared_file_profile(headers: Path) -> None:
    """Require exact typed declarations in the named bounded contract header."""
    for name in SHARED_FILE_PROFILE_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("SDK75 shared-file contract header is missing: " + name)
    source = shared_file_contract_code((headers / SHARED_FILE_PROFILE_HEADER).read_text())
    for name, expected in (("native_shared_file_profile", NATIVE_SHARED_FILE_PROFILE),
                           ("linux_shared_file_profile", LINUX_SHARED_FILE_PROFILE)):
        pattern = rf'^[ \t]*inline[ \t]+constexpr[ \t]+std::string_view[ \t]+{name}[ \t]*=[ \t]*"([^"\n]+)"[ \t]*;[ \t]*$'
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 shared-file profile mismatch: " + name)
    for name, kind, expected in (("native_shared_file_module_abi", "u32", "75"),
                                 ("native_shared_file_capacity", "usize", "16"),
                                 ("native_shared_file_max_pages", "usize", "64"),
                                 ("native_shared_file_page_size", "usize", "4096"),
                                 ("native_shared_file_supported_seals", "u32", "15")):
        pattern = rf"^[ \t]*inline[ \t]+constexpr[ \t]+{kind}[ \t]+{name}[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 shared-file contract marker mismatch: " + name)


TCP_PROFILE_HEADER = "ok/net/native_tcp_sdk_profile.hpp"
NATIVE_TCP_PROFILE = "bootcpu-static-peer-ipv4-captured-nonblocking-immediate-v1"
LINUX_TCP_PROFILE = "bootcpu-direct-static-peer-ipv4-captured-nonblocking-immediate-v1"
NATIVE_TCP_ACCEPT_PROFILE = "bootcpu-explicit-ipv4-captured-nonblocking-reserved-accept-v1"
LINUX_TCP_ACCEPT_PROFILE = "bootcpu-direct-explicit-ipv4-captured-nonblocking-reserved-accept-v1"
TCP_PROFILE_HEADERS = (
    TCP_PROFILE_HEADER, "ok/net/tcp_wire.hpp", "ok/net/tcp_transport.hpp", "ok/net/tcp_executor.hpp",
    "ok/net/tcp_endpoints.hpp", "ok/net/tcp_stream_handle.hpp", "ok/net/native_tcp_stream.hpp",
    "ok/net/tcp_stream_wait.hpp", "ok/net/tcp_stream_checked.hpp", "ok/net/native_tcp_ethernet.hpp",
    "ok/abi/linux_tcp_data.hpp", "ok/abi/linux_tcp_accept_call.hpp",
    "ok/net/tcp_prepared_accept.hpp", "ok/net/tcp_accept_copied.hpp",
)

def validate_tcp_profile(headers: Path) -> None:
    """Require real typed declarations for bounded client and prepared accept profiles."""
    for name in TCP_PROFILE_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("SDK75 TCP contract header is missing: " + name)
    source = shared_file_contract_code((headers / TCP_PROFILE_HEADER).read_text())
    for name, expected in (("native_tcp_profile", NATIVE_TCP_PROFILE),
                           ("linux_tcp_profile", LINUX_TCP_PROFILE),
                           ("native_tcp_accept_profile", NATIVE_TCP_ACCEPT_PROFILE),
                           ("linux_tcp_accept_profile", LINUX_TCP_ACCEPT_PROFILE)):
        pattern = rf'^[ \t]*inline[ \t]+constexpr[ \t]+std::string_view[ \t]+{name}[ \t]*=[ \t]*"([^"\n]+)"[ \t]*;[ \t]*$'
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 TCP profile mismatch: " + name)
    for name, expected in (("native_tcp_module_abi", "75"), ("native_tcp_stream_capacity", "16"),
                           ("native_tcp_connection_capacity", "8"), ("native_tcp_listener_capacity", "4"),
                           ("native_tcp_backlog_capacity", "4"), ("native_tcp_send_capacity", "1024"),
                           ("native_tcp_receive_capacity", "1024"), ("native_tcp_segment_capacity", "536"),
                           ("native_tcp_poll_budget", "8")):
        kind = "u32" if name == "native_tcp_module_abi" else "usize"
        pattern = rf"^[ \t]*inline[ \t]+constexpr[ \t]+{kind}[ \t]+{name}[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 TCP contract marker mismatch: " + name)


def validate_udp_profile(headers: Path) -> None:
    """Require the existing bounded UDP values as actual typed declarations."""
    for name in UDP_PROFILE_HEADERS:
        if not (headers / name).is_file():
            raise ValueError("SDK75 UDP contract header is missing: " + name)
    source = shared_file_contract_code((headers / UDP_PROFILE_HEADER).read_text())
    for name, expected in (("native_udp_profile", NATIVE_UDP_PROFILE),
                           ("linux_udp_profile", LINUX_UDP_PROFILE),
                           ("native_udp_connected_profile", CONNECTED_UDP_PROFILE)):
        pattern = rf'^[ \t]*inline[ \t]+constexpr[ \t]+std::string_view[ \t]+{name}[ \t]*=[ \t]*"([^"\n]+)"[ \t]*;[ \t]*$'
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 UDP profile mismatch: " + name)
    for name, expected in (("native_udp_module_abi", "75"), ("native_udp_socket_capacity", "16"),
                           ("native_udp_queue_capacity", "2"), ("native_udp_datagram_capacity", "1472"),
                           ("native_udp_frame_capacity", "1514")):
        kind = "u32" if name == "native_udp_module_abi" else "usize"
        pattern = rf"^[ \t]*inline[ \t]+constexpr[ \t]+{kind}[ \t]+{name}[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 UDP contract marker mismatch: " + name)


def validate_common_profile(sdk: Path) -> None:
    """Require actual typed declarations for the preserved ext4 common profile."""
    for name in COMMON_HEADERS:
        if not (sdk / name).is_file():
            raise ValueError("SDK75 common-opening header is missing: " + name)
    source = shared_file_contract_code((sdk / COMMON_HEADERS[0]).read_text())
    pattern = r'^[ \t]*inline[ \t]+constexpr[ \t]+std::string_view[ \t]+ext4_common_opening_profile[ \t]*=[ \t]*"([^"\n]+)"[ \t]*;[ \t]*$'
    if contract_declaration_values(source, "ext4_common_opening_profile", pattern) != [COMMON_PROFILE]:
        raise ValueError("SDK75 common-opening profile declaration mismatch")
    for name, expected in (("ext4_common_module_abi", "75"), ("ext4_common_session_counter_bits", "64")):
        pattern = rf"^[ \t]*inline[ \t]+constexpr[ \t]+u32[ \t]+{name}[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
        if contract_declaration_values(source, name, pattern) != [expected]:
            raise ValueError("SDK75 common-opening contract mismatch: " + name)


def bios_payload_capacity(manifest: dict, boot_sector: bytes) -> int:
    """Bind the manifest extent to the actual versioned BIOS loader."""
    capacity = manifest.get("bios_payload_bytes", LEGACY_BIOS_PAYLOAD_CAPACITY)
    if type(capacity) is not int or capacity not in (LEGACY_BIOS_PAYLOAD_CAPACITY,
                                                     EXTENDED_BIOS_PAYLOAD_CAPACITY):
        raise ValueError("kernel SDK has invalid BIOS payload extent")
    if len(boot_sector) != 512 or boot_sector[-2:] != b"\x55\xaa":
        raise ValueError("invalid BIOS boot sector in kernel SDK")
    marker = boot_sector[0x1f0:0x1f4]
    if marker == b"OKB2":
        declared = struct.unpack_from("<I", boot_sector, 0x1f4)[0]
        if ("bios_payload_bytes" not in manifest or declared != capacity or
                declared != EXTENDED_BIOS_PAYLOAD_CAPACITY):
            raise ValueError("BIOS loader and manifest payload extent mismatch")
    elif capacity != LEGACY_BIOS_PAYLOAD_CAPACITY:
        raise ValueError("BIOS loader and manifest payload extent mismatch")
    return capacity


def validate_uapi_version(header: Path) -> None:
    """Check real unconditional version directives, excluding comment decoys."""
    source = header.read_text()
    if any(token in source for token in ('\\', '??', '%:')):
        raise ValueError("kernel SDK UAPI version rejects line splicing")
    source = re.sub(r"/\*.*?\*/|//[^\n]*", lambda match: re.sub(r"[^\n]", " ", match[0]),
                    source, flags=re.DOTALL)
    if any(token in source for token in ('/*', '*/', '"', "'")):
        raise ValueError("kernel SDK UAPI version has unsupported syntax")
    directives = [" ".join(line.split()) for line in source.split("\n") if line.lstrip().startswith("#")]
    for component, expected in (("MAJOR", "0"), ("MINOR", "16"), ("PATCH", "0")):
        name = "OK_UAPI_VERSION_" + component
        definitions = [line for line in directives if re.match(r"#define " + name + r"(?:\s|\(|$)", line)]
        if definitions != ["#define " + name + " " + expected]:
            raise ValueError(f"kernel SDK UAPI version requires UAPI 0.16.0: invalid {component.lower()} version")


def validate_module_abi(header: Path) -> None:
    """Check one actual typed native ABI declaration in the hashed SDK header."""
    source = shared_file_contract_code(header.read_text())
    pattern = r"^[ \t]*inline[ \t]+constexpr[ \t]+u32[ \t]+kernel_module_abi_version[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$"
    if contract_declaration_values(source, "kernel_module_abi_version", pattern) != ["75"]:
        raise ValueError("kernel SDK requires the compiled native module ABI75 header")


def signal_macro_options(flags: list[str]) -> list[tuple[str, str]]:
    """Read direct and forwarded preprocessor options without executing them."""
    words = []
    for flag in flags:
        words.extend(flag[4:].split(",") if flag.startswith("-Wp,") else shlex.split(flag))
    result = []
    index = 0
    while index < len(words):
        word = words[index]
        if word in ("-D", "-U"):
            index += 1
            if index >= len(words):
                raise ValueError("kernel SDK incomplete preprocessor option")
            result.append((word[1], words[index]))
        elif word.startswith(("-D", "-U")):
            result.append((word[1], word[2:]))
        index += 1
    return result


def validate_terminal_reboot_backend(manifest: dict, arch: str) -> None:
    """Bind machine-specific reset admission to one explicit exported build policy."""
    name = "OK_NATIVE_PC8042_REBOOT"
    def names_backend(value: str) -> bool:
        identifier = re.match(r"\s*([A-Za-z_][A-Za-z_0-9]*)", value)
        return bool(identifier and identifier[1] == name)
    definitions = [flag for flag in manifest["defines"] if names_backend(flag)]
    if definitions and definitions != [name + "=1"]:
        raise ValueError("kernel SDK reboot backend requires one canonical opt-in definition")
    for field in ("cxxflags", "asflags"):
        if any(names_backend(value) for _, value in signal_macro_options(manifest[field])):
            raise ValueError("kernel SDK reboot backend macro override is not permitted")
    if definitions and arch != "x86_64":
        raise ValueError("kernel SDK PC/8042 reboot backend requires x86_64")
    expected = "x86_64-pc-8042-v1" if definitions else "unsupported"
    if manifest.get("terminal_reboot_backend") != expected:
        raise ValueError("kernel SDK terminal reboot backend contradicts its exported build policy")


def validate_terminal_poweroff_backend(manifest: dict, arch: str) -> None:
    """Bind selected PM poweroff admission to one explicit exported build policy."""
    name = "OK_NATIVE_QEMU_PIIX4_POWEROFF"
    def names_backend(value: str) -> bool:
        identifier = re.match(r"\s*([A-Za-z_][A-Za-z_0-9]*)", value)
        return bool(identifier and identifier[1] == name)
    definitions = [flag for flag in manifest["defines"] if names_backend(flag)]
    if definitions and definitions != [name + "=1"]:
        raise ValueError("kernel SDK poweroff backend requires one canonical opt-in definition")
    for field in ("cxxflags", "asflags"):
        if any(names_backend(value) for _, value in signal_macro_options(manifest[field])):
            raise ValueError("kernel SDK poweroff backend macro override is not permitted")
    if definitions and arch != "x86_64":
        raise ValueError("kernel SDK QEMU PIIX4 PM poweroff backend requires x86_64")
    expected = "x86_64-qemu-piix4-pm-v1" if definitions else "unsupported"
    if manifest.get("terminal_poweroff_backend") != expected:
        raise ValueError("kernel SDK terminal poweroff backend contradicts its exported build policy")


def validate_arm32_image(payload: bytes) -> None:
    """Validate the exported ARM format without consulting kernel source."""
    if len(payload) < 52:
        raise ValueError("ARM image is truncated: header and entry instruction are required")
    magic, start, end = struct.unpack_from("<III", payload, 0x24)
    if magic != 0x016f2818:
        raise ValueError("invalid ARM Linux image magic")
    if start != 0x40010000:
        raise ValueError("ARM image must link at 0x40010000")
    if end <= start or end - start != len(payload):
        raise ValueError("ARM image file extent does not match the emitted bytes")
    branch, = struct.unpack_from("<I", payload)
    if branch & 0xff000000 != 0xea000000:
        raise ValueError("ARM image entry must be an unconditional ARM B instruction")
    displacement = branch & 0x00ffffff
    if displacement >= 0x00800000:
        displacement -= 0x01000000
    destination = 8 + 4 * displacement
    if destination < 48 or destination % 4 or destination + 4 > len(payload):
        raise ValueError("ARM image entry branch must land after the header inside the emitted image")


def validate_sdk(sdk: Path, arch: str, mode: str, compiler: Path | None = None) -> dict:
    sdk = sdk.resolve()
    manifest_path = sdk / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"kernel SDK missing: {manifest_path}; build 'xmake -b kernel-sdk' in ObfuscationKernel first")
    manifest = json.loads(manifest_path.read_text())
    # JSON booleans and floating values must not borrow Python's numeric
    # equality to impersonate exact schema or native module ABI identities.
    for field in ("schema", "abi_version"):
        if type(manifest.get(field)) is not int:
            raise ValueError(f"kernel SDK {field} must be an integer")
    expected = {"schema": 1, "abi_version": 75, "arch": arch, "mode": mode, "triple": ARCH_TRIPLES.get(arch)}
    for key, value in expected.items():
        if value is None or manifest.get(key) != value:
            raise ValueError(f"kernel SDK {key} mismatch: expected {value!r}, found {manifest.get(key)!r}")
    if not manifest.get("kernel_version"):
        raise ValueError("kernel SDK has no kernel version")
    for name, expected_profile in (("native_udp_profile", NATIVE_UDP_PROFILE),
                                    ("linux_udp_profile", LINUX_UDP_PROFILE),
                           ("native_udp_connected_profile", CONNECTED_UDP_PROFILE)):
        if manifest.get(name) != expected_profile:
            raise ValueError("kernel SDK UDP profile mismatch: " + name)
    for name, expected_profile in (("native_tcp_profile", NATIVE_TCP_PROFILE),
                                    ("linux_tcp_profile", LINUX_TCP_PROFILE),
                                    ("native_tcp_accept_profile", NATIVE_TCP_ACCEPT_PROFILE),
                                    ("linux_tcp_accept_profile", LINUX_TCP_ACCEPT_PROFILE)):
        if manifest.get(name) != expected_profile:
            raise ValueError("kernel SDK TCP profile mismatch: " + name)
    for name, expected_profile in (("native_shared_file_profile", NATIVE_SHARED_FILE_PROFILE),
                                    ("linux_shared_file_profile", LINUX_SHARED_FILE_PROFILE)):
        if manifest.get(name) != expected_profile:
            raise ValueError("kernel SDK shared-file profile mismatch: " + name)
    for name in ("native_futex_wake_operation_profile", "linux_futex_wake_operation_profile"):
        if manifest.get(name) != FUTEX_WAKE_OPERATION_PROFILE:
            raise ValueError("kernel SDK futex wake-operation profile mismatch: " + name)
    for name in ("native_futex_requeue_profile", "linux_futex_requeue_profile"):
        if manifest.get(name) != FUTEX_REQUEUE_PROFILE:
            raise ValueError("kernel SDK futex requeue profile mismatch: " + name)
    for name in ("native_unix_pathname_profile", "linux_unix_pathname_profile"):
        if manifest.get(name) != UNIX_PATHNAME_PROFILE:
            raise ValueError("kernel SDK UNIX pathname profile mismatch: " + name)
    if manifest.get("ext4_directory_create_profile") != DIRECTORY_CREATE_PROFILE:
        raise ValueError("kernel SDK directory-create profile mismatch")
    if manifest.get("ext4_common_opening_profile") != COMMON_PROFILE:
        raise ValueError("kernel SDK common-opening profile mismatch")
    compiler_metadata = manifest.get("compiler")
    if (not isinstance(compiler_metadata, dict) or compiler_metadata.get("family") != "gcc" or
            not isinstance(compiler_metadata.get("version"), str) or
            not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", compiler_metadata["version"])):
        raise ValueError("kernel SDK requires an explicit GCC compiler family and version")
    if manifest.get("ext4_ordered_data_profile") != "bounded-mounted-dirty-existing-file-v1":
        raise ValueError("kernel SDK mounted-dirty ordered-data profile mismatch")
    if manifest.get("ext4_directory_rename_profile") != "bounded-mounted-dirty-same-dir-absent-fit-or-relocate-ordered-home-v2":
        raise ValueError("kernel SDK ordered-home directory-rename profile mismatch")
    if manifest.get("ext4_empty_create_profile") != "bounded-mounted-dirty-empty-regular-initial-attrs-ordered-home-v1":
        raise ValueError("kernel SDK ordered-home empty-create profile mismatch")
    if manifest.get("ext4_first_data_profile") != "bounded-mounted-dirty-fresh-empty-first-block-ordered-home-v1":
        raise ValueError("kernel SDK ordered-home first-data profile mismatch")
    if manifest.get("ext4_next_data_profile") != "bounded-mounted-dirty-aligned-inline-next-block-ordered-home-v1":
        raise ValueError("kernel SDK ordered-home next-data profile mismatch")
    for field in ("cxxflags", "asflags", "ldflags", "defines"):
        flags = manifest.get(field)
        if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
            raise ValueError(f"kernel SDK has invalid or missing {field}")
    # The native C++ layout version does not imply the ordinary signal service.
    # Older SDK31 exports had the same layouts with that service disabled.
    if manifest.get("native_signal_profile") != "bounded-bootcpu-v1":
        raise ValueError("kernel SDK requires native_signal_profile bounded-bootcpu-v1")
    if manifest.get("native_init_profile") != "designated-pid1-native-linux-adoption-v2":
        raise ValueError("kernel SDK requires native_init_profile designated-pid1-native-linux-adoption-v2")
    if manifest.get("native_console_input_profile") != NATIVE_CONSOLE_INPUT_PROFILE:
        raise ValueError("kernel SDK native console input profile mismatch")
    if manifest.get("native_persistent_sync_profile") != NATIVE_PERSISTENT_SYNC_PROFILE:
        raise ValueError("kernel SDK persistent sync profile mismatch")
    if manifest.get("native_mount_info_profile") != NATIVE_MOUNT_INFO_PROFILE:
        raise ValueError("kernel SDK mount inventory profile mismatch")
    if manifest.get("native_power_profile") != NATIVE_POWER_PROFILE:
        raise ValueError("kernel SDK native power profile mismatch")
    if manifest.get("native_sessions_profile") != NATIVE_SESSIONS_PROFILE:
        raise ValueError("kernel SDK native sessions profile mismatch")
    if manifest.get("native_group_signal_profile") != NATIVE_GROUP_SIGNAL_PROFILE:
        raise ValueError("kernel SDK native group signal profile mismatch")
    if manifest.get("native_console_control_profile") != NATIVE_CONSOLE_CONTROL_PROFILE:
        raise ValueError("kernel SDK native console control profile mismatch")
    if manifest.get("native_pty_profile") != NATIVE_PTY_PROFILE:
        raise ValueError("kernel SDK native PTY profile mismatch")
    if manifest.get("native_metadata_profile") != NATIVE_METADATA_PROFILE:
        raise ValueError("kernel SDK native metadata profile mismatch")
    validate_terminal_reboot_backend(manifest, arch)
    validate_terminal_poweroff_backend(manifest, arch)
    if manifest.get("boot_archive_directory_profile") != BOOT_ARCHIVE_DIRECTORY_PROFILE:
        raise ValueError("kernel SDK boot archive directory profile mismatch")
    if manifest.get("native_credentials_profile") != NATIVE_CREDENTIALS_PROFILE:
        raise ValueError("kernel SDK native credentials profile mismatch")
    if manifest.get("native_termination_profile") != NATIVE_TERMINATION_PROFILE:
        raise ValueError("kernel SDK native termination profile mismatch")
    runtime_defines = [flag for flag in manifest["defines"]
                       if flag.split("=", 1)[0] == "OK_NATIVE_SIGNAL_RUNTIME"]
    if runtime_defines != ["OK_NATIVE_SIGNAL_RUNTIME"]:
        raise ValueError("kernel SDK native signal profile contradicts runtime definition")
    controls = {"OK_NATIVE_SIGNAL_RUNTIME", "OK_ENABLE_TEST_POINTS", "OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE"}
    for name in controls - {"OK_NATIVE_SIGNAL_RUNTIME"}:
        values = [flag for flag in manifest["defines"] if flag.split("=", 1)[0] == name]
        if values and values != [name]:
            raise ValueError("kernel SDK diagnostics require one canonical bare definition")
    cpp_options = signal_macro_options(manifest["cxxflags"])
    asm_options = signal_macro_options(manifest["asflags"])
    if any(action == "U" and name.split("=", 1)[0] in controls
           for action, name in cpp_options + asm_options):
        raise ValueError("kernel SDK signal macro override contradicts exported capability")
    if any(name.split("=", 1)[0] in controls for _, name in cpp_options):
        raise ValueError("kernel SDK runtime and diagnostics must use canonical exported defines")
    assembly_controls = [name for _, name in asm_options if name.split("=", 1)[0] in controls]
    if (len(assembly_controls) != len(set(assembly_controls)) or
            any(name not in manifest["defines"] for name in assembly_controls)):
        raise ValueError("kernel SDK assembly admission for runtime/diagnostics contradicts exported defines")
    asm_runtime = [(action, name) for action, name in asm_options
                   if name.split("=", 1)[0] == "OK_NATIVE_SIGNAL_RUNTIME"]
    if asm_runtime != ([("D", "OK_NATIVE_SIGNAL_RUNTIME")] if arch == "mips64" else []):
        raise ValueError("kernel SDK runtime assembly admission differs from architecture profile")
    defined = {flag.split("=", 1)[0] for flag in manifest["defines"]}
    for action, name in cpp_options + asm_options:
        if action == "D": defined.add(name.split("=", 1)[0])
    if "OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE" in defined and (
            mode != "debug" or "OK_ENABLE_TEST_POINTS" not in defined):
        raise ValueError("kernel SDK private diagnostics require Debug test points")
    if mode == "release":
        diagnostics = {"OK_ENABLE_TEST_POINTS", "OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE"}
        if defined & diagnostics:
            raise ValueError("kernel SDK Release exposes private signal or test-point diagnostics")
    image_format = manifest.get("image_format")
    if image_format not in {"bios-disk", "elf", "linux-image", "arm32-linux-image"}:
        raise ValueError(f"unsupported kernel image format: {image_format}")
    if (arch == "arm32") != (image_format == "arm32-linux-image"):
        raise ValueError("arm32 requires the ARM-only arm32-linux-image format")
    files = manifest.get("files", {})
    required = {"lib/libokernel.a", "lib/libokernel_boot.a", "boot/linker.ld", "image/kernel.bin", "image/kernel.elf", "include/ok/uapi/syscall.h", "include/ok/core/module.hpp"}
    required.update(COMMON_HEADERS)
    required.add("include/ok/uapi/signal.h")
    required.update("include/" + name for name in NATIVE_CREDENTIALS_HEADERS)
    required.update("include/" + name for name in BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADERS)
    required.update("include/" + name for name in NATIVE_CONSOLE_INPUT_HEADERS)
    required.update("include/" + name for name in NATIVE_PERSISTENT_SYNC_HEADERS)
    required.update("include/" + name for name in NATIVE_MOUNT_INFO_HEADERS)
    required.update("include/" + name for name in NATIVE_POWER_HEADERS)
    required.update("include/" + name for name in NATIVE_METADATA_HEADERS)
    required.update("include/" + name for name in NATIVE_SESSIONS_HEADERS)
    required.update("include/" + name for name in NATIVE_GROUP_SIGNAL_HEADERS)
    required.update("include/" + name for name in NATIVE_CONSOLE_CONTROL_HEADERS)
    required.update("include/" + name for name in NATIVE_PTY_HEADERS)
    required.update("include/" + name for name in DIRECTORY_CREATE_PROFILE_HEADERS)
    required.update("include/" + name for name in UDP_PROFILE_HEADERS)
    required.update("include/" + name for name in TCP_PROFILE_HEADERS)
    required.update("include/" + name for name in SHARED_FILE_PROFILE_HEADERS)
    required.update("include/" + name for name in UNIX_PATHNAME_PROFILE_HEADERS)
    required.update("include/" + name for name in FUTEX_WAKE_OPERATION_PROFILE_HEADERS)
    required.update("include/" + name for name in FUTEX_REQUEUE_PROFILE_HEADERS)
    if image_format == "bios-disk":
        required.add("boot/boot16.bin")
    if not required.issubset(files):
        raise ValueError(f"kernel SDK manifest is missing artifacts: {sorted(required - files.keys())}")
    for relative, digest in files.items():
        artifact = (sdk / relative).resolve()
        if not artifact.is_relative_to(sdk):
            raise ValueError(f"kernel SDK artifact escapes SDK root: {relative}")
        if not artifact.is_file():
            raise ValueError(f"kernel SDK artifact is missing: {relative}")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
            raise ValueError(f"kernel SDK artifact checksum mismatch: {relative}")
    if image_format == "bios-disk":
        bios_payload_capacity(manifest, (sdk / "boot/boot16.bin").read_bytes())
    validate_uapi_version(sdk / "include/ok/uapi/syscall.h")
    validate_module_abi(sdk / "include/ok/core/module.hpp")
    validate_common_profile(sdk)
    validate_udp_profile(sdk / "include")
    validate_tcp_profile(sdk / "include")
    validate_shared_file_profile(sdk / "include")
    validate_unix_pathname_profile(sdk / "include")
    validate_directory_create_profile(sdk / "include")
    validate_futex_wake_operation_profile(sdk / "include")
    validate_futex_requeue_profile(sdk / "include")
    validate_native_credentials_profile(sdk / "include")
    validate_boot_archive_directory_profile(sdk / "include")
    validate_native_console_input_profile(sdk / "include")
    validate_native_persistent_sync_profile(sdk / "include")
    validate_native_mount_info_profile(sdk / "include")
    validate_native_power_profile(sdk / "include")
    validate_native_metadata_profile(sdk / "include")
    validate_native_sessions_profile(sdk / "include")
    validate_native_group_signal_profile(sdk / "include")
    validate_native_console_control_profile(sdk / "include")
    validate_native_pty_profile(sdk / "include")
    validate_native_termination_profile(sdk / "include")
    if image_format == "arm32-linux-image":
        validate_arm32_image((sdk / "image/kernel.bin").read_bytes())
    if compiler:
        triple = subprocess.check_output([str(compiler), "-dumpmachine"], text=True).strip()
        version = subprocess.check_output([str(compiler), "-dumpfullversion"], text=True).strip()
        if triple != manifest["triple"] or version != manifest["compiler"]["version"]:
            raise ValueError(f"C++ module ABI requires SDK compiler {manifest['triple']} GCC {manifest['compiler']['version']}; got {triple} GCC {version}")
    return manifest


def assemble_image(elf: Path, output: Path, sdk: Path, image_format: str, objcopy: Path | None) -> None:
    if image_format not in {"bios-disk", "elf", "linux-image", "arm32-linux-image"}:
        raise ValueError(f"unsupported kernel image format: {image_format}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if image_format == "elf":
        shutil.copy2(elf, output)
        return
    if objcopy is None:
        raise ValueError("non-ELF image requires --objcopy")
    payload_path = output.with_name(output.stem + "_payload.bin")
    subprocess.run([str(objcopy), "-O", "binary", str(elf), str(payload_path)], check=True)
    payload = payload_path.read_bytes()
    if image_format == "arm32-linux-image":
        validate_arm32_image(payload)
        output.write_bytes(payload)
        return
    if image_format == "linux-image":
        output.write_bytes(payload)
        return
    boot_sector = (sdk / "boot/boot16.bin").read_bytes()
    manifest = json.loads((sdk / "manifest.json").read_text())
    capacity = bios_payload_capacity(manifest, boot_sector)
    if len(payload) > capacity:
        raise ValueError(f"kernel payload too large: {len(payload)} > {capacity}")
    output.write_bytes(boot_sector + payload + bytes(capacity - len(payload)))


def require_fat_filesystem(manifest: dict) -> None:
    """The distribution storage extension needs the optional mounted FAT API."""
    required = {"include/ok/fs/fat.hpp", "include/ok/fs/fat_fs.hpp"}
    if not required.issubset(manifest.get("files", {})):
        raise ValueError("kernel SDK lacks mounted FAT32/exFAT artifacts; export a fresh matching SDK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "assemble"))
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument("--require-fat-filesystem", action="store_true")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--objcopy", type=Path)
    args = parser.parse_args()
    try:
        manifest = validate_sdk(args.sdk, args.arch, args.mode, args.compiler)
        if args.require_fat_filesystem:
            require_fat_filesystem(manifest)
        if args.command == "assemble":
            if args.elf is None or args.out is None:
                parser.error("assemble requires --elf and --out")
            assemble_image(args.elf, args.out, args.sdk, manifest["image_format"], args.objcopy)
        print(f"[kernel-sdk] {args.arch}/{args.mode} version={manifest['kernel_version']} verified: {args.sdk}")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"kernel SDK error: {exc}\n")


if __name__ == "__main__":
    main()
