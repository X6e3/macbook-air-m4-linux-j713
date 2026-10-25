#!/usr/bin/env python3
"""Fig. 1: framebuffer console attachment across the 21 boots of the first bring-up night.

Reads data/01-first-boot/boot_ab.csv and boot_ab_summary.json (written by analysis/boot_ab.py) and
writes figures/out/fig01-light.svg, fig01-dark.svg and fig01-caption.md. Layout only: every number
shown is read from those two files. The controlled A/B is one shaded region across both panels; the
result, the definitions and the source paths are in the caption, not in the image.

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

DATA = ROOT / "data/01-first-boot"
rows = list(csv.DictReader((DATA / "boot_ab.csv").open()))
S = json.loads((DATA / "boot_ab_summary.json").read_text())
G = S["groups"]
N = len(rows)
_diff = (DATA / "dtb_diff.txt").read_text().split("== v4 -> v5", 1)[1]
ATC_NODES = int(_diff.split("changes in meaning: ", 1)[1].split("\n", 1)[0])
ctl, ab, base = G["4ctl"], G["4"], G["3c"]
controlled = set(ctl["boots"]) | set(ab["boots"])

# ---------------------------------------------------------------- geometry
L, R = 92, style.WIDTH - 20
step = (R - L) / N
xc = lambda i: L + step * (i + 0.5)                          # i: 0-based boot index
P1T, P1B, YLO, YHI = 124, 388, 0.02, 20.0                    # console panel, log scale
P2T, P2B = 456, 566                                          # error-count panel
PMAX = max(int(r["pmgr_fail"]) for r in rows)
H = P2B + 74
TICK, LABEL, SMALL = 14, 15, 13.5


def ylog(v):
    return P1T + (P1B - P1T) * (math.log10(YHI) - math.log10(v)) / (math.log10(YHI) - math.log10(YLO))


def ybar(v):
    return P2B - (P2B - P2T) * v / PMAX


def edges(b0, b1):
    """Left and right edge of boots b0..b1 (1-based)."""
    return xc(b0 - 1) - step / 2, xc(b1 - 1) + step / 2


def groups():
    start = 0
    for i in range(1, N + 1):
        if i == N or rows[i]["variant"] != rows[start]["variant"]:
            yield start, i - 1, rows[start]["variant"]
            start = i


TITLE = f"Framebuffer console attachment across {N} boots"
later = S["from_boot_12"]
DESC = (f"Dot plot, log scale: time of the first framebuffer console line in the kernel log for each of {N} boots. "
        f"In the controlled pair (boots {min(controlled)} to {max(controlled)}), v4ctl with the framebuffer on disp_cpu "
        f"attaches at a mean {ctl['console_mean_s']:.3f} s (n={ctl['n']}) and v4 with disp_fe at "
        f"{ab['console_mean_s']:.4f} s (n={ab['n']}). Lower panel: power-domain errors per boot, {ctl['pmgr_fail'][0]} "
        f"with disp_cpu, {ab['pmgr_fail'][0]} with disp_fe, {later['pmgr_fail'][0]} from boot 12, where the DTB, "
        f"kernel and initramfs changed together.")


def draw(f):
    c0, c1 = min(controlled), max(controlled)
    ctx = style.CONTEXT_OPACITY
    f.text(16, 34, TITLE, 19, "ink", weight=600)

    # one shaded region for the controlled A/B, through both panels
    x0, x1 = edges(c0, c1)
    f.rect(x0, P1T - 34, x1 - x0, P2B - P1T + 34, "band")
    f.text((x0 + x1) / 2, P1T - 14, "Controlled A/B: only the DTB differs", SMALL, "ink", "middle", weight=600)
    a0, a1 = edges(min(base["boots"]), max(base["boots"]))
    f.text((a0 + a1) / 2, P1T - 14, "Other kernel", SMALL, "soft", "middle")
    b0, b1 = edges(c1 + 1, N)
    f.text((b0 + b1) / 2, P1T - 14, "DTB, kernel and initramfs changed", SMALL, "soft", "middle")

    # console panel
    f.text(16, P1T - 48, "Console attach time, seconds (log scale)", SMALL, "soft")
    for t in (0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20):
        major = t in (0.1, 1, 10)
        f.line(L, ylog(t), R, ylog(t), "rule", 1 if major else 0.6)
        f.text(L - 10, ylog(t) + 5, f"{t:g}", TICK, "soft" if major else "muted", "end", mono=True)

    for i, r in enumerate(rows):
        role = "red" if r["fb_power_domain"] == "disp_cpu" else "blue"
        f.dot(xc(i), ylog(float(r["console_s"])), role, 7, 1 if int(r["boot"]) in controlled else ctx)

    # direct labels: ink text, identity carried by the dot beside it
    y_cpu, y_fe, y_base = ylog(ctl["console_mean_s"]), ylog(ab["console_mean_s"]), ylog(base["console_mean_s"])
    xl = xc(min(ctl["boots"]) - 1) - step * 0.4
    f.dot(xl + 6, y_cpu + 29, "red", 6)
    f.text(xl + 18, y_cpu + 34, "disp_cpu  ·  v4ctl", LABEL, "ink", weight=600, halo=True)
    f.text(xl + 18, y_cpu + 53, f"mean {ctl['console_mean_s']:.3f} s, n={ctl['n']}", SMALL, "soft", halo=True)
    xl = xc(min(ab["boots"]) - 1) - step * 0.4
    f.dot(xl + 6, y_fe - 47, "blue", 6)
    f.text(xl + 18, y_fe - 42, "disp_fe  ·  v4", LABEL, "ink", weight=600, halo=True)
    f.text(xl + 18, y_fe - 23, f"mean {ab['console_mean_s']:.4f} s, n={ab['n']}", SMALL, "soft", halo=True)
    xl = xc(min(base["boots"]) - 1) - step * 0.4
    f.dot(xl + 6, y_base + 29, "red", 6, ctx)
    f.text(xl + 18, y_base + 34, "disp_cpu", LABEL, "soft", weight=600, halo=True)

    # error-count panel
    f.text(16, P2T - 30, "Power-domain errors per boot", SMALL, "soft")
    f.line(L, P2B, R, P2B, "rule")
    for i, r in enumerate(rows):
        v, op = int(r["pmgr_fail"]), 1 if int(r["boot"]) in controlled else ctx
        if v:
            f.rect(xc(i) - step * 0.27, ybar(v), step * 0.54, P2B - ybar(v), "grey", op)
        f.text(xc(i), ybar(v) - 7, str(v), SMALL, "ink", "middle", mono=True, opacity=op)

    # axis: boot numbers, then the image each boot ran
    for i, r in enumerate(rows):
        f.text(xc(i), P2B + 24, r["boot"], TICK, "ink", "middle", mono=True)
    f.text(L - 10, P2B + 24, "boot", SMALL, "muted", "end")
    f.text(L - 10, P2B + 52, "image", SMALL, "muted", "end")
    for i0, i1, v in groups():
        g0, g1 = xc(i0) - step / 2, xc(i1) + step / 2
        f.line(g0 + 4, P2B + 34, g1 - 4, P2B + 34, "muted", 1)
        f.text((g0 + g1) / 2, P2B + 52, f"v{v}", SMALL, "soft", "middle", mono=True)


style.render(draw, "fig01", H, TITLE, DESC, ROOT / "figures/out")

# ---------------------------------------------------------------- caption for the README
c = f"""<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/out/fig01-dark.svg">
  <img src="figures/out/fig01-light.svg" width="100%" alt="{DESC}">
