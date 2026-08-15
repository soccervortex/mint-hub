#!/bin/bash
set -e

VERSION="1.0.0"
PKG="mint-hub"
BUILDDIR="/tmp/${PKG}_${VERSION}_all"

echo "Building ${PKG} ${VERSION} .deb package..."

rm -rf "$BUILDDIR"
mkdir -p "$BUILDDIR/DEBIAN"
mkdir -p "$BUILDDIR/usr/share/mint-hub/data"
mkdir -p "$BUILDDIR/usr/bin"
mkdir -p "$BUILDDIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$BUILDDIR/usr/share/applications"

# Control file
cat > "$BUILDDIR/DEBIAN/control" << EOF
Package: mint-hub
Version: ${VERSION}
Architecture: all
Maintainer: SkinVaults <drmizayt@gmail.com>
Depends: python3 (>= 3.8), python3-gi, python3-requests, gir1.2-gtk-3.0, gir1.2-xapp-1.0
Section: utils
Priority: optional
Homepage: https://github.com/soccervortex/mint-hub
Description: Enhancement Hub for Linux Mint
 Linux Mint Hub is a native GTK3 desktop application for browsing,
 installing, and managing Linux Mint enhancements including themes,
 icons, cursors, wallpapers, applets, extensions, desklets, fonts,
 and more.
EOF

# Post-install script
cat > "$BUILDDIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
EOF
chmod 755 "$BUILDDIR/DEBIAN/postinst"

# Copy Python files
cp *.py "$BUILDDIR/usr/share/mint-hub/"
cp seed_catalog.json "$BUILDDIR/usr/share/mint-hub/"

# Copy data
cp data/mint-hub.svg "$BUILDDIR/usr/share/mint-hub/data/"

# Create launcher
cat > "$BUILDDIR/usr/bin/mint-hub" << 'EOF'
#!/bin/bash
exec python3 /usr/share/mint-hub/mint_hub.py "$@"
EOF
chmod 755 "$BUILDDIR/usr/bin/mint-hub"

# Install icon and desktop file
cp data/mint-hub.svg "$BUILDDIR/usr/share/icons/hicolor/scalable/apps/mint-hub.svg"
cp data/com.linuxmint.minthub.desktop "$BUILDDIR/usr/share/applications/"

# Build the .deb
dpkg-deb --build "$BUILDDIR" "${PKG}_${VERSION}_all.deb"

echo ""
echo "Package built: ${PKG}_${VERSION}_all.deb"
echo "Install with: sudo dpkg -i ${PKG}_${VERSION}_all.deb"
