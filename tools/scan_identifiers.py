#!/usr/bin/env python3
"""Refuse to publish device identity or secrets. Run before every commit (make check).

Text files: MAC addresses, UUIDs, serial/ECID/IMEI fields, Wi-Fi SSID/PSK fields, private keys,
GitHub tokens, e-mail addresses. JPEGs: any metadata segment besides JFIF and ICC. DTBs: identity
properties. Exits 1 and lists every hit; an allowed hit needs an entry in ALLOW with a reason.

    python3 tools/scan_identifiers.py [path]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))
import fdt  # noqa: E402

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
SKIP_DIRS = {".git", ".preview", "__pycache__"}
SKIP_FILES = {"tools/scan_identifiers.py"}   # holds the patterns themselves
FILE_EXT = re.compile(r"\.(?:png|svg|jpe?g|gif|txt|md|csv|json|py|dtb|bin|zst)$", re.I)
TEXT = [
    ("MAC address", re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.I)),
    ("UUID", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("serial number", re.compile(r"serial[-_ ]?(?:number|no)\b\s*[=:]\s*\S+", re.I)),
    ("ECID", re.compile(r"\becid\b\s*[=:]?\s*(?:0x)?[0-9a-f]{8,}", re.I)),
    ("IMEI", re.compile(r"\bimei\b", re.I)),
    ("Wi-Fi SSID/PSK", re.compile(r"\b(?:ssid|psk|wpa_passphrase)\b\s*[=:]", re.I)),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
]
MAC_PROPS = {"mac-address", "local-mac-address"}
ID_PROPS = {"serial-number", "ecid", "apple,ecid"}
# (label, matched text) -> reason it is fine
ALLOW = {
    ("e-mail", "giometti@linux.it"): "kernel pps_core copyright banner in dmesg, public text",
}


def jpeg_metadata(b):
    found, i = [], 2
    while i + 4 <= len(b) and b[i] == 0xFF and b[i + 1] != 0xDA:
        if (0xE1 <= b[i + 1] <= 0xEF and b[i + 1] != 0xE2) or b[i + 1] == 0xFE:
            found.append(f"marker 0x{b[i + 1]:02x}")
        i += 2 + int.from_bytes(b[i + 2:i + 4], "big")
    return found


hits = []
for p in sorted(ROOT.rglob("*")):
    if not p.is_file() or SKIP_DIRS & set(p.relative_to(ROOT).parts) or str(p.relative_to(ROOT)) in SKIP_FILES:
        continue
    rel, data = str(p.relative_to(ROOT)), p.read_bytes()
    if p.suffix.lower() in (".jpg", ".jpeg"):
        hits += [(rel, "JPEG metadata", m) for m in jpeg_metadata(data)]
    elif p.suffix == ".dtb":
        for path, props in fdt.parse(data).items():
            hits += [(rel, "DTB MAC address", f"{path}:{k}={v.hex(':')}") for k, v in props.items()
                     if k in MAC_PROPS and any(v)]          # all-zero placeholders are filled by m1n1 at boot
            hits += [(rel, "DTB identity property", f"{path}:{k}") for k in props if k in ID_PROPS]
    elif p.suffix.lower() in (".png", ".gz", ".zst", ".bin"):
        continue
    else:
        text = data.decode("utf-8", errors="replace")
        for label, rx in TEXT:
            hits += [(rel, label, m.group(0)) for m in rx.finditer(text)
                     if not (label == "e-mail" and FILE_EXT.search(m.group(0)))]

bad = [h for h in hits if (h[1], h[2]) not in ALLOW]
for rel, label, m in bad:
    print(f"{rel}: {label}: {m}")
print(f"scan: {len(bad)} finding(s), {len(hits) - len(bad)} allowed")
sys.exit(1 if bad else 0)
