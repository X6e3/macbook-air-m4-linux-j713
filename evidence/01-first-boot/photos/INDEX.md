# First-boot photos

Phone photos of the J713 screen, taken during the first bring-up night. Copies are re-encoded at
1600 px with every metadata segment removed (`tools/import_photos.py`); `SOURCES.tsv` keeps each
original's file name, SHA-256 and capture time (UTC+3).

| file | taken | what is on screen |
|---|---|---|
| `20260926-232154-IMG_0019.jpg` | 26 Sep 23:21:54 | Kernel log on the internal display. `Console: switching to colour frame buffer device` appears at about 10.25 s, after the framebuffer's deferred-probe timeout. |
| `20260927-011340-IMG_0055.jpg` | 27 Sep 01:13:40 | Ten penguins (10 CPUs online), the console at 0.06 s, and the x6e3 initramfs lines `x6e3: booting Linux on Mac16,12` and `cpus_online=0-9`. |
| `20260927-045832-IMG_0113.jpg` | 27 Sep 04:58:32 | KDE Plasma desktop with a terminal open as `x6e3@x6e3-j713-fedora`. The panel clock reads 03:07, 14.09.2026: the machine had no working RTC yet, so the system clock was wrong. The capture time comes from the phone (`SOURCES.tsv`). |
| `20260927-053929-IMG_0126.jpg` | 27 Sep 05:39:29 | Text console after an unattended boot: `Fedora 44 on Mac16,12/J713`, `root (automatic login)`. The value after `password fallback:` on both lines (the test root's console password) is covered with a dark box in this copy; nothing else was altered. |
