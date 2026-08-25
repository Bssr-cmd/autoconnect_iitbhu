# Chrome Web Store Listing: IIT BHU Wi-Fi AutoConnect

## Overview
- **Name**: IIT BHU Wi-Fi AutoConnect
- **Short Description**: Automatically authenticates with IIT BHU campus Wi-Fi & LAN captive portals.
- **Category**: Productivity / Network Tools
- **Version**: 1.0.0
- **Supported Locales**: English

---

## Detailed Description
**IIT BHU Wi-Fi AutoConnect** eliminates the hassle of manually typing your username and password every time your campus Wi-Fi or LAN session expires.

### Features
- ⚡ **Instant Auto-Login**: Automatically fills and submits captive portal authentication forms on `192.168.249.1` and Fortinet gateways within 100ms.
- 🔒 **100% Private & Local**: Credentials remain stored exclusively on your local machine using Chrome's local storage API. No external servers, no tracking, and no analytics.
- 📶 **One-Click Connectivity**: Convenient popup interface allowing quick connect, credentials management, and live connectivity status indicator.
- 🔋 **Lightweight & Fast**: Built with Manifest V3 for optimal performance and near-zero battery consumption.

---

## Permissions Justification
- `storage`: Required to store your IIT BHU login username, encrypted credentials, and auto-login preferences locally on your device.
- `alarms`: Required to periodically check connectivity status and update the extension badge indicator.
- `host_permissions` (`*://192.168.249.1/*`, `*://detectportal.firefox.com/*`, `*://connectivitycheck.gstatic.com/*`):
  - `*://192.168.249.1/*`: Required to detect the campus captive portal login page and automatically submit the login form.
  - `*://detectportal.firefox.com/*` & `*://connectivitycheck.gstatic.com/*`: Required to verify whether the laptop currently has active internet access or is captive-portal locked.

---

## Privacy & Data Use
- **Data Collection**: None. The extension does not collect, transmit, or share any personal data.
- **Storage**: Login credentials are saved strictly inside the browser's sandboxed local storage (`chrome.storage.local`).
- **Network Requests**: Authentication requests are made exclusively to your local institute gateway (`192.168.249.1`).

---

## Version History
- **1.0.0** (2026-08-25): Initial release with Manifest V3 support, popup interface, status indicator, and instant captive portal autofill.
