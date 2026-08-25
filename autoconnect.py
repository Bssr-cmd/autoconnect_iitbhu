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
from datetime import datetime
from config import ConfigManager
from portal_client import PortalClient, NetworkStatus
from notifier import send_notification

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("autoconnect_iitbhu")

class AutoConnectDaemon:
    """Daemon process that continuously monitors network and auto-logs in."""

    def __init__(self, config: ConfigManager, verbose: bool = False):
        self.config = config
        self.running = True
        self.last_login_time = None
        self.last_keepalive_time = 0
        
        if verbose:
            logger.setLevel(logging.DEBUG)

        self.client = PortalClient(
            portal_host=self.config.get("portal_host", "192.168.249.1"),
            portal_auth_url=self.config.get("portal_auth_url", "http://192.168.249.1:1000/fgtauth"),
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

    def run_single_login(self) -> bool:
        """Run a single manual login attempt."""
        if not self.config.is_configured():
            logger.error("No credentials configured. Run 'python3 autoconnect.py --configure' first.")
            return False

        username = self.config.get("username")
        password = self.config.get("password")

        logger.info(f"Initiating login check for user: {username}...")
        status, _, magic = self.client.check_network_status()

        if status == NetworkStatus.ONLINE:
            logger.info("[✓] Internet is already active and online! No login needed.")
            return True

        logger.info("[*] Captive portal detected. Attempting authentication...")
        success, msg = self.client.login(username=username, password=password, magic=magic)

        if success:
            logger.info(f"[✓] {msg}")
            self.notify_user("Wi-Fi Connected", f"Successfully logged into IIT BHU Wi-Fi ({username})")
            return True
        else:
            logger.error(f"[✗] Login failed: {msg}")
            return False

    def run_status_check(self):
        """Check current network status."""
        logger.info("Checking network connectivity...")
        status, info, magic = self.client.check_network_status()

        print("\n" + "=" * 50)
        print("  IIT BHU Network Status Check")
        print("=" * 50)
        print(f"Status       : {status.value}")
        print(f"Portal Host  : {self.config.get('portal_host')}")
        print(f"Configured   : {'Yes (' + self.config.get('username') + ')' if self.config.is_configured() else 'No'}")
        if magic:
            print(f"Portal Magic : {magic}")
        if info:
            print(f"Details      : {info[:100]}...")
        print("=" * 50 + "\n")

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
                status, _, magic = self.client.check_network_status()

                if status == NetworkStatus.CAPTIVE_PORTAL:
                    logger.warning("[!] Captive portal detected! Authenticating...")
                    success, msg = self.client.login(username=username, password=password, magic=magic)

                    if success:
                        logger.info(f"[✓] {msg}")
                        self.last_login_time = datetime.now()
                        self.last_keepalive_time = time.time()
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
                    # Perform periodic keep-alive
                    if now - self.last_keepalive_time >= keepalive_interval:
                        logger.debug("Sending session keep-alive ping...")
                        self.client.keep_alive_ping()
                        self.last_keepalive_time = now

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
  python3 autoconnect.py --configure       # Set username and password
  python3 autoconnect.py --login           # Test login immediately
  python3 autoconnect.py --status          # Check connectivity status
  python3 autoconnect.py --daemon          # Run background auto-login daemon
        """
    )
    parser.add_argument("-c", "--configure", action="store_true", help="Configure username, password, and settings")
    parser.add_argument("-l", "--login", action="store_true", help="Perform immediate one-time login attempt")
    parser.add_argument("-s", "--status", action="store_true", help="Check current network & captive portal status")
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
