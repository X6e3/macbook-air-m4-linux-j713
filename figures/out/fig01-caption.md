<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/out/fig01-dark.svg">
  <img src="figures/out/fig01-light.svg" width="100%" alt="Dot plot, log scale: time of the first framebuffer console line in the kernel log for each of 21 boots. In the controlled pair (boots 4 to 11), v4ctl with the framebuffer on disp_cpu attaches at a mean 10.233 s (n=3) and v4 with disp_fe at 0.0600 s (n=5). Lower panel: power-domain errors per boot, 24 with disp_cpu, 20 with disp_fe, 0 from boot 12, where the DTB, kernel and initramfs changed together.">
</picture>

**Fig. 1 — Framebuffer console attachment across 21 boots, first bring-up night (26–27 Sep 2026).**
Each point is one boot (21 in total). The measured event is the printk timestamp of the first
`Console: switching to colour frame buffer device` line: the moment the kernel console attaches to the
framebuffer, not a full boot time. The initramfs wrote it into each log (`evidence/01-first-boot/init-busybox-v6`,
line 46); `analysis/boot_ab.py` re-reads it from the log's own dmesg and stops if the two disagree.
The time axis is logarithmic. Power-domain errors are the lines containing `Failed to reach power state` in
the same log.

**Controlled comparison.** v4ctl (boots 6, 7, 8, n=3) and v4
(boots 4, 5, 9, 10, 11, n=5) carry byte-identical m1n1 and kernel+initramfs
(`evidence/01-first-boot/image-parts.csv`). The only DTB difference in meaning is
`/chosen/framebuffer@0 power-domains`: `disp_cpu` → `disp_fe` (`data/01-first-boot/dtb_diff.txt`). Mean console start
went from 10.233 s to 0.0600 s, 170.4× earlier, and power-domain
errors from 24 to 20. In 6/6 disp_cpu boots
the log shows the framebuffer giving up on its power domain at the deferred-probe timeout (v4ctl mean
10.213 s, `pm_domain_attach_by_id(0) failed: -110`) just before the console
starts; 0/15 disp_fe boots show it.

**Not part of the comparison** (outside the shaded region, drawn lighter). v3c (boots 1, 2, 3) used a different
kernel build. From boot 12 (v5) the DTB disables 22 ATC2/3 port nodes and the error count
is 0, but the kernel+initramfs changed in the same step (and m1n1 from boot 16),
so that drop is not attributed to ATC2/3 alone.

Data: `evidence/01-first-boot/logs/boot-1..21.txt`, `evidence/01-first-boot/image-parts.csv`, `evidence/01-first-boot/dtb/`.
Code: `analysis/boot_ab.py` → `figures/fig01_console_ab.py`. Reproduce: `make fig01` (Python 3, standard
library only).
