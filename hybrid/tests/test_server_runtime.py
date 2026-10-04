from __future__ import annotations

import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import main  # noqa: E402


class ServerRuntimeTests(unittest.TestCase):
    def test_dynamic_port_binding_returns_real_ephemeral_port(self):
        server = main.create_server(0)
        try:
            host, port = server.server_address[:2]
            self.assertEqual(host, main.HOST)
            self.assertIsInstance(port, int)
            self.assertGreater(port, 0)
            self.assertNotEqual(port, 8768)
        finally:
            server.server_close()

    def test_health_identity_constant_is_schoolsvs(self):
        self.assertEqual(main.APP_ID, "schoolsvs-hybrid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
