import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import musl_cc  # noqa: E402

PROFILE = {"schema_version": 1, "arch": "x86_64", "compiler": "/tc/bin/x86_64-elf-gcc", "frontend": None,
           "abi_flags": ["-m64"], "defines": ["-D__linux__=1"], "include": "/musl/include",
           "lib": "/musl/lib", "compiler_include": "/tc/include", "ldflags": [],
           "linker_script": "/ports/musl/static-exec.ld", "user_base": "0x40000000",
           "supplements": ["/softfp.a"], "elf_abi_version": 0}


def elf(elf_class=2, order=1, osabi=0, abiversion=0, kind=2) -> bytes:
    header = bytearray(64)
    header[:9] = b"\x7fELF" + bytes((elf_class, order, 1, osabi, abiversion))
    struct.pack_into("<H" if order == 1 else ">H", header, 16, kind)
    return bytes(header)


class DriverModeTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(musl_cc.classify(["-O2", "-c", "a.c", "-o", "a.o"]), ("compile", [2], "a.o"))
        self.assertEqual(musl_cc.classify(["-E", "-x", "c", "-"])[0], "compile")
        self.assertEqual(musl_cc.classify(["-M", "a.c"])[0], "compile")
        self.assertEqual(musl_cc.classify(["a.o", "b.o", "-oprog", "-lm"]), ("link", [], "prog"))
        self.assertEqual(musl_cc.classify(["-O2", "t.c", "-o", "t"]), ("link", [1], "t"))
        self.assertEqual(musl_cc.classify(["-print-file-name=include"])[0], "query")
        self.assertEqual(musl_cc.classify(["-dumpmachine"])[0], "query")
        # A separate option value is never an input.
        self.assertEqual(musl_cc.classify(["-include", "x.c", "-c", "y.c"])[1], [3])

    def test_refuses_dynamic_links(self):
        for flag in ("-shared", "-pie", "-static-pie", "-nostdlib", "-nostartfiles"):
            with self.assertRaises(SystemExit, msg=flag):
                musl_cc.classify(["a.o", flag])

    def test_relocatable_links_pass_through(self):
        # Kbuild: LD = $(CC) -nostdlib; $(LD) $(LDFLAGS) -r -o built-in.o ...
        self.assertEqual(musl_cc.classify(["-nostdlib", "-r", "-o", "built-in.o", "a.o", "b.o"]),
                         ("partial", [], "built-in.o"))
        with self.assertRaises(SystemExit):
            musl_cc.classify(["-r", "a.c", "-o", "a.o"])

    def test_compile_sees_only_musl_and_builtin_headers(self):
        command = musl_cc.compile_command(PROFILE, ["-c", "a.c"])
        self.assertEqual(command[:2], ["/tc/bin/x86_64-elf-gcc", "-m64"])
        at = command.index("-nostdinc")
        self.assertEqual(command[at:at + 5], ["-nostdinc", "-isystem", "/musl/include", "-isystem", "/tc/include"])
        self.assertIn("-fno-pie", command)
        ppc = dict(PROFILE, frontend={"path": "/usr/bin/clang-18", "flags": ["--target=powerpc-linux-musl"],
                                      "include": "/clang/include"})
        command = musl_cc.compile_command(ppc, ["-c", "a.c"])
        self.assertEqual(command[:2], ["/usr/bin/clang-18", "--target=powerpc-linux-musl"])
        self.assertEqual(command[command.index("/musl/include") + 1:][:2], ["-isystem", "/clang/include"])

    def test_link_uses_static_layout_and_libc_group(self):
        command = musl_cc.link_command(PROFILE, ["a.o", "-o", "prog"])
        self.assertIn("-Wl,-T,/ports/musl/static-exec.ld", command)
        self.assertIn("-Wl,--defsym,USER_BASE=0x40000000", command)
        self.assertLess(command.index("/musl/lib/crt1.o"), command.index("a.o"))
        group = command[command.index("-Wl,--start-group"):command.index("-Wl,--end-group")]
        self.assertEqual(group, ["-Wl,--start-group", "/musl/lib/libc.a", "/softfp.a", "-lgcc"])
        self.assertEqual(command[-1], "/musl/lib/crtn.o")

    def test_compile_options_drop_link_only_arguments(self):
        argv = ["-O2", "-I", "inc", "t.c", "x.o", "-Wl,--gc-sections", "-L", "lib", "-lm", "-o", "t", "-static"]
        self.assertEqual(musl_cc.compile_options(argv, [3]), ["-O2", "-I", "inc"])


class PersonalityMarkingTests(unittest.TestCase):
    def mark(self, payload: bytes, profile=PROFILE) -> bytes:
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "prog"
            path.write_bytes(payload)
            musl_cc.mark_linux(path, profile)
            return path.read_bytes()

    def test_marks_linux_osabi(self):
        self.assertEqual(self.mark(elf())[7], 3)
        self.assertEqual(self.mark(elf(osabi=3))[7], 3)
        mips = dict(PROFILE, arch="mips", elf_abi_version=1)
        self.assertEqual(self.mark(elf(elf_class=1, order=2, abiversion=1), mips)[7], 3)

    def test_refuses_unexpected_identity(self):
        for payload in (elf(elf_class=1), elf(order=2), elf(osabi=9), elf(abiversion=1), elf(kind=3), b"\x7fELF"):
            with self.assertRaises(SystemExit):
                self.mark(payload)


if __name__ == "__main__":
    unittest.main()
