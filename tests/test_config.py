import os
import unittest
from pathlib import Path

from backend.config import load_config


class ConfigTests(unittest.TestCase):
    def test_environment_is_loaded_without_exposing_or_mutating_process_values(self):
        root = Path("C:/campo-test")
        environment = {
            "DATA_DIR": "C:/campo-data",
            "ERP_MODE": "live",
            "ERP_API_URL": "https://erp.example/",
            "ERP_API_KEY": "secret-key",
            "TELEGRAM_ALLOWED_USERS": "123, 456,,",
            "APP_RESPONSIBLE_NAME": " Ana ",
            "PUBLIC_URL": "https://campo.example/",
        }
        config = load_config(root, environment)
        self.assertEqual(config.data_dir, Path("C:/campo-data"))
        self.assertEqual(config.erp_url, "https://erp.example")
        self.assertEqual(config.allowed_users, {"123", " 456"})
        self.assertEqual(config.responsible_name, "Ana")
        self.assertEqual(config.public_url, "https://campo.example")
        self.assertEqual(environment["ERP_API_KEY"], "secret-key")
        self.assertNotIn("ERP_API_KEY", repr(config))

    def test_defaults_are_stable(self):
        config = load_config(Path("C:/campo-test"), {})
        self.assertEqual(config.data_dir, Path("C:/campo-test/data"))
        self.assertEqual(config.erp_mode, "demo")
        self.assertEqual(config.telegram_mode, "demo")
        self.assertEqual(config.user, "dev")


if __name__ == "__main__":
    unittest.main()
