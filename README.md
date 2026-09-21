<div align="center">

# ⚡ IIT BHU Wi-Fi & LAN AutoConnect

**Seamless, autonomous Wi-Fi captive portal authentication and keep-alive daemon for laptops.**

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Manifest V3](https://img.shields.io/badge/Chrome_Extension-Manifest_V3-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![Platform](https://img.shields.io/badge/Platform-Linux_%7C_macOS_%7C_Windows-blue?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/Bssr-cmd/autoconnect_iitbhu)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Campus](https://img.shields.io/badge/IIT_(BHU)-Varanasi-red?style=for-the-badge)](https://iitbhu.ac.in)

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-how-it-works">How It Works</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-system-service-setup-auto-start-on-boot">Service Setup</a> •
  <a href="#-browser-extension">Browser Extension</a> •
  <a href="#-security--privacy">Security</a> •
  <a href="#-troubleshooting">FAQ</a>
</p>

</div>

---

## 📌 Problem & Motivation

On the **IIT (BHU) Varanasi** campus network (Wi-Fi & Hostel LAN), the institute firewall (`192.168.249.1` Fortinet FortiGate) forces users through a captive portal login page. 

- Sessions expire every **12–24 hours** or whenever your device disconnects/reconnects.
- On laptops, this constantly interrupts workflow by opening browser popups asking for your Roll Number and Password.
- While mobile apps exist, laptops lacked an automated background solution.

**IIT BHU AutoConnect** solves this entirely by automating the network handshake and keeping your connection alive in the background—**with zero human intervention**.

---

## ✨ Features

- 🔄 **Fully Autonomous Background Daemon**: Detects captive portal redirects silently and authenticates within seconds without opening any browser tabs.
- 🌐 **Multi-Interface Route Guard**: Automatically binds outbound traffic directly to the physical campus network card (`172.16-31.*`), ensuring login packets always reach the firewall even when mobile hotspot or USB tethering is connected concurrently.
- ⚡ **Authentic Two-Step Handshake**: Probes connectivity, dynamically extracts the live hidden `magic` token and `4Tredir` target from the login page HTML, and submits directly to the Fortinet form action (`/`).
- 💓 **Intelligent Keep-Alive Heartbeat**: Captures the session token (`/keepalive?{token}`) upon successful authentication and dispatches periodic pings to keep your session permanently active.
- 🔔 **Cross-Platform Native Notifications**: Sends unobtrusive desktop notifications on successful connection (Linux `notify-send`/`kdialog`, macOS `osascript`, Windows Toast).
- 🔒 **Zero-Trust Local Security**: Credentials are encrypted/obfuscated locally (`~/.config/autoconnect_iitbhu/config.json`) with strict POSIX `0600` permissions (owner-only access).
- 🧩 **Manifest V3 Browser Extension**: Includes a modern Chrome/Brave/Edge extension for instant <100ms form auto-fill & auto-submit.
- 🚀 **1-Click System Service**: Pre-configured `systemd` user service (Linux), `launchd` (macOS), and Windows Startup support.

---

## ⚙️ Architecture & How It Works

```mermaid
graph TD
    A["Wi-Fi / LAN Connected"] --> B{"Campus Interface Bound"}
    B --> C{"Connectivity Check (HTTP 204)"}
    C -->|"Direct Internet Access"| D["Online: Keep-Alive Heartbeat"]
    C -->|"Intercepted (HTML / 302)"| E["Captive Portal (192.168.249.1:1000/fgtauth)"]
    E --> F["Parse Form Action (/), Live 'magic' & 4Tredir"]
    F --> G["POST Credentials to Gateway (/)"]
    G --> H{"Keepalive Redirect Received?"}
    H -->|"Success"| I["Internet Unlocked + Keepalive Session Captured"]
    H -->|"Failure"| J["Log Error & Exponential Backoff"]
    I --> D
    J --> E
```

```
[ Laptop Connected to Campus Wi-Fi / LAN ]
                   │
                   ▼
       [ Bind to Campus Interface (172.16-31.*) ]
                   │
                   ▼
       [ Connectivity Probe (204) ]
         │                       │
         ├─ (Online) ────────────┼──────────► [ Active: Keep-Alive Ping (5m) ]
         │                       │
         └─ (Intercepted) ───────▼
                  [ Captive Portal at 192.168.249.1:1000/fgtauth ]
                                 │
                                 ▼
                  [ Fetch HTML & Extract Form Magic + 4Tredir ]
                                 │
                                 ▼
                  [ POST Roll No + Password to http://192.168.249.1:1000/ ]
                                 │
                                 ▼
                  [ Capture Keepalive Session & Unlock Internet! ]
```

---

## 🚀 Quick Start

### Option A: 1-Click Automated Setup (Linux & macOS)

Clone and run the automated setup wizard:

```bash
git clone https://github.com/Bssr-cmd/autoconnect_iitbhu.git
cd autoconnect_iitbhu
chmod +x install.sh
./install.sh
```

The script will:
1. Install necessary Python dependencies.
2. Prompt securely for your Roll Number and Wi-Fi password.
3. Automatically enable and start the background service so it runs at boot.

---

### Option B: Manual CLI Usage (All Platforms)

#### 1. Install dependencies:
```bash
pip install -r requirements.txt
```

#### 2. Configure credentials:
```bash
python3 autoconnect.py --configure
```

#### 3. Test immediate login:
```bash
python3 autoconnect.py --login
```

#### 4. Check live status & connection history:
```bash
python3 autoconnect.py --status
```

#### 5. Check when it connected last time:
```bash
python3 autoconnect.py --last-connected
```

#### 6. View background service logs:
```bash
python3 autoconnect.py --logs
```

#### 7. Run the background daemon manually:
```bash
python3 autoconnect.py --daemon
```

---

## 🛠️ System Service Setup (Auto-Start on Boot)

### 🐧 Linux (`systemd` User Service)
Runs quietly in the background upon login:

```bash
# Enable and start service
python3 service_installer.py

# Check status
systemctl --user status autoconnect-iitbhu.service

# View live real-time logs
journalctl --user -u autoconnect-iitbhu.service -f

# Stop / Disable service
systemctl --user stop autoconnect-iitbhu.service
```

### 🪟 Windows (Startup Folder)
1. Press <kbd>Win</kbd> + <kbd>R</kbd>, type `shell:startup`, and press <kbd>Enter</kbd>.
2. Create a shortcut in that folder pointing to:
   ```cmd
   pythonw.exe C:\path\to\autoconnect_iitbhu\autoconnect.py --daemon
   ```
   *(Using `pythonw.exe` ensures the daemon runs silently with no console window).*

### 🍎 macOS (`launchd` Agent)
Run:
```bash
python3 service_installer.py
```
This registers a `launchd` service at `~/Library/LaunchAgents/com.iitbhu.autoconnect.plist`.

---

## 🧩 Browser Extension (Manifest V3)

If you prefer using a browser extension instead of or alongside the background daemon:

<div align="center">
  <img src="extension/icons/icon-128.png" width="80" alt="Extension Icon" />
</div>

1. Open your browser and go to the extensions manager:
   - **Google Chrome / Brave**: `chrome://extensions`
   - **Microsoft Edge**: `edge://extensions`
2. Enable **Developer mode** (toggle in top right).
3. Click **Load unpacked** and select the [`extension/`](extension/) directory.
4. Click the extension toolbar icon, enter your Roll Number & Password, and click **Save Settings**.
5. Whenever the captive portal opens, the extension logs in automatically in **<100ms**.

---

## 🔐 Security & Privacy

| Principle | Guarantee |
| :--- | :--- |
| **No External Traffic** | Your credentials are sent **only** to the local IIT BHU firewall (`192.168.249.1`). |
| **Local Storage Only** | Credentials are stored in `~/.config/autoconnect_iitbhu/config.json` with `0600` permissions (readable solely by your OS user account). |
| **No Tracking / Telemetry** | 0 analytics, 0 external APIs, 0 data collection. |
| **Open Source** | 100% auditable Python and JavaScript codebase. |

---

## 📂 Project Structure

```
autoconnect_iitbhu/
├── autoconnect.py          # Core CLI application & background daemon
├── config.py               # Secure credential storage & encryption manager
├── portal_client.py        # Captive portal detection, token parser & HTTP engine
├── notifier.py             # Cross-platform desktop notification provider
├── service_installer.py    # Cross-platform background service installer
├── install.sh              # 1-Click installation shell script
├── package_extension.py    # Extension packager & zip generator
├── requirements.txt        # Python dependencies
├── tests/
│   └── test_portal.py      # Unit test suite (token parsing, status tests)
└── extension/              # Manifest V3 Chrome/Edge/Brave Extension
    ├── manifest.json
    ├── content.js          # Captive portal autofill & auto-submit script
    ├── service-worker.js   # Background badge & connectivity watcher
    ├── popup/              # Extension UI (HTML/CSS/JS)
    └── icons/              # Extension icons (16px, 48px, 128px)
```

---

## ❓ FAQ & Troubleshooting

<details>
<summary><b>1. What is <code>http://192.168.249.1:1000</code> and how does authentication work?</b></summary>
<code>192.168.249.1</code> is the IP address of the IIT BHU Fortinet firewall gateway. Port <code>1000</code> hosts the captive portal. When unauthenticated, HTTP traffic is intercepted and redirected to <code>/fgtauth</code> which displays the login form with dynamic hidden session tokens (<code>magic</code> and <code>4Tredir</code>). Credentials are submitted via POST to <code>/</code>, which returns a session keepalive URL (<code>/keepalive?{token}</code>).
</details>

<details>
<summary><b>2. How do I change or reset my saved password?</b></summary>
Simply run:
<pre><code>python3 autoconnect.py --configure</code></pre>
</details>

<details>
<summary><b>3. Does this work on Ethernet (Hostel LAN) as well as Wi-Fi?</b></summary>
Yes! Both IIT BHU campus Wi-Fi and hostel LAN connections share the same captive portal gateway and authentication protocol.
</details>

<details>
<summary><b>4. How do I run the automated unit tests?</b></summary>
Run:
<pre><code>python3 -m unittest discover tests/</code></pre>
</details>

<details>
<summary><b>5. What happens if I am connected to mobile hotspot or USB tethering at the same time?</b></summary>
The client automatically detects the network interface assigned to the campus subnet (typically <code>172.16.0.0/12</code>, e.g. <code>172.16.x.x</code> to <code>172.31.x.x</code>) and binds outbound requests directly to that adapter. This guarantees login requests and portal checks reach the campus firewall even if another default route (such as mobile hotspot with lower route metric) is active.
</details>

---

## 🤝 Contributing

Contributions, bug reports, and suggestions are welcome!
1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

<div align="center">
  <sub>Crafted for IIT (BHU) Varanasi Campus Network</sub>
</div>
