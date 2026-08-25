#!/usr/bin/env python3
"""
Unit tests for IIT BHU Wi-Fi Auto-Connect.
Tests configuration management, token parsing, and network logic.
"""

import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import project modules
from config import ConfigManager, _obfuscate, _deobfuscate
from portal_client import PortalClient, NetworkStatus

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
        self.config.set("username", "21074012")
        self.config.set("password", "TestPassword99")
        self.assertTrue(self.config.save())

        # Load fresh
        loaded = ConfigManager(config_file=self.config_path)
        self.assertEqual(loaded.get("username"), "21074012")
        self.assertEqual(loaded.get("password"), "TestPassword99")
        self.assertTrue(loaded.is_configured())


class TestPortalClient(unittest.TestCase):
    """Test token parsing and captive portal workflows."""

    def setUp(self):
        self.client = PortalClient()

    def test_extract_magic_from_url(self):
        url = "http://192.168.249.1:1000/fgtauth?magic=0123456789abcdef&4Tredir=http://google.com"
        magic = self.client.extract_magic_token(url)
        self.assertEqual(magic, "0123456789abcdef")

    def test_extract_magic_from_html_input(self):
        html = """
        <html>
        <head><title>Authentication Required</title></head>
        <body>
            <form action="http://192.168.249.1:1000/fgtauth" method="post">
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

    def test_extract_magic_from_general_hex(self):
        sample = 'Some random portal text with token feedcafe12345678 inside'
        magic = self.client.extract_magic_token(sample)
        self.assertEqual(magic, "feedcafe12345678")

    @patch("portal_client.requests.Session.get")
    def test_check_network_status_online_204(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_get.return_value = mock_resp

        status, _, _ = self.client.check_network_status()
        self.assertEqual(status, NetworkStatus.ONLINE)

    @patch("portal_client.requests.Session.get")
    def test_check_network_status_captive_redirect(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.headers = {"Location": "http://192.168.249.1:1000/fgtauth?magic=deadbeefcafe1234"}
        mock_get.return_value = mock_resp

        status, redirect_url, magic = self.client.check_network_status()
        self.assertEqual(status, NetworkStatus.CAPTIVE_PORTAL)
        self.assertEqual(magic, "deadbeefcafe1234")


if __name__ == "__main__":
    unittest.main()
