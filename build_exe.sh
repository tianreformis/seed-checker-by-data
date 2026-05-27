#!/usr/bin/env bash
set -e

APP_NAME="SeedBalanceScanner"
BINARY_NAME="seed-balance-scanner"
VERSION="1.0.0"
MAINTAINER="developer@example.com"
DESCRIPTION="Scan mnemonic seed phrases for BTC, ETH, SOL, BNB wallet balances"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN} $APP_NAME - Linux Build${NC}"
echo -e "${CYAN}=============================================${NC}"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[ERROR] Python 3 not found.${NC}"
    exit 1
fi

# Install dependencies
echo -e "${YELLOW}[1/5]${NC} Installing dependencies..."
pip3 install -r requirements.txt 2>/dev/null || \
pip3 install pyinstaller customtkinter mnemonic coincurve pycryptodome PyNaCl base58 requests Pillow

# Build with PyInstaller
echo -e "${YELLOW}[2/5]${NC} Building standalone binary..."
pyinstaller \
    --onefile \
    --noconsole \
    --clean \
    --noconfirm \
    --name "$APP_NAME" \
    main.py

# Copy data.txt to dist
echo -e "${YELLOW}[3/5]${NC} Copying data.txt..."
if [ -f data.txt ]; then
    cp data.txt "dist/"
    echo "  -> data.txt copied"
else
    echo -e "${YELLOW}  [WARN] data.txt not found${NC}"
fi

echo ""
echo -e "${GREEN}Standalone binary: dist/$APP_NAME${NC}"
echo "Run it directly: ./dist/$APP_NAME"
echo ""

# --- Optional: build .deb package ---
read -p "Create .deb package? (y/N): " BUILD_DEB
if [ "$BUILD_DEB" != "y" ] && [ "$BUILD_DEB" != "Y" ]; then
    echo "Skipping .deb. Done."
    exit 0
fi

echo -e "${YELLOW}[4/5]${NC} Building .deb package..."

ROOTDIR="$(mktemp -d)"
DEBDIR="$ROOTDIR/DEBIAN"
BINDIR="$ROOTDIR/usr/bin"
APPDIR="$ROOTDIR/usr/share/applications"
DOCDIR="$ROOTDIR/usr/share/doc/$BINARY_NAME"

mkdir -p "$DEBDIR" "$BINDIR" "$APPDIR" "$DOCDIR"

# Install the binary
cp "dist/$APP_NAME" "$BINDIR/$BINARY_NAME"
chmod 755 "$BINDIR/$BINARY_NAME"

# Control file
cat > "$DEBDIR/control" << EOF
Package: $BINARY_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: $MAINTAINER
Depends: libc6 (>= 2.17)
Description: $DESCRIPTION
 Scans BIP39 mnemonic seed phrases from data.txt
 and checks balances for Bitcoin, Ethereum, Solana,
 and Binance Coin using public RPC APIs.
 Bundled with all dependencies — no Python required.
EOF

# .desktop entry
cat > "$APPDIR/$BINARY_NAME.desktop" << EOF
[Desktop Entry]
Name=Seed Balance Scanner
Comment=$DESCRIPTION
Exec=/usr/bin/$BINARY_NAME
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Utility;Finance;
EOF

# Copyright
cat > "$DOCDIR/copyright" << EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: $APP_NAME
Source: https://github.com/example/seed-balance-scanner
EOF

# Build the .deb
DEB_FILENAME="${BINARY_NAME}_${VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "$ROOTDIR" "$DEB_FILENAME" >/dev/null

# Cleanup
rm -rf "$ROOTDIR"

# Move .deb to dist/
mv "$DEB_FILENAME" "dist/$DEB_FILENAME"

echo -e "${YELLOW}[5/5]${NC} Done!"
echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}  Build complete!${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo "  Binary:    dist/$APP_NAME"
echo "  .deb:      dist/$DEB_FILENAME"
echo ""
echo "  Install .deb with:"
echo "    sudo dpkg -i dist/$DEB_FILENAME"
echo ""
echo "  Then run: seed-balance-scanner"
echo "  (Place data.txt in the same directory)"
echo ""
