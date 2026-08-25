#!/usr/bin/env python3
"""
Generate PNG icons for the Chrome extension.
Creates clean Wi-Fi themed icon files at 16x16, 48x48, and 128x128.
"""

import os
import struct
import zlib
from pathlib import Path

ICONS_DIR = Path(__file__).parent / "extension" / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

def create_png_image(width: int, height: int, filepath: Path):
    """Generate a clean Wi-Fi / connectivity themed PNG image without external dependencies."""
    raw_data = bytearray()
    
    # Background color: #2563EB (Navy / Blue)
    bg_r, bg_g, bg_b, bg_a = 37, 99, 235, 255
    # Foreground color: White (#FFFFFF)
    fg_r, fg_g, fg_b, fg_a = 255, 255, 255, 255

    cx, cy = width / 2.0, height / 2.0
    radius = min(width, height) / 2.0

    for y in range(height):
        # Filter byte for PNG scanline
        raw_data.append(0)
        for x in range(width):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            dist = (dx * dx + dy * dy) ** 0.5

            # Circular rounded badge
            if dist <= radius - 0.5:
                # Simple geometric Wi-Fi signal arcs
                ny = y / float(height)
                nx = abs(x - cx) / (width / 2.0)
                
                is_arc = False
                # Top arc
                if 0.20 <= ny <= 0.35 and nx <= 0.8:
                    is_arc = True
                # Middle arc
                elif 0.45 <= ny <= 0.58 and nx <= 0.55:
                    is_arc = True
                # Center dot
                elif 0.70 <= ny <= 0.85 and nx <= 0.25:
                    is_arc = True

                if is_arc:
                    raw_data.extend([fg_r, fg_g, fg_b, fg_a])
                else:
                    raw_data.extend([bg_r, bg_g, bg_b, bg_a])
            else:
                # Transparent outside circle
                raw_data.extend([0, 0, 0, 0])

    # PNG chunks assembly
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xffffffff
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    compressed = zlib.compress(bytes(raw_data), level=9)

    png_bytes = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")

    with open(filepath, "wb") as f:
        f.write(png_bytes)
    print(f"[✓] Created icon: {filepath} ({width}x{height})")

def main():
    create_png_image(16, 16, ICONS_DIR / "icon-16.png")
    create_png_image(48, 48, ICONS_DIR / "icon-48.png")
    create_png_image(128, 128, ICONS_DIR / "icon-128.png")

if __name__ == "__main__":
    main()
