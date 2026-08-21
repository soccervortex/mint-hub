"""Advanced security scanner for enhancement packages.

Multi-layered scanning engine that checks archives and directories for:
- Path traversal and symlink escape attacks
- Dangerous shell commands and code injection
- Reverse shells, backdoors, and C2 communication
- Privilege escalation (setuid, sudo, pkexec, polkit)
- Persistence mechanisms (cron, systemd, autostart, init)
- Data exfiltration and network abuse
- Crypto miners and resource exhaustion
- Keyloggers and input capture
- Rootkit indicators and kernel module loading
- Binary analysis (ELF in unexpected locations)
- Obfuscated payloads (base64, hex, eval chains)
- File permission abuse and ownership changes
- Package manager abuse (apt, pip, npm in scripts)
- Environment manipulation (PATH, LD_PRELOAD)
- Desktop entry hijacking and MIME type abuse
- SSH key injection and credential theft
- DNS and hosts file manipulation
- Browser config/extension hijacking
- Decompression bombs and oversized archives
- Entropy analysis for encrypted/packed payloads
"""

import math
import os
import re
import stat
import tarfile
import zipfile
from collections import Counter
from pathlib import Path

# ── Severity levels ──

BLOCKER = "blocker"
WARNING = "warning"

# ── Pattern categories ──

SHELL_INJECTION = [
    (r'\brm\s+-r[f]?\s+/', "Recursive delete from root"),
    (r'\brm\s+-r[f]?\s+~', "Recursive delete of home directory"),
    (r'\brm\s+-r[f]?\s+\$HOME', "Recursive delete of $HOME"),
    (r'>\s*/dev/[sh]d[a-z]', "Writing directly to block device"),
    (r'\bdd\b\s+if=.*of=/dev/', "dd to block device"),
    (r'\bmkfs\b', "Filesystem format command"),
    (r'\bfdisk\b', "Disk partition command"),
    (r'\bparted\b', "Disk partition command"),
    (r'\bshred\b\s', "Secure file destruction"),
]

REVERSE_SHELLS = [
    (r'\bcurl\b.*\|\s*\b(?:ba)?sh\b', "Pipe from curl to shell"),
    (r'\bwget\b.*\|\s*\b(?:ba)?sh\b', "Pipe from wget to shell"),
    (r'\bnc\b\s+-[elp]', "Netcat listener/connect"),
    (r'\bncat\b', "Ncat network tool"),
    (r'\bsocat\b', "Socat network relay"),
    (r'/dev/tcp/', "Bash TCP device"),
    (r'/dev/udp/', "Bash UDP device"),
    (r'\breverse.?shell\b', "Reverse shell reference"),
    (r'\bbind.?shell\b', "Bind shell reference"),
    (r'socket\.connect\s*\(', "Python socket connect"),
    (r'subprocess\..*shell\s*=\s*True', "Python subprocess with shell=True"),
    (r'\bimport\s+socket\b.*\bconnect\b', "Python socket usage"),
    (r'exec\s+\d+<>/dev/tcp/', "Bash file descriptor redirect to TCP"),
    (r'\btelnet\b\s+\S+\s+\d+', "Telnet connection"),
    (r'python[23]?\s+-c\s+.*socket', "Python one-liner with socket"),
    (r'perl\s+-e\s+.*socket', "Perl one-liner with socket"),
    (r'ruby\s+-e\s+.*TCPSocket', "Ruby one-liner with socket"),
    (r'php\s+-r\s+.*fsockopen', "PHP one-liner with socket"),
    (r'\blua\s+-e\s+.*socket', "Lua one-liner with socket"),
]

