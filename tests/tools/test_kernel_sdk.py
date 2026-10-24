"""Artifact contract tests independent of an installed cross compiler."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from kernel_sdk import (ARCH_TRIPLES, EXTENDED_BIOS_PAYLOAD_CAPACITY,
                        LEGACY_BIOS_PAYLOAD_CAPACITY, assemble_image,
                        validate_arm32_image, validate_sdk, UDP_PROFILE_HEADER, UDP_PROFILE_HEADERS,
                        NATIVE_UDP_PROFILE, LINUX_UDP_PROFILE, CONNECTED_UDP_PROFILE,
                        TCP_PROFILE_HEADER, TCP_PROFILE_HEADERS, NATIVE_TCP_PROFILE, LINUX_TCP_PROFILE,
                        NATIVE_TCP_ACCEPT_PROFILE, LINUX_TCP_ACCEPT_PROFILE,
                        SHARED_FILE_PROFILE_HEADER, SHARED_FILE_PROFILE_HEADERS,
                        NATIVE_SHARED_FILE_PROFILE, LINUX_SHARED_FILE_PROFILE,
                        UNIX_PATHNAME_PROFILE_HEADER, UNIX_PATHNAME_PROFILE_HEADERS, UNIX_PATHNAME_PROFILE,
                        DIRECTORY_CREATE_PROFILE_HEADER, DIRECTORY_CREATE_PROFILE_HEADERS, DIRECTORY_CREATE_PROFILE,
                        FUTEX_WAKE_OPERATION_PROFILE_HEADER, FUTEX_WAKE_OPERATION_PROFILE_HEADERS,
                        FUTEX_WAKE_OPERATION_PROFILE, FUTEX_REQUEUE_PROFILE_HEADER,
                        FUTEX_REQUEUE_PROFILE_HEADERS, FUTEX_REQUEUE_PROFILE,
                        NATIVE_CREDENTIALS_PROFILE, NATIVE_CREDENTIALS_HEADERS,
                        NATIVE_CREDENTIALS_DEFINES, BOOT_ARCHIVE_DIRECTORY_PROFILE,
                        BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADER, BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADERS,
                        NATIVE_CONSOLE_INPUT_PROFILE_HEADER, NATIVE_CONSOLE_INPUT_HEADERS,
                        NATIVE_PERSISTENT_SYNC_PROFILE_HEADER, NATIVE_PERSISTENT_SYNC_HEADERS,
                        NATIVE_POWER_PROFILE_HEADER, NATIVE_POWER_HEADERS, NATIVE_MOUNT_INFO_HEADERS,
                        NATIVE_MOUNT_INFO_PROFILE_HEADER, NATIVE_METADATA_PROFILE_HEADER,
                        NATIVE_METADATA_HEADERS, NATIVE_METADATA_PROFILE, NATIVE_SESSIONS_PROFILE,
                        NATIVE_SESSIONS_HEADERS, NATIVE_SESSIONS_PROFILE_HEADER,
                        NATIVE_GROUP_SIGNAL_PROFILE, NATIVE_GROUP_SIGNAL_PROFILE_HEADER, NATIVE_GROUP_SIGNAL_HEADERS,
                        NATIVE_CONSOLE_CONTROL_PROFILE, NATIVE_CONSOLE_CONTROL_PROFILE_HEADER, NATIVE_CONSOLE_CONTROL_HEADERS,
                        NATIVE_PTY_PROFILE, NATIVE_PTY_PROFILE_HEADER, NATIVE_PTY_HEADERS)

UNIX_PATHNAME_HEADER = 'inline constexpr std::string_view native_unix_pathname_profile = "bootcpu-ram-pathname-stream-owned-queue-direct-v1";\ninline constexpr std::string_view linux_unix_pathname_profile = "bootcpu-ram-pathname-stream-owned-queue-direct-v1";\ninline constexpr u32 unix_pathname_module_abi = 74;\ninline constexpr usize unix_pathname_endpoint_capacity = 32;\ninline constexpr usize unix_pathname_backlog_capacity = 4;\ninline constexpr usize unix_pathname_address_capacity = 110;\ninline constexpr usize unix_pathname_text_capacity = 107;\ninline constexpr usize unix_pathname_peer_credentials_bytes = 12;\n'

DIRECTORY_CREATE_HEADER = 'inline constexpr std::string_view ext4_directory_create_profile = "bounded-journalled-single-block-directory-create-ordered-free-init-v2";\ninline constexpr u32 ext4_directory_create_module_abi = 74;\ninline constexpr usize ext4_directory_create_home_capacity = 8;\ninline constexpr usize ext4_directory_create_owner_buffers = 9;\n'

BOOT_ARCHIVE_DIRECTORY_HEADER = ('#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\n'
    'namespace ok::fs\n{\n'
    'inline constexpr std::string_view boot_archive_directory_profile = "root-owned-ram-exact-sticky-sgid-v1";\n'
    'inline constexpr u32 boot_archive_directory_mode_mask = 03777;\n'
    'inline constexpr u32 boot_archive_regular_mode_mask = 0777;\n} // namespace ok::fs\n')

CONSOLE_INPUT_HEADER = ('#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\n'
    'namespace ok::sched\n{\n'
    'inline constexpr std::string_view native_console_input_profile = "pid1-issued-epoch-fork-exec-leader-revoke-noecho-v1";\n'
    'inline constexpr u32 native_console_epoch_limit = 0x3fffffff;\n} // namespace ok::sched\n')
CONSOLE_INPUT_DEFINITIONS = (
    ('OK_NATIVE_CONSOLE_LEASE_VERSION', '1'), ('OK_CONSOLE_EPOCH_MAX', '0x3fffffffU'),
    ('OK_SYS_CONSOLE_CLAIM', '1028ULL'), ('OK_SYS_CONSOLE_REVOKE', '1029ULL'),
    ('OK_SYS_CONSOLE_FLUSH', '1030ULL'))

PERSISTENT_SYNC_HEADER = ('#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\n'
    'namespace ok::fs\n{\n'
    'inline constexpr std::string_view native_persistent_sync_profile = "retained-linked-mounted-ordered-journal-device-flush-v1";\n'
    'inline constexpr u32 native_persistent_sync_version = 1;\n} // namespace ok::fs\n')
PERSISTENT_SYNC_DEFINITIONS = (('OK_NATIVE_PERSISTENT_SYNC_VERSION', '1'),
                              ('OK_SYS_SYNC_PERSISTENT', '1031ULL'))

POWER_HEADER = ('#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\n'
    'namespace ok::user\n{\n'
    'inline constexpr std::string_view native_power_profile = "original-init-scalar-prepare-queued-commit-v1";\n'
    'inline constexpr u32 native_power_version = 1;\n'
    'inline constexpr u32 native_power_token_limit = 0x3fffffff;\n} // namespace ok::user\n')
POWER_DEFINITIONS = (
    ('OK_NATIVE_POWER_VERSION', '1'), ('OK_POWER_TOKEN_MAX', '0x3fffffffU'),
    ('OK_POWER_HALT', '1U'), ('OK_POWER_REBOOT', '2U'), ('OK_POWER_POWEROFF', '3U'),
    ('OK_SYS_POWER_PREPARE', '1032ULL'), ('OK_SYS_POWER_COMMIT', '1033ULL'))

METADATA_HEADER = '#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\nnamespace ok::user\n{\ninline constexpr std::string_view native_metadata_profile = "checked-mode-root-owner-u32-v1";\ninline constexpr u32 native_metadata_version = 1;\ninline constexpr u32 native_metadata_module_abi = 74;\n} // namespace ok::user\n'
METADATA_DEFINITIONS = (('OK_NATIVE_METADATA_VERSION', '1'), ('OK_SYS_CHMOD', '90ULL'), ('OK_SYS_FCHMOD', '91ULL'), ('OK_SYS_CHOWN', '92ULL'), ('OK_SYS_FCHOWN', '93ULL'), ('OK_SYS_FCHOWNAT', '260ULL'), ('OK_SYS_FCHMODAT', '268ULL'), ('OK_AT_EMPTY_PATH', '0x1000U'), ('OK_AT_SYMLINK_NOFOLLOW', '0x0100U'))

EXPECTED_CREDENTIALS_PROFILE = 'bootcpu-single-live-thread-real-effective-saved-v1'
EXPECTED_CREDENTIALS_HEADERS = ('ok/uapi/syscall.h', 'ok/user/native_credentials.hpp',
                               'ok/user/credential_change.hpp', 'ok/user/linux_credentials.hpp',
                               'ok/sched/scheduler.hpp')
CREDENTIALS_DEFINITIONS = (
    ('OK_NATIVE_CREDENTIALS_VERSION', '1'), ('OK_SYS_SETUID', '105ULL'),
    ('OK_SYS_SETGID', '106ULL'), ('OK_SYS_SETREUID', '113ULL'),
    ('OK_SYS_SETREGID', '114ULL'), ('OK_SYS_SETRESUID', '117ULL'),
    ('OK_SYS_GETRESUID', '118ULL'), ('OK_SYS_SETRESGID', '119ULL'),
    ('OK_SYS_GETRESGID', '120ULL'), ('OK_ID_UNCHANGED', 'UINT32_C(0xffffffff)'))
UAPI_HEADER = ('#ifndef OK_UAPI_SYSCALL_H\n#define OK_UAPI_SYSCALL_H\n#include <stdint.h>\n'
               '#define OK_UAPI_VERSION_MAJOR 0\n#define OK_UAPI_VERSION_MINOR 16\n'
               '#define OK_UAPI_VERSION_PATCH 0\n' +
               ''.join('#define ' + name + ' ' + value + '\n'
                       for name, value in CREDENTIALS_DEFINITIONS + CONSOLE_INPUT_DEFINITIONS +
                                          PERSISTENT_SYNC_DEFINITIONS + POWER_DEFINITIONS + METADATA_DEFINITIONS) + '#endif\n')

MOUNT_INFO_HEADER = '#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\nnamespace ok::fs\n{\ninline constexpr std::string_view native_mount_snapshot_profile = "global-nine-slot-read-only-derived-generation-v1";\ninline constexpr u32 native_mount_snapshot_version = 1;\ninline constexpr u32 native_mount_snapshot_slots = 9;\ninline constexpr u32 native_mount_snapshot_path_bytes = 256;\ninline constexpr u32 native_mount_snapshot_wire_bytes = 288;\n} // namespace ok::fs\n'
MOUNT_INFO_UAPI = '#define OK_NATIVE_MOUNT_INFO_VERSION 1\n#define OK_MOUNT_INFO_CAPACITY 9U\n#define OK_MOUNT_INFO_PATH_CAPACITY 256U\n#define OK_MOUNT_STATE_UNUSED 0U\n#define OK_MOUNT_STATE_UNDERLYING_RAM 1U\n#define OK_MOUNT_STATE_BORROWED 2U\n#define OK_MOUNT_STATE_OWNED_PROVIDER 3U\n#define OK_MOUNT_STATE_OWNED_RAM 4U\n#define OK_MOUNT_STATE_DETACHED 5U\n#define OK_SYS_MOUNT_INFO 1034ULL\nstruct ok_mount_info\n{\n    uint32_t version;\n    uint32_t size;\n    uint32_t generation;\n    uint32_t slot;\n    uint32_t capacity;\n    uint32_t state;\n    uint32_t parent_id;\n    uint32_t path_length;\n    char path[OK_MOUNT_INFO_PATH_CAPACITY];\n};\n'
UAPI_HEADER = UAPI_HEADER.replace("#endif", MOUNT_INFO_UAPI + "#endif")

def invalid_credentials_sources():
    """Rehashing a misleading header must not turn it into an admitted UAPI."""
    for name, value in CREDENTIALS_DEFINITIONS:
        line = '#define ' + name + ' ' + value + '\n'
        yield 'absent ' + name, UAPI_HEADER.replace(line, '')
        yield 'wrong ' + name, UAPI_HEADER.replace(line, '#define ' + name + ' 0\n')
        yield 'duplicate ' + name, UAPI_HEADER.replace('#endif', line + '#endif')
        yield 'function replacement ' + name, UAPI_HEADER.replace(
            line, '#define ' + name + '(value) ' + value + '\n')
        yield 'function duplicate ' + name, UAPI_HEADER.replace(
            '#endif', '#define ' + name + '() ' + value + '\n#endif')
        yield 'conditional ' + name, UAPI_HEADER.replace(line, '#if 0\n' + line + '#endif\n')
        yield 'quoted ' + name, UAPI_HEADER.replace(line, 'const char text[] = "' + line.rstrip() + '";\n')
        yield 'continued comment ' + name, UAPI_HEADER.replace(line, '// hidden definition\\\n' + line)
    for directive in ('#define UINT32_C(value) 0', '#define UINT32_C 0',
                      '#define UINT32_C(value) value', '#define OK_UAPI_SYSCALL_H(value) 0'):
        yield directive, UAPI_HEADER.replace('#endif', directive + '\n#endif')
    yield 'quoted contract', 'const char text[] = R"contract(\n' + UAPI_HEADER + ')contract";\n'
    yield 'comment contract', '/*\n' + UAPI_HEADER + '*/\n'
    yield 'conditional contract', '#if 0\n' + UAPI_HEADER + '#endif\n'
    yield 'digraph conditional', '%:if 0\n' + UAPI_HEADER + '%:endif\n'
    yield 'trigraph continuation', '// hidden contract??/\n' + UAPI_HEADER
TERMINATION_HEADER = '#ifndef OK_UAPI_SIGNAL_H\n#define OK_UAPI_SIGNAL_H\n#define OK_SIGKILL 9\n#define OK_SIGTERM 15\n#define OK_NATIVE_SIGNAL_MAX 64\n#define OK_NATIVE_TERMINATION_VERSION 1\n#endif\n'
COMMON_HEADER = 'inline constexpr std::string_view ext4_common_opening_profile = "serialized-common-eight-family-directory-create-ordered-free-init-zero-refill-optional-revoke-legacy-v4";\ninline constexpr u32 ext4_common_module_abi = 74;\ninline constexpr u32 ext4_common_session_counter_bits = 64;\n'


UDP_HEADER = 'inline constexpr std::string_view native_udp_profile = "bootcpu-static-peer-ipv4-polling-captured-connected-zero-send-v3";\ninline constexpr std::string_view linux_udp_profile = "bootcpu-static-peer-ipv4-captured-connected-zero-send-v3";\ninline constexpr std::string_view native_udp_connected_profile = "bounded-static-peer-association-zero-destination-output-v2";\ninline constexpr u32 native_udp_module_abi = 74;\ninline constexpr usize native_udp_socket_capacity = 16;\ninline constexpr usize native_udp_queue_capacity = 2;\ninline constexpr usize native_udp_datagram_capacity = 1472;\ninline constexpr usize native_udp_frame_capacity = 1514;\n'


TCP_HEADER = 'inline constexpr std::string_view native_tcp_profile = "bootcpu-static-peer-ipv4-captured-nonblocking-immediate-v1";\ninline constexpr std::string_view linux_tcp_profile = "bootcpu-direct-static-peer-ipv4-captured-nonblocking-immediate-v1";\ninline constexpr std::string_view native_tcp_accept_profile = "bootcpu-explicit-ipv4-captured-nonblocking-reserved-accept-v1";\ninline constexpr std::string_view linux_tcp_accept_profile = "bootcpu-direct-explicit-ipv4-captured-nonblocking-reserved-accept-v1";\ninline constexpr u32 native_tcp_module_abi = 74;\ninline constexpr usize native_tcp_stream_capacity = 16;\ninline constexpr usize native_tcp_connection_capacity = 8;\ninline constexpr usize native_tcp_listener_capacity = 4;\ninline constexpr usize native_tcp_backlog_capacity = 4;\ninline constexpr usize native_tcp_send_capacity = 1024;\ninline constexpr usize native_tcp_receive_capacity = 1024;\ninline constexpr usize native_tcp_segment_capacity = 536;\ninline constexpr usize native_tcp_poll_budget = 8;\n'


SHARED_FILE_HEADER = 'inline constexpr std::string_view native_shared_file_profile = "bootcpu-volatile-sealed-size-write-eager-pages-v2";\ninline constexpr std::string_view linux_shared_file_profile = "bootcpu-volatile-sealed-size-write-eager-pages-v2";\ninline constexpr u32 native_shared_file_module_abi = 74;\ninline constexpr usize native_shared_file_capacity = 16;\ninline constexpr usize native_shared_file_max_pages = 64;\ninline constexpr usize native_shared_file_page_size = 4096;\ninline constexpr u32 native_shared_file_supported_seals = 15;\n'


FUTEX_WAKE_OPERATION_HEADER = 'inline constexpr std::string_view native_futex_wake_operation_profile = "bootcpu-serialized-two-key-private-anonymous-shared-signed-wrap-legacy-count-v1";\ninline constexpr std::string_view linux_futex_wake_operation_profile = "bootcpu-serialized-two-key-private-anonymous-shared-signed-wrap-legacy-count-v1";\ninline constexpr u32 native_futex_wake_operation_module_abi = 74;\ninline constexpr usize native_futex_wake_operation_word_bits = 32;\ninline constexpr usize native_futex_wake_operation_operand_bits = 12;\ninline constexpr usize native_futex_wake_operation_shift_bits = 5;\ninline constexpr usize native_futex_wake_operation_arithmetic_count = 5;\ninline constexpr usize native_futex_wake_operation_comparison_count = 6;\ninline constexpr usize native_futex_wake_operation_wake_passes = 2;\ninline constexpr usize native_futex_wake_operation_key_domains = 2;\ninline constexpr usize native_futex_wake_operation_nonpositive_wake_minimum = 1;\ninline constexpr u32 native_futex_wake_operation_smp_atomic = 0;\ninline constexpr u32 native_futex_wake_operation_file_backed = 0;\ninline constexpr u32 native_futex_wake_operation_cross_process_clone_vm = 0;\n'


FUTEX_REQUEUE_HEADER = 'inline constexpr std::string_view native_futex_requeue_profile = "bootcpu-nonpi-read-keys-signed-counts-exact-origin-ticket-sequence-owned-transfer-v1";\ninline constexpr std::string_view linux_futex_requeue_profile = "bootcpu-nonpi-read-keys-signed-counts-exact-origin-ticket-sequence-owned-transfer-v1";\ninline constexpr u32 native_futex_requeue_module_abi = 74;\ninline constexpr usize native_futex_requeue_word_bits = 32;\ninline constexpr usize native_futex_requeue_operation_count = 2;\ninline constexpr usize native_futex_requeue_linux_operation = 3;\ninline constexpr usize native_futex_cmp_requeue_linux_operation = 4;\ninline constexpr usize native_futex_requeue_private_flag = 128;\ninline constexpr usize native_futex_requeue_key_domains = 2;\ninline constexpr usize native_futex_requeue_waiter_capacity = 64;\ninline constexpr usize native_futex_requeue_sequence_bits = 64;\ninline constexpr u32 native_futex_requeue_original_continuation_preserved = 1;\ninline constexpr u32 native_futex_requeue_same_key_sequence_preserved = 1;\ninline constexpr u32 native_futex_requeue_zero_wake_minimum = 0;\ninline constexpr u32 native_futex_requeue_signed_negative_counts_rejected = 1;\ninline constexpr u32 native_futex_requeue_transfer_pin_owners_retained = 1;\ninline constexpr u32 native_futex_requeue_smp_atomic = 0;\ninline constexpr u32 native_futex_requeue_priority_inheritance = 0;\ninline constexpr u32 native_futex_requeue_realtime_priority = 0;\ninline constexpr u32 native_futex_requeue_file_backed = 0;\ninline constexpr u32 native_futex_requeue_cross_process_clone_vm = 0;\n'

SESSIONS_HEADER = '#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\nnamespace ok::user\n{\ninline constexpr std::string_view native_sessions_profile = "bootcpu-serialized-process-group-session-console-lifecycle-v3";\ninline constexpr u32 native_sessions_version = 3;\ninline constexpr u32 native_sessions_module_abi = 74;\ninline constexpr u32 native_sessions_pid_bits = 32;\ninline constexpr u32 native_sessions_process_capacity = 64;\ninline constexpr u32 native_sessions_fork_inherits = 1;\ninline constexpr u32 native_sessions_exec_preserves = 1;\ninline constexpr u32 native_sessions_reparent_preserves = 1;\ninline constexpr u32 native_sessions_controlling_tty = 1;\ninline constexpr u32 native_sessions_pty = 0;\ninline constexpr u32 native_sessions_job_control = 0;\n} // namespace ok::user\n'
GROUP_SIGNAL_HEADER = '#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\nnamespace ok::user\n{\ninline constexpr std::string_view native_group_signal_profile = "bootcpu-signed32-current-negative-pgid-probe-term-kill-deferred-partial-v2";\ninline constexpr u32 native_group_signal_version = 2;\ninline constexpr u32 native_group_signal_module_abi = 74;\ninline constexpr u32 native_group_signal_pid_bits = 32;\ninline constexpr u32 native_group_signal_process_capacity = 64;\ninline constexpr u32 native_group_signal_current_group = 1;\ninline constexpr u32 native_group_signal_negative_group = 1;\ninline constexpr u32 native_group_signal_probe = 1;\ninline constexpr u32 native_group_signal_term = 15;\ninline constexpr u32 native_group_signal_kill = 9;\ninline constexpr u32 native_group_signal_deferred_fatal = 1;\ninline constexpr u32 native_group_signal_partial_success = 1;\ninline constexpr u32 native_group_signal_broadcast = 0;\ninline constexpr u32 native_group_signal_stop_continue = 0;\ninline constexpr u32 native_group_signal_controlling_tty = 1;\ninline constexpr u32 native_group_signal_job_control = 0;\ninline constexpr u32 native_group_signal_smp = 0;\n} // namespace ok::user\n'
SESSIONS_DEFINITIONS = (("OK_NATIVE_SESSIONS_VERSION", "3"), ("OK_SYS_SETPGID", "109ULL"), ("OK_SYS_GETPGRP", "111ULL"), ("OK_SYS_SETSID", "112ULL"), ("OK_SYS_GETPGID", "121ULL"), ("OK_SYS_GETSID", "124ULL"), ("OK_ESRCH", "3"))
UAPI_HEADER = UAPI_HEADER.replace("#endif", "".join("#define " + n + " " + v + "\n" for n,v in SESSIONS_DEFINITIONS) + "#endif")

CONSOLE_CONTROL_HEADER = '#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\nnamespace ok::user\n{\ninline constexpr std::string_view native_console_control_profile = "bootcpu-lease-epoch-explicit-session-foreground-eio-pid32-ioctl-v1";\ninline constexpr u32 native_console_control_version = 1;\ninline constexpr u32 native_console_control_module_abi = 74;\ninline constexpr u32 native_console_control_serialized_boot_cpu = 1;\ninline constexpr u32 native_console_control_lease_epoch = 1;\ninline constexpr u32 native_console_control_explicit_acquire = 1;\ninline constexpr u32 native_console_control_original_lease_session_leader = 1;\ninline constexpr u32 native_console_control_foreground_read = 1;\ninline constexpr u32 native_console_control_background_eio = 1;\ninline constexpr u32 native_console_control_same_session_background_control = 1;\ninline constexpr u32 native_console_control_zombie_group_until_reap = 1;\ninline constexpr u32 native_console_control_pid_bytes = 4;\ninline constexpr u32 native_console_control_native_uniform_requests = 1;\ninline constexpr u32 native_console_control_linux_generated_requests = 1;\ninline constexpr u32 native_console_control_auto_open_acquire = 0;\ninline constexpr u32 native_console_control_force_steal = 0;\ninline constexpr u32 native_console_control_empty_foreground_replaced = 0;\ninline constexpr u32 native_console_control_pty = 0;\ninline constexpr u32 native_console_control_termios = 0;\ninline constexpr u32 native_console_control_stop_continue = 0;\ninline constexpr u32 native_console_control_job_control = 0;\ninline constexpr u32 native_console_control_smp = 0;\n} // namespace ok::user\n'
CONSOLE_CONTROL_DEFINITIONS = (('OK_NATIVE_CONSOLE_CONTROL_VERSION', '1'), ('OK_SYS_IOCTL', '16ULL'), ('OK_TIOCSCTTY', '0x540eU'), ('OK_TIOCGSID', '0x5429U'), ('OK_TIOCGPGRP', '0x540fU'), ('OK_TIOCSPGRP', '0x5410U'), ('OK_EBADF', '9'), ('OK_EACCES', '13'), ('OK_EFAULT', '14'), ('OK_EIO', '5'), ('OK_EPERM', '1'), ('OK_ENOTTY', '25'), ('OK_EOPNOTSUPP', '95'))
UAPI_HEADER = UAPI_HEADER.replace("#endif", "".join("#define " + n + " " + v + "\n" for n,v in CONSOLE_CONTROL_DEFINITIONS) + "#endif")

PTY_HEADER = '#pragma once\n#include "ok/core/types.hpp"\n#include <string_view>\nnamespace ok::user\n{\ninline constexpr std::string_view native_pty_profile = "bootcpu-native-raw-pair-ofd-waits-drain-eof-eio-v1";\ninline constexpr u32 native_pty_version = 1;\ninline constexpr u32 native_pty_module_abi = 74;\ninline constexpr u32 native_pty_pair_capacity = 8;\ninline constexpr u32 native_pty_queue_capacity = 4096;\ninline constexpr u32 native_pty_generation_bits = 64;\ninline constexpr u32 native_pty_descriptor_bytes = 4;\ninline constexpr u32 native_pty_pair_output_bytes = 8;\ninline constexpr u32 native_pty_serialized_boot_cpu = 1;\ninline constexpr u32 native_pty_raw = 1;\ninline constexpr u32 native_pty_retained_ofd_waits = 1;\ninline constexpr u32 native_pty_unconditional_hangup = 1;\ninline constexpr u32 native_pty_slave_master_closed_poll_error = 1;\ninline constexpr u32 native_pty_master_slave_closed_poll_error = 0;\ninline constexpr u32 native_pty_scm_rights = 0;\ninline constexpr u32 native_pty_linux_creation = 0;\ninline constexpr u32 native_pty_slave_reopen = 0;\ninline constexpr u32 native_pty_termios = 0;\ninline constexpr u32 native_pty_controlling_terminal = 0;\ninline constexpr u32 native_pty_terminal_signals = 0;\ninline constexpr u32 native_pty_job_control = 0;\ninline constexpr u32 native_pty_devpts = 0;\ninline constexpr u32 native_pty_smp = 0;\n} // namespace ok::user\n'
PTY_DEFINITIONS = (('OK_SYS_PTY_PAIR', '1035ULL'), ('OK_NATIVE_PTY_PAIR_VERSION', '1U'), ('OK_NATIVE_PTY_NONBLOCK', '0x0800U'), ('OK_NATIVE_PTY_CLOEXEC', '0x080000U'))
UAPI_HEADER = UAPI_HEADER.replace("#endif", "".join("#define " + n + " " + v + "\n" for n, v in PTY_DEFINITIONS) + "#endif")

def nondeclaration_marker_sources(declaration):
    """Exercise contexts that a comment-only regex mistakes for declarations."""
    sources = ["#if 0\n" + declaration + "#endif\n",
               "%:if 0\n" + declaration + "%:endif\n",
               "\v#if 0\n" + declaration + "#endif\n",
               "#define constexpr\n" + declaration,
               "#ifdef SDK_MARKERS\n" + declaration + "#endif\n",
               "#if 1\n// intentionally absent\n#else\n" + declaration + "#endif\n",
               "#i\\\nf 0\n" + declaration + "#endif\n",
               "// continued comment\\\n" + declaration.replace("\n", "\\\n") + "\n"]
    for prefix in ("R", "u8R", "uR", "UR", "LR"):
        sources.append('constexpr auto text = ' + prefix + '"markers(\n' + declaration + ')markers";\n')
    sources.append('constexpr auto text = R"tag(\n)ta\\\ng";\n' + declaration +
                   'constexpr auto another = R"tag(\n)tag";\n')
    for line in declaration.splitlines(keepends=True):
        field = line.split(" = ", 1)[0].rsplit(" ", 1)[1]
        sources.append("#define " + field + " unrelated_marker\n" + declaration)
        sources.append(declaration + "extern int " + field + " = 0;\n")
        sources.append(declaration + "extern int " + field + "{0};\n")
        sources.append(declaration + "extern int " + field + "(0);\n")
        sources.append(declaration + "extern int " + field + ";\n")
        sources.append("inline constexpr int " + field + "{0}\n" + declaration)
        sources.append(declaration + "inline constexpr int " + field + "{0}\n")
        sources.append("extern int " + field + "\n" + declaration)
        sources.append(declaration + "extern int " + field + "\n")
        sources.append(declaration + "inline constexpr int " + field + " [[maybe_unused]] = 0;\n")
        sources.append(declaration + "inline constexpr int " + field + "[1] = {0};\n")
        sources.append(declaration + "inline constexpr int (" + field + ") = 0;\n")
        sources.append(declaration + "inline constexpr int ((" + field + ")) = 0;\n")
        sources.append(declaration + "inline constexpr int " + field + " __attribute__((unused)) = 0;\n")
        sources.append(declaration + "[[maybe_unused]] inline constexpr int (" + field + ") = 0;\n")
        sources.append(declaration + "alignas(4) inline constexpr int (" + field + ") = 0;\n")
        sources.append(declaration + "inline constexpr decltype(0) (" + field + ") = 0;\n")
        sources.append(declaration + "[[maybe_unused]] int (" + field + ") = 0;\n")
    return sources

class KernelSdkTests(unittest.TestCase):
    def test_fat_consumer_requires_explicit_hashed_sdk_headers(self):
        from kernel_sdk import require_fat_filesystem
        manifest = validate_sdk(self.sdk, "x86_64", "debug")
        with self.assertRaisesRegex(ValueError, "mounted FAT32/exFAT"):
            require_fat_filesystem(manifest)
        for name in ("include/ok/fs/fat.hpp", "include/ok/fs/fat_fs.hpp"):
            path = self.sdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// FAT SDK test artifact\n")
            self.manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save()
        require_fat_filesystem(validate_sdk(self.sdk, "x86_64", "debug"))
        path.write_text("// Modified FAT SDK artifact\n")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_abi74_rehashed_profiles_refuse_stale73_and_future75(self):
        cases = (("include/ok/fs/ext4_mounted_common_profile.hpp", COMMON_HEADER),
                 ("include/" + UDP_PROFILE_HEADER, UDP_HEADER),
                 ("include/" + TCP_PROFILE_HEADER, TCP_HEADER),
                 ("include/" + SHARED_FILE_PROFILE_HEADER, SHARED_FILE_HEADER),
                 ("include/" + UNIX_PATHNAME_PROFILE_HEADER, UNIX_PATHNAME_HEADER),
                 ("include/" + DIRECTORY_CREATE_PROFILE_HEADER, DIRECTORY_CREATE_HEADER),
                 ("include/" + FUTEX_WAKE_OPERATION_PROFILE_HEADER, FUTEX_WAKE_OPERATION_HEADER),
                 ("include/" + FUTEX_REQUEUE_PROFILE_HEADER, FUTEX_REQUEUE_HEADER))
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["abi_version"], 74)
        for name, declaration in cases:
            self.assertIn("module_abi = 74;", declaration)
            header = self.sdk / name
            for version in (69, 70, 71, 72, 73, 75):
                header.write_text(declaration.replace("module_abi = 74;", f"module_abi = {version};"))
                self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
                self.save()
                with self.subTest(marker=name, version=version), self.assertRaises(ValueError):
                    validate_sdk(self.sdk, "x86_64", "debug")
            header.write_text(declaration)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_native_credentials_requires_exact_independent_contract(self):
        self.assertEqual(NATIVE_CREDENTIALS_PROFILE, EXPECTED_CREDENTIALS_PROFILE)
        self.assertEqual(NATIVE_CREDENTIALS_HEADERS, EXPECTED_CREDENTIALS_HEADERS)
        self.assertEqual(NATIVE_CREDENTIALS_DEFINES, dict(CREDENTIALS_DEFINITIONS))
        self.assertEqual(validate_sdk(self.sdk, 'x86_64', 'debug')['native_credentials_profile'],
                         EXPECTED_CREDENTIALS_PROFILE)

    def test_native_credentials_manifest_capability_is_required(self):
        for value in (None, '', True, 'linux-only-real-effective-saved-v1',
                      'smp-per-thread-posix-credentials-v1'):
            if value is None:
                self.manifest.pop('native_credentials_profile', None)
            else:
                self.manifest['native_credentials_profile'] = value
            self.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'native credentials profile mismatch'):
                validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_native_credentials_dependency_files_and_hashes_are_required(self):
        for relative in EXPECTED_CREDENTIALS_HEADERS:
            name = 'include/' + relative
            path = self.sdk / name
            original = path.read_bytes()
            path.unlink()
            with self.subTest(header=name, refusal='missing'), self.assertRaisesRegex(ValueError, 'artifact is missing'):
                validate_sdk(self.sdk, 'x86_64', 'debug')
            path.write_bytes(original + b' changed')
            with self.subTest(header=name, refusal='hash'), self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                validate_sdk(self.sdk, 'x86_64', 'debug')
            path.write_bytes(original)
            digest = self.manifest['files'].pop(name)
            self.save()
            with self.subTest(header=name, refusal='manifest'), self.assertRaisesRegex(ValueError, 'missing artifacts'):
                validate_sdk(self.sdk, 'x86_64', 'debug')
            self.manifest['files'][name] = digest
            self.save()

    def test_native_credentials_rehashed_UAPI_refuses_deception(self):
        name = 'include/ok/uapi/syscall.h'
        path = self.sdk / name
        for label, source in invalid_credentials_sources():
            path.write_text(source)
            self.manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.save()
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, '(native credentials UAPI|UAPI version)'):
                validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_native_termination_manifest_and_UAPI_cannot_claim_full_signals(self):
        original = self.manifest['native_termination_profile']
        for value in (None, True, 'full-posix-signals-v1'):
            self.manifest['native_termination_profile'] = value
            self.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'native termination'):
                validate_sdk(self.sdk, 'x86_64', 'debug')
        self.manifest['native_termination_profile'] = original
        name = 'include/ok/uapi/signal.h'
        path = self.sdk / name
        for source in ('#if 0\n' + TERMINATION_HEADER + '#endif\n',
                       TERMINATION_HEADER.replace('OK_SIGTERM 15', 'OK_SIGTERM 10'),
                       TERMINATION_HEADER + '#define OK_SIGKILL 9\n'):
            path.write_text(source)
            self.manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'native termination UAPI'):
                validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_futex_wake_operation_manifest_capabilities_are_required(self):
        for name in ("native_futex_wake_operation_profile", "linux_futex_wake_operation_profile"):
            original = self.manifest[name]
            for invalid in (None, "", True, "smp-file-backed-full-posix-v1"):
                if invalid is None:
                    self.manifest.pop(name, None)
                else:
                    self.manifest[name] = invalid
                self.save()
                with self.subTest(name=name, invalid=invalid), self.assertRaisesRegex(
                        ValueError, "futex wake-operation profile mismatch"):
                    validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest[name] = original
            self.save()

    def test_futex_wake_operation_hashed_contract_refuses_marker_changes(self):
        name = "include/" + FUTEX_WAKE_OPERATION_PROFILE_HEADER
        header = self.sdk / name
        lines = FUTEX_WAKE_OPERATION_HEADER.splitlines(keepends=True)
        invalid = [FUTEX_WAKE_OPERATION_HEADER.replace(line, "") for line in lines]
        invalid += [FUTEX_WAKE_OPERATION_HEADER + line for line in lines]
        invalid += [FUTEX_WAKE_OPERATION_HEADER.replace("module_abi = 74", "module_abi = 65"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("module_abi = 74", "module_abi = 75"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("word_bits = 32", "word_bits = 64"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("operand_bits = 12", "operand_bits = 16"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("shift_bits = 5", "shift_bits = 6"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("arithmetic_count = 5", "arithmetic_count = 8"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("comparison_count = 6", "comparison_count = 16"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("wake_passes = 2", "wake_passes = 1"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("key_domains = 2", "key_domains = 3"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("nonpositive_wake_minimum = 1", "nonpositive_wake_minimum = 0"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("smp_atomic = 0", "smp_atomic = 1"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("file_backed = 0", "file_backed = 1"),
                    FUTEX_WAKE_OPERATION_HEADER.replace("cross_process_clone_vm = 0", "cross_process_clone_vm = 1")]
        for source in invalid:
            header.write_text(source)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "futex wake-operation"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_futex_wake_operation_dependency_files_and_hashes_are_required(self):
        for relative in FUTEX_WAKE_OPERATION_PROFILE_HEADERS:
            name = "include/" + relative
            header = self.sdk / name
            content = header.read_bytes()
            header.unlink()
            with self.subTest(header=name, refusal="missing"), self.assertRaisesRegex(ValueError, "artifact is missing"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_bytes(content + b" changed")
            with self.subTest(header=name, refusal="hash"), self.assertRaisesRegex(ValueError, "checksum mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_bytes(content)
            digest = self.manifest["files"].pop(name)
            self.save()
            with self.subTest(header=name, refusal="manifest"), self.assertRaisesRegex(ValueError, "missing artifacts"):
                validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest["files"][name] = digest
            self.save()

    def test_futex_wake_operation_contract_preserves_ten_architectures_and_twenty_sdk_modes(self):
        expected_arches = ("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32",
                           "loongarch64", "mips", "mips64", "ppc")
        self.assertEqual(tuple(ARCH_TRIPLES), expected_arches)
        rows = []
        # These are SDK metadata/header admission models. No target image runs.
        for arch in expected_arches:
            for mode in ("debug", "release"):
                if arch == "arm32":
                    self.set_arm_image(self.arm_image())
                else:
                    self.manifest.update(arch=arch, triple=ARCH_TRIPLES[arch], image_format=(
                        "bios-disk" if arch in ("i386", "x86_64") else
                        "linux-image" if arch == "aarch64" else "elf"))
                self.manifest.update(mode=mode, asflags=(
                    ["-DOK_NATIVE_SIGNAL_RUNTIME"] if arch == "mips64" else []))
                self.save()
                with self.subTest(arch=arch, mode=mode):
                    admitted = validate_sdk(self.sdk, arch, mode)
                    self.assertEqual(admitted["abi_version"], 74)
                    self.assertEqual(admitted['native_credentials_profile'], EXPECTED_CREDENTIALS_PROFILE)
                    self.assertEqual(admitted["native_futex_wake_operation_profile"], FUTEX_WAKE_OPERATION_PROFILE)
                    self.assertEqual(admitted["linux_futex_wake_operation_profile"], FUTEX_WAKE_OPERATION_PROFILE)
                rows.append((arch, mode))
        self.assertEqual(len(rows), 20)

    def test_shared_file_manifest_capabilities_are_required(self):
        for name in ("native_shared_file_profile", "linux_shared_file_profile"):
            original = self.manifest[name]
            for invalid in (None, "", True, "persistent-unsealed-file-mappings-v1"):
                if invalid is None:
                    self.manifest.pop(name, None)
                else:
                    self.manifest[name] = invalid
                self.save()
                with self.subTest(name=name, invalid=invalid), self.assertRaisesRegex(ValueError, "shared-file profile mismatch"):
                    validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest[name] = original
            self.save()

    def test_shared_file_hashed_contract_rejects_missing_duplicate_or_wrong_markers(self):
        name = "include/" + SHARED_FILE_PROFILE_HEADER
        header = self.sdk / name
        invalid = [SHARED_FILE_HEADER.replace(line, "") for line in SHARED_FILE_HEADER.splitlines(keepends=True)]
        invalid += [SHARED_FILE_HEADER + line for line in SHARED_FILE_HEADER.splitlines(keepends=True)]
        invalid += [SHARED_FILE_HEADER.replace("module_abi = 74", "module_abi = 59"),
                    SHARED_FILE_HEADER.replace("module_abi = 74", "module_abi = 58"),
                    SHARED_FILE_HEADER.replace("module_abi = 74", "module_abi = 64"),
                    SHARED_FILE_HEADER.replace("module_abi = 74", "module_abi = 65"),
                    SHARED_FILE_HEADER.replace("module_abi = 74", "module_abi = 75"),
                    SHARED_FILE_HEADER.replace("capacity = 16", "capacity = 32"),
                    SHARED_FILE_HEADER.replace("max_pages = 64", "max_pages = 128"),
                    SHARED_FILE_HEADER.replace("page_size = 4096", "page_size = 8192"),
                    SHARED_FILE_HEADER.replace("supported_seals = 15", "supported_seals = 7"),
                    SHARED_FILE_HEADER.replace("supported_seals = 15", "supported_seals = 31"),
                    SHARED_FILE_HEADER.replace("volatile-sealed-size-write-eager-pages-v2", "persistent-full-v1"),
                    SHARED_FILE_HEADER.replace("volatile-sealed-size-write-eager-pages-v2", "volatile-sealed-size-eager-pages-v1")]
        for source in invalid:
            header.write_text(source)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "shared-file"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_shared_file_dependency_files_and_hashes_are_required(self):
        for relative in SHARED_FILE_PROFILE_HEADERS:
            name = "include/" + relative
            header = self.sdk / name
            content = header.read_bytes()
            header.unlink()
            with self.subTest(header=name, refusal="missing"), self.assertRaisesRegex(ValueError, "artifact is missing"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_bytes(content + b" changed")
            with self.subTest(header=name, refusal="hash"), self.assertRaisesRegex(ValueError, "checksum mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_bytes(content)
            digest = self.manifest["files"].pop(name)
            self.save()
            with self.subTest(header=name, refusal="manifest"), self.assertRaisesRegex(ValueError, "missing artifacts"):
                validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest["files"][name] = digest
            self.save()

    def test_shared_file_renamed_and_comment_only_declarations_are_refused(self):
        name = "include/" + SHARED_FILE_PROFILE_HEADER
        header = self.sdk / name
        for source in (SHARED_FILE_HEADER.replace(" native_shared_file_", " bogus_native_shared_file_")
                                        .replace(" linux_shared_file_", " bogus_linux_shared_file_"),
                       "// " + SHARED_FILE_HEADER.replace("\n", "\n// "),
                       "/*\n" + SHARED_FILE_HEADER + "*/\n"):
            header.write_text(source)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "shared-file"):
                validate_sdk(self.sdk, "x86_64", "debug")


    def test_tcp_manifest_capabilities_are_required(self):
        for name in ("native_tcp_profile", "linux_tcp_profile", "native_tcp_accept_profile", "linux_tcp_accept_profile"):
            original = self.manifest[name]
            for invalid in (None, "", True, "bootcpu-static-peer-ipv4-captured-blocking-full-v1"):
                if invalid is None:
                    self.manifest.pop(name, None)
                else:
                    self.manifest[name] = invalid
                self.save()
                with self.subTest(name=name, invalid=invalid), self.assertRaisesRegex(ValueError, "TCP profile mismatch"):
                    validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest[name] = original
            self.save()

    def test_tcp_hashed_contract_rejects_missing_duplicate_or_old_markers(self):
        name = "include/" + TCP_PROFILE_HEADER
        header = self.sdk / name
        invalid = [TCP_HEADER.replace(line, "") for line in TCP_HEADER.splitlines(keepends=True)]
        invalid += [TCP_HEADER + line for line in TCP_HEADER.splitlines(keepends=True)]
        invalid += [TCP_HEADER.replace("module_abi = 74", "module_abi = 59"),
                    TCP_HEADER.replace("module_abi = 74", "module_abi = 55"),
                    TCP_HEADER.replace("module_abi = 74", "module_abi = 56"),
                    TCP_HEADER.replace("module_abi = 74", "module_abi = 58"),
                    TCP_HEADER.replace("module_abi = 74", "module_abi = 64"),
                    TCP_HEADER.replace("module_abi = 74", "module_abi = 65"),
                    TCP_HEADER.replace("module_abi = 74", "module_abi = 75"),
                    TCP_HEADER.replace("nonblocking-immediate-v1", "blocking-full-v1"),
                    TCP_HEADER.replace("segment_capacity = 536", "segment_capacity = 1460")]
        for source in invalid:
            header.write_text(source)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "TCP"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_tcp_dependency_files_and_hashes_are_required(self):
        for relative in TCP_PROFILE_HEADERS:
            name = "include/" + relative
            header = self.sdk / name
            content = header.read_bytes()
            header.unlink()
            with self.subTest(header=name, refusal="missing"), self.assertRaisesRegex(ValueError, "artifact is missing"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_bytes(content + b" changed")
            with self.subTest(header=name, refusal="hash"), self.assertRaisesRegex(ValueError, "checksum mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_bytes(content)
            digest = self.manifest["files"].pop(name)
            self.save()
            with self.subTest(header=name, refusal="manifest"), self.assertRaisesRegex(ValueError, "missing artifacts"):
                validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest["files"][name] = digest
            self.save()

    def test_existing_native_contracts_require_real_typed_markers_and_ABI74(self):
        cases = (("include/ok/fs/ext4_mounted_common_profile.hpp", COMMON_HEADER),
                 ("include/" + UDP_PROFILE_HEADER, UDP_HEADER),
                 ("include/" + SHARED_FILE_PROFILE_HEADER, SHARED_FILE_HEADER))
        for name, declaration in cases:
            header = self.sdk / name
            bad = ["// " + declaration.replace("\n", "\n// "), "/*\n" + declaration + "*/\n",
                   declaration.replace("inline constexpr", "extern"),
                   declaration.replace("module_abi = 74", "module_abi = 59"),
                   declaration.replace("module_abi = 74", "module_abi = 64"),
                   declaration.replace("module_abi = 74", "module_abi = 65"),
                   declaration.replace("module_abi = 74", "module_abi = 75")]
            for line in declaration.splitlines(keepends=True):
                field = line.split(" = ", 1)[0].rsplit(" ", 1)[1]
                bad.append(declaration.replace(field, "unrelated_" + field))
                bad.append(declaration.replace(line, "// " + line))
            for source in bad:
                header.write_text(source)
                self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
                self.save()
                with self.subTest(marker=name, source=source), self.assertRaises(ValueError):
                    validate_sdk(self.sdk, "x86_64", "debug")
            header.write_text(declaration)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_tcp_accept_fields_comment_only_typed_markers_and_all_capacities(self):
        name = "include/" + TCP_PROFILE_HEADER
        header = self.sdk / name
        bad = ["// " + TCP_HEADER.replace("\n", "\n// "), "/*\n" + TCP_HEADER + "*/\n",
               TCP_HEADER.replace(" native_tcp_", " unrelated_native_tcp_").replace(" linux_tcp_", " unrelated_linux_tcp_"),
               TCP_HEADER.replace("inline constexpr", "extern")]
        for line in TCP_HEADER.splitlines(keepends=True):
            if "capacity" in line or "poll_budget" in line:
                bad.append(TCP_HEADER.replace(line, line.replace(" = ", " = 9")))
            if "accept_profile" in line:
                bad.append(TCP_HEADER.replace(line, "// " + line))
                bad.append(TCP_HEADER.replace(line, line.replace("reserved-accept-v1", "blocking-full-v1")))
        for source in bad:
            header.write_text(source)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "TCP"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_comment_only_and_untyped_native_module_declarations_are_refused(self):
        name = "include/ok/core/module.hpp"
        header = self.sdk / name
        for source in ("// inline constexpr u32 kernel_module_abi_version = 74;\n",
                       "/* inline constexpr u32 kernel_module_abi_version = 74; */\n",
                       "kernel_module_abi_version = 74;\n"):
            header.write_text(source)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "ABI74 header"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_all_native_markers_reject_conditional_raw_string_and_malformed_duplicate_declarations(self):
        cases = (("include/ok/fs/ext4_mounted_common_profile.hpp", COMMON_HEADER),
                 ("include/" + UDP_PROFILE_HEADER, UDP_HEADER),
                 ("include/" + TCP_PROFILE_HEADER, TCP_HEADER),
                 ("include/" + SHARED_FILE_PROFILE_HEADER, SHARED_FILE_HEADER),
                 ("include/" + FUTEX_WAKE_OPERATION_PROFILE_HEADER, FUTEX_WAKE_OPERATION_HEADER),
                 ("include/ok/core/module.hpp", "inline constexpr u32 kernel_module_abi_version = 74;\n"))
        for name, declaration in cases:
            header = self.sdk / name
            for source in nondeclaration_marker_sources(declaration):
                header.write_text(source)
                self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
                self.save()
                with self.subTest(marker=name, source=source), self.assertRaises(ValueError):
                    validate_sdk(self.sdk, "x86_64", "debug")
            header.write_text('constexpr auto example = R"example(\n' + declaration + ')example";\n' + declaration)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            validate_sdk(self.sdk, "x86_64", "debug")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sdk = self.root / "sdk"
        self.sdk.mkdir()
        files = {}
        for name in ("lib/libokernel.a", "lib/libokernel_boot.a", "boot/linker.ld",
                     "image/kernel.bin", "image/kernel.elf", "include/ok/uapi/syscall.h",
                     "include/ok/uapi/signal.h",
                     *("include/" + name for name in EXPECTED_CREDENTIALS_HEADERS),
                     *("include/" + name for name in BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADERS),
                     *("include/" + name for name in NATIVE_CONSOLE_INPUT_HEADERS),
                     *("include/" + name for name in NATIVE_PERSISTENT_SYNC_HEADERS),
                     *("include/" + name for name in NATIVE_MOUNT_INFO_HEADERS),
                     *("include/" + name for name in NATIVE_POWER_HEADERS),
                     *("include/" + name for name in NATIVE_METADATA_HEADERS),
                     *("include/" + name for name in NATIVE_SESSIONS_HEADERS),
                     *("include/" + name for name in NATIVE_GROUP_SIGNAL_HEADERS),
                     *("include/" + name for name in NATIVE_CONSOLE_CONTROL_HEADERS),
                     *("include/" + name for name in NATIVE_PTY_HEADERS),
                     "include/ok/core/module.hpp", "boot/boot16.bin",
                     "include/ok/fs/ext4_mounted_common_profile.hpp",
                     "include/ok/fs/ext4_mounted_metadata.hpp",
                     "include/ok/fs/ext4_mounted_common_opening_budget.hpp",
                     "include/ok/block/session_counters.hpp",
                     *("include/" + name for name in UDP_PROFILE_HEADERS),
                     *("include/" + name for name in TCP_PROFILE_HEADERS),
                     *("include/" + name for name in SHARED_FILE_PROFILE_HEADERS),
                     *("include/" + name for name in UNIX_PATHNAME_PROFILE_HEADERS),
                     *("include/" + name for name in DIRECTORY_CREATE_PROFILE_HEADERS),
                     *("include/" + name for name in FUTEX_WAKE_OPERATION_PROFILE_HEADERS),
                     *("include/" + name for name in FUTEX_REQUEUE_PROFILE_HEADERS)):
            path = self.sdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            content = (bytes(510) + b"\x55\xaa" if name.endswith("boot16.bin") else
                       UAPI_HEADER.encode() if name.endswith("syscall.h") else
                       TERMINATION_HEADER.encode() if name == "include/ok/uapi/signal.h" else
                       b"inline constexpr u32 kernel_module_abi_version = 74;\n"
                       if name.endswith("module.hpp") else
                       COMMON_HEADER.encode() if name.endswith("ext4_mounted_common_profile.hpp") else
                       UDP_HEADER.encode() if name == "include/" + UDP_PROFILE_HEADER else
                       TCP_HEADER.encode() if name == "include/" + TCP_PROFILE_HEADER else
                       SHARED_FILE_HEADER.encode() if name == "include/" + SHARED_FILE_PROFILE_HEADER else
                       UNIX_PATHNAME_HEADER.encode() if name == "include/" + UNIX_PATHNAME_PROFILE_HEADER else
                       DIRECTORY_CREATE_HEADER.encode() if name == "include/" + DIRECTORY_CREATE_PROFILE_HEADER else
                       CONSOLE_INPUT_HEADER.encode() if name == "include/" + NATIVE_CONSOLE_INPUT_PROFILE_HEADER else
                       PERSISTENT_SYNC_HEADER.encode() if name == "include/" + NATIVE_PERSISTENT_SYNC_PROFILE_HEADER else
                       MOUNT_INFO_HEADER.encode() if name == "include/" + NATIVE_MOUNT_INFO_PROFILE_HEADER else
                       POWER_HEADER.encode() if name == "include/" + NATIVE_POWER_PROFILE_HEADER else
                       METADATA_HEADER.encode() if name == "include/" + NATIVE_METADATA_PROFILE_HEADER else
                       SESSIONS_HEADER.encode() if name == "include/" + NATIVE_SESSIONS_PROFILE_HEADER else
                       GROUP_SIGNAL_HEADER.encode() if name == "include/" + NATIVE_GROUP_SIGNAL_PROFILE_HEADER else
                       CONSOLE_CONTROL_HEADER.encode() if name == "include/" + NATIVE_CONSOLE_CONTROL_PROFILE_HEADER else
                       PTY_HEADER.encode() if name == "include/" + NATIVE_PTY_PROFILE_HEADER else
                       BOOT_ARCHIVE_DIRECTORY_HEADER.encode() if name == "include/" + BOOT_ARCHIVE_DIRECTORY_PROFILE_HEADER else
                       FUTEX_WAKE_OPERATION_HEADER.encode() if name == "include/" + FUTEX_WAKE_OPERATION_PROFILE_HEADER else
                       FUTEX_REQUEUE_HEADER.encode() if name == "include/" + FUTEX_REQUEUE_PROFILE_HEADER else name.encode())
            path.write_bytes(content)
            files[name] = hashlib.sha256(content).hexdigest()
        self.manifest = {"schema": 1, "abi_version": 74, "kernel_version": "0.1.0",
                         "native_udp_profile": NATIVE_UDP_PROFILE, "linux_udp_profile": LINUX_UDP_PROFILE,
                         "native_udp_connected_profile": CONNECTED_UDP_PROFILE,
                         "native_tcp_profile": NATIVE_TCP_PROFILE, "linux_tcp_profile": LINUX_TCP_PROFILE,
                         "native_tcp_accept_profile": NATIVE_TCP_ACCEPT_PROFILE,
                         "linux_tcp_accept_profile": LINUX_TCP_ACCEPT_PROFILE,
                         "native_unix_pathname_profile": UNIX_PATHNAME_PROFILE,
                         "linux_unix_pathname_profile": UNIX_PATHNAME_PROFILE,
                         "native_shared_file_profile": NATIVE_SHARED_FILE_PROFILE,
                         "linux_shared_file_profile": LINUX_SHARED_FILE_PROFILE,
                         "native_futex_wake_operation_profile": FUTEX_WAKE_OPERATION_PROFILE,
                         "linux_futex_wake_operation_profile": FUTEX_WAKE_OPERATION_PROFILE,
                         "native_futex_requeue_profile": FUTEX_REQUEUE_PROFILE,
                         "linux_futex_requeue_profile": FUTEX_REQUEUE_PROFILE,
                         "ext4_common_opening_profile": "serialized-common-eight-family-directory-create-ordered-free-init-zero-refill-optional-revoke-legacy-v4",
                         "ext4_directory_create_profile": DIRECTORY_CREATE_PROFILE,
                         "ext4_ordered_data_profile": "bounded-mounted-dirty-existing-file-v1",
                         "ext4_empty_create_profile": "bounded-mounted-dirty-empty-regular-initial-attrs-ordered-home-v1",
                         "ext4_first_data_profile": "bounded-mounted-dirty-fresh-empty-first-block-ordered-home-v1",
                         "ext4_next_data_profile": "bounded-mounted-dirty-aligned-inline-next-block-ordered-home-v1",
                         "ext4_directory_rename_profile": "bounded-mounted-dirty-same-dir-absent-fit-or-relocate-ordered-home-v2", "arch": "x86_64",
                         "mode": "debug", "triple": "x86_64-elf", "image_format": "bios-disk",
                         "cxxflags": [], "asflags": [], "ldflags": [], "defines": ["OK_NATIVE_SIGNAL_RUNTIME"],
                         "native_signal_profile": "bounded-bootcpu-v1",
                         "native_init_profile": "designated-pid1-native-linux-adoption-v2",
                         "native_termination_profile": "bootcpu-positive-pid-probe-term-kill-deferred-v1",
                         "native_credentials_profile": EXPECTED_CREDENTIALS_PROFILE,
                         "boot_archive_directory_profile": "root-owned-ram-exact-sticky-sgid-v1",
                         "native_console_input_profile": "pid1-issued-epoch-fork-exec-leader-revoke-noecho-v1",
                         "native_persistent_sync_profile": "retained-linked-mounted-ordered-journal-device-flush-v1",
                         "native_mount_info_profile": "global-nine-slot-read-only-derived-generation-v1",
                         "native_power_profile": "original-init-scalar-prepare-queued-commit-v1",
                         "native_metadata_profile": NATIVE_METADATA_PROFILE,
                         "native_sessions_profile": NATIVE_SESSIONS_PROFILE,
                         "native_group_signal_profile": NATIVE_GROUP_SIGNAL_PROFILE,
                         "native_console_control_profile": NATIVE_CONSOLE_CONTROL_PROFILE,
                         "native_pty_profile": NATIVE_PTY_PROFILE,
                         "terminal_reboot_backend": "unsupported",
                         "terminal_poweroff_backend": "unsupported",
                         "compiler": {"family": "gcc", "version": "14.2.0"}, "files": files}
        self.save()

    def save(self):
        (self.sdk / "manifest.json").write_text(json.dumps(self.manifest))

    @staticmethod
    def arm_image(size=64, target=48):
        image = bytearray(size)
        struct.pack_into("<I", image, 0, 0xea000000 | ((target - 8) // 4 & 0x00ffffff))
        struct.pack_into("<III", image, 0x24, 0x016f2818, 0x40010000, 0x40010000 + size)
        struct.pack_into("<I", image, target, 0xe1a00000)
        return bytes(image)

    def set_arm_image(self, payload):
        self.manifest.update(arch="arm32", triple="arm-none-eabi", image_format="arm32-linux-image")
        (self.sdk / "image/kernel.bin").write_bytes(payload)
        self.manifest["files"]["image/kernel.bin"] = hashlib.sha256(payload).hexdigest()
        self.save()

    def test_connected_capability_header_refusals(self):
        declaration = 'inline constexpr std::string_view native_udp_connected_profile = "bounded-static-peer-association-zero-destination-output-v2";\n'
        invalid = (UDP_HEADER.replace(declaration, ""),
                   UDP_HEADER.replace(declaration, declaration + declaration),
                   UDP_HEADER.replace('bounded-static-peer-association-zero-destination-output-v2', "bounded-static-peer-association-v0"))
        name = "include/" + UDP_PROFILE_HEADER
        header = self.sdk / name
        for content in invalid:
            header.write_text(content)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "UDP profile mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_connected_and_name_header_file_and_hash_refusals(self):
        for relative in ("ok/abi/linux_udp_name_data.hpp", "ok/abi/linux_udp_connected_data.hpp", "ok/net/wire.hpp"):
            name = "include/" + relative
            header = self.sdk / name
            content = header.read_bytes()
            header.unlink()
            with self.subTest(header=relative, refusal="missing file"), self.assertRaisesRegex(ValueError, "artifact is missing"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_bytes(content + b" changed")
            with self.subTest(header=relative, refusal="checksum"), self.assertRaisesRegex(ValueError, "checksum mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_bytes(content)

    def test_previous_zero_port_gap_headers_and_manifests_are_refused(self):
        name = "include/" + UDP_PROFILE_HEADER
        header = self.sdk / name
        for key, old, current in (('native_udp_profile', 'bootcpu-static-peer-ipv4-polling-captured-connected-v2', 'bootcpu-static-peer-ipv4-polling-captured-connected-zero-send-v3'), ('linux_udp_profile', 'bootcpu-static-peer-ipv4-captured-connected-v2', 'bootcpu-static-peer-ipv4-captured-connected-zero-send-v3'), ('native_udp_connected_profile', 'bounded-static-peer-association-port-zero-wire-gap-v1', 'bounded-static-peer-association-zero-destination-output-v2')):
            self.assertEqual(UDP_HEADER.count(current), 1)
            header.write_text(UDP_HEADER.replace(current, old))
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(old=old, boundary="header"), self.assertRaisesRegex(ValueError, "UDP profile mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")
            header.write_text(UDP_HEADER)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.manifest[key] = old
            self.save()
            with self.subTest(old=old, boundary="manifest"), self.assertRaisesRegex(ValueError, "UDP profile mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest[key] = current
            self.save()
        validate_sdk(self.sdk, "x86_64", "debug")

    def test_valid_sdk(self):
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["arch"], "x86_64")

    def test_exact_udp_manifest_profiles(self):
        for name, valid in (("native_udp_profile", NATIVE_UDP_PROFILE), ("linux_udp_profile", LINUX_UDP_PROFILE),
                            ("native_udp_connected_profile", CONNECTED_UDP_PROFILE)):
            for value in (None, False, {}, "disabled", valid + "-wrong"):
                self.manifest[name] = value
                self.save()
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, "UDP profile mismatch"):
                    validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest[name] = valid
            self.save()

    def test_udp_headers_are_explicit_hashed_artifacts(self):
        for header in UDP_PROFILE_HEADERS:
            name = "include/" + header
            digest = self.manifest["files"].pop(name)
            self.save()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "missing artifacts"):
                validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest["files"][name] = digest

    def test_rehashed_udp_contract_mixed_markers_are_rejected(self):
        name = "include/" + UDP_PROFILE_HEADER
        header = self.sdk / name
        for content in (UDP_HEADER.replace("module_abi = 74", "module_abi = 49"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 51"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 52"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 53"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 54"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 55"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 56"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 57"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 58"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 64"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 65"),
                        UDP_HEADER.replace("module_abi = 74", "module_abi = 75"),
                        UDP_HEADER.replace("capacity = 16", "capacity = 15"),
                        UDP_HEADER.replace("capacity = 2", "capacity = 1"),
                        UDP_HEADER.replace("capacity = 1472", "capacity = 1500"),
                        UDP_HEADER.replace("capacity = 1514", "capacity = 1518"),
                        UDP_HEADER.replace("bootcpu-static-peer-ipv4-captured-connected-zero-send-v3", "bootcpu-static-peer-ipv4-nonblocking-immediate-v1"),
                        UDP_HEADER.replace("bootcpu-static-peer-ipv4-polling-captured-connected-zero-send-v3", "bootcpu-static-peer-ipv4-polling-captured-receive-v1"),
                        UDP_HEADER + UDP_HEADER):
            header.write_text(content)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "UDP"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_requires_exact_common_profile(self):
        for profile in (None, False, {}, "disabled", "general-ext4", "serialized-common-v0",
                        "serialized-common-seven-family-zero-refill-bounded-legacy-v1",
                        "serialized-common-seven-family-zero-refill-optional-revoke-legacy-v2"):
            self.manifest["ext4_common_opening_profile"] = profile
            self.save()
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, "common-opening profile"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_common_headers_must_be_explicit_hashed_artifacts(self):
        for name in ("include/ok/fs/ext4_mounted_common_profile.hpp",
                     "include/ok/fs/ext4_mounted_metadata.hpp",
                     "include/ok/fs/ext4_mounted_common_opening_budget.hpp",
                     "include/ok/block/session_counters.hpp"):
            digest = self.manifest["files"].pop(name)
            self.save()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "missing artifacts"):
                validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest["files"][name] = digest

    def test_rehashed_common_header_cannot_admit_old_or_duplicate_layout_markers(self):
        name = "include/ok/fs/ext4_mounted_common_profile.hpp"
        header = self.sdk / name
        for content in (COMMON_HEADER.replace("module_abi = 74", "module_abi = 51"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 52"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 53"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 54"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 55"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 56"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 57"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 58"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 64"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 65"),
                        COMMON_HEADER.replace("module_abi = 74", "module_abi = 75"),
                        COMMON_HEADER.replace("counter_bits = 64", "counter_bits = 32"),
                        COMMON_HEADER.replace("optional-revoke-legacy-v4", "unrestricted-v1"),
                        COMMON_HEADER + COMMON_HEADER,
                        "inline constexpr u32 unrelated = 52;\n"):
            header.write_text(content)
            self.manifest["files"][name] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "common-opening"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_requires_compiler_family_and_version_without_running_a_compiler(self):
        for metadata in (None, False, [], {}, {"family": "clang", "version": "14.2.0"},
                         {"family": "gcc", "version": ""}, {"family": "gcc", "version": 14}):
            self.manifest["compiler"] = metadata
            self.save()
            with self.subTest(metadata=metadata), self.assertRaisesRegex(ValueError, "GCC compiler"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_requires_explicit_ordinary_signal_capability(self):
        for value in (None, False, {}, "disabled", "private-debug-v1", "bounded-bootcpu-v2"):
            if value is None:
                self.manifest.pop("native_signal_profile", None)
            else:
                self.manifest["native_signal_profile"] = value
            self.save()
            with self.subTest(profile=value), self.assertRaisesRegex(ValueError, "native_signal_profile"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_requires_exact_init_adoption_capability(self):
        for value in (None, False, {}, "disabled", "designated-pid1-adoption-v1", "designated-pid1-adoption-v2"):
            self.manifest["native_init_profile"] = value
            self.save()
            with self.subTest(profile=value), self.assertRaisesRegex(ValueError, "native_init_profile"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_requires_exact_mounted_dirty_storage_capability(self):
        for value in (None, False, {}, "disabled", "bounded-mounted-dirty-existing-file-v2"):
            self.manifest["ext4_ordered_data_profile"] = value
            self.save()
            with self.subTest(profile=value), self.assertRaisesRegex(ValueError, "mounted-dirty"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_reboot_backend_requires_explicit_matching_machine_policy(self):
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["terminal_reboot_backend"], "unsupported")
        self.manifest["defines"].append("OK_NATIVE_PC8042_REBOOT=1")
        self.manifest["terminal_reboot_backend"] = "x86_64-pc-8042-v1"
        self.save()
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["terminal_reboot_backend"], "x86_64-pc-8042-v1")
        self.manifest.update(arch="aarch64", triple=ARCH_TRIPLES["aarch64"])
        self.save()
        with self.assertRaisesRegex(ValueError, "requires x86_64"):
            validate_sdk(self.sdk, "aarch64", "debug")

    def test_reboot_backend_rejects_missing_unknown_or_contradictory_manifest(self):
        for enabled in (False, True):
            self.manifest["defines"] = ["OK_NATIVE_SIGNAL_RUNTIME"] + (["OK_NATIVE_PC8042_REBOOT=1"] if enabled else [])
            for value in (None, False, "pc8042", "x86_64-pc-8042-v0", "unsupported" if enabled else "x86_64-pc-8042-v1"):
                self.manifest["terminal_reboot_backend"] = value
                self.save()
                with self.subTest(enabled=enabled, value=value), self.assertRaisesRegex(ValueError, "reboot backend"):
                    validate_sdk(self.sdk, "x86_64", "debug")
        self.manifest.pop("terminal_reboot_backend")
        self.save()
        with self.assertRaisesRegex(ValueError, "reboot backend"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_reboot_backend_rejects_ambiguous_opt_in_definitions(self):
        name = "OK_NATIVE_PC8042_REBOOT"
        for definitions in ([name], [name + "=0"], [name + "=true"], [name + "=1"] * 2,
                            [name + "=1", name + "=0"], [name + "=1 trailing"],
                            [name + " =1"], [" " + name + "=1"], [name + "()=1"]):
            self.manifest["defines"] = ["OK_NATIVE_SIGNAL_RUNTIME", *definitions]
            self.manifest["terminal_reboot_backend"] = "x86_64-pc-8042-v1"
            self.save()
            with self.subTest(definitions=definitions), self.assertRaisesRegex(ValueError, "canonical opt-in"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_reboot_backend_rejects_direct_and_forwarded_macro_overrides(self):
        name = "OK_NATIVE_PC8042_REBOOT"
        for field in ("cxxflags", "asflags"):
            for flags in (["-D" + name + "=1"], ["-D", name + "=0"], ["-U" + name],
                          ["-U", name], ["-Wp,-D," + name + "=1"], ["-Wp,-U," + name]):
                self.manifest[field] = flags
                self.save()
                with self.subTest(field=field, flags=flags), self.assertRaisesRegex(ValueError, "reboot backend macro override"):
                    validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest[field] = []

    def test_poweroff_backend_requires_explicit_matching_machine_policy(self):
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["terminal_poweroff_backend"], "unsupported")
        self.manifest["defines"].append("OK_NATIVE_QEMU_PIIX4_POWEROFF=1")
        self.manifest["terminal_poweroff_backend"] = "x86_64-qemu-piix4-pm-v1"
        self.save()
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["terminal_poweroff_backend"], "x86_64-qemu-piix4-pm-v1")
        self.manifest.update(arch="aarch64", triple=ARCH_TRIPLES["aarch64"])
        self.save()
        with self.assertRaisesRegex(ValueError, "requires x86_64"):
            validate_sdk(self.sdk, "aarch64", "debug")

    def test_poweroff_backend_rejects_missing_unknown_or_contradictory_manifest(self):
        for enabled in (False, True):
            self.manifest["defines"] = ["OK_NATIVE_SIGNAL_RUNTIME"] + (["OK_NATIVE_QEMU_PIIX4_POWEROFF=1"] if enabled else [])
            for value in (None, False, "piix4-pm", "x86_64-qemu-piix4-pm-v0", "unsupported" if enabled else "x86_64-qemu-piix4-pm-v1"):
                self.manifest["terminal_poweroff_backend"] = value
                self.save()
                with self.subTest(enabled=enabled, value=value), self.assertRaisesRegex(ValueError, "poweroff backend"):
                    validate_sdk(self.sdk, "x86_64", "debug")
        self.manifest.pop("terminal_poweroff_backend")
        self.save()
        with self.assertRaisesRegex(ValueError, "poweroff backend"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_poweroff_backend_rejects_ambiguous_opt_in_definitions(self):
        name = "OK_NATIVE_QEMU_PIIX4_POWEROFF"
        for definitions in ([name], [name + "=0"], [name + "=true"], [name + "=1"] * 2,
                            [name + "=1", name + "=0"], [name + "=1 trailing"],
                            [name + " =1"], [" " + name + "=1"], [name + "()=1"], [name + "+1"], [name + "-1"]):
            self.manifest["defines"] = ["OK_NATIVE_SIGNAL_RUNTIME", *definitions]
            self.manifest["terminal_poweroff_backend"] = "x86_64-qemu-piix4-pm-v1"
            self.save()
            with self.subTest(definitions=definitions), self.assertRaisesRegex(ValueError, "canonical opt-in"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_poweroff_backend_rejects_direct_and_forwarded_macro_overrides(self):
        name = "OK_NATIVE_QEMU_PIIX4_POWEROFF"
        for field in ("cxxflags", "asflags"):
            for flags in (["-D" + name + "=1"], ["-D", name + "=0"], ["-U" + name],
                          ["-U", name], ["-Wp,-D," + name + "=1"], ["-Wp,-U," + name]):
                self.manifest[field] = flags
                self.save()
                with self.subTest(field=field, flags=flags), self.assertRaisesRegex(ValueError, "poweroff backend macro override"):
                    validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest[field] = []

    def test_signal_capability_requires_matching_runtime_definition(self):
        for flags in ([], ["OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE"], ["OK_NATIVE_SIGNAL_RUNTIME=0"],
                      ["OK_NATIVE_SIGNAL_RUNTIME=1"], ["OK_NATIVE_SIGNAL_RUNTIME"] * 2,
                      ["OK_NATIVE_SIGNAL_RUNTIME", "OK_NATIVE_SIGNAL_RUNTIME=0"]):
            self.manifest["defines"] = flags
            self.save()
            with self.subTest(defines=flags), self.assertRaisesRegex(ValueError, "runtime definition"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_release_runtime_is_admitted_without_diagnostics(self):
        self.manifest["mode"] = "release"
        self.save()
        result = validate_sdk(self.sdk, "x86_64", "release")
        self.assertEqual(result["native_signal_profile"], "bounded-bootcpu-v1")

    def test_release_rejects_diagnostic_definitions(self):
        self.manifest["mode"] = "release"
        for field in ("defines", "cxxflags", "asflags"):
            for name in ("OK_ENABLE_TEST_POINTS", "OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE"):
                for suffix in ("", "=1", "=0"):
                    flag = ("" if field == "defines" else "-D") + name + suffix
                    self.manifest[field].append(flag)
                    self.save()
                    with self.subTest(field=field, flag=flag), self.assertRaisesRegex(ValueError, "diagnostics"):
                        validate_sdk(self.sdk, "x86_64", "release")
                    self.manifest[field].pop()

    def test_debug_runtime_allows_explicit_private_diagnostics(self):
        self.manifest["defines"] += ["OK_ENABLE_TEST_POINTS", "OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE"]
        self.save()
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["native_signal_profile"],
                         "bounded-bootcpu-v1")

    def test_mips64_requires_canonical_assembly_runtime_admission(self):
        self.manifest.update(arch="mips64", triple="mips64-elf", image_format="elf")
        for flags in ([], ["-DOK_NATIVE_SIGNAL_RUNTIME=0"], ["-DOK_NATIVE_SIGNAL_RUNTIME=1"],
                      ["-DOK_NATIVE_SIGNAL_RUNTIME"] * 2):
            self.manifest["asflags"] = flags
            self.save()
            with self.subTest(flags=flags), self.assertRaisesRegex(ValueError, "assembly admission"):
                validate_sdk(self.sdk, "mips64", "debug")
        self.manifest["asflags"] = ["-DOK_NATIVE_SIGNAL_RUNTIME"]
        self.save()
        self.assertEqual(validate_sdk(self.sdk, "mips64", "debug")["arch"], "mips64")

    def test_signal_macro_undef_overrides_are_rejected(self):
        for field in ("cxxflags", "asflags"):
            for name in ("OK_NATIVE_SIGNAL_RUNTIME", "OK_ENABLE_TEST_POINTS", "OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE"):
                for flags in (["-U" + name], ["-U", name], ["-Wp,-U," + name], ["-U " + name]):
                    self.manifest[field] = flags
                    self.save()
                    with self.subTest(field=field, flags=flags), self.assertRaisesRegex(ValueError, "macro override"):
                        validate_sdk(self.sdk, "x86_64", "debug")
                self.manifest[field] = []

    def test_private_diagnostics_require_debug_test_points(self):
        self.manifest["defines"].append("OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE")
        self.save()
        with self.assertRaisesRegex(ValueError, "private diagnostics require"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_debug_diagnostics_use_canonical_definitions(self):
        for name in ("OK_ENABLE_TEST_POINTS", "OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE"):
            for definitions in ([name + "=1"], [name + "=0"], [name, name]):
                self.manifest["defines"] = ["OK_NATIVE_SIGNAL_RUNTIME", *definitions]
                self.save()
                with self.subTest(definitions=definitions), self.assertRaisesRegex(ValueError, "canonical bare"):
                    validate_sdk(self.sdk, "x86_64", "debug")

    def test_diagnostics_cannot_bypass_canonical_defines_through_flags(self):
        for name in ("OK_ENABLE_TEST_POINTS", "OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE"):
            for flags in (["-D" + name], ["-D", name], ["-Wp,-D," + name]):
                self.manifest["cxxflags"] = flags
                self.save()
                with self.subTest(flags=flags), self.assertRaisesRegex(ValueError, "canonical exported"):
                    validate_sdk(self.sdk, "x86_64", "debug")
        self.manifest["cxxflags"] = []
        self.manifest["asflags"] = ["-DOK_ENABLE_TEST_POINTS"]
        self.save()
        with self.assertRaisesRegex(ValueError, "assembly admission"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_directory_rename_profile_is_required(self):
        self.manifest.pop("ext4_directory_rename_profile")
        self.save()
        with self.assertRaisesRegex(ValueError, "directory-rename profile mismatch"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_directory_rename_profile_without_ordered_home_boundary(self):
        for profile in ("bounded-mounted-dirty-same-dir-absent-fit-v1",
                        "bounded-mounted-dirty-same-dir-absent-fit-ordered-home-v1",
                        "bounded-mounted-dirty-same-dir-absent-fit-or-relocate-ordered-home-v1",
                        "bounded-mounted-dirty-same-dir-absent-fit-or-relocate-ordered-home-v3",
                        "bounded-mounted-dirty-existing-file-v1", "unknown"):
            self.manifest["ext4_directory_rename_profile"] = profile
            self.save()
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, "directory-rename profile mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_missing_or_mismatched_empty_create_profile(self):
        for profile in (None, "bounded-empty-regular-v1", ""):
            if profile is None:
                self.manifest.pop("ext4_empty_create_profile", None)
            else:
                self.manifest["ext4_empty_create_profile"] = profile
            self.save()
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, "empty-create profile mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_missing_or_mismatched_first_data_profile(self):
        for profile in (None, False, "", "bounded-mounted-dirty-empty-regular-initial-attrs-ordered-home-v1",
                        "bounded-mounted-dirty-fresh-empty-first-block-ordered-home-v2"):
            if profile is None:
                self.manifest.pop("ext4_first_data_profile", None)
            else:
                self.manifest["ext4_first_data_profile"] = profile
            self.save()
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, "first-data profile mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_wrong_arch_and_mode(self):
        for arch, mode in (("aarch64", "debug"), ("x86_64", "release")):
            with self.subTest(arch=arch, mode=mode), self.assertRaisesRegex(ValueError, "mismatch"):
                validate_sdk(self.sdk, arch, mode)

    def test_reject_missing_or_mismatched_next_data_profile(self):
        for profile in (None, False, '',
                        'bounded-mounted-dirty-fresh-empty-first-block-ordered-home-v1',
                        'bounded-mounted-dirty-aligned-inline-next-block-ordered-home-v2'):
            if profile is None:
                self.manifest.pop('ext4_next_data_profile', None)
            else:
                self.manifest['ext4_next_data_profile'] = profile
            self.save()
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, 'next-data profile mismatch'):
                validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_reject_mismatched_native_interface_abi(self):
        for version in (*range(1, 74), 75):
            self.manifest["abi_version"] = version
            self.save()
            with self.subTest(abi_version=version), self.assertRaisesRegex(ValueError, "abi_version mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_schema_and_native_abi_require_json_integer_identity(self):
        # 1.0 == 1, True == 1 and 71.0 == 71 in Python; these exact-value
        # impostors previously passed the manifest equality comparison.
        for field, accepted in (("schema", 1), ("abi_version", 74)):
            for value in (True, False, float(accepted), float(accepted) + 0.5,
                          str(accepted), None, [], {}):
                self.manifest[field] = value
                self.save()
                with self.subTest(field=field, value=value), self.assertRaisesRegex(
                        ValueError, f"{field} must be an integer"):
                    validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest.pop(field)
            self.save()
            with self.subTest(field=field, missing=True), self.assertRaisesRegex(
                    ValueError, f"{field} must be an integer"):
                validate_sdk(self.sdk, "x86_64", "debug")
            self.manifest[field] = accepted
            self.save()
            admitted = validate_sdk(self.sdk, "x86_64", "debug")
            self.assertIs(type(admitted[field]), int)
            self.assertEqual(admitted[field], accepted)

    def test_integer_schema_identity_still_requires_supported_value(self):
        for version in (0, 2, -1):
            self.manifest["schema"] = version
            self.save()
            with self.subTest(schema=version), self.assertRaisesRegex(ValueError, "schema mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_mismatched_hashed_native_module_header(self):
        header = self.sdk / "include/ok/core/module.hpp"
        for source in ("inline constexpr u32 kernel_module_abi_version = 48;\n",
                       "inline constexpr u32 kernel_module_abi_version = 49;\n",
                       "inline constexpr u32 kernel_module_abi_version = 50;\n",
                       "inline constexpr u32 kernel_module_abi_version = 51;\n",
                       "inline constexpr u32 kernel_module_abi_version = 52;\n",
                       "inline constexpr u32 kernel_module_abi_version = 53;\n",
                       "inline constexpr u32 kernel_module_abi_version = 54;\n",
                       "inline constexpr u32 kernel_module_abi_version = 55;\n",
                       "inline constexpr u32 kernel_module_abi_version = 56;\n",
                       "inline constexpr u32 kernel_module_abi_version = 57;\n",
                       "inline constexpr u32 kernel_module_abi_version = 58;\n",
                       "inline constexpr u32 kernel_module_abi_version = 59;\n",
                       "inline constexpr u32 kernel_module_abi_version = 60;\n",
                       "inline constexpr u32 kernel_module_abi_version = 63;\n",
                       "inline constexpr u32 kernel_module_abi_version = 64;\n",
                       "inline constexpr u32 kernel_module_abi_version = 65;\n",
                       "inline constexpr u32 kernel_module_abi_version = 66;\n",
                       "inline constexpr u32 kernel_module_abi_version = 67;\n",
                       "inline constexpr u32 kernel_module_abi_version = 68;\n",
                       "inline constexpr u32 kernel_module_abi_version = 69;\n",
                       "inline constexpr u32 kernel_module_abi_version = 71;\n",
                       "inline constexpr u32 unrelated = 49;\n",
                       "inline constexpr u32 kernel_module_abi_version = 74;\n" * 2):
            header.write_text(source)
            self.manifest["files"]["include/ok/core/module.hpp"] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "ABI74 header"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_wrong_hashed_uapi_version(self):
        header = self.sdk / "include/ok/uapi/syscall.h"
        for source in (UAPI_HEADER.replace("MINOR 16", "MINOR 9"),
                       UAPI_HEADER.replace("MINOR 16", "MINOR 17"),
                       UAPI_HEADER.replace("PATCH 0", "PATCH 1"),
                       UAPI_HEADER.replace("MAJOR 0", "MAJOR 1"),
                       UAPI_HEADER.replace("#define OK_UAPI_VERSION_MINOR 16\n", ""),
                       UAPI_HEADER + "#define OK_UAPI_VERSION_MINOR 16\n"):
            header.write_text(source)
            self.manifest["files"]["include/ok/uapi/syscall.h"] = hashlib.sha256(header.read_bytes()).hexdigest()
            self.save()
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "UAPI 0.16.0"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_all_ten_profile_contracts(self):
        for arch, triple in ARCH_TRIPLES.items():
            with self.subTest(arch=arch):
                self.manifest["asflags"] = ["-DOK_NATIVE_SIGNAL_RUNTIME"] if arch == "mips64" else []
                if arch == "arm32":
                    self.set_arm_image(self.arm_image())
                else:
                    image_format = {"i386": "bios-disk", "x86_64": "bios-disk", "aarch64": "linux-image"}.get(arch, "elf")
                    self.manifest.update(arch=arch, triple=triple, image_format=image_format)
                    self.save()
                self.assertEqual(validate_sdk(self.sdk, arch, "debug")["arch"], arch)

    def test_arm32_requires_explicit_format(self):
        self.set_arm_image(self.arm_image())
        for image_format in ("elf", "linux-image", "bios-disk"):
            self.manifest["image_format"] = image_format
            self.save()
            with self.subTest(image_format=image_format), self.assertRaisesRegex(ValueError, "ARM-only"):
                validate_sdk(self.sdk, "arm32", "debug")

    def test_arm_format_cannot_be_used_by_other_architectures(self):
        self.set_arm_image(self.arm_image())
        for arch, triple in ARCH_TRIPLES.items():
            if arch == "arm32":
                continue
            self.manifest.update(arch=arch, triple=triple)
            self.manifest["asflags"] = ["-DOK_NATIVE_SIGNAL_RUNTIME"] if arch == "mips64" else []
            self.save()
            with self.subTest(arch=arch), self.assertRaisesRegex(ValueError, "ARM-only"):
                validate_sdk(self.sdk, arch, "debug")

    def test_arm_entry_at_first_and_last_complete_instruction(self):
        for size, target in ((52, 48), (64, 48), (64, 60), (65, 60)):
            with self.subTest(size=size, target=target):
                self.set_arm_image(self.arm_image(size, target))
                validate_sdk(self.sdk, "arm32", "debug")

    def test_arm_header_and_entry_truncation_rejected(self):
        image = self.arm_image()
        for size in range(52):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "truncated"):
                validate_arm32_image(image[:size])

    def test_arm_header_corruption_rejected_even_with_matching_checksum(self):
        cases = (
            (0x24, 0, "magic"), (0x24, 0x18286f01, "magic"),
            (0x28, 0x40008000, "link"), (0x28, 0xfffffff0, "link"),
            (0x2c, 0x40010000, "extent"), (0x2c, 0x4000ffff, "extent"),
            (0x2c, 0x4001003f, "extent"), (0x2c, 0x40010041, "extent"),
            (0x2c, 0x10, "extent"), (0x2c, 0xffffffff, "extent"),
            (0, 0x0a00000a, "unconditional"), (0, 0xeb00000a, "unconditional"),
            (0, 0xfa00000a, "unconditional"), (0, 0xe12fff10, "unconditional"),
            (0, 0x0a0000ea, "unconditional"),
            (0, 0xea000009, "branch"), (0, 0xea00000e, "branch"),
            (0, 0xeafffffe, "branch"), (0, 0xea800000, "branch"),
            (0, 0xea7fffff, "branch"),
        )
        for offset, value, error in cases:
            with self.subTest(offset=offset, value=hex(value)):
                payload = bytearray(self.arm_image())
                struct.pack_into("<I", payload, offset, value)
                self.set_arm_image(payload)
                with self.assertRaisesRegex(ValueError, error):
                    validate_sdk(self.sdk, "arm32", "debug")

    def test_arm_partial_destination_instruction_is_rejected(self):
        payload = bytearray(self.arm_image(64, 60)[:63])
        struct.pack_into("<I", payload, 0x2c, 0x40010000 + len(payload))
        with self.assertRaisesRegex(ValueError, "branch"):
            validate_arm32_image(payload)

    def test_arm_extra_or_missing_bytes_rejected(self):
        payload = self.arm_image()
        for altered in (payload + b"\0", payload[:-1]):
            with self.subTest(size=len(altered)), self.assertRaisesRegex(ValueError, "extent"):
                validate_arm32_image(altered)

    def test_arm_assembler_validates_new_raw_payload_before_publication(self):
        output = self.root / "image.bin"
        self.set_arm_image(self.arm_image())
        for payload, valid in ((self.arm_image(80, 76), True), (b"not an ARM image", False)):
            with self.subTest(valid=valid):
                def objcopy(args, check):
                    self.assertEqual(args[1:3], ["-O", "binary"])
                    Path(args[-1]).write_bytes(payload)
                output.write_bytes(b"previous image")
                with patch("kernel_sdk.subprocess.run", side_effect=objcopy):
                    if valid:
                        assemble_image(self.sdk / "image/kernel.elf", output, self.sdk, "arm32-linux-image", Path("objcopy"))
                        self.assertEqual(output.read_bytes(), payload)
                    else:
                        with self.assertRaisesRegex(ValueError, "truncated"):
                            assemble_image(self.sdk / "image/kernel.elf", output, self.sdk, "arm32-linux-image", Path("objcopy"))
                        self.assertEqual(output.read_bytes(), b"previous image")

    def test_arm_assembler_requires_objcopy(self):
        with self.assertRaisesRegex(ValueError, "objcopy"):
            assemble_image(self.sdk / "image/kernel.elf", self.root / "image.bin", self.sdk, "arm32-linux-image", None)

    def test_unknown_assembly_format_fails_before_running_tools(self):
        with patch("kernel_sdk.subprocess.run") as run, self.assertRaisesRegex(ValueError, "unsupported"):
            assemble_image(self.sdk / "image/kernel.elf", self.root / "image.bin", self.sdk, "unknown", Path("objcopy"))
        run.assert_not_called()

    def test_assembler_abi_flags_are_required(self):
        for invalid in (None, "-mabi=64", [64]):
            self.manifest["asflags"] = invalid
            self.save()
            with self.subTest(flags=invalid), self.assertRaisesRegex(ValueError, "asflags"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_matching_compiler_abi(self):
        with patch("kernel_sdk.subprocess.check_output", side_effect=["x86_64-elf\n", "14.2.0\n"]):
            validate_sdk(self.sdk, "x86_64", "debug", Path("g++"))

    def test_mismatched_compiler_abi(self):
        for triple, version in (("aarch64-elf", "14.2.0"), ("x86_64-elf", "13.3.0")):
            with self.subTest(triple=triple, version=version), patch(
                "kernel_sdk.subprocess.check_output", side_effect=[triple, version]
            ), self.assertRaisesRegex(ValueError, r"C\+\+ module ABI"):
                validate_sdk(self.sdk, "x86_64", "debug", Path("g++"))

    def test_missing_sdk_has_build_instruction(self):
        with self.assertRaisesRegex(ValueError, "kernel-sdk"):
            validate_sdk(self.root / "missing", "x86_64", "debug")

    def test_modified_headers_cannot_mix_with_old_library(self):
        (self.sdk / "include/ok/uapi/syscall.h").write_text("changed ABI")
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_missing_boot_library(self):
        (self.sdk / "lib/libokernel_boot.a").unlink()
        with self.assertRaisesRegex(ValueError, "artifact is missing"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_manifest_without_required_artifact(self):
        del self.manifest["files"]["lib/libokernel.a"]
        self.save()
        with self.assertRaisesRegex(ValueError, "missing artifacts"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_path_escape(self):
        self.manifest["files"]["../secret"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "escapes"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_elf_image_is_copied_without_conversion(self):
        elf = self.sdk / "image/kernel.elf"
        output = self.root / "image.bin"
        assemble_image(elf, output, self.sdk, "elf", None)
        self.assertEqual(output.read_bytes(), elf.read_bytes())

    def assemble_bios(self, payload):
        def objcopy(args, check):
            Path(args[-1]).write_bytes(payload)
        output = self.root / "image.bin"
        with patch("kernel_sdk.subprocess.run", side_effect=objcopy):
            assemble_image(self.sdk / "image/kernel.elf", output, self.sdk, "bios-disk", Path("objcopy"))
        return output.read_bytes()

    def set_extended_bios_loader(self):
        boot = bytearray((self.sdk / "boot/boot16.bin").read_bytes())
        boot[0x1f0:0x1f8] = b"OKB2" + struct.pack("<I", EXTENDED_BIOS_PAYLOAD_CAPACITY)
        (self.sdk / "boot/boot16.bin").write_bytes(boot)
        self.manifest["files"]["boot/boot16.bin"] = hashlib.sha256(boot).hexdigest()
        self.manifest["bios_payload_bytes"] = EXTENDED_BIOS_PAYLOAD_CAPACITY
        self.save()

    def test_bios_sector_payload_and_padding(self):
        image = self.assemble_bios(b"payload")
        self.assertEqual(len(image), 512 + LEGACY_BIOS_PAYLOAD_CAPACITY)
        self.assertEqual(image[510:519], b"\x55\xaapayload")
        self.assertFalse(any(image[519:]))

    def test_bios_payload_overflow_fails(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            self.assemble_bios(bytes(LEGACY_BIOS_PAYLOAD_CAPACITY + 1))

    def test_extended_bios_manifest_admits_8mib_payload(self):
        self.set_extended_bios_loader()
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["bios_payload_bytes"],
                         EXTENDED_BIOS_PAYLOAD_CAPACITY)
        payload = bytes(LEGACY_BIOS_PAYLOAD_CAPACITY + 1)
        image = self.assemble_bios(payload)
        self.assertEqual(len(image), 512 + EXTENDED_BIOS_PAYLOAD_CAPACITY)
        self.assertEqual(image[512:512 + len(payload)], payload)

    def test_extended_bios_payload_overflow_fails(self):
        self.set_extended_bios_loader()
        with self.assertRaisesRegex(ValueError, "too large"):
            self.assemble_bios(bytes(EXTENDED_BIOS_PAYLOAD_CAPACITY + 1))

    def test_reject_extended_manifest_with_legacy_loader(self):
        self.manifest["bios_payload_bytes"] = EXTENDED_BIOS_PAYLOAD_CAPACITY
        self.save()
        with self.assertRaisesRegex(ValueError, "loader and manifest"):
            validate_sdk(self.sdk, "x86_64", "debug")
        with self.assertRaisesRegex(ValueError, "loader and manifest"):
            self.assemble_bios(b"payload")

    def test_reject_versioned_loader_with_missing_or_wrong_manifest_extent(self):
        self.set_extended_bios_loader()
        for value in (None, LEGACY_BIOS_PAYLOAD_CAPACITY):
            if value is None:
                self.manifest.pop("bios_payload_bytes", None)
            else:
                self.manifest["bios_payload_bytes"] = value
            self.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "loader and manifest"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_malformed_bios_payload_extent(self):
        for value in (0, 4 * 1024 * 1024 + 512, 16 * 1024 * 1024, "8388608", None, True):
            self.manifest["bios_payload_bytes"] = value
            self.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "BIOS payload extent"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_bios_invalid_signature_fails(self):
        (self.sdk / "boot/boot16.bin").write_bytes(bytes(512))
        with self.assertRaisesRegex(ValueError, "boot sector"):
            self.assemble_bios(b"payload")


if __name__ == "__main__":
    unittest.main()
