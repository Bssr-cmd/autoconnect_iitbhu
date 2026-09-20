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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        # Disable SSL verification warnings if captive portal uses self-signed cert
        requests.packages.urllib3.disable_warnings()
        return session

    def extract_portal_url(self, content_or_url: Optional[str]) -> Optional[str]:
        """Extract redirected URL or form action from portal response."""
        if not content_or_url:
            return None

        # If it is already a full URL
        if content_or_url.startswith(("http://", "https://")):
            return content_or_url.split("?")[0]

        # window.location="https://..."
        match_loc = re.search(r'window\.location\s*=\s*["\'](https?://[^"\']+)["\']', content_or_url, re.I)
        if match_loc:
            return match_loc.group(1).split("?")[0]

        # <form action="..."
        match_form = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', content_or_url, re.I)
        if match_form:
            action = match_form.group(1)
            if action.startswith(("http://", "https://")):
                return action.split("?")[0]
            elif action.startswith("/"):
                return f"https://{self.portal_host}:1000{action}"

        return None

    def check_network_status(self) -> Tuple[NetworkStatus, Optional[str], Optional[str]]:
        """
        Check if internet is directly accessible, behind a captive portal, or offline.
        Returns (Status, portal_html_or_url, detected_magic).
        """
        if not self.session:
            self.session = self._create_session()

        probe_urls = [
            "http://connectivitycheck.gstatic.com/generate_204",
            "http://clients3.google.com/generate_204",
            "http://www.google.com/generate_204",
            self.detection_url
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

                # Check Redirect (301/302/303/307/308) to captive portal
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_url = response.headers.get("Location", "")
                    logger.info(f"Detected redirect to captive portal: {redirect_url}")
                    magic = self.extract_magic_token(redirect_url)
                    return NetworkStatus.CAPTIVE_PORTAL, redirect_url, magic

                # If status 200: check if it's captive portal or normal content
                if response.status_code == 200:
                    html = response.text
                    magic = self.extract_magic_token(html)
                    portal_url = self.extract_portal_url(html)

                    if magic or portal_url or "fgtauth" in html or self.portal_host in html or "Authentication Required" in html:
                        return NetworkStatus.CAPTIVE_PORTAL, (portal_url or html), magic
                    elif "<title>Canonical" in html:
                        return NetworkStatus.ONLINE, None, None
                    else:
                        # Got 200 without portal signatures -> assume online
                        return NetworkStatus.ONLINE, None, None

            except requests.exceptions.RequestException as e:
                last_error = e
                continue

        # If all standard probes failed, check if portal host is reachable on HTTPS or HTTP
        for probe_scheme, probe_port in [("https", 1000), ("https", 1003), ("http", 1000)]:
            try:
                portal_probe = self.session.get(
                    f"{probe_scheme}://{self.portal_host}:{probe_port}/fgtauth",
                    timeout=2.0,
                    verify=False
                )
                if portal_probe.status_code in (200, 302):
                    html = portal_probe.text
                    magic = self.extract_magic_token(html) or self.extract_magic_token(portal_probe.url)
                    portal_url = self.extract_portal_url(html) or portal_probe.url
                    return NetworkStatus.CAPTIVE_PORTAL, (portal_url or html), magic
            except Exception:
                pass

        logger.debug(f"Probing failed with error: {last_error}")
        return NetworkStatus.OFFLINE, None, None

    def extract_magic_token(self, content_or_url: str) -> Optional[str]:
        """Extract the 16-character hexadecimal magic token from URL or HTML body."""
        if not content_or_url:
            return None

        # 1. Try URL query parameter 'magic=...' or path 'fgtauth?...'
        match_url = re.search(r"[?&]magic=([0-9a-fA-F]{16})", content_or_url)
        if match_url:
            return match_url.group(1)

        match_fgtauth = re.search(r"fgtauth\?([0-9a-fA-F]{16})", content_or_url)
        if match_fgtauth:
            return match_fgtauth.group(1)

        # 2. Try HTML input tag <input type="hidden" name="magic" value="...">
        match_input = re.search(r'name=["\']magic["\']\s+value=["\']([0-9a-fA-F]{16})["\']', content_or_url, re.I)
        if match_input:
            return match_input.group(1)

        match_input_rev = re.search(r'value=["\']([0-9a-fA-F]{16})["\']\s+name=["\']magic["\']', content_or_url, re.I)
        if match_input_rev:
            return match_input_rev.group(1)

        # 3. General regex matching any 16-character hex token in portal page
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

        # 1. Try probing generate_204 or detection URL to get redirected portal HTML
        for probe_url in [
            "http://connectivitycheck.gstatic.com/generate_204",
            "http://clients3.google.com/generate_204",
            self.detection_url
        ]:
            try:
                resp = self.session.get(probe_url, timeout=self.timeout, allow_redirects=True, verify=False)
                magic = self.extract_magic_token(resp.url) or self.extract_magic_token(resp.text)
                if magic:
                    action_url = self.extract_portal_url(resp.text) or (resp.url.split("?")[0] if "fgtauth" in resp.url else target_url)
                    return magic, action_url
            except Exception as e:
                logger.debug(f"Direct detection fetch failed for {probe_url}: {e}")

        # 2. Try fetching candidate portal endpoints directly
        for direct_url in [
            f"https://{self.portal_host}:1000/fgtauth",
            f"https://{self.portal_host}:1000/",
            f"https://{self.portal_host}:1003/fgtauth",
            f"http://{self.portal_host}:1000/fgtauth",
            f"http://{self.portal_host}/"
        ]:
            try:
                resp = self.session.get(direct_url, timeout=self.timeout, verify=False)
                magic = self.extract_magic_token(resp.text) or self.extract_magic_token(resp.url)
                if magic:
                    return magic, direct_url
            except Exception:
                continue

        return None, target_url

    def login(
        self,
        username: str,
        password: str,
        magic: Optional[str] = None,
        portal_context: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Perform captive portal login with username, password, and magic token.
        Cascades through candidate endpoints with proper HTTPS/TLS and headers.
        Returns (is_success, status_message).
        """
        if not username or not password:
            return False, "Missing username or password"

        detected_url = self.extract_portal_url(portal_context) if portal_context else None

        # If magic token not provided, fetch fresh from portal
        if not magic:
            magic, fetched_url = self.fetch_portal_magic()
            if not detected_url and fetched_url:
                detected_url = fetched_url

            if not magic:
                return False, "Failed to extract captive portal 'magic' token (Gateway unreachable or already online)"

        # Build candidate URLs in order of preference
        candidate_urls = []
        if detected_url:
            candidate_urls.append(detected_url)
            if detected_url.endswith("/fgtauth"):
                candidate_urls.append(detected_url.rsplit("/fgtauth", 1)[0] + "/")
            elif detected_url.endswith("/"):
                candidate_urls.append(detected_url + "fgtauth")

        standard_endpoints = [
            f"https://{self.portal_host}:1000/fgtauth",
            f"https://{self.portal_host}:1000/",
            f"https://{self.portal_host}:1003/fgtauth",
            f"https://{self.portal_host}:1003/",
            f"http://{self.portal_host}:1000/fgtauth",
            f"http://{self.portal_host}:1000/",
            self.portal_auth_url
        ]

        for ep in standard_endpoints:
            if ep and ep not in candidate_urls:
                candidate_urls.append(ep)

        payload = {
            "4Tredir": "http://connectivitycheck.gstatic.com/generate_204",
            "magic": magic,
            "username": username,
            "password": password,
            "submit": "Continue"
        }

        last_error = None

        for target_url in candidate_urls:
            parsed = urllib.parse.urlparse(target_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            referer = f"{target_url}?{magic}" if not target_url.endswith("/") else f"{origin}/fgtauth?{magic}"
            headers = {
                "Origin": origin,
                "Referer": referer,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            logger.info(f"Submitting credentials to {target_url} with magic={magic}...")

            try:
                response = self.session.post(
                    target_url,
                    data=payload,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=False
                )

                resp_text = response.text
                if "authentication_failed" in resp_text.lower() or "invalid username" in resp_text.lower():
                    return False, "Invalid username or password"

                # Allow a short moment for firewall to update state
                time.sleep(1.0)

                # Verify connectivity
                status, _, _ = self.check_network_status()
                if status == NetworkStatus.ONLINE:
                    return True, f"Login successful via {target_url}! Internet is now active."
                elif status == NetworkStatus.CAPTIVE_PORTAL:
                    logger.warning(f"Submitted to {target_url} but portal still active, trying next endpoint...")
                    continue
                else:
                    return True, f"Login request sent to {target_url} (HTTP {response.status_code})."

            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"Connection attempt to {target_url} failed: {e}")
                continue

        # Final verification
        time.sleep(1.5)
        status, _, _ = self.check_network_status()
        if status == NetworkStatus.ONLINE:
            return True, "Login successful! Internet is active."

        return False, f"All login attempts failed. Last error: {last_error}"

    def keep_alive_ping(self) -> bool:
        """Send a lightweight ping to maintain session activity."""
        try:
            resp = self.session.get("http://connectivitycheck.gstatic.com/generate_204", timeout=4.0, verify=False)
            return resp.status_code in (200, 204)
        except Exception:
            return False