PRIVILEGE_ESCALATION = [
    (r'\bchmod\b\s+[0-7]*[4-7][0-7]{2}\b', "Chmod to setuid/setgid"),
    (r'\bchmod\b\s+\+s\b', "Adding setuid bit"),
    (r'\bchmod\b\s+4755\b', "Setuid root permission"),
    (r'\bchown\b\s+root\b', "Changing ownership to root"),
    (r'\bsudo\b\s', "Sudo usage"),
    (r'\bpkexec\b', "Polkit pkexec usage"),
    (r'\bsu\s+-\s', "Switch user command"),
    (r'\bdoas\b\s', "OpenBSD doas usage"),
    (r'NOPASSWD', "Sudoers NOPASSWD entry"),
    (r'/etc/sudoers', "Sudoers file access"),
    (r'\bvisudo\b', "Sudoers editing"),
    (r'\bcapsh\b', "Linux capabilities shell"),
    (r'\bsetcap\b', "Setting file capabilities"),
    (r'\bnewgrp\b', "Group switching"),
]

PERSISTENCE = [
    (r'\bcrontab\b', "Crontab modification"),
    (r'/etc/cron\b', "System cron directory access"),
    (r'\bat\b\s+\d', "at job scheduling"),
    (r'\bsystemctl\b\s+(enable|start|mask|link)', "Systemd service manipulation"),
    (r'/etc/systemd/', "Systemd directory access"),
    (r'\.config/autostart/', "Desktop autostart directory"),
    (r'/etc/xdg/autostart/', "System autostart directory"),
    (r'/etc/init\.d/', "Init.d script directory"),
    (r'/etc/rc\.local', "rc.local modification"),
    (r'\.bashrc\b', "Bashrc modification"),
    (r'\.bash_profile\b', "Bash profile modification"),
    (r'\.profile\b', "Profile modification"),
    (r'\.zshrc\b', "Zshrc modification"),
    (r'/etc/environment', "System environment modification"),
    (r'/etc/profile', "System profile modification"),
    (r'update-rc\.d', "Init script management"),
    (r'\bchkconfig\b', "Service management"),
    (r'XDG_CONFIG_HOME.*autostart', "Autostart via XDG"),
    (r'\bsystemd-run\b', "Systemd transient service"),
]

DATA_EXFILTRATION = [
    (r'\bcurl\b\s+.*-[dFX]\s', "Curl sending data"),
    (r'\bwget\b\s+--post', "Wget POST request"),
    (r'\bcurl\b\s+.*\b(passwd|shadow|ssh|key|token|secret)\b', "Curl accessing sensitive files"),
    (r'/etc/passwd\b', "Accessing passwd file"),
    (r'/etc/shadow\b', "Accessing shadow file"),
    (r'\.ssh/', "SSH directory access"),
    (r'id_rsa\b', "SSH private key access"),
    (r'id_ed25519\b', "SSH private key access"),
    (r'authorized_keys\b', "SSH authorized keys"),
    (r'known_hosts\b', "SSH known hosts"),
    (r'\.gnupg/', "GPG keyring access"),
    (r'\.aws/', "AWS credentials access"),
    (r'\.kube/', "Kubernetes config access"),
    (r'\.docker/', "Docker config access"),
    (r'\.npmrc\b', "NPM config with tokens"),
    (r'\.pypirc\b', "PyPI config with tokens"),
    (r'\.netrc\b', "Netrc credentials"),
    (r'\.git-credentials\b', "Git credentials"),
    (r'\.env\b', "Environment file with secrets"),
    (r'wallet\.dat\b', "Cryptocurrency wallet"),
    (r'\.mozilla/firefox/.*\.default.*/(logins|key[34]|cookies)', "Firefox credential files"),
    (r'\.config/google-chrome/.*(Login|Cookies)', "Chrome credential files"),
    (r'HISTFILE\b', "Shell history file"),
    (r'\.bash_history\b', "Bash history"),
]

CRYPTO_MINERS = [
    (r'\bxmrig\b', "XMRig crypto miner"),
    (r'\bxmr-stak\b', "XMR-STAK crypto miner"),
    (r'\bcpuminer\b', "CPU miner"),
    (r'\bminerd\b', "Minerd crypto miner"),
    (r'\bcgminer\b', "CG miner"),
    (r'\bbfgminer\b', "BFG miner"),
    (r'\bnbminer\b', "NB miner"),
    (r'\bethmine\b', "Ethereum miner"),
    (r'stratum\+tcp://', "Mining pool connection"),
    (r'stratum\+ssl://', "Mining pool connection"),
    (r'pool\.minergate\.com', "Minergate pool"),
    (r'nicehash\.com', "NiceHash pool"),
    (r'moneroocean\.stream', "MoneroOcean pool"),
    (r'\bcryptonight\b', "CryptoNight algorithm"),
    (r'\brandomx\b', "RandomX algorithm"),
]

