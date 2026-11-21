#!/usr/bin/env bash
# Builds extension/dist/trop-extension.zip (the unpacked extension, ready for chrome://extensions)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
rm -f dist/trop-extension.zip
zip -qr -X dist/trop-extension.zip manifest.json background.js content.js phash.js popup.html popup.js options.html options.js ui.css icons
unzip -l dist/trop-extension.zip | tail -1
