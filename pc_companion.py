#!/usr/bin/env python3
"""
NEXORA AI - Local Windows PC Companion Service
Quick Launcher: Run this script on your Windows PC to enable native desktop automation:
- Launching Calculator, Notepad, File Explorer, VS Code, Windows Terminal
- Live Windows Hardware Diagnostics (CPU, RAM, Battery, Disk)
- Safe permission-based command execution
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from backend.app.companion import run_companion_server

if __name__ == "__main__":
    port = 8765
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_companion_server(port=port)