KEYLOGGERS = [
    (r'\bxinput\b\s+test', "X11 input monitoring"),
    (r'\bxdotool\b\s+key.*getactivewindow', "X11 key capture"),
    (r'\bxev\b', "X event monitor"),
    (r'XGrabKeyboard', "X11 keyboard grab"),
    (r'XQueryKeymap', "X11 keymap query"),
    (r'\bkeylogger\b', "Keylogger reference"),
    (r'\bpynput\b', "Python input monitoring library"),
    (r'from\s+pynput', "Python pynput import"),
    (r'keyboard\.on_press', "Keyboard event capture"),
    (r'/dev/input/', "Direct input device access"),
    (r'evdev.*InputDevice', "Linux evdev input capture"),
]

ROOTKIT_INDICATORS = [
    (r'\binsmod\b', "Kernel module loading"),
    (r'\bmodprobe\b\s', "Kernel module loading"),
    (r'\brmmod\b', "Kernel module removal"),
    (r'\.ko\b', "Kernel module file"),
    (r'/proc/self/maps', "Process memory map access"),
    (r'/proc/self/mem\b', "Process memory access"),
    (r'ptrace\b', "Process tracing/debugging"),
    (r'LD_PRELOAD', "Shared library preloading"),
    (r'/etc/ld\.so\.preload', "System-wide library preloading"),
    (r'/etc/ld\.so\.conf', "Library path configuration"),
    (r'\bmknod\b', "Device node creation"),
    (r'\bmkfifo\b', "Named pipe creation"),
    (r'/dev/mem\b', "Physical memory access"),
    (r'/dev/kmem\b', "Kernel memory access"),
    (r'/proc/kallsyms', "Kernel symbol table"),
    (r'/proc/modules', "Loaded kernel modules"),
    (r'\bdmesg\b.*-c', "Clearing kernel ring buffer"),
]

NETWORK_ABUSE = [
    (r'\biptables\b.*-[AID]\b', "Firewall rule manipulation"),
    (r'\bnftables\b', "Firewall rule manipulation"),
    (r'\bufw\b\s+(allow|deny|delete)', "UFW firewall manipulation"),
    (r'\bfirewall-cmd\b', "Firewalld manipulation"),
    (r'/etc/resolv\.conf\b', "DNS configuration modification"),
    (r'/etc/hosts\b', "Hosts file modification"),
    (r'\bip\b\s+route\b', "Network route manipulation"),
    (r'\barp\b\s+-s', "ARP table manipulation"),
    (r'\btcpdump\b', "Network packet capture"),
    (r'\bwireshark\b', "Network analysis tool"),
    (r'\btshark\b', "Network analysis tool"),
    (r'\bnmap\b', "Network scanning"),
    (r'\bmasscan\b', "Mass port scanning"),
    (r'\bsshd\b', "SSH server manipulation"),
    (r'\bopenvpn\b.*--config', "VPN configuration"),
    (r'\bwireguard\b', "WireGuard VPN"),
    (r'socks[45]\b', "SOCKS proxy"),
    (r'\bproxychains\b', "Proxy chains"),
    (r'\btor\b\s', "Tor network"),
]

