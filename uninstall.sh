#!/bin/bash
set -e

PREFIX="${PREFIX:-/usr/local}"

echo "Uninstalling Linux Mint Hub..."

rm -rf "$PREFIX/share/mint-hub"
rm -f "$PREFIX/bin/mint-hub"
rm -f "$PREFIX/share/applications/io.github.soccervortex.mint-hub.desktop"
rm -f "$PREFIX/share/icons/hicolor/scalable/apps/io.github.soccervortex.mint-hub.svg"

gtk-update-icon-cache -f "$PREFIX/share/icons/hicolor" 2>/dev/null || true

echo "Linux Mint Hub uninstalled."
