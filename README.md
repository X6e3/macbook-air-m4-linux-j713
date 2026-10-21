# Linux on the M4 MacBook Air (J713)

This repository documents my work on Linux support for the 13-inch
M4 MacBook Air (2025, J713/T8132). It contains hardware investigations,
test results, and the logs and scripts behind them. The device-tree and
driver changes are in [`X6e3/j713-linux`](https://github.com/X6e3/j713-linux).

I started on 26 September 2026, building on Asahi Linux's m1n1, kernel
drivers and documentation, and GravityLinux's M4 kernel, installer
and Mesa.

As of 19 October 2026, Fedora 44 runs from the internal NVMe with all
ten CPU cores online. KDE Plasma uses the M4 GPU for compositing,
and the display controller (DCP) drives the internal display at
2560×1600, 60 Hz. The full glmark2 suite completes, and games run with
hardware acceleration. The internal keyboard and trackpad, Wi-Fi,
Bluetooth and both woofers also work.

Suspend, power-off, the headphone jack, the microphones and the camera
do not work yet. The full list is in
[`docs/publication-status.md`](docs/publication-status.md).

This is a development record, not an installer or a supported distribution.

Each section below says what I observed, what I changed and held constant, how I tested it, and what the result does
and does not show. The logs, device trees and scripts behind every figure are in this repository.

For the first-night evidence, start with the [boot comparison](data/01-first-boot/boot_ab_summary.json),
[device-tree comparison](data/01-first-boot/dtb_diff.txt), [image-part hashes](evidence/01-first-boot/image-parts.csv)
and [original boot logs](evidence/01-first-boot/logs/). The [A1/B1/B2 MTP startup records](docs/02-input-mtp.md)
follow in section 2, with the [trackpad firmware and HID investigation](docs/02-input-trackpad.md).
Records for the GPU, the native display, audio and idle remain to be added.

The [Wi-Fi account](docs/03-wifi.md) follows in section 3: PCIe/configuration, J713 firmware identity,
the early-firmware layer and a real connection from Fedora.

## 1. First boot (26–27 September 2026)

I started working on J713 because I wanted Linux running directly on my M4 MacBook Air, not inside a virtual machine.
There wasn't a ready-to-use Linux installation path for this particular machine in the projects I was working with.
Gravity's M4 kernel gave me a starting point, but the J713 device tree was still a small board stub, and the installer
didn't recognise the 13-inch MacBook Air.

I built on the existing work from Asahi Linux and Gravity Linux, adapting the boot configuration and working through
the hardware-specific problems as they appeared.

The first challenge wasn't simply getting the kernel to execute. Linux was already running, the initramfs had
started, and all ten ARM64 CPU cores were online. But the framebuffer console was taking roughly ten seconds to
attach.

The kernel logs pointed towards a power-domain attachment failure. Rather than treating this as a general boot
performance problem, I started investigating the relationship between the framebuffer configuration and the display
power domains in the device tree.

I tested different configurations across 21 boot attempts. For the controlled comparison, I kept m1n1 and the
kernel/initramfs byte-identical, changing only the relevant device-tree configuration. Switching the framebuffer
power-domain reference from `disp_cpu` to `disp_fe` reduced the measured console attachment time from approximately
10.23 seconds to 0.06 seconds.

That was a 170-fold difference in console attachment time, not a 170-fold improvement in total system boot time. I
also returned to the previous configuration for control runs rather than relying on a single successful boot.

By the early morning of 27 September, I had Fedora 44 running with KDE Plasma on the MacBook Air's internal display.

It was far from a complete port. Graphics were still using software rendering through `llvmpipe` and the existing
framebuffer. Hardware GPU acceleration, internal input devices, wireless connectivity, audio and several other
platform components still required further work.

By 28 September, I had also verified Fedora running from a persistent ext4 root filesystem on the internal NVMe.

Getting to a desktop was an important milestone, but it wasn't the end of the work. The next challenge was making
the hardware around that desktop functional, understanding the dependencies between its components, and turning the
individual experiments into a usable Linux system.

This repository documents that process, including the unsuccessful experiments, the changes that produced measurable
results, and the limitations of what each test actually demonstrates.

<!-- fig01:begin -->
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
<!-- fig01:end -->

## 2. Keyboard and trackpad (28 September – 7 October 2026)

### 2.1 MTP startup (28 September)

I traced the failing internal-input path through A1 (read-only DAPF snapshot), B1 (program the board's
rules) and B2 (remove the experimental RUN-to-wake delay). The [full account](docs/02-input-mtp.md)
links each observation to the retained kernel exports and the corresponding source changes.

| Record | DAPF readback | MTP result |
| --- | --- | --- |
| [A1](evidence/02-input/logs/a1-kernel.txt) | 0/9 before programming | Endpoint-map timeout; wake -62; IRQ count 100005 at return |
| [B1](evidence/02-input/logs/b1-kernel.txt) and [repeat](evidence/02-input/logs/b1-repeat-kernel.txt) | 8/9 after programming | Protocol v12, then IOP power ACK timeout; wake -62 |
| [B2](evidence/02-input/logs/b2-kernel.txt) | 8/9 after programming | Wake 0, MTP Says Hello, keyboard ready; trackpad firmware still missing in this boot |

These are complete archived kernel-export copies with identity substitutions, not newly run tests.
The [manifest](evidence/02-input/manifest.json) records original/published hashes and the redactions.
The [analysis](analysis/mtp.py) derives the [summary](data/02-input/mtp_summary.json) from the logs.
Reproduce with `make mtp`; verify with `make check`.

### 2.2 Trackpad firmware and HID (28–29 September, with October follow-up)

I prepared the J713 firmware through the existing Gravity converter, then enabled the existing MTP HID
decoder and keyboard driver in a two-symbol configuration experiment. A later boot of that same artifact
produced physically confirmed internal-trackpad cursor movement. Intermittent AFE startup remained a separate
problem. The [full account](docs/02-input-trackpad.md) distinguishes retained journal records, archived build
metadata and my own observations at the machine. It includes the later reset-retry attempt and its limits.
Reproduce the [selected timeline](data/02-input/trackpad_summary.json) with `make trackpad`; verify with `make check`.

### 2.3 AFE power sequence (18 October)

On the first boot after macOS the trackpad's analog front end (AFE) did not start; after a Linux reboot it did.
Every boot that followed an image change, and so followed macOS, failed: 7 of 7. The reset line, the startup chime
and cold power were each ruled out. macOS power-cycles the AFE for 50 ms before every bootload, and the J713 ADT
describes the same `power-sequence`. With that sequence in the driver, the trackpad started on the first attempt
on the first boot after macOS. The [full account](docs/02-input-afe.md) lists what the evidence does and does
not show.

## 3. Wi-Fi (2 October 2026)

I followed the device from PCIe enumeration through the bin-only failure and the successful complete J713
firmware environment. I made that environment available during early boot, incorporated Michael Reeves's
join-preference fallback, and provisioned the missing networking userspace. Retained photos show a connection,
DHCP routing, DNS and package downloads. The [full account](docs/03-wifi.md) links the failure/success records,
archived build metadata and identifier-free photo observations. Regenerate its summary with `make wifi`.

## How this repository is organised

```
evidence/   what the machine produced: per-boot logs, DTBs, image part hashes, photos (metadata removed)
analysis/   scripts that turn evidence into data; they check the evidence and stop on a contradiction
data/       the numbers and diffs the figures use
figures/    one script per figure, plus style.py shared by all of them; output in figures/out/
tools/      rasterising, README captions, the identity/secret scan
docs/       current support, known limits and the scope of the two repositories
```

`make fig01` rebuilds Fig. 1 from `evidence/`. `make check` runs before every commit: it refuses
device identifiers and secrets, checks that the first-boot logs match the original bytes, and verifies the
published hashes, source lineage and derived summaries of sections 2 and 3.
Boot images are not published: later initramfs layers contain vendor firmware. Their part hashes are
in `evidence/01-first-boot/image-parts.csv`.

## License

- Code (`analysis/`, `figures/*.py`, `tools/`, `Makefile`, `evidence/01-first-boot/init-busybox-v6`): MIT, see `LICENSE`.
- Text, data, figures and photos (`README.md`, `docs/`, `data/`, `figures/out/`, `evidence/01-first-boot/photos/`,
  `evidence/01-first-boot/image-parts.csv`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The DTBs in `evidence/01-first-boot/dtb/` are compiled from the GravityLinux and Asahi Linux device-tree sources for T8132
  and J713 (SPDX: `GPL-2.0+ OR MIT`), with the J713 changes described in section 1. They are not relicensed here.
- The boot logs in `evidence/01-first-boot/logs/` are the machine's console output, published unchanged as evidence.
- The section 2 logs are identity-redacted evidence copies with original/published hashes in their manifest. The source
  excerpt in `evidence/02-input/bootloader-context.txt` retains its original MIT license.