OBFUSCATION = [
    (r'base64\s+(-d|--decode)\s*[|<]', "Base64 decode piped to execution"),
    (r'base64\.b64decode', "Python base64 decode"),
    (r'\beval\b\s*\(', "Eval execution"),
    (r'\bexec\b\s*\(', "Exec execution"),
    (r'\\x[0-9a-fA-F]{2}.*\\x[0-9a-fA-F]{2}', "Hex-escaped payload"),
    (r'\\u[0-9a-fA-F]{4}.*\\u[0-9a-fA-F]{4}', "Unicode-escaped payload"),
    (r'\$\(\s*echo\s.*\|\s*base64', "Obfuscated command via echo+base64"),
    (r'printf\s+.*\\\\x', "Printf with hex escape"),
    (r'xxd\s+-r', "Hex to binary conversion"),
    (r'compile\s*\(.*exec', "Dynamic code compilation"),
    (r'__import__\s*\(', "Dynamic Python import"),
    (r'importlib\.import_module', "Dynamic Python module import"),
    (r'getattr\s*\(.*__', "Python dunder attribute access"),
    (r'marshal\.loads', "Python marshal deserialization"),
    (r'pickle\.loads', "Python pickle deserialization"),
    (r'os\.system\s*\(', "Python os.system call"),
    (r'os\.popen\s*\(', "Python os.popen call"),
    (r'commands\.getoutput', "Python commands module"),
]

ENV_MANIPULATION = [
    (r'export\s+PATH=', "PATH manipulation"),
    (r'export\s+LD_LIBRARY_PATH=', "Library path manipulation"),
    (r'export\s+LD_PRELOAD=', "Library preloading"),
    (r'export\s+PYTHONPATH=', "Python path manipulation"),
    (r'export\s+NODE_PATH=', "Node.js path manipulation"),
    (r'export\s+DISPLAY=', "Display variable manipulation"),
    (r'export\s+DBUS_SESSION', "D-Bus session manipulation"),
    (r'export\s+XDG_', "XDG environment manipulation"),
    (r'export\s+http_proxy=', "HTTP proxy setting"),
    (r'export\s+https_proxy=', "HTTPS proxy setting"),
    (r'export\s+ALL_PROXY=', "Global proxy setting"),
]

PKG_MANAGER_ABUSE = [
    (r'\bapt\b\s+install\b', "APT package installation"),
    (r'\bapt-get\b\s+install\b', "APT package installation"),
    (r'\bdpkg\b\s+-i\b', "dpkg package installation"),
    (r'\bsnap\b\s+install\b', "Snap package installation"),
    (r'\bflatpak\b\s+install\b', "Flatpak installation"),
    (r'\bpip[3]?\b\s+install\b', "Python pip installation"),
    (r'\bnpm\b\s+install\b', "npm package installation"),
    (r'\byarn\b\s+add\b', "Yarn package installation"),
    (r'\bgem\b\s+install\b', "Ruby gem installation"),
    (r'\bcargo\b\s+install\b', "Rust cargo installation"),
    (r'\bgo\b\s+install\b', "Go package installation"),
    (r'add-apt-repository\b', "Adding APT repository"),
    (r'/etc/apt/sources\.list', "APT sources modification"),
]

DESKTOP_HIJACKING = [
    (r'Exec\s*=.*(?:curl|wget|nc|bash\s+-c|python|perl|ruby)', "Suspicious Exec in desktop entry"),
    (r'MimeType\s*=', "MIME type handler registration"),
    (r'x-scheme-handler/', "URL scheme handler registration"),
    (r'Hidden\s*=\s*true', "Hidden desktop entry"),
    (r'NoDisplay\s*=\s*true', "Hidden desktop entry"),
    (r'StartupNotify\s*=\s*false.*Exec\s*=\s*/', "Silent execution desktop entry"),
    (r'OnlyShowIn\s*=\s*$', "Empty OnlyShowIn (runs everywhere)"),
    (r'xdg-mime\s+default', "Changing default file handler"),
    (r'update-alternatives', "Changing system alternatives"),
]

RESOURCE_EXHAUSTION = [
    (r':\(\)\s*\{\s*:\|:&\s*\};:', "Fork bomb"),
    (r'while\s+true.*done', "Infinite loop"),
    (r'for\s*\(\s*;\s*;\s*\)', "Infinite loop"),
    (r'\byes\b\s*\|', "Yes pipe (potential resource abuse)"),
    (r'/dev/zero\b', "Zero device (potential resource abuse)"),
    (r'/dev/urandom\b.*\bdd\b', "Random data generation"),
    (r'ulimit\s+-[nvu]\s+unlimited', "Removing resource limits"),
]

