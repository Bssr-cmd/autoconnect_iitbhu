#!/usr/bin/env python3
"""
Configuration Manager for IIT BHU Wi-Fi Auto-Connect.
Handles secure storage and retrieval of credentials and settings.
"""

import json
import os
import sys
import stat
import base64
import getpass
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "autoconnect_iitbhu"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"

DEFAULT_SETTINGS = {
    "username": "",
    "password": "",
    "portal_host": "192.168.249.1",
    "portal_auth_url": "http://192.168.249.1:1000/fgtauth",
    "detection_url": "http://detectportal.firefox.com/canonical.html",
    "fallback_detection_url": "http://connectivitycheck.gstatic.com/generate_204",
    "check_interval_seconds": 20,
    "keepalive_interval_seconds": 300,
    "enable_notifications": True,
    "timeout_seconds": 6,
    "auto_retry_max": 3,
}

# Simple obfuscation layer for at-rest storage
_OBFUSCATION_KEY = 0x5A

def _obfuscate(text: str) -> str:
    """Simple obfuscation so password is not stored in raw plaintext."""
    if not text:
        return ""
    bytes_data = text.encode("utf-8")
    obf_bytes = bytes([b ^ _OBFUSCATION_KEY for b in bytes_data])
    return "enc:" + base64.b64encode(obf_bytes).decode("ascii")

def _deobfuscate(text: str) -> str:
    """De-obfuscate stored password."""
    if not text:
        return ""
    if text.startswith("enc:"):
        try:
            b64_data = text[4:]
            raw_bytes = base64.b64decode(b64_data.encode("ascii"))
            orig_bytes = bytes([b ^ _OBFUSCATION_KEY for b in raw_bytes])
            return orig_bytes.decode("utf-8")
        except Exception:
            return text
    return text

class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or DEFAULT_CONFIG_FILE
        self.config_dir = self.config_file.parent
        self.data: Dict[str, Any] = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self) -> bool:
        """Load configuration from disk."""
        if not self.config_file.exists():
            return False
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                self.data.update(saved)
                # Deobfuscate password if needed
                if "password" in self.data:
                    self.data["password"] = _deobfuscate(self.data["password"])
                return True
        except Exception as e:
            print(f"[!] Warning: Failed to load config from {self.config_file}: {e}", file=sys.stderr)
            return False

    def save(self) -> bool:
        """Save configuration to disk with strict permissions (0600)."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            # Ensure directory permissions 0700
            try:
                os.chmod(self.config_dir, stat.S_IRWXU)
            except Exception:
                pass

            to_save = self.data.copy()
            if to_save.get("password"):
                to_save["password"] = _obfuscate(to_save["password"])

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=2)

            # Ensure file permissions 0600 (owner read/write only)
            try:
                os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass

            return True
        except Exception as e:
            print(f"[!] Error: Failed to save config to {self.config_file}: {e}", file=sys.stderr)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self.data[key] = value

    def is_configured(self) -> bool:
        """Check if essential credentials are set."""
        return bool(self.data.get("username") and self.data.get("password"))

    def interactive_configure(self) -> bool:
        """Interactive setup CLI prompt for the user."""
        print("=" * 60)
        print("  IIT BHU Wi-Fi Auto-Connect Configuration Setup")
        print("=" * 60)
        
        current_user = self.get("username", "")
        if current_user:
            print(f"Current Username / Roll No: {current_user}")
            change = input("Do you want to update credentials? [Y/n]: ").strip().lower()
            if change == 'n':
                return True

        username = input("Enter your IIT BHU Username / Roll No: ").strip()
        while not username:
            print("Username cannot be empty.")
            username = input("Enter your IIT BHU Username / Roll No: ").strip()

        password = getpass.getpass("Enter your Wi-Fi Password: ").strip()
        while not password:
            print("Password cannot be empty.")
            password = getpass.getpass("Enter your Wi-Fi Password: ").strip()

        portal_host = input(f"Captive Portal Host [{self.get('portal_host')}]: ").strip()
        if portal_host:
            self.set("portal_host", portal_host)
            self.set("portal_auth_url", f"http://{portal_host}:1000/fgtauth")

        notif_input = input(f"Enable Desktop Notifications? (y/n) [y]: ").strip().lower()
        enable_notif = notif_input != 'n'

        self.set("username", username)
        self.set("password", password)
        self.set("enable_notifications", enable_notif)

        if self.save():
            print(f"\n[+] Configuration saved successfully to: {self.config_file}")
            return True
        else:
            print("\n[-] Failed to save configuration.")
            return False
