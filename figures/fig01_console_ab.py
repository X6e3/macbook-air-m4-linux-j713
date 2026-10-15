#!/usr/bin/env python3
"""Fig. 1, stage 1: console start per boot on the first bring-up night.

Reads data/stage1/boot_ab.csv and boot_ab_summary.json (written by analysis/stage1_boot_ab.py) and
writes figures/out/fig01-light.svg, fig01-dark.svg and fig01-caption.md. Layout only: every number
shown is read from those two files.

    python3 figures/fig01_console_ab.py
"""
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "figures"))
import style  # noqa: E402

DATA = ROOT / "data/stage1"
rows = list(csv.DictReader((DATA / "boot_ab.csv").open()))
S = json.loads((DATA / "boot_ab_summary.json").read_text())
G = S["groups"]
N = len(rows)
_diff = (DATA / "dtb_diff.txt").read_text().split("== v4 -> v5", 1)[1]
ATC_NODES = int(_diff.split("changes in meaning: ", 1)[1].split("\n", 1)[0])
ctl, ab, base = G["4ctl"], G["4"], G["3c"]
controlled = set(ctl["boots"]) | set(ab["boots"])

# ---------------------------------------------------------------- geometry
L, R = 76, style.WIDTH - 16
step = (R - L) / N
xc = lambda i: L + step * (i + 0.5)                          # i: 0-based boot index
P1T, P1B, YLO, YHI = 124, 372, 0.01, 50.0                    # console panel, log scale
P2T, P2B = 438, 528                                          # error-count panel
PMAX = max(int(r["pmgr_fail"]) for r in rows)
H = P2B + 108


def ylog(v):
    return P1T + (P1B - P1T) * (math.log10(YHI) - math.log10(v)) / (math.log10(YHI) - math.log10(YLO))


def ybar(v):
    return P2B - (P2B - P2T) * v / PMAX


def groups():
    start = 0
    for i in range(1, N + 1):
        if i == N or rows[i]["variant"] != rows[start]["variant"]:
            yield start, i - 1, rows[start]["variant"]
            start = i


def span(boots):
    return xc(min(boots) - 1) - step * 0.45, xc(max(boots) - 1) + step * 0.45


TITLE = f"One device-tree property moved console start from {ctl['console_mean_s']:.2f} s to {ab['console_mean_s']:.3f} s"
later = S["from_boot_12"]
DESC = (f"Dot plot on a log scale: console start time for {N} boots. With the framebuffer on disp_cpu the console "
        f"starts at about {ctl['console_mean_s']:.2f} s; with disp_fe at about {ab['console_mean_s']:.2f} s. In the "
        f"controlled pair v4ctl and v4, which differ only in the DTB, the difference is {S['ratio_v4ctl_over_v4']:.0f}-fold. "
        f"Bar chart below: {ctl['pmgr_fail'][0]} power-domain errors per boot with disp_cpu, {ab['pmgr_fail'][0]} with "
        f"disp_fe, and {later['pmgr_fail'][0]} from boot 12, where the DTB, kernel and initramfs changed together.")


