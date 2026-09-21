#!/usr/bin/env python3
"""
IIT BHU Wi-Fi Auto-Connect CLI & Background Service
Automates campus captive portal authentication and session keep-alive.
"""

import sys
import time
import signal
import logging
import argparse
import subprocess
from datetime import datetime
from typing import Optional
from config import ConfigManager, StateManager
from portal_client import PortalClient, NetworkStatus
from notifier import send_notification

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("autoconnect_iitbhu")


def get_service_status() -> str:
    """Check status of system background service."""
    if sys.platform.startswith("linux"):
        try:
            res = subprocess.run(
                ["systemctl", "--user", "is-active", "autoconnect-iitbhu.service"],
                capture_output=True, text=True, timeout=2
            )
            is_active = res.stdout.strip()
            if is_active == "active":
                t_res = subprocess.run(
                    ["systemctl", "--user", "show", "autoconnect-iitbhu.service", "--property=ActiveEnterTimestamp"],
                    capture_output=True, text=True, timeout=2
                )
                ts = t_res.stdout.strip().replace("ActiveEnterTimestamp=", "")
                return f"active (running since {ts})" if ts else "active (running)"
            return is_active or "inactive"
        except Exception:
            return "unknown"
    return "N/A"


class AutoConnectDaemon:
    """Daemon process that continuously monitors network and auto-logs in."""

    def __init__(self, config: ConfigManager, verbose: bool = False):
        self.config = config
        self.state = StateManager()
        self.running = True
        self.last_login_time = None
        self.last_keepalive_time = 0
        
        if verbose:
            logger.setLevel(logging.DEBUG)

        self.client = PortalClient(
            portal_host=self.config.get("portal_host", "192.168.249.1"),
            portal_auth_url=self.config.get("portal_auth_url", "http://192.168.249.1:1000/"),
            detection_url=self.config.get("detection_url", "http://detectportal.firefox.com/canonical.html"),
            timeout=float(self.config.get("timeout_seconds", 6))
        )

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info("Termination signal received. Shutting down daemon gracefully...")
        self.running = False

    def notify_user(self, title: str, message: str):
        if self.config.get("enable_notifications", True):
            send_notification(title, message)

    def _find_last_login_from_journal(self) -> Optional[str]:
        """Query systemd journal for the most recent login or service startup event."""
        if not sys.platform.startswith("linux"):
            return None
        try:
            res = subprocess.run(
                ["journalctl", "--user", "-u", "autoconnect-iitbhu.service", "-o", "short-iso", "--no-pager"],
                capture_output=True, text=True, timeout=3
            )
            for line in reversed(res.stdout.splitlines()):
                if any(k in line for k in ["[✓]", "Auto-connected", "Daemon Started", "Keepalive session"]):
                    return line
        except Exception:
            pass
        return None

    def run_single_login(self) -> bool:
        """Run a single manual login attempt."""
        if not self.config.is_configured():
            logger.error("No credentials configured. Run 'python3 autoconnect.py --configure' first.")
            return False

        username = self.config.get("username")
        password = self.config.get("password")

        logger.info(f"Initiating login check for user: {username}...")
        status, info, magic = self.client.check_network_status()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if status == NetworkStatus.ONLINE:
            logger.info("[✓] Internet is already active and online! No login needed.")
            self.state.update(
                last_verified_online=now_str,
                current_status="ONLINE",
                campus_interface=self.client.current_bound_ip or "auto"
            )
            return True

        logger.info("[*] Captive portal detected. Attempting authentication...")
        success, msg = self.client.login(username=username, password=password, magic=magic, portal_context=info)

        if success:
            logger.info(f"[✓] {msg}")
            self.state.update(
                last_login_time=now_str,
                last_verified_online=now_str,
                last_login_user=username,
                last_login_message=msg,
                current_status="ONLINE",
                campus_interface=self.client.current_bound_ip or "auto"
            )
            self.notify_user("Wi-Fi Connected", f"Successfully logged into IIT BHU Wi-Fi ({username})")
            return True
        else:
            logger.error(f"[✗] Login failed: {msg}")
            return False

    def run_status_check(self):
        """Check current network status and connection history."""
        logger.info("Checking network connectivity...")
        status, info, magic = self.client.check_network_status()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.state.update(
            last_checked=now_str,
            current_status=status.value,
            campus_interface=self.client.current_bound_ip or "auto"
        )

        last_login = self.state.get("last_login_time")
        if not last_login:
            journal_line = self._find_last_login_from_journal()
            if journal_line:
                last_login = f"{journal_line.split()[0]} (from service journal)"

        svc_status = get_service_status()

        print("\n" + "=" * 55)
        print("  IIT BHU Network Status Check")
        print("=" * 55)
        print(f"Status              : {status.value}")
        print(f"Campus Interface IP : {self.client.current_bound_ip or 'Default (all)'}")
        print(f"Last Login / Event  : {last_login or 'Session active / No recent login needed'}")
        if status == NetworkStatus.ONLINE:
            print(f"Last Verified Online: {now_str}")
        print(f"Background Service  : {svc_status}")
        print(f"Portal Host         : {self.config.get('portal_host')}")
        print(f"Configured          : {'Yes (' + self.config.get('username') + ')' if self.config.is_configured() else 'No'}")
        if magic:
            print(f"Portal Magic        : {magic}")
        if info:
            print(f"Details             : {info[:80]}...")
        print("=" * 55 + "\n")

    def run_last_connected(self):
        """Display when the client last authenticated or verified online."""
        last_login = self.state.get("last_login_time")
        last_online = self.state.get("last_verified_online")
        last_user = self.state.get("last_login_user", self.config.get("username", "Unknown"))
        last_ip = self.state.get("campus_interface", self.client.current_bound_ip or "Auto")
        last_msg = self.state.get("last_login_message", "N/A")
        svc_status = get_service_status()

        if not last_login:
            journal_line = self._find_last_login_from_journal()
            if journal_line:
                last_login = journal_line

        print("\n" + "=" * 55)
        print("  IIT BHU AutoConnect - Connection Info")
        print("=" * 55)
        print(f"Last Login Event    : {last_login or 'Session was already active / No recent login needed'}")
        if last_online:
            print(f"Last Verified Online: {last_online}")
        if last_msg and last_msg != "N/A":
            print(f"Login Message       : {last_msg}")
        print(f"User / Roll No      : {last_user}")
        print(f"Campus Interface IP : {last_ip}")
        print(f"Background Service  : {svc_status}")
        print("=" * 55)
        print("Tip: Run 'python3 autoconnect.py --logs' to see detailed service logs.\n")

    def run_show_logs(self, lines: int = 25):
        """Display recent background service logs from systemd journal."""
        if sys.platform.startswith("linux"):
            print(f"\n[*] Recent {lines} lines from autoconnect-iitbhu.service:")
            print("-" * 60)
            try:
                subprocess.run(
                    ["journalctl", "--user", "-u", "autoconnect-iitbhu.service", "-n", str(lines), "--no-pager"],
                    check=False
                )
            except Exception as e:
                print(f"Error running journalctl: {e}")
            print("-" * 60 + "\n")
        else:
            print("Log viewer via journalctl is available on Linux systemd.")

    def run_daemon(self):
        """Continuous background monitoring and auto-login loop."""
        if not self.config.is_configured():
            logger.error("Credentials not configured. Please run 'python3 autoconnect.py --configure' first.")
            sys.exit(1)

        check_interval = int(self.config.get("check_interval_seconds", 20))
        keepalive_interval = int(self.config.get("keepalive_interval_seconds", 300))
        username = self.config.get("username")
        password = self.config.get("password")

        logger.info("=" * 60)
        logger.info(" IIT BHU Wi-Fi Auto-Connect Daemon Started")
        logger.info(f" User: {username} | Check Interval: {check_interval}s | Keep-Alive: {keepalive_interval}s")
        logger.info("=" * 60)

        consecutive_failures = 0

        while self.running:
            try:
                status, info, magic = self.client.check_network_status()

                if status == NetworkStatus.CAPTIVE_PORTAL:
                    logger.warning("[!] Captive portal detected! Authenticating...")
                    success, msg = self.client.login(username=username, password=password, magic=magic, portal_context=info)

                    if success:
                        logger.info(f"[✓] {msg}")
                        self.last_login_time = datetime.now()
                        self.last_keepalive_time = time.time()
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self.state.update(
                            last_login_time=now_str,
                            last_verified_online=now_str,
                            last_login_user=username,
                            last_login_message=msg,
                            current_status="ONLINE",
                            campus_interface=self.client.current_bound_ip or "auto"
                        )
                        consecutive_failures = 0
                        self.notify_user("Wi-Fi Connected", f"Auto-connected to IIT BHU network as {username}")
                    else:
                        consecutive_failures += 1
                        logger.error(f"[✗] Login attempt {consecutive_failures} failed: {msg}")
                        if consecutive_failures >= 5:
                            # Back off slightly on repeated authentication errors
                            time.sleep(15)

                elif status == NetworkStatus.ONLINE:
                    consecutive_failures = 0
                    now = time.time()
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.state.update(
                        last_verified_online=now_str,
                        current_status="ONLINE",
                        campus_interface=self.client.current_bound_ip or "auto"
                    )
                    # Perform periodic keep-alive
                    if now - self.last_keepalive_time >= keepalive_interval:
                        logger.debug("Sending session keep-alive ping...")
                        self.client.keep_alive_ping()
                        self.last_keepalive_time = now
                        self.state.update(last_keepalive_time=now_str)

                elif status == NetworkStatus.OFFLINE:
                    logger.debug("Network interface is offline or Wi-Fi is disconnected. Waiting...")

            except Exception as e:
                logger.error(f"Unexpected error in daemon loop: {e}", exc_info=True)

            # Sleep in 1-second increments for responsive SIGINT handling
            for _ in range(check_interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("IIT BHU Wi-Fi Auto-Connect Daemon stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="IIT BHU Wi-Fi / LAN Auto-Connect Client & Background Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 autoconnect.py --status          # Check connectivity status & connection history
  python3 autoconnect.py --last-connected # Show when client last connected
  python3 autoconnect.py --logs            # View recent service logs
  python3 autoconnect.py --login           # Test login immediately
  python3 autoconnect.py --daemon          # Run background auto-login daemon
        """
    )
    parser.add_argument("-c", "--configure", action="store_true", help="Configure username, password, and settings")
    parser.add_argument("-l", "--login", action="store_true", help="Perform immediate one-time login attempt")
    parser.add_argument("-s", "--status", action="store_true", help="Check current network & captive portal status")
    parser.add_argument("--last-connected", action="store_true", help="Show when the client last connected / authenticated")
    parser.add_argument("--logs", action="store_true", help="View recent background service connection logs")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run background monitoring daemon")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    config = ConfigManager()

    if args.configure:
        config.interactive_configure()
        return

    daemon = AutoConnectDaemon(config, verbose=args.verbose)

    if args.status:
        daemon.run_status_check()
    elif args.last_connected:
        daemon.run_last_connected()
    elif args.logs:
        daemon.run_show_logs()
    elif args.login:
        daemon.run_single_login()
    elif args.daemon:
        daemon.run_daemon()
    else:
        # If no arguments provided and not configured, launch configuration
        if not config.is_configured():
            print("[!] No credentials found. Starting initial setup...\n")
            if config.interactive_configure():
                print("\n[+] Setup complete! Starting auto-connect daemon...\n")
                daemon.run_daemon()
        else:
            # Default to running daemon
            daemon.run_daemon()

if __name__ == "__main__":
    main()
