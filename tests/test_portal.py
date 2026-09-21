#!/usr/bin/env python3
"""
Unit tests for IIT BHU Wi-Fi Auto-Connect.
Tests configuration management, token parsing, form extraction, and network logic.
"""

import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import project modules
from config import ConfigManager, StateManager, _obfuscate, _deobfuscate
from portal_client import PortalClient, NetworkStatus, find_campus_interface_ip


class TestConfigManager(unittest.TestCase):
    """Test configuration storage and encryption/obfuscation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.config = ConfigManager(config_file=self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_obfuscation(self):
        secret = "MySecretPass123!@"
        obf = _obfuscate(secret)
        self.assertTrue(obf.startswith("enc:"))
        self.assertNotEqual(secret, obf)
        deobf = _deobfuscate(obf)
        self.assertEqual(secret, deobf)

    def test_save_and_load(self):
        self.config.set("username", "test_user_123")
        self.config.set("password", "TestPassword99")
        self.assertTrue(self.config.save())

        # Load fresh
        loaded = ConfigManager(config_file=self.config_path)
        self.assertEqual(loaded.get("username"), "test_user_123")
        self.assertEqual(loaded.get("password"), "TestPassword99")
        self.assertTrue(loaded.is_configured())


class TestStateManager(unittest.TestCase):
    """Test persistent runtime state management."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"
        self.state = StateManager(state_file=self.state_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_state_persistence(self):
        self.assertEqual(self.state.get_all(), {})
        self.state.update(last_login_time="2026-09-21 12:00:00", current_status="ONLINE")

        loaded = StateManager(state_file=self.state_path)
        self.assertEqual(loaded.get("last_login_time"), "2026-09-21 12:00:00")
        self.assertEqual(loaded.get("current_status"), "ONLINE")
        self.assertIsNone(loaded.get("nonexistent_key"))


class TestPortalClient(unittest.TestCase):
    """Test token parsing, form extraction, and captive portal workflows."""

    def setUp(self):
        self.client = PortalClient()

    def test_extract_magic_from_url(self):
        url = "http://192.168.249.1:1000/fgtauth?0123456789abcdef"
        magic = self.client.extract_magic_token(url)
        self.assertEqual(magic, "0123456789abcdef")

    def test_extract_magic_from_html_input(self):
        html = """
        <html>
        <head><title>Firewall Authentication</title></head>
        <body>
            <form action="/" method="post">
                <input type="hidden" name="4Tredir" value="http://connectivity-check.ubuntu.com/">
                <input type="hidden" name="magic" value="abcdef0123456789">
                <input type="text" name="username">
                <input type="password" name="password">
                <input type="submit" value="Continue">
            </form>
        </body>
        </html>
        """
        magic = self.client.extract_magic_token(html)
        self.assertEqual(magic, "abcdef0123456789")

    def test_extract_form_action(self):
        html = '<form action="/" method="post"><input type="hidden" name="magic" value="1234567890abcdef"></form>'
        action = self.client.extract_form_action(html)
        self.assertEqual(action, "/")

    def test_extract_redir_url(self):
        html = '<input type="hidden" name="4Tredir" value="http://connectivity-check.ubuntu.com/">'
        redir = self.client.extract_redir_url(html)
        self.assertEqual(redir, "http://connectivity-check.ubuntu.com/")

    def test_extract_portal_url(self):
        sample = '<html><body><script language="JavaScript">window.location="http://192.168.249.1:1000/fgtauth?064286da5717635f";</script></body></html>'
        url = self.client.extract_portal_url(sample)
        self.assertEqual(url, "http://192.168.249.1:1000/fgtauth?064286da5717635f")

    @patch("portal_client.requests.Session.get")
    def test_check_network_status_online_204(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_get.return_value = mock_resp

        status, _, _ = self.client.check_network_status()
        self.assertEqual(status, NetworkStatus.ONLINE)

    @patch("portal_client.requests.Session.get")
    def test_check_network_status_captive_script(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<html><body><script>window.location="http://192.168.249.1:1000/fgtauth?deadbeefcafe1234";</script></body></html>'
        mock_get.return_value = mock_resp

        status, portal_url, magic = self.client.check_network_status()
        self.assertEqual(status, NetworkStatus.CAPTIVE_PORTAL)
        self.assertEqual(magic, "deadbeefcafe1234")


if __name__ == "__main__":
    unittest.main()