ALL_PATTERN_GROUPS = [
    ("Shell injection", SHELL_INJECTION, BLOCKER),
    ("Reverse shell / backdoor", REVERSE_SHELLS, BLOCKER),
    ("Privilege escalation", PRIVILEGE_ESCALATION, BLOCKER),
    ("Persistence mechanism", PERSISTENCE, BLOCKER),
    ("Data exfiltration", DATA_EXFILTRATION, BLOCKER),
    ("Crypto miner", CRYPTO_MINERS, BLOCKER),
    ("Keylogger / input capture", KEYLOGGERS, BLOCKER),
    ("Rootkit indicator", ROOTKIT_INDICATORS, BLOCKER),
    ("Network abuse", NETWORK_ABUSE, BLOCKER),
    ("Obfuscated code", OBFUSCATION, BLOCKER),
    ("Environment manipulation", ENV_MANIPULATION, WARNING),
    ("Package manager usage", PKG_MANAGER_ABUSE, WARNING),
    ("Desktop entry hijacking", DESKTOP_HIJACKING, BLOCKER),
    ("Resource exhaustion", RESOURCE_EXHAUSTION, BLOCKER),
]

COMPILED_GROUPS = [
    (name, [(re.compile(p, re.IGNORECASE | re.MULTILINE), desc) for p, desc in patterns], severity)
    for name, patterns, severity in ALL_PATTERN_GROUPS
]

SUSPICIOUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".scr", ".pif",
    ".msi", ".dll", ".sys", ".vbs", ".ps1", ".wsf",
    ".hta", ".cpl", ".inf", ".reg",
    ".elf", ".bin", ".so", ".ko",
}

ALLOWED_SCRIPT_LOCATIONS = {"scripts", "script", "bin", "tools", "hooks"}

SCANNABLE_TEXT_EXTENSIONS = {
    ".sh", ".bash", ".zsh", ".fish", ".csh", ".ksh",
    ".py", ".pyw", ".pl", ".pm", ".rb",
    ".js", ".ts", ".lua", ".php",
    ".desktop", ".service", ".timer", ".socket", ".path",
    ".conf", ".cfg", ".ini", ".yaml", ".yml", ".toml",
    ".xml", ".json",
    "", ".txt", ".md",
}

MAX_FILE_SCAN_SIZE = 2_000_000
MAX_ARCHIVE_SIZE = 500_000_000
MAX_ARCHIVE_FILES = 10_000
MAX_COMPRESSION_RATIO = 100


class Finding:
    __slots__ = ("severity", "category", "description", "path", "detail")

    def __init__(self, severity: str, category: str, description: str,
                 path: str = "", detail: str = ""):
        self.severity = severity
        self.category = category
        self.description = description
        self.path = path
        self.detail = detail

    def __str__(self):
        prefix = "[BLOCKED]" if self.severity == BLOCKER else "[WARNING]"
        loc = f" in {self.path}" if self.path else ""
        extra = f" — {self.detail}" if self.detail else ""
        return f"{prefix} {self.category}: {self.description}{loc}{extra}"


