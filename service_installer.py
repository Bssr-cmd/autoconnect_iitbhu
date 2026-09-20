#!/usr/bin/env python3
"""
System Service Installer for IIT BHU Wi-Fi Auto-Connect.
Configures autoconnect to run silently in the background at startup.
Supports Linux (systemd & desktop autostart) and macOS (launchd).
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
AUTOCONNECT_SCRIPT = CURRENT_DIR / "autoconnect.py"

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SYSTEMD_SERVICE_FILE = SYSTEMD_USER_DIR / "autoconnect-iitbhu.service"

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_DESKTOP_FILE = AUTOSTART_DIR / "autoconnect-iitbhu.desktop"

LAUNCHD_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCHD_PLIST_FILE = LAUNCHD_DIR / "com.iitbhu.autoconnect.plist"


def install_linux_systemd() -> bool:
    """Install systemd user service for Linux."""
    print("[*] Setting up systemd user service...")
    try:
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)

        service_content = f"""[Unit]
Description=IIT BHU Wi-Fi Auto-Connect Background Service
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={PYTHON_EXE} {AUTOCONNECT_SCRIPT} --daemon
WorkingDirectory={CURRENT_DIR}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
        with open(SYSTEMD_SERVICE_FILE, "w", encoding="utf-8") as f:
            f.write(service_content)

        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "autoconnect-iitbhu.service"], check=True)
        subprocess.run(["systemctl", "--user", "restart", "autoconnect-iitbhu.service"], check=True)

        print("[✓] systemd user service installed and started successfully!")
        print("    Check status with: systemctl --user status autoconnect-iitbhu.service")
        return True
    except Exception as e:
        print(f"[-] systemd installation failed: {e}")
        return False


def install_linux_autostart() -> bool:
    """Install .desktop entry in ~/.config/autostart for desktop environments."""
    print("[*] Setting up Desktop Autostart entry...")
    try:
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=IIT BHU Wi-Fi Auto-Connect
Comment=Automatic background login for campus captive portal
Exec={PYTHON_EXE} {AUTOCONNECT_SCRIPT} --daemon
Path={CURRENT_DIR}
Terminal=false
Categories=Network;Utility;
X-GNOME-Autostart-enabled=true
"""
        with open(AUTOSTART_DESKTOP_FILE, "w", encoding="utf-8") as f:
            f.write(desktop_content)

        print("[✓] Desktop autostart entry created successfully!")
        return True
    except Exception as e:
        print(f"[-] Desktop autostart setup failed: {e}")
        return False


def install_macos_launchd() -> bool:
    """Install launchd agent for macOS."""
    print("[*] Setting up macOS launchd agent...")
    try:
        LAUNCHD_DIR.mkdir(parents=True, exist_ok=True)
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.iitbhu.autoconnect</string>
    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON_EXE}</string>
        <string>{AUTOCONNECT_SCRIPT}</string>
        <string>--daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{CURRENT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
        with open(LAUNCHD_PLIST_FILE, "w", encoding="utf-8") as f:
            f.write(plist_content)

        subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST_FILE)], stderr=subprocess.DEVNULL)
        subprocess.run(["launchctl", "load", str(LAUNCHD_PLIST_FILE)], check=True)

        print("[✓] macOS LaunchAgent installed and loaded successfully!")
        return True
    except Exception as e:
        print(f"[-] macOS launchd installation failed: {e}")
        return False


def uninstall():
    """Remove background services."""
    system = platform.system().lower()
    print(f"[*] Removing background services on {system}...")

    if system == "linux":
        if SYSTEMD_SERVICE_FILE.exists():
            try:
                subprocess.run(["systemctl", "--user", "stop", "autoconnect-iitbhu.service"])
                subprocess.run(["systemctl", "--user", "disable", "autoconnect-iitbhu.service"])
                SYSTEMD_SERVICE_FILE.unlink(missing_ok=True)
                subprocess.run(["systemctl", "--user", "daemon-reload"])
                print("[✓] systemd service removed.")
            except Exception as e:
                print(f"[-] Error removing systemd service: {e}")

        if AUTOSTART_DESKTOP_FILE.exists():
            AUTOSTART_DESKTOP_FILE.unlink(missing_ok=True)
            print("[✓] Autostart desktop file removed.")

    elif system == "darwin":
        if LAUNCHD_PLIST_FILE.exists():
            try:
                subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST_FILE)])
                LAUNCHD_PLIST_FILE.unlink(missing_ok=True)
                print("[✓] macOS LaunchAgent removed.")
            except Exception as e:
                print(f"[-] Error removing LaunchAgent: {e}")

    print("[✓] Uninstallation complete.")


def install():
    """Install appropriate service based on operating system."""
    system = platform.system().lower()
    print(f"[*] Detecting system platform: {system}")

    if system == "linux":
        # Prefer systemd user service if systemctl is available
        if subprocess.run(["which", "systemctl"], capture_output=True).returncode == 0:
            install_linux_systemd()
        else:
            install_linux_autostart()
    elif system == "darwin":
        install_macos_launchd()
    elif system == "windows":
        print("[*] On Windows, you can add a shortcut to autoconnect.py in your Startup folder:")
        print(f"    Press Win+R -> type 'shell:startup' -> create shortcut for:")
        print(f"    pythonw.exe {AUTOCONNECT_SCRIPT} --daemon")
    else:
        print(f"[-] Unsupported platform for automated service installation: {system}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--uninstall", "-u", "uninstall"):
        uninstall()
    else:
        install()
