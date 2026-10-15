<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/out/fig01-dark.svg">
  <img src="figures/out/fig01-light.svg" width="100%" alt="Dot plot on a log scale: console start time for 21 boots. With the framebuffer on disp_cpu the console starts at about 10.23 s; with disp_fe at about 0.06 s. In the controlled pair v4ctl and v4, which differ only in the DTB, the difference is 170-fold. Bar chart below: 24 power-domain errors per boot with disp_cpu, 20 with disp_fe, and 0 from boot 12, where the DTB, kernel and initramfs changed together.">
</picture>

**Fig. 1 — Console start per boot, first bring-up night (26–27 Sep 2026).**
Each point is one boot (21 in total). The measured event is the printk timestamp of the first
`Console: switching to colour frame buffer device` line: the moment the kernel console attaches to the
framebuffer, not a full boot time. The initramfs wrote it into each log (`evidence/stage1/init-busybox-v6`,
line 46); `analysis/stage1_boot_ab.py` re-reads it from the log's own dmesg and stops if the two disagree.

**Controlled comparison.** v4ctl (boots 6, 7, 8, n=3) and v4
(boots 4, 5, 9, 10, 11, n=5) carry byte-identical m1n1 and kernel+initramfs
(`evidence/stage1/image-parts.csv`). The only DTB difference in meaning is
`/chosen/framebuffer@0 power-domains`: `disp_cpu` → `disp_fe` (`data/stage1/dtb_diff.txt`). Mean console start
went from 10.233 s to 0.0600 s (170.4×), and power-domain
errors from 24 to 20. In 6/6 disp_cpu boots
the log shows the framebuffer giving up on its power domain at the deferred-probe timeout (v4ctl mean
10.213 s, `pm_domain_attach_by_id(0) failed: -110`) just before the console
starts; 0/15 disp_fe boots show it.

**Not part of the comparison** (drawn faded). v3c (boots 1, 2, 3) used a different
kernel build. From boot 12 (v5) the DTB disables 22 ATC2/3 port nodes and the error count
is 0, but the kernel+initramfs changed in the same step (and m1n1 from boot 16),
so that drop is not attributed to ATC2/3 alone.

Reproduce: `make fig01` (Python 3, standard library only).