def draw(f):
    f.header(1, 1, "first bring-up night, 26–27 Sep 2026", TITLE,
             "Kernel-log time of the first “Console: switching to colour frame buffer device” line, one point per boot.",
             L)

    # what each block of boots is, and whether it belongs to the comparison
    first_later = min(r for r in range(1, N + 1) if r > max(controlled))
    f.bracket(*span(base["boots"]), 104, "OTHER KERNEL")
    f.bracket(*span(range(min(controlled), max(controlled) + 1)), 104, "CONTROLLED A/B  ·  ONLY THE DTB DIFFERS")
    f.bracket(*span(range(first_later, N + 1)), 104, "DTB, KERNEL AND INITRAMFS CHANGED TOGETHER")

    # image-variant bands, shared by both panels and the axis
    for k, (i0, i1, v) in enumerate(groups()):
        x0, x1 = xc(i0) - step / 2, xc(i1) + step / 2
        if k % 2 == 0:
            f.rect(x0, P1T, x1 - x0, P1B - P1T, "band")
            f.rect(x0, P2B + 27, x1 - x0, 19, "band")
        f.text((x0 + x1) / 2, P2B + 41, f"v{v}", "small", "soft", "middle", mono=True)

    for t in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50):
        major = t in (0.01, 0.1, 1, 10)
        f.line(L, ylog(t), R, ylog(t), "rule", 1 if major else 0.5, 1 if major else 0.7)
        if t not in (0.01, 50):
            f.text(L - 8, ylog(t) + 4, f"{t:g} s", "small", "soft" if major else "muted", "end", mono=True)

    for i, r in enumerate(rows):
        role = "red" if r["fb_power_domain"] == "disp_cpu" else "blue"
        f.dot(xc(i), ylog(float(r["console_s"])), role, 6, 1 if r["boot"] and int(r["boot"]) in controlled
              else style.CONTEXT_OPACITY)

    # direct labels
    y_cpu, y_fe = ylog(ctl["console_mean_s"]), ylog(ab["console_mean_s"])
    x = xc(min(base["boots"]) - 1) - step * 0.35
    f.text(x, ylog(base["console_mean_s"]) - 24, "disp_cpu", "label", "muted", weight=600, halo=True)
    f.text(x, ylog(base["console_mean_s"]) - 11, f"v3c  {base['console_mean_s']:.3f} s  n={base['n']}", "small",
           "muted", mono=True, halo=True)
    x = xc(min(ctl["boots"]) - 1) - step * 0.35
    f.text(x, y_cpu - 24, "disp_cpu", "label", "red", weight=600, halo=True)
    f.text(x, y_cpu - 11, f"v4ctl  {ctl['console_mean_s']:.3f} s  n={ctl['n']}", "small", "soft", mono=True, halo=True)
    x = xc(max(ctl["boots"])) - step * 0.35
    f.text(x, y_fe + 24, "disp_fe", "label", "blue", weight=600, halo=True)
    f.text(x, y_fe + 38, f"v4  {ab['console_mean_s']:.4f} s  n={ab['n']}", "small", "soft", mono=True, halo=True)

    # the switch from the last control boot to the next treatment boot
    xa = (xc(max(ctl["boots"]) - 1) + xc(max(ctl["boots"]))) / 2
    f.path(f"M{xa:.1f},{y_cpu + 12:.1f} V{y_fe - 12:.1f}", "soft", 1.2)
    f.path(f"M{xa - 4:.1f},{y_fe - 19:.1f} L{xa:.1f},{y_fe - 12:.1f} L{xa + 4:.1f},{y_fe - 19:.1f}", "soft", 1.2)
    ym = (y_cpu + y_fe) / 2
    f.text(xa + 9, ym, f"{S['ratio_v4ctl_over_v4']:.0f}×", 14, "ink", weight=600, halo=True)
    f.text(xa + 9, ym + 15, "earlier", "small", "soft", halo=True)

    # power-domain errors
    f.text(L, P2T - 30, "Power-domain errors per boot", "panel", "ink", weight=600)
    f.text(L + 196, P2T - 30, "lines containing “Failed to reach power state”, same log", "small", "muted")
    f.line(L, P2B, R, P2B, "rule")
    for i, r in enumerate(rows):
        v, op = int(r["pmgr_fail"]), 1 if int(r["boot"]) in controlled else style.CONTEXT_OPACITY
        if v:
            f.rect(xc(i) - step * 0.26, ybar(v), step * 0.52, P2B - ybar(v), "grey", op)
        f.text(xc(i), ybar(v) - 5, str(v), "small", "ink", "middle", mono=True, opacity=op)
    a, b = sorted(ab["boots"])[:2]
    f.text((xc(a - 1) + xc(b - 1)) / 2, ybar(PMAX) - 5, f"−{S['pmgr_drop_v4ctl_to_v4']} vs v4ctl", "small", "blue",
           "middle", italic=True)
    x = xc(first_later - 1) - step * 0.35
    f.text(x, P2T - 6, f"{later['pmgr_fail'][0]} from boot {first_later}: DTB, kernel and initramfs changed in one step,",
           "small", "soft", italic=True)
    f.text(x, P2T + 8, "so this drop is not attributed to the ATC2/3 change alone.", "small", "soft", italic=True)

    for i, r in enumerate(rows):
        f.text(xc(i), P2B + 17, r["boot"], "small", "ink", "middle", mono=True)
    f.text(L - 8, P2B + 17, "boot", "small", "muted", "end")
    f.text(L - 8, P2B + 41, "image", "small", "muted", "end")

    f.source(H - 24, L, "evidence/stage1/logs/boot-1..21.txt, image-parts.csv, dtb/",
             "analysis/stage1_boot_ab.py → figures/fig01_console_ab.py")


style.render(draw, "fig01", H, TITLE, DESC, ROOT / "figures/out")

# ---------------------------------------------------------------- caption for the README
c = f"""<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/out/fig01-dark.svg">
  <img src="figures/out/fig01-light.svg" width="100%" alt="{DESC}">
</picture>

**Fig. 1 — Console start per boot, first bring-up night (26–27 Sep 2026).**
Each point is one boot ({N} in total). The measured event is the printk timestamp of the first
`Console: switching to colour frame buffer device` line: the moment the kernel console attaches to the
framebuffer, not a full boot time. The initramfs wrote it into each log (`evidence/stage1/init-busybox-v6`,
line 46); `analysis/stage1_boot_ab.py` re-reads it from the log's own dmesg and stops if the two disagree.

**Controlled comparison.** v4ctl (boots {', '.join(map(str, ctl['boots']))}, n={ctl['n']}) and v4
(boots {', '.join(map(str, ab['boots']))}, n={ab['n']}) carry byte-identical m1n1 and kernel+initramfs
(`evidence/stage1/image-parts.csv`). The only DTB difference in meaning is
`/chosen/framebuffer@0 power-domains`: `disp_cpu` → `disp_fe` (`data/stage1/dtb_diff.txt`). Mean console start
went from {ctl['console_mean_s']:.3f} s to {ab['console_mean_s']:.4f} s ({S['ratio_v4ctl_over_v4']}×), and power-domain
errors from {ctl['pmgr_fail'][0]} to {ab['pmgr_fail'][0]}. In {S['timeout_and_110_by_domain']['disp_cpu']} disp_cpu boots
the log shows the framebuffer giving up on its power domain at the deferred-probe timeout (v4ctl mean
{S['v4ctl_deferred_probe_timeout_mean_s']:.3f} s, `pm_domain_attach_by_id(0) failed: -110`) just before the console
starts; {S['timeout_and_110_by_domain']['disp_fe']} disp_fe boots show it.

**Not part of the comparison** (drawn faded). v3c (boots {', '.join(map(str, base['boots']))}) used a different
kernel build. From boot {min(G['5']['boots'])} (v5) the DTB disables {ATC_NODES} ATC2/3 port nodes and the error count
is {later['pmgr_fail'][0]}, but the kernel+initramfs changed in the same step (and m1n1 from boot {min(G['6d']['boots'])}),
so that drop is not attributed to ATC2/3 alone.

Reproduce: `make fig01` (Python 3, standard library only).
"""
(ROOT / "figures/out/fig01-caption.md").write_text(c)
print(f"fig01: {N} boots, H={H}, ratio {S['ratio_v4ctl_over_v4']}")
