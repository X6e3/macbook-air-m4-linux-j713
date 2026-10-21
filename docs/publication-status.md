# Publication status

Last updated: 21 October 2026.

## The two repositories

- **macbook-air-m4-linux-j713** (this repository) is the record: logs, device trees, analysis scripts and figures,
  one subsystem at a time. It contains no kernel source, no boot images and no firmware.
- **[j713-linux](https://github.com/X6e3/j713-linux)** holds the kernel changes behind these records, as a commit
  series on top of GravityLinux's M4 kernel (base `3b85d81f656a`). Commits by other authors keep their original
  authorship and messages.

## System status (through 19 October 2026)

Kernel `7.1.13-x6e3-s2` on Fedora 44, built from the tip of the j713-linux series. The first boot, the
[MTP startup records](02-input-mtp.md), the [trackpad continuation](02-input-trackpad.md) and the
[Wi-Fi account](03-wifi.md) are recorded here; the GPU, display, audio and idle records will follow.

| Area | Status | Notes |
|---|---|---|
| CPU cores | Working | All ten cores online (four performance, six efficiency). |
| Storage | Working | Fedora 44 from an ext4 root filesystem on the internal NVMe. |
| Desktop | Working | KDE Plasma on the internal display. |
| Internal display | Working | Native, through the display controller (DCP): 2560×1600 at 60 Hz. The DCP node now holds the display PHY's power domain, so the PHY is no longer switched off after boot. The driver started 26.6-firmware panels at zero brightness; the series starts them at 30%. |
| GPU rendering | Working, local Mesa fix | KWin renders on the M4 GPU (`Apple M4 (G16G B1)`), and glmark2-es2-wayland completed its full suite on the native display. Mesa is GravityLinux's `26.3.0~devel-103` with a local fix for compressed textures, installed by replacing one library file rather than as a package; a Mesa package update would overwrite it. |
| External displays | Not working | The external display controllers (dcpext) stay disabled: when the bootloader enabled them, the boot stalled. |
| Keyboard and trackpad | Working | The trackpad used to fail on the first boot after macOS, because its analog front end (AFE) stayed in the state macOS left it in. The series now applies the AFE power sequence from the device's ADT before sending firmware; the trackpad started on the first attempt in both cold boots after macOS tested on 18 October 2026. At shutdown, the MTP coprocessor can leave a crash report that Linux does not fully parse; shutdown still completes. |
| Wi-Fi | Working | |
| Bluetooth | Working | Music playback over Bluetooth headphones was confirmed in a user test. |
| Speakers | Partly working | Both woofers play in stereo through their two TAS2764 amplifiers, behind a −30 dB volume ceiling and the thermal limiter of the Mac mini driver; J713's own speaker-protection parameters are unknown. The audio controller (MCA) layout was read from J713's own audio-coprocessor firmware. The tweeters stay disabled: without a crossover they could be damaged. |
| Headphone jack | Not working | The jack codec needs a bit clock that only the audio NCO can produce, and the NCO is not described in the ADT. |
| Microphones | Not working | Not started. |
| Camera | Not working | The kernel has no Apple ISP driver. |
| Suspend | Not validated | |
| CPU idle | Experimental, opt-in | WFI through a J713 path added to Asahi's cpuidle-apple driver, enabled with `cpuidle_apple.j713_deepwfi=1`. It also works alongside the native display. |
| CPU frequency scaling | Not active | The driver is built as a module, and no kernel modules are installed (checked on 18 October 2026). |
| Reboot | Working | |
| Power-off | Restarts instead | Power-off goes through the SMC. Without the PMU shutdown flag, the SMC restarts the machine instead, as the driver's own comment predicts. Setting that flag means writing PMU NVMEM, and that work is parked. Before 18 October, power-off hung. |
| RTC | Not active | The device tree lacks the RTC's PMU NVMEM description. The PMU research is parked. |

## Kernel source

j713-linux has 33 commits on GravityLinux's M4 kernel. The first 19 reproduce the tree of the kernel recorded on
15 October 2026 (`85fe15f109379e80e8a16e176abd7aaef0860236`). The next three restrict two board-specific changes, the
framebuffer power domain and the MTP DART DAPF programming, to J713, and add that repository's README, status and
evidence notes. The last 11 add a GPU queue-priority clamp for G16, the native display, the trackpad AFE power
sequence, SMC power-off, stereo woofers and the matching configuration (`configs/j713-s2e.config`). The tree at the tip
is identical, file for file, to the source of the kernel booted on 19 October 2026, and the configuration equals that
build's.

## Kept out of both repositories

Apple firmware (Wi-Fi, Bluetooth, trackpad), boot images (their initramfs layers contain that firmware) and device
identifiers.
