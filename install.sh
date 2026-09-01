#!/bin/bash
set -e

PREFIX="${PREFIX:-/usr/local}"
BINDIR="$PREFIX/bin"
SHAREDIR="$PREFIX/share/mint-hub"
ICONDIR="$PREFIX/share/icons/hicolor"
APPDIR="$PREFIX/share/applications"

echo "Installing Linux Mint Hub..."

# Install Python files
install -d "$SHAREDIR"
install -m644 *.py "$SHAREDIR/"

# Install data
install -d "$SHAREDIR/data"
install -m644 data/mint-hub.svg "$SHAREDIR/data/"

# Install launcher script
install -d "$BINDIR"
printf '#!/bin/bash\nexec python3 \"%s/mint_hub.py\" \"$@\"\n' "$SHAREDIR" > "$BINDIR/mint-hub"
chmod 755 "$BINDIR/mint-hub"

# Install icons
install -d "$ICONDIR/scalable/apps"
install -m644 data/mint-hub.svg "$ICONDIR/scalable/apps/io.github.soccervortex.mint-hub.svg"

# Install .desktop file
install -d "$APPDIR"
install -m644 data/io.github.soccervortex.mint-hub.desktop "$APPDIR/"

# Update icon cache
gtk-update-icon-cache -f "$ICONDIR" 2>/dev/null || true

echo "Linux Mint Hub installed successfully!"
echo "Launch from your application menu or run: mint-hub"
