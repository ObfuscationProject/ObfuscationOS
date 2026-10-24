# Native file metadata wrappers

The exported native headers provide chmod/fchmod/fchmodat and
chown/fchown/fchownat. ObfuscationOS consumes an explicit architecture/mode SDK
with ABI 70, UAPI 0.12.0 and native_metadata_profile
checked-mode-root-owner-u32-v1. Source-header fallback is not supported.

okcrt preserves the complete 32-bit mode/uid/gid values, uses syscall6 with every
unused argument zero, and translates checked kernel errors into errno. The at
variants accept AT_EMPTY_PATH and AT_SYMLINK_NOFOLLOW; unsupported flags are
rejected by the native boundary. UINT32_MAX independently means unchanged uid or
gid. Ownership changes require effective root, including all-unchanged requests.
Provider capability may be unavailable and returns EOPNOTSUPP; read-only mounts
return EROFS.

Run the hosted actual wrapper test with an explicit exported debug SDK:

```sh
OK_TEST_KERNEL_SDK=/absolute/path/to/sdk/x86_64/debug \
  python3 -m unittest discover -s tests/tools -p test_native_metadata_wrappers.py
```

The test validates that SDK before compiling actual syscalls.c and errno.c with
xmake, captures syscall6 arguments, and checks errno propagation and unused
words. It is hosted marshalling coverage, not a native trap or persistence test.
test_native_metadata_sdk.py separately checks exact producer/consumer admission
using synthetic artifact fixtures; those fixtures do not contain executable
kernel artifacts.
