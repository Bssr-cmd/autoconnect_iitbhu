#!/usr/bin/env python3
"""
Captive Portal Client for IIT BHU Wi-Fi / LAN Network.
Detects captive portals, extracts dynamic magic tokens, handles authentication,
and maintains keep-alive session states.
"""

import re
import time
import logging
import urllib.parse
from enum import Enum
from typing import Optional, Tuple, Dict, Any

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    requests = None

# Configure logger
logger = logging.getLogger("autoconnect_iitbhu")

class NetworkStatus(Enum):
    ONLINE = "ONLINE"
    CAPTIVE_PORTAL = "CAPTIVE_PORTAL"
    OFFLINE = "OFFLINE"

class PortalClient:
    """Client to authenticate against IIT BHU Fortinet Captive Portal."""

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(
        self,
        portal_host: str = "192.168.249.1",
        portal_auth_url: str = "http://192.168.249.1:1000/fgtauth",
        detection_url: str = "http://detectportal.firefox.com/canonical.html",
        timeout: float = 6.0
    ):
        self.portal_host = portal_host
        self.portal_auth_url = portal_auth_url
        self.detection_url = detection_url
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self):
        """Create a requests session with sensible retries and timeouts."""
        if not requests:
            return None
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "close"
        })
        # Disable SSL verification warnings if captive portal uses self-signed cert
        requests.packages.urllib3.disable_warnings()
        return session

    def check_network_status(self) -> Tuple[NetworkStatus, Optional[str], Optional[str]]:
        """
        Check if internet is directly accessible, behind a captive portal, or offline.
        Returns (Status, portal_html_or_url, detected_magic).
        """
        if not self.session:
            self.session = self._create_session()

        probe_urls = [
            self.detection_url,
            "http://connectivitycheck.gstatic.com/generate_204",
            "http://www.google.com/generate_204",
            "http://clients3.google.com/generate_204"
        ]

        last_error = None
        for url in probe_urls:
            try:
                # Don't automatically follow redirect so we can inspect redirect location
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=False,
                    verify=False
                )

                # Check HTTP 204 No Content -> Direct Internet Access
                if response.status_code == 204:
                    return NetworkStatus.ONLINE, None, None

                # Check Firefox detection expected response
                if response.status_code == 200 and "<title>Canonical" in response.text:
                    return NetworkStatus.ONLINE, None, None

                # Check Redirect (302/307) to captive portal
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_url = response.headers.get("Location", "")
                    logger.info(f"Detected redirect to captive portal: {redirect_url}")
                    magic = self.extract_magic_token(redirect_url)
                    return NetworkStatus.CAPTIVE_PORTAL, redirect_url, magic

                # If status 200 but contains portal HTML
                if response.status_code == 200:
                    html = response.text
                    magic = self.extract_magic_token(html)
                    if magic or "fgtauth" in html or self.portal_host in html or "Authentication Required" in html:
                        return NetworkStatus.CAPTIVE_PORTAL, html, magic
                    else:
                        # Got normal 200 response with other content -> assume online
                        return NetworkStatus.ONLINE, None, None

            except requests.exceptions.RequestException as e:
                last_error = e
                continue

        # If all probes failed, check if portal host is directly reachable
        try:
            portal_probe = self.session.get(
                f"http://{self.portal_host}:1000/fgtauth",
                timeout=3.0,
                verify=False
            )
            if portal_probe.status_code == 200:
                html = portal_probe.text
                magic = self.extract_magic_token(html)
                return NetworkStatus.CAPTIVE_PORTAL, html, magic
        except Exception:
            pass

        logger.debug(f"Probing failed with error: {last_error}")
        return NetworkStatus.OFFLINE, None, None

    def extract_magic_token(self, content_or_url: str) -> Optional[str]:
        """Extract the 16-character hexadecimal magic token from URL or HTML body."""
        if not content_or_url:
            return None

        # Try URL query parameter 'magic=...'
        match_url = re.search(r"[?&]magic=([0-9a-fA-F]{16})", content_or_url)
        if match_url:
            return match_url.group(1)

        # Try HTML input tag <input type="hidden" name="magic" value="...">
        match_input = re.search(r'name=["\']magic["\']\s+value=["\']([0-9a-fA-F]{16})["\']', content_or_url, re.I)
        if match_input:
            return match_input.group(1)

        match_input_rev = re.search(r'value=["\']([0-9a-fA-F]{16})["\']\s+name=["\']magic["\']', content_or_url, re.I)
        if match_input_rev:
            return match_input_rev.group(1)

        # General regex matching any 16-character hex token in portal page
        match_hex = re.search(r'\b([0-9a-fA-F]{16})\b', content_or_url)
        if match_hex:
            return match_hex.group(1)

        return None

    def fetch_portal_magic(self) -> Tuple[Optional[str], str]:
        """
        Fetch the live captive portal page to get the freshest magic token.
        Returns (magic_token, target_action_url).
        """
        target_url = self.portal_auth_url

        try:
            # 1. Try fetching detection URL to get redirected portal HTML
            resp = self.session.get(self.detection_url, timeout=self.timeout, allow_redirects=True, verify=False)
            magic = self.extract_magic_token(resp.url) or self.extract_magic_token(resp.text)
            if magic:
                # If redirected to a specific fgtauth endpoint, use that URL
                if "fgtauth" in resp.url:
                    target_url = resp.url.split("?")[0]
                return magic, target_url
        except Exception as e:
            logger.debug(f"Direct detection fetch failed: {e}")

        # 2. Try fetching the portal host directly
        for direct_url in [
            f"http://{self.portal_host}:1000/fgtauth",
            f"https://{self.portal_host}:1003/fgtauth",
            f"http://{self.portal_host}/"
        ]:
            try:
                resp = self.session.get(direct_url, timeout=self.timeout, verify=False)
                magic = self.extract_magic_token(resp.text)
                if magic:
                    return magic, direct_url
            except Exception:
                continue

        return None, target_url

    def login(self, username: str, password: str, magic: Optional[str] = None) -> Tuple[bool, str]:
        """
        Perform captive portal login with username, password, and magic token.
        Returns (is_success, status_message).
        """
        if not username or not password:
            return False, "Missing username or password"

        target_url = self.portal_auth_url

        # If magic token not provided, fetch fresh from portal
        if not magic:
            magic, target_url = self.fetch_portal_magic()
            if not magic:
                return False, "Failed to extract captive portal 'magic' token (Gateway unreachable or already online)"

        payload = {
            "4Tredir": "http://detectportal.firefox.com/canonical.html",
            "magic": magic,
            "username": username,
            "password": password
        }

        logger.info(f"Submitting credentials to {target_url} with magic={magic}...")

        try:
            response = self.session.post(
                target_url,
                data=payload,
                timeout=self.timeout,
                allow_redirects=True,
                verify=False
            )

            # Check response indicators
            resp_text = response.text
            if "authentication_failed" in resp_text.lower() or "invalid username" in resp_text.lower():
                return False, "Invalid username or password"

            # Allow a short moment for firewall to update state
            time.sleep(1.0)

            # Verify connectivity
            status, _, _ = self.check_network_status()
            if status == NetworkStatus.ONLINE:
                return True, "Login successful! Internet is now active."
            elif status == NetworkStatus.CAPTIVE_PORTAL:
                return False, "Authentication submitted, but network is still locked in captive portal."
            else:
                return True, f"Login request sent (HTTP {response.status_code})."

        except requests.exceptions.RequestException as e:
            return False, f"Connection error during login: {e}"

    def keep_alive_ping(self) -> bool:
        """Send a lightweight ping to maintain session activity."""
        try:
            resp = self.session.get(self.detection_url, timeout=4.0, verify=False)
            return resp.status_code in (200, 204)
        except Exception:
            return False
