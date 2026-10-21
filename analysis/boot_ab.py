#!/usr/bin/env python3
"""First boot: the first-night boot series (21 boots) as data.

Inputs (all in evidence/01-first-boot/):
  logs/boot-N.txt   one log per boot, written to the ESP by the x6e3 initramfs (init-busybox-v6)
  image-parts.csv   SHA-256 of the m1n1, DTB and kernel+initramfs parts of each boot image

Outputs (data/01-first-boot/):
  boot_ab.csv            one row per boot
  boot_ab_summary.json   the numbers the figure and its caption use

The measured event is the kernel-log (printk) timestamp of the first
"Console: switching to colour frame buffer device" line. The initramfs extracted it into the
"fbcon_at=" field (init-busybox-v6, line 46); this script re-reads the same line from the dmesg
section of each log and stops if the two disagree.

    python3 analysis/boot_ab.py
"""
import csv
import json
import re
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
EV, OUT = ROOT / "evidence/01-first-boot", ROOT / "data/01-first-boot"
CONSOLE = "Console: switching to colour frame buffer device"
TIMEOUT = "framebuffer: deferred probe timeout"
ATTACH_FAIL = "pm_domain_attach_by_id(0) failed: -110"
DISP_CPU_DTB = "c35fabb6"  # see data/01-first-boot/dtb_diff.txt: framebuffer power-domains -> disp_cpu

parts = {r["variant"]: r for r in csv.DictReader((EV / "image-parts.csv").open())}


def field(text, key):
    m = re.search(rf"^{key}=(\S+)", text, re.M)
    return m.group(1) if m else None


def dmesg_ts(text, needle):
    dm = text.split("\n== dmesg\n", 1)[1]
    m = re.search(rf"^\[\s*([0-9.]+)\][^\n]*{re.escape(needle)}", dm, re.M)
    return float(m.group(1)) if m else None


rows = []
for n in range(1, 22):
    t = (EV / f"logs/boot-{n}.txt").read_text()
    v = field(t, "variant")
    fb = float(field(t, "fbcon_at"))
    assert fb == dmesg_ts(t, CONSOLE), f"boot {n}: fbcon_at disagrees with its own dmesg"
    p = parts[v]
    rows.append({
        "boot": n, "variant": v,
        "dtb": p["dtb_sha256"][:8], "m1n1": p["m1n1_sha256"][:8], "kernel_initramfs": p["kernel_initramfs_sha256"][:8],
        "fb_power_domain": "disp_cpu" if p["dtb_sha256"].startswith(DISP_CPU_DTB) else "disp_fe",
        "console_s": fb,
        "deferred_probe_timeout_s": dmesg_ts(t, TIMEOUT),
        "attach_fail_110": dmesg_ts(t, ATTACH_FAIL) is not None,
        "pmgr_fail": int(field(t, "pmgr_fail")),
    })

OUT.mkdir(parents=True, exist_ok=True)
with (OUT / "boot_ab.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)


def group(v):
    g = [r for r in rows if r["variant"] == v]
    return {"boots": [r["boot"] for r in g], "n": len(g), "console_mean_s": round(mean(r["console_s"] for r in g), 6),
            "console_min_s": min(r["console_s"] for r in g), "console_max_s": max(r["console_s"] for r in g),
            "pmgr_fail": sorted({r["pmgr_fail"] for r in g})}


ctl, ab = parts["4ctl"], parts["4"]
controlled = {k: ctl[k] == ab[k] for k in ("m1n1_sha256", "kernel_initramfs_sha256", "dtb_sha256")}
assert controlled == {"m1n1_sha256": True, "kernel_initramfs_sha256": True, "dtb_sha256": False}, controlled
v4ctl, v4 = group("4ctl"), group("4")
timeouts = [r["deferred_probe_timeout_s"] for r in rows if r["variant"] == "4ctl"]
later = [r for r in rows if r["boot"] >= 12]
summary = {
    "measured_event": f'printk timestamp of the first "{CONSOLE}" line',
    "boots": len(rows),
    "groups": {v: group(v) for v in dict.fromkeys(r["variant"] for r in rows)},
    "controlled_pair": {"control": "4ctl", "treatment": "4", "identical_parts": ["m1n1", "kernel+initramfs"],
                        "differing_part": "dtb"},
    "ratio_v4ctl_over_v4": round(v4ctl["console_mean_s"] / v4["console_mean_s"], 1),
    "pmgr_drop_v4ctl_to_v4": v4ctl["pmgr_fail"][0] - v4["pmgr_fail"][0],
    "v4ctl_deferred_probe_timeout_mean_s": round(mean(timeouts), 6),
    "timeout_and_110_by_domain": {d: f"{sum(r['attach_fail_110'] and r['deferred_probe_timeout_s'] is not None for r in rows if r['fb_power_domain'] == d)}"
                                     f"/{sum(r['fb_power_domain'] == d for r in rows)}" for d in ("disp_cpu", "disp_fe")},
    "from_boot_12": {"pmgr_fail": sorted({r["pmgr_fail"] for r in later}),
                     "changed_vs_v4": [k for k in ("dtb", "kernel_initramfs", "m1n1")
                                       if any(r[k] != rows[3][k] for r in later)]},
}
(OUT / "boot_ab_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("ratio_v4ctl_over_v4", "pmgr_drop_v4ctl_to_v4",
                                         "v4ctl_deferred_probe_timeout_mean_s", "from_boot_12")}, indent=1))