class ScanResult:
    __slots__ = ("safe", "findings", "_seen")

    def __init__(self):
        self.safe = True
        self.findings = []
        self._seen = set()

    def add(self, finding: Finding):
        key = (finding.severity, finding.category, finding.description, finding.path)
        if key in self._seen:
            return
        self._seen.add(key)
        self.findings.append(finding)
        if finding.severity == BLOCKER:
            self.safe = False

    def add_blocker(self, category: str, description: str,
                    path: str = "", detail: str = ""):
        self.add(Finding(BLOCKER, category, description, path, detail))

    def add_warning(self, category: str, description: str,
                    path: str = "", detail: str = ""):
        self.add(Finding(WARNING, category, description, path, detail))

    @property
    def blockers(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == BLOCKER]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def summary(self) -> str:
        lines = []
        blockers = self.blockers
        warnings = self.warnings

        if blockers:
            lines.append(f"BLOCKED — {len(blockers)} security issue(s) found:")
            for f in blockers:
                lines.append(f"  [!] {f.category}: {f.description}")
                if f.path:
                    lines.append(f"      File: {f.path}")
                if f.detail:
                    lines.append(f"      Detail: {f.detail}")

        if warnings:
            lines.append(f"\n{len(warnings)} warning(s):")
            for f in warnings:
                lines.append(f"  [~] {f.category}: {f.description}")
                if f.path:
                    lines.append(f"      File: {f.path}")

        if not lines:
            lines.append("Security scan passed — no issues found.")

        return "\n".join(lines)


def scan_archive(archive_path: str) -> ScanResult:
    result = ScanResult()
    path = Path(archive_path)

    if not path.exists():
        result.add_blocker("File error", f"Archive not found: {archive_path}")
        return result

    archive_size = path.stat().st_size
    if archive_size > MAX_ARCHIVE_SIZE:
        result.add_blocker("Size limit", f"Archive too large: {archive_size / 1_000_000:.1f} MB")
        return result

    if zipfile.is_zipfile(str(path)):
        try:
            with zipfile.ZipFile(str(path), "r") as zf:
                infos = zf.infolist()
                if len(infos) > MAX_ARCHIVE_FILES:
                    result.add_blocker("Archive bomb",
                                       f"Too many files: {len(infos)} (max {MAX_ARCHIVE_FILES})")
                    return result
                total_uncompressed = sum(i.file_size for i in infos)
                if archive_size > 0 and total_uncompressed / archive_size > MAX_COMPRESSION_RATIO:
                    result.add_blocker("Archive bomb",
                                       f"Compression ratio {total_uncompressed / archive_size:.0f}:1 "
                                       f"exceeds limit of {MAX_COMPRESSION_RATIO}:1")
                    return result
                _scan_zip_members(zf, infos, result)
        except zipfile.BadZipFile as e:
            result.add_blocker("Archive error", f"Cannot read zip: {e}")
    else:
        try:
            with tarfile.open(str(path), "r:*") as tar:
                members = tar.getmembers()
                if len(members) > MAX_ARCHIVE_FILES:
                    result.add_blocker("Archive bomb",
                                       f"Too many files: {len(members)} (max {MAX_ARCHIVE_FILES})")
                    return result
                total_uncompressed = sum(m.size for m in members if m.isfile())
                if archive_size > 0 and total_uncompressed / archive_size > MAX_COMPRESSION_RATIO:
                    result.add_blocker("Archive bomb",
                                       f"Compression ratio {total_uncompressed / archive_size:.0f}:1 "
                                       f"exceeds limit of {MAX_COMPRESSION_RATIO}:1")
                    return result
                _scan_tar_members(tar, members, result)
        except tarfile.TarError as e:
            result.add_blocker("Archive error", f"Cannot read archive: {e}")

    return result


def scan_directory(directory: str) -> ScanResult:
    result = ScanResult()
    root = Path(directory)

    if not root.exists():
        result.add_blocker("File error", f"Directory not found: {directory}")
        return result

    file_count = 0
    total_size = 0

    for path in root.rglob("*"):
        rel = str(path.relative_to(root))

        if path.is_symlink():
            _check_symlink(path, rel, result)

        if path.is_file():
            file_count += 1
            try:
                size = path.stat().st_size
                total_size += size
            except OSError:
                continue

            _check_file_name(rel, result)
            _check_file_permissions(path, rel, result)

            if size <= MAX_FILE_SCAN_SIZE:
                _check_file_content(path, rel, result)

    _check_package_metrics(file_count, total_size, root, result)

    return result


