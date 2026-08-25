# Privacy Policy for IIT BHU Wi-Fi AutoConnect

**Last updated:** August 26, 2026

## 1. Introduction
**IIT BHU Wi-Fi AutoConnect** is an open-source browser extension designed to automate authentication on the IIT (BHU) Varanasi campus Wi-Fi and LAN captive portal.

We respect your privacy. This privacy policy explains our strict commitment to zero data collection.

---

## 2. Information We Collect
**We do NOT collect, transmit, track, or share any personal data.**

- **Credentials**: Your Roll Number / Username and Wi-Fi password are stored strictly inside your browser's local sandbox (`chrome.storage.local`).
- **Network Requests**: Authentication requests and credential submissions are made solely and directly to your local institute gateway (`192.168.249.1`).
- **Analytics & Telemetry**: We do not use any analytics, cookies, tracking pixels, or third-party monitoring services.

---

## 3. Permissions Used
- `storage`: Used solely to persist your login credentials and auto-login preferences on your own device.
- `alarms`: Used to periodically verify whether the device has internet access.
- `host_permissions` (`*://192.168.249.1/*`, `*://detectportal.firefox.com/*`, `*://connectivitycheck.gstatic.com/*`): Used solely to detect captive portal redirects and submit the login form to the campus gateway.

---

## 4. Third-Party Sharing
We never sell, rent, trade, or transfer your information to any third parties.

---

## 5. Contact
If you have any questions about this Privacy Policy or the extension, you can contact the project maintainer:
- GitHub: [https://github.com/Bssr-cmd/autoconnect_iitbhu](https://github.com/Bssr-cmd/autoconnect_iitbhu)
- Email: `bsrisharith.reddy.ece24@itbhu.ac.in`
