# Linux Mint Hub

**Enhancement Hub for Linux Mint** — a native GTK3 desktop app for browsing, installing, and managing themes, icons, cursors, wallpapers, applets, extensions, fonts, and more.

## Features

- **16 Enhancement Categories** — GTK themes, Cinnamon themes, icon themes, cursor themes, wallpapers, applets, desklets, extensions, fonts, sound themes, Conky configs, scripts, fixes, GRUB themes, Plymouth themes
- **Cinnamon Spices Integration** — automatically fetches applets, desklets, extensions, and themes from the official Cinnamon Spices repository
- **One-Click Install & Apply** — install, apply, revert, and uninstall enhancements with a single click
- **Built-in Malware Scanner** — 200+ detection patterns scan every download and upload for security threats
- **Upload Studio** — package and publish your own enhancements to the marketplace
- **Local-Only Mode** — browse installed themes and Cinnamon Spices without needing an API key
- **Full-Text Search** — instant FTS5-powered search across all enhancements
- **Favorites & Reviews** — bookmark enhancements and leave reviews
- **Toast Notifications** — non-intrusive feedback for actions
- **Keyboard Shortcuts** — Ctrl+F (search), Escape (back), Ctrl+R (refresh), F5 (reload)

## Installation

### Method 1: .deb Package (Recommended for Linux Mint)

```bash
git clone https://github.com/soccervortex/mint-hub.git
cd mint-hub
./build-deb.sh
sudo dpkg -i mint-hub_1.0.0_all.deb
```

If you're missing dependencies:
```bash
sudo apt install -f
```

### Method 2: Make Install

```bash
git clone https://github.com/soccervortex/mint-hub.git
cd mint-hub
sudo make install
```

To uninstall:
```bash
sudo make uninstall
```

### Method 3: Run from Source

```bash
git clone https://github.com/soccervortex/mint-hub.git
cd mint-hub
python3 mint_hub.py
```

### Dependencies

- Python 3.8+
- GTK 3.0 (`python3-gi`, `gir1.2-gtk-3.0`)
- XApp (`gir1.2-xapp-1.0`)
- Requests (`python3-requests`)

On Linux Mint / Ubuntu:
```bash
sudo apt install python3-gi python3-requests gir1.2-gtk-3.0 gir1.2-xapp-1.0
```

## Usage

Launch from your application menu or run:
```bash
mint-hub
```

On first launch, you can either:
1. **Enter your OmniStream API key** to access the full marketplace
2. **Click "Browse Local Only"** to browse installed themes, Cinnamon Spices, and curated content without an API key

## Architecture

```
┌─────────────────────────────────┐
│  Linux Mint Hub (GTK3 App)      │
├─────────────────────────────────┤
│  Local Scanner    │  API Client │
│  SQLite Cache     │  Installer  │
│  Safety Scanner   │  Applier    │
└───────┬───────────┴──────┬──────┘
        │                  │
  Local filesystem    Mint Hub API
  + Cinnamon Spices   (direct HTTP)
```

## Categories

| Category | Description |
|----------|-------------|
| GTK Themes | Window and widget styling |
| Cinnamon Themes | Desktop shell themes |
| Icon Themes | Application and file icons |
| Cursor Themes | Mouse cursor packs |
| Wallpapers | Desktop backgrounds |
| Wallpaper Packs | Curated wallpaper collections |
| Applets | Cinnamon panel applets |
| Desklets | Cinnamon desktop widgets |
| Extensions | Cinnamon shell extensions |
| Fonts | TrueType and OpenType fonts |
| Sound Themes | System sound packs |
| Conky Configs | System monitor configurations |
| Scripts | Automation and utilities |
| Fixes & Tweaks | System optimizations |
| GRUB Themes | Boot loader themes |
| Plymouth Themes | Boot splash screens |

## Project Structure

```
mint-hub/
├── mint_hub.py          # Entry point
├── application.py       # Gtk.Application subclass
├── window.py            # Main window with all pages
├── constants.py         # App config and paths
├── enhancement.py       # Data model
├── scanner.py           # Local filesystem scanner
├── local_cache.py       # SQLite cache with FTS5
├── api_client.py        # Mint Hub + OmniStream API client
├── installer.py         # Download, extract, install
├── applier.py           # Apply/revert via gsettings
├── tiles.py             # Grid tile widgets
├── imaging.py           # Async thumbnail loading
├── packager.py          # Package creator for uploads
├── safety_scanner.py    # Malware detection (200+ patterns)
├── spices_fetcher.py    # Cinnamon Spices integration
├── seeder.py            # Seed catalog loader
├── seed_catalog.json    # Curated starter content
├── threading_utils.py   # Async helpers
├── Makefile             # make install / uninstall
├── build-deb.sh         # .deb package builder
├── install.sh           # Manual install script
├── uninstall.sh         # Manual uninstall script
├── data/
│   ├── mint-hub.svg                        # App icon
│   └── com.linuxmint.minthub.desktop       # Desktop entry
└── debian/                                  # Debian packaging
    ├── control
    ├── changelog
    ├── rules
    └── compat
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on Linux Mint (`python3 mint_hub.py`)
5. Submit a pull request

## License

GPL-3.0
