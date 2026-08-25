#!/usr/bin/env python3
"""
Package the Chrome Extension into a clean, store-ready ZIP file.
Validates manifest.json and ensures only required extension files are included.
"""

import os
import sys
import json
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
EXTENSION_DIR = ROOT_DIR / "extension"
DIST_DIR = ROOT_DIR / "dist"
MANIFEST_FILE = EXTENSION_DIR / "manifest.json"


def package():
    if not EXTENSION_DIR.exists() or not MANIFEST_FILE.exists():
        print("[-] Error: extension/manifest.json not found.", file=sys.stderr)
        sys.exit(1)

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    version = manifest.get("version", "1.0.0")
    zip_name = f"iitbhu-autoconnect-v{version}.zip"
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / zip_name

    print(f"[*] Packaging Chrome Extension v{version}...")

    # Files to include
    files_to_pack = []
    for root, _, files in os.walk(EXTENSION_DIR):
        for file in files:
            if file.startswith(".") or file.endswith(".swp"):
                continue
            full_path = Path(root) / file
            rel_path = full_path.relative_to(EXTENSION_DIR)
            files_to_pack.append((full_path, rel_path))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for full_path, rel_path in files_to_pack:
            print(f"  + Adding: {rel_path}")
            zipf.write(full_path, rel_path)

    print(f"\n[✓] Successfully created store-ready package:")
    print(f"    {zip_path} ({zip_path.stat().st_size / 1024:.1f} KB)")
    print("\nNext step: Upload this ZIP file to the Chrome Developer Dashboard:")
    print("https://chrome.google.com/webstore/devconsole")


if __name__ == "__main__":
    package()
