"""Stable display names; preserve each lobby's independent port/rotation."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LobbyNames(unittest.TestCase):
    def test_numbered_names(self):
        ports = set()
        for n in range(1, 13):
            with self.subTest(lobby=n):
                text = (ROOT / f"ftesurf/cfg/lobby/lobby{n}.cfg").read_text()
                self.assertEqual(re.findall(r'^set hostname\s+"([^"]+)"', text, re.M),
                                 [f"Open Lobby #{n}"])
                port = re.findall(r'^set sv_port\s+(\d+)', text, re.M)
                self.assertEqual(len(port), 1)
                self.assertNotIn(port[0], ports)
                ports.add(port[0])
                self.assertRegex(text, r'(?m)^set lobby_maps\s+"[^\"]+"')


if __name__ == "__main__":
    unittest.main()
