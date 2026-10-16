#!/bin/sh
# Double-click (or run) to open the Desembarque launcher on Linux / macOS.
cd "$(dirname "$0")"
exec python3 launcher/desembarque_launcher.py
