#!/usr/bin/env python3
"""
Captive Portal Client for IIT BHU Wi-Fi / LAN Network.
Detects Fortinet captive portals, extracts dynamic magic tokens, handles authentication,
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
    from urllib3.poolmanager import PoolManager
except ImportError:
    requests = None

# Configure logger
logger = logging.getLogger("autoconnect_iitbhu")

class NetworkStatus(Enum):
    ONLINE = "ONLINE"
    CAPTIVE_PORTAL = "CAPTIVE_PORTAL"
    OFFLINE = "OFFLINE"


class SourceAddressAdapter(HTTPAdapter):
    """Binds outbound HTTP/HTTPS connections to a specific local source IP."""
    def __init__(self, source_ip: str, **kwargs):
        self.source_ip = source_ip
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["source_address"] = (self.source_ip, 0)
        self.poolmanager = PoolManager(*args, **kwargs)


def find_campus_interface_ip() -> Optional[str]:
    """
    Find local IP address assigned to the campus Wi-Fi or LAN connection.
    Prefers connections named 'IIT(BHU)' or Wi-Fi devices on 172.16-31.* campus subnets.
    """
    try:
        import subprocess
        # 1. Check nmcli for active IIT(BHU) or campus Wi-Fi connection
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
                stderr=subprocess.DEVNULL
            ).decode()
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 4 and parts[2] == "connected":
                    dev, dev_type, _, conn = parts[0], parts[1], parts[2], parts[3]
                    if "iit" in conn.lower() or dev_type in ("wifi", "wireless"):
                        ip_out = subprocess.check_output(
                            ["ip", "-br", "addr", "show", "dev", dev],
                            stderr=subprocess.DEVNULL
                        ).decode()
                        for ip_line in ip_out.splitlines():
                            items = ip_line.split()
                            if len(items) >= 3 and "/" in items[2]:
                                return items[2].split("/")[0]
        except Exception:
            pass

        # 2. Check for campus subnet 172.16.0.0/12 (172.16.* - 172.31.*)
        out = subprocess.check_output(["ip", "-br", "addr", "show"], stderr=subprocess.DEVNULL).decode()
        campus_ip = None
        for line in out.splitlines():
            items = line.split()
            if len(items) >= 3 and "/" in items[2]:
                ip = items[2].split("/")[0]
                if ip.startswith("172."):
                    try:
                        second = int(ip.split(".")[1])
                        if 16 <= second <= 31:
                            if items[0].startswith(("wl", "wifi")):
                                return ip
                            campus_ip = ip
                    except (ValueError, IndexError):
                        pass
        return campus_ip
    except Exception:
        return None


class PortalClient:
    """Client to authenticate against IIT BHU Fortinet Captive Portal."""

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

    def __init__(
        self,
        portal_host: str = "192.168.249.1",
        portal_auth_url: str = "http://192.168.249.1:1000/",
        detection_url: str = "http://connectivity-check.ubuntu.com/",
        timeout: float = 6.0
    ):
        self.portal_host = portal_host
        self.portal_auth_url = portal_auth_url
        self.detection_url = detection_url
        self.timeout = timeout
        self.current_bound_ip: Optional[str] = None
        self.last_keepalive_url: Optional[str] = None
        self.session = self._create_session()

    def _create_session(self):
        """Create a requests session bound to the campus network interface."""
        if not requests:
            return None

        session = requests.Session()
        session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        requests.packages.urllib3.disable_warnings()

        campus_ip = find_campus_interface_ip()
        self.current_bound_ip = campus_ip
        if campus_ip:
            logger.info(f"Binding captive portal traffic to campus interface IP: {campus_ip}")
            adapter = SourceAddressAdapter(campus_ip)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

        return session

    def _ensure_session(self):
        """Ensure session exists and is bound to current campus IP."""
        campus_ip = find_campus_interface_ip()
        if not self.session or campus_ip != self.current_bound_ip:
            self.session = self._create_session()

    def extract_form_action(self, html: Optional[str]) -> Optional[str]:
        """Extract the action URL attribute from an HTML <form> tag."""
        if not html:
            return None
        match = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', html, re.I)
        return match.group(1) if match else None

    def extract_redir_url(self, html: Optional[str]) -> Optional[str]:
        """Extract the 4Tredir parameter value from HTML inputs."""
        if not html:
            return None
        m1 = re.search(r'name=["\']4Tredir["\'][^>]*value=["\']([^"\']+)["\']', html, re.I)
        if m1:
            return m1.group(1)
        m2 = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']4Tredir["\']', html, re.I)
        return m2.group(1) if m2 else None

    def extract_portal_url(self, content_or_url: Optional[str]) -> Optional[str]:
        """Extract redirected URL from portal probe response."""
        if not content_or_url:
            return None

        if content_or_url.startswith(("http://", "https://")):
            return content_or_url

        # Match window.location="http://..."
        match_loc = re.search(r'window\.location\s*=\s*["\'](http[^"\']+)["\']', content_or_url, re.I)
        if match_loc:
            return match_loc.group(1)

        return None

    def extract_magic_token(self, content_or_url: Optional[str]) -> Optional[str]:
        """Extract the 16-character hexadecimal magic token from URL or HTML body."""
        if not content_or_url:
            return None

        # 1. Try HTML input tag <input type="hidden" name="magic" value="...">
        match_input = re.search(r'name=["\']magic["\'][^>]*value=["\']([0-9a-fA-F]{16})["\']', content_or_url, re.I)
        if match_input:
            return match_input.group(1)

        match_input_rev = re.search(r'value=["\']([0-9a-fA-F]{16})["\'][^>]*name=["\']magic["\']', content_or_url, re.I)
        if match_input_rev:
            return match_input_rev.group(1)

        # 2. Try URL query parameter 'magic=...' or 'fgtauth?...'
        match_url = re.search(r"[?&]magic=([0-9a-fA-F]{16})", content_or_url)
        if match_url:
            return match_url.group(1)

        match_fgtauth = re.search(r"fgtauth\?([0-9a-fA-F]{16})", content_or_url)
        if match_fgtauth:
            return match_fgtauth.group(1)

        # 3. General regex matching any 16-character hex token in portal page
        match_hex = re.search(r'\b([0-9a-fA-F]{16})\b', content_or_url)
        if match_hex:
            return match_hex.group(1)

        return None

    def check_network_status(self) -> Tuple[NetworkStatus, Optional[str], Optional[str]]:
        """
        Check if internet is directly accessible, behind a captive portal, or offline.
        Returns (Status, portal_html_or_url, detected_magic).
        """
        self._ensure_session()

        probe_urls = [
            self.detection_url,
            "http://connectivitycheck.gstatic.com/generate_204",
            "http://clients3.google.com/generate_204",
            "http://www.google.com/generate_204"
        ]

        last_error = None
        for url in probe_urls:
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=False,
                    verify=False
                )

                # HTTP 204 No Content -> Direct Internet Access
                if response.status_code == 204:
                    return NetworkStatus.ONLINE, None, None

                # HTTP 301/302/307 Redirect to captive portal
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_url = response.headers.get("Location", "")
                    logger.info(f"Detected redirect to captive portal: {redirect_url}")
                    magic = self.extract_magic_token(redirect_url)
                    return NetworkStatus.CAPTIVE_PORTAL, redirect_url, magic

                # HTTP 200: Check if it's captive portal script or normal web content
                if response.status_code == 200:
                    html = response.text
                    portal_url = self.extract_portal_url(html)
                    magic = self.extract_magic_token(html)

                    # Fortinet captive portal returns an HTML page containing window.location or fgtauth
                    if portal_url or magic or "fgtauth" in html or self.portal_host in html or "Authentication Required" in html:
                        return NetworkStatus.CAPTIVE_PORTAL, (portal_url or html), magic
                    else:
                        return NetworkStatus.ONLINE, None, None

            except requests.exceptions.RequestException as e:
                last_error = e
                continue

        # If all standard probes timed out/failed, check if portal host is directly reachable
        try:
            portal_probe = self.session.get(
                f"http://{self.portal_host}:1000/fgtauth",
                timeout=2.0,
                verify=False
            )
            if portal_probe.status_code in (200, 302):
                html = portal_probe.text
                magic = self.extract_magic_token(html) or self.extract_magic_token(portal_probe.url)
                return NetworkStatus.CAPTIVE_PORTAL, portal_probe.url, magic
        except Exception:
            pass

        logger.debug(f"Probing failed with error: {last_error}")
        return NetworkStatus.OFFLINE, None, None

    def fetch_portal_magic(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch the live captive portal page to get fresh token and URL.
        Returns (magic_token, portal_page_url).
        """
        for probe_url in [
            self.detection_url,
            "http://connectivitycheck.gstatic.com/generate_204",
            "http://clients3.google.com/generate_204"
        ]:
            try:
                resp = self.session.get(probe_url, timeout=self.timeout, allow_redirects=False, verify=False)
                portal_url = self.extract_portal_url(resp.headers.get("Location")) or self.extract_portal_url(resp.text)
                if portal_url:
                    magic = self.extract_magic_token(portal_url)
                    return magic, portal_url
            except Exception as e:
                logger.debug(f"Probe {probe_url} failed: {e}")

        return None, None

    def login(
        self,
        username: str,
        password: str,
        magic: Optional[str] = None,
        portal_context: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Perform captive portal login with credentials against IIT BHU Fortinet portal.
        Fetches the live login page, extracts form parameters, and submits to form action (/).
        Returns (is_success, status_message).
        """
        if not username or not password:
            return False, "Missing username or password"

        self._ensure_session()

        # Step 1: Determine the portal login page URL
        portal_page_url = None
        if portal_context and portal_context.startswith("http"):
            portal_page_url = portal_context
        elif magic:
            portal_page_url = f"http://{self.portal_host}:1000/fgtauth?{magic}"
        else:
            magic, portal_page_url = self.fetch_portal_magic()

        page_html = ""
        if portal_page_url:
            logger.info(f"Fetching captive portal login page: {portal_page_url}...")
            try:
                page_resp = self.session.get(portal_page_url, timeout=self.timeout, verify=False)
                page_html = page_resp.text
            except Exception as e:
                logger.warning(f"Failed to fetch portal page from {portal_page_url}: {e}")

        # Step 2: Extract form fields from the live HTML
        form_action = self.extract_form_action(page_html) or "/"
        form_magic = self.extract_magic_token(page_html) or magic
        form_redir = self.extract_redir_url(page_html) or self.detection_url

        if not form_magic:
            return False, "Failed to extract captive portal 'magic' token (Gateway unreachable or already online)"

        # Step 3: Target action URL (Fortinet form submits to http://192.168.249.1:1000/)
        if form_action.startswith(("http://", "https://")):
            target_url = form_action
        else:
            action_path = form_action if form_action.startswith("/") else "/" + form_action
            target_url = f"http://{self.portal_host}:1000{action_path}"

        payload = {
            "4Tredir": form_redir,
            "magic": form_magic,
            "username": username,
            "password": password
        }

        parsed = urllib.parse.urlparse(target_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        referer = portal_page_url or f"http://{self.portal_host}:1000/fgtauth?{form_magic}"

        headers = {
            "Origin": origin,
            "Referer": referer,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        logger.info(f"Submitting credentials to {target_url} with magic={form_magic}...")

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

            # Check if keepalive window redirect was returned
            m_keep = re.search(r'window\.location\s*=\s*["\'](http[^"\']*keepalive[^"\']*)["\']', resp_text, re.I)
            if m_keep:
                self.last_keepalive_url = m_keep.group(1)
                logger.info(f"[✓] Keepalive session established: {self.last_keepalive_url}")
                time.sleep(0.5)
                return True, "Login successful! Internet is now active."

            # Verify connectivity status
            time.sleep(1.0)
            status, _, _ = self.check_network_status()
            if status == NetworkStatus.ONLINE:
                return True, "Login successful! Internet is now active."

            return True, f"Login request sent to {target_url} (HTTP {response.status_code})."

        except requests.exceptions.RequestException as e:
            return False, f"Connection error during login: {e}"

    def keep_alive_ping(self) -> bool:
        """Send a lightweight ping to maintain session activity."""
        self._ensure_session()
        if self.last_keepalive_url:
            try:
                resp = self.session.get(self.last_keepalive_url, timeout=4.0, verify=False)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass

        try:
            resp = self.session.get(self.detection_url, timeout=4.0, verify=False)
            return resp.status_code in (200, 204)
        except Exception:
            return False