def scan_for_upload(source_dir: str) -> ScanResult:
    result = scan_directory(source_dir)
    root = Path(source_dir)

    script_exts = {".sh", ".bash", ".py", ".pl", ".rb", ".lua", ".php"}
    script_count = sum(
        1 for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in script_exts
    )
    total_count = sum(1 for p in root.rglob("*") if p.is_file())

    if total_count > 0 and script_count / total_count > 0.7:
        result.add_warning("Package composition",
                           f"Very high script ratio: {script_count}/{total_count} files are scripts")

    for p in root.rglob("*.desktop"):
        _check_desktop_entry(p, str(p.relative_to(root)), result)

    for p in root.rglob("*.service"):
        _check_systemd_unit(p, str(p.relative_to(root)), result)

    return result


# ── Internal scanning functions ──

def _scan_tar_members(tar: tarfile.TarFile, members: list, result: ScanResult):
    for member in members:
        name = member.name

        if name.startswith("/"):
            result.add_blocker("Path traversal", "Absolute path in archive", name)
            continue
        if ".." in name.split("/"):
            result.add_blocker("Path traversal", "Parent directory escape", name)
            continue

        normalized = os.path.normpath(name)
        if normalized.startswith(".."):
            result.add_blocker("Path traversal", "Normalized path escapes archive", name)
            continue

        if member.issym() or member.islnk():
            link = member.linkname
            if link.startswith("/"):
                result.add_blocker("Symlink attack", "Absolute symlink target", name,
                                   f"-> {link}")
            elif ".." in link.split("/"):
                result.add_blocker("Symlink attack", "Symlink escapes archive", name,
                                   f"-> {link}")

        if member.isdev():
            result.add_blocker("Device node", "Device node in archive", name)

        if member.isfile():
            _check_file_name(name, result)

            if member.mode & (stat.S_ISUID | stat.S_ISGID):
                result.add_blocker("Privilege escalation", "Setuid/setgid binary", name)

            if member.mode & stat.S_IXUSR:
                rel = Path(name)
                if rel.suffix not in (".sh", ".py", ".pl", ".rb"):
                    if not any(p in rel.parts for p in ALLOWED_SCRIPT_LOCATIONS):
                        result.add_warning("Executable", "Unexpected executable permission", name)

            if member.size <= MAX_FILE_SCAN_SIZE:
                try:
                    f = tar.extractfile(member)
                    if f:
                        content = f.read()
                        _check_content_bytes(content, name, result)
                except Exception:
                    pass


def _scan_zip_members(zf: zipfile.ZipFile, infos: list, result: ScanResult):
    for info in infos:
        name = info.filename
        if info.is_dir():
            continue
        if name.startswith("/"):
            result.add_blocker("Path traversal", "Absolute path in archive", name)
            continue
        if ".." in name.split("/"):
            result.add_blocker("Path traversal", "Parent directory escape", name)
            continue
        normalized = os.path.normpath(name)
        if normalized.startswith(".."):
            result.add_blocker("Path traversal", "Normalized path escapes archive", name)
            continue
        _check_file_name(name, result)
        if info.file_size <= MAX_FILE_SCAN_SIZE:
            try:
                content = zf.read(info)
                _check_content_bytes(content, name, result)
            except Exception:
                pass


def _check_symlink(path: Path, rel: str, result: ScanResult):
    try:
        target = os.readlink(str(path))
    except OSError:
        return

    if target.startswith("/"):
        result.add_blocker("Symlink attack", "Absolute symlink target", rel,
                           f"-> {target}")
    elif ".." in target.split("/"):
        result.add_blocker("Symlink attack", "Symlink escapes directory", rel,
                           f"-> {target}")

    sensitive_targets = [
        "/etc/passwd", "/etc/shadow", "/etc/sudoers",
        "/root/", "/.ssh/", "/etc/ssl/",
    ]
    for s in sensitive_targets:
        if s in target:
            result.add_blocker("Symlink attack", f"Symlink to sensitive location", rel,
                               f"-> {target}")
            break


