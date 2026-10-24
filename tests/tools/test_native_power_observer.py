import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from native_power_observer import terminal_site, halted_registers


DISASSEMBLY = """0000000000401000 <ok::arch::terminal_power_action(ok::SystemPowerAction)>:
  401000: fa                    cli
  401001: f4                    hlt
  401002: eb fc                 jmp    401000 <ok::arch::terminal_power_action(ok::SystemPowerAction)>
"""
REGISTERS = "RIP=0000000000401002 RFL=00000002 [-------] CPL=0 II=0 A20=1 SMM=0 HLT=1\n"


class TerminalObserverTests(unittest.TestCase):
    def test_exact_kernel_halt(self):
        site = terminal_site(DISASSEMBLY)
        self.assertEqual(halted_registers(REGISTERS, site)["RIP"], 0x401002)

    def test_reject_other_halt_or_interruptible_cpu(self):
        site = terminal_site(DISASSEMBLY)
        for registers in (REGISTERS.replace("401002", "401001"),
                          REGISTERS.replace("00000002", "00000202"),
                          REGISTERS.replace("HLT=1", "HLT=0"),
                          REGISTERS.replace("CPL=0", "CPL=3"),
                          REGISTERS + "RIP=401002\n", REGISTERS.replace("HLT=1", "")):
            with self.subTest(registers=registers), self.assertRaises(ValueError):
                halted_registers(registers, site)

    def test_reject_different_or_ambiguous_loop(self):
        for disassembly in (DISASSEMBLY.replace("fa                    cli", "90                    nop"),
                            DISASSEMBLY.replace("eb fc", "eb fd"),
                            DISASSEMBLY.replace("jmp    401000", "jmp    401001"),
                            DISASSEMBLY + DISASSEMBLY,
                            DISASSEMBLY.replace("terminal_power_action", "unrelated_hold"),
                            DISASSEMBLY + "  401004: 90                    nop\n"):
            with self.subTest(disassembly=disassembly), self.assertRaises(ValueError):
                terminal_site(disassembly)


if __name__ == "__main__":
    unittest.main()
