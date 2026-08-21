import os
from pathlib import Path

APP_ID = "com.linuxmint.minthub"
APP_NAME = "Linux Mint Hub"
APP_VERSION = "1.0.0"
API_SLUG = "mint-hub"

OMNISTREAM_BASE = "https://grid.skinvaults.online"
MINT_HUB_BASE = "https://mint-hub.skinvaults.online"

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mint-hub"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mint-hub"
THUMBNAIL_CACHE_DIR = CACHE_DIR / "thumbnails"
DOWNLOAD_DIR = CACHE_DIR / "downloads"
DB_PATH = CACHE_DIR / "local.db"
CONFIG_FILE = CONFIG_DIR / "config.json"

INSTALL_PATHS = {
    "gtk-theme":       Path.home() / ".themes",
    "cinnamon-theme":  Path.home() / ".themes",
    "icon-theme":      Path.home() / ".icons",
    "cursor-theme":    Path.home() / ".icons",
    "wallpaper":       Path.home() / ".local/share/backgrounds",
    "wallpaper-pack":  Path.home() / ".local/share/backgrounds",
    "applet":          Path.home() / ".local/share/cinnamon/applets",
    "desklet":         Path.home() / ".local/share/cinnamon/desklets",
    "extension":       Path.home() / ".local/share/cinnamon/extensions",
    "font":            Path.home() / ".local/share/fonts",
    "sound-theme":     Path.home() / ".local/share/sounds",
    "conky":           Path.home() / ".config/conky",
    "script":          Path.home() / ".local/share/mint-hub/scripts",
    "fix":             Path.home() / ".local/share/mint-hub/fixes",
    "grub-theme":      Path("/boot/grub/themes"),
    "plymouth-theme":  Path("/usr/share/plymouth/themes"),
}

SCAN_PATHS = {
    "gtk-theme":      [Path.home() / ".themes", Path("/usr/share/themes")],
    "cinnamon-theme": [Path.home() / ".themes", Path("/usr/share/themes")],
    "icon-theme":     [Path.home() / ".icons", Path.home() / ".local/share/icons", Path("/usr/share/icons")],
    "cursor-theme":   [Path.home() / ".icons", Path.home() / ".local/share/icons", Path("/usr/share/icons")],
    "wallpaper":      [Path.home() / ".local/share/backgrounds", Path("/usr/share/backgrounds")],
    "applet":         [Path.home() / ".local/share/cinnamon/applets", Path("/usr/share/cinnamon/applets")],
    "desklet":        [Path.home() / ".local/share/cinnamon/desklets", Path("/usr/share/cinnamon/desklets")],
    "extension":      [Path.home() / ".local/share/cinnamon/extensions", Path("/usr/share/cinnamon/extensions")],
    "font":           [Path.home() / ".local/share/fonts", Path("/usr/share/fonts")],
}

GSETTINGS_MAP = {
    "gtk-theme":       ("org.cinnamon.desktop.interface", "gtk-theme"),
    "icon-theme":      ("org.cinnamon.desktop.interface", "icon-theme"),
    "cursor-theme":    ("org.cinnamon.desktop.interface", "cursor-theme"),
    "cinnamon-theme":  ("org.cinnamon.theme", "name"),
    "wallpaper":       ("org.cinnamon.desktop.background", "picture-uri"),
}

CATEGORIES = [
    {"id": "gtk-theme",       "label": "GTK Themes",          "icon": "cs-themes"},
    {"id": "cinnamon-theme",  "label": "Cinnamon Themes",     "icon": "cs-themes"},
    {"id": "icon-theme",      "label": "Icon Themes",         "icon": "preferences-desktop-icons"},
    {"id": "cursor-theme",    "label": "Cursor Themes",       "icon": "input-mouse"},
    {"id": "wallpaper",       "label": "Wallpapers",          "icon": "cs-backgrounds"},
    {"id": "wallpaper-pack",  "label": "Wallpaper Packs",     "icon": "cs-backgrounds"},
    {"id": "applet",          "label": "Cinnamon Applets",    "icon": "cs-applets"},
    {"id": "desklet",         "label": "Cinnamon Desklets",   "icon": "cs-desklets"},
    {"id": "extension",       "label": "Cinnamon Extensions", "icon": "cs-extensions"},
    {"id": "font",            "label": "Fonts",               "icon": "cs-fonts"},
    {"id": "sound-theme",     "label": "Sound Themes",        "icon": "cs-sound"},
    {"id": "conky",           "label": "Conky Configs",       "icon": "utilities-system-monitor"},
    {"id": "script",          "label": "Scripts & Automation", "icon": "utilities-terminal"},
    {"id": "fix",             "label": "Fixes & Tweaks",      "icon": "preferences-system"},
    {"id": "grub-theme",      "label": "GRUB Themes",         "icon": "drive-harddisk"},
    {"id": "plymouth-theme",  "label": "Plymouth Themes",     "icon": "video-display"},
]

CATEGORY_MAP = {c["id"]: c for c in CATEGORIES}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".bmp"}
FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}