def _check_file_name(name: str, result: ScanResult):
    rel = Path(name)

    if rel.suffix.lower() in SUSPICIOUS_EXTENSIONS:
        result.add_blocker("Suspicious file", f"Dangerous file type ({rel.suffix})", name)

    if rel.name.startswith(".") and rel.suffix.lower() in (".sh", ".py", ".pl", ".rb"):
        result.add_warning("Hidden script", "Hidden script file detected", name)

    if rel.name.lower() in ("authorized_keys", "id_rsa", "id_ed25519", "id_ecdsa"):
        result.add_blocker("SSH key", "SSH key file in package", name)

    if rel.name.lower() in (".env", ".netrc", ".pgpass", ".my.cnf"):
        result.add_blocker("Credentials", "Credential file in package", name)


def _check_file_permissions(path: Path, rel: str, result: ScanResult):
    try:
        st = path.stat()
    except OSError:
        return

    if st.st_mode & (stat.S_ISUID | stat.S_ISGID):
        result.add_blocker("Privilege escalation", "Setuid/setgid binary", rel)

    if st.st_mode & stat.S_IWOTH:
        result.add_warning("Permissions", "World-writable file", rel)


def _check_file_content(path: Path, rel: str, result: ScanResult):
    try:
        content = path.read_bytes()
    except Exception:
        return
    _check_content_bytes(content, rel, result)


def _check_content_bytes(content: bytes, rel: str, result: ScanResult):
    if content[:4] == b"\x7fELF":
        path = Path(rel)
        if not any(p in path.parts for p in ALLOWED_SCRIPT_LOCATIONS):
            result.add_warning("Binary", "Compiled ELF binary in package", rel)
        return

    if content[:2] in (b"MZ", b"\x4d\x5a"):
        result.add_blocker("Binary", "Windows PE executable in package", rel)
        return

    entropy = _calculate_entropy(content)
    if entropy > 7.5 and len(content) > 10_000:
        result.add_warning("Entropy", f"High entropy file ({entropy:.2f}) — may be packed/encrypted", rel)

    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        return

    ext = Path(rel).suffix.lower()
    if ext not in SCANNABLE_TEXT_EXTENSIONS and not _looks_like_script(content):
        return

    for group_name, patterns, severity in COMPILED_GROUPS:
        for pattern, desc in patterns:
            match = pattern.search(text)
            if match:
                snippet = match.group(0)[:80].strip()
                if severity == BLOCKER:
                    result.add_blocker(group_name, desc, rel, f"Match: '{snippet}'")
                else:
                    result.add_warning(group_name, desc, rel, f"Match: '{snippet}'")
                break


def _check_desktop_entry(path: Path, rel: str, result: ScanResult):
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return

    for pattern, desc in DESKTOP_HIJACKING:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            result.add_blocker("Desktop hijacking", desc, rel)


def _check_systemd_unit(path: Path, rel: str, result: ScanResult):
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return

    dangerous = [
        (r'ExecStart\s*=.*(?:curl|wget|nc|bash\s+-c|python.*-c)', "Suspicious ExecStart"),
        (r'ExecStartPre\s*=.*(?:curl|wget|nc)', "Suspicious ExecStartPre"),
        (r'PrivateNetwork\s*=\s*no', "Service disabling network isolation"),
        (r'CapabilityBoundingSet\s*=.*CAP_SYS_ADMIN', "Service with CAP_SYS_ADMIN"),
    ]
    for pattern, desc in dangerous:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            result.add_blocker("Systemd abuse", desc, rel)


def _check_package_metrics(file_count: int, total_size: int,
                           root: Path, result: ScanResult):
    if total_size > MAX_ARCHIVE_SIZE:
        result.add_warning("Size limit",
                           f"Package is very large: {total_size / 1_000_000:.1f} MB")

    if file_count > MAX_ARCHIVE_FILES:
        result.add_warning("File count",
                           f"Too many files: {file_count}")


def _calculate_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    sample = data[:65536]
    counts = Counter(sample)
    length = len(sample)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def _looks_like_script(content: bytes) -> bool:
    if content[:2] == b"#!":
        return True
    if content[:100].lstrip().startswith((b"#!/", b"# ", b"import ", b"from ")):
        return True
    return False
