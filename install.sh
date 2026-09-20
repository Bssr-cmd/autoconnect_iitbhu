#!/usr/bin/env bash
# ==============================================================================
# IIT BHU Wi-Fi Auto-Connect - 1-Click Installer
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "    IIT BHU Wi-Fi Auto-Connect Installer"
echo "=========================================================="

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "[-] Python 3 is required but was not found. Please install Python 3."
    exit 1
fi

echo "[*] Checking Python dependencies..."
if ! python3 -c "import requests, urllib3" &> /dev/null; then
    python3 -m pip install --quiet --user --break-system-packages -r requirements.txt 2>/dev/null || \
    python3 -m pip install --quiet --user -r requirements.txt 2>/dev/null || \
    python3 -m pip install --quiet -r requirements.txt 2>/dev/null || true
fi

# Make executables
chmod +x autoconnect.py service_installer.py

# Run interactive configuration
echo ""
python3 autoconnect.py --configure

echo ""
echo "[*] Setting up automatic background service..."
python3 service_installer.py

echo ""
echo "=========================================================="
echo " [✓] Installation and Setup Completed Successfully!"
echo "=========================================================="
echo " Useful Commands:"
echo "   - Test Login Now       : python3 autoconnect.py --login"
echo "   - Check Network Status : python3 autoconnect.py --status"
echo "   - Change Credentials   : python3 autoconnect.py --configure"
echo "   - Service Status       : systemctl --user status autoconnect-iitbhu.service"
echo "   - Service Logs         : journalctl --user -u autoconnect-iitbhu.service -f"
echo "=========================================================="