</picture>

**Fig. 1 — Framebuffer console attachment across {N} boots, first bring-up night (26–27 Sep 2026).**
Each point is one boot ({N} in total). The measured event is the printk timestamp of the first
`Console: switching to colour frame buffer device` line: the moment the kernel console attaches to the
framebuffer, not a full boot time. The initramfs wrote it into each log (`evidence/01-first-boot/init-busybox-v6`,
line 46); `analysis/boot_ab.py` re-reads it from the log's own dmesg and stops if the two disagree.
The time axis is logarithmic. Power-domain errors are the lines containing `Failed to reach power state` in
the same log.

**Controlled comparison.** v4ctl (boots {', '.join(map(str, ctl['boots']))}, n={ctl['n']}) and v4
(boots {', '.join(map(str, ab['boots']))}, n={ab['n']}) carry byte-identical m1n1 and kernel+initramfs
(`evidence/01-first-boot/image-parts.csv`). The only DTB difference in meaning is
`/chosen/framebuffer@0 power-domains`: `disp_cpu` → `disp_fe` (`data/01-first-boot/dtb_diff.txt`). Mean console start
went from {ctl['console_mean_s']:.3f} s to {ab['console_mean_s']:.4f} s, {S['ratio_v4ctl_over_v4']}× earlier, and power-domain
errors from {ctl['pmgr_fail'][0]} to {ab['pmgr_fail'][0]}. In {S['timeout_and_110_by_domain']['disp_cpu']} disp_cpu boots
the log shows the framebuffer giving up on its power domain at the deferred-probe timeout (v4ctl mean
{S['v4ctl_deferred_probe_timeout_mean_s']:.3f} s, `pm_domain_attach_by_id(0) failed: -110`) just before the console
starts; {S['timeout_and_110_by_domain']['disp_fe']} disp_fe boots show it.

**Not part of the comparison** (outside the shaded region, drawn lighter). v3c (boots {', '.join(map(str, base['boots']))}) used a different
kernel build. From boot {min(G['5']['boots'])} (v5) the DTB disables {ATC_NODES} ATC2/3 port nodes and the error count
is {later['pmgr_fail'][0]}, but the kernel+initramfs changed in the same step (and m1n1 from boot {min(G['6d']['boots'])}),
so that drop is not attributed to ATC2/3 alone.

Data: `evidence/01-first-boot/logs/boot-1..21.txt`, `evidence/01-first-boot/image-parts.csv`, `evidence/01-first-boot/dtb/`.
Code: `analysis/boot_ab.py` → `figures/fig01_console_ab.py`. Reproduce: `make fig01` (Python 3 plus the PNG renderer described in [reproduction notes](docs/reproducing.md)).
"""
(ROOT / "figures/out/fig01-caption.md").write_text(c)
print(f"fig01: {N} boots, H={H}, ratio {S['ratio_v4ctl_over_v4']}")
