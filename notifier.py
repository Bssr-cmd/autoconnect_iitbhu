#!/usr/bin/env python3
"""
Cross-platform Desktop Notification module.
Sends notifications without blocking the main event loop.
"""

import os
import sys
import platform
import subprocess
import shutil

def send_notification(title: str, message: str, app_name: str = "IIT BHU AutoConnect") -> bool:
    """Send a non-blocking desktop notification across Linux, macOS, and Windows."""
    system = platform.system().lower()

    try:
        if system == "linux":
            # Check for notify-send
            if shutil.which("notify-send"):
                subprocess.Popen(
                    ["notify-send", "-a", app_name, "-i", "network-wireless", title, message],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            # Check for kdialog (KDE)
            elif shutil.which("kdialog"):
                subprocess.Popen(
                    ["kdialog", "--title", f"{app_name}: {title}", "--passivepopup", message, "5"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True

        elif system == "darwin":  # macOS
            script = f'display notification "{message}" with title "{title}" subtitle "{app_name}"'
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True

        elif system == "windows":
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $template = @"
            <toast>
                <visual>
                    <binding template="ToastText02">
                        <text id="1">{title}</text>
                        <text id="2">{message}</text>
                    </binding>
                </visual>
            </toast>
"@
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app_name}").Show($toast)
            """
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True

    except Exception:
        # Silently fail notification without crashing core connection logic
        pass

    return False
