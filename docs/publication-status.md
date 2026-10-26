# Publication status

Last updated: 26 October 2026.

## The two repositories

- **macbook-air-m4-linux-j713** (this repository) is the record: logs, device trees, analysis scripts and figures,
  one subsystem at a time. It contains no kernel source, no boot images and no firmware.
- **[j713-linux](https://github.com/X6e3/j713-linux)** is the companion kernel repository. Its first commit imports
  GravityLinux's M4 kernel (base `3b85d81f656a`) unchanged, and the J713 series follows. Commits by other
  authors keep their original authorship and messages.

## System status

The functional results below are from S2e on 19 October 2026, running Fedora 44.
The later LIM2 thermal test on 23 October used kernel `7.1.13-x6e3-pri1` with a
revised thermal DTB. That kernel string alone does not identify the full source or image. The first boot, the
[MTP startup records](02-input-mtp.md), the [trackpad continuation](02-input-trackpad.md) and the
[Wi-Fi account](03-wifi.md) are followed by the [GPU](04-gpu.md), [display](05-display.md),
[audio](06-audio.md) and [idle](07-idle.md) records.

| Area | Status | Notes |
|---|---|---|
| CPU cores | Working | All ten cores online (four performance, six efficiency). |
| Storage | Working | Fedora 44 from an ext4 root filesystem on the internal NVMe. |
| Desktop | Working | KDE Plasma on the internal display. In normal use the counter reaches 60 FPS, sometimes 61; games run normally. The approximately 30 FPS observation was under the synthetic GPU stress load. |
| Internal display | Working | Through DCP: 2560×1600 at 60 Hz below the 64-pixel notch; physical panel 2560×1664. The DCP node now holds the display PHY's power domain, so the PHY is no longer switched off after boot. The driver started 26.6-firmware panels at zero brightness; the series starts them at 30%. |
| GPU rendering | Working, local Mesa fix | KWin renders on the M4 GPU (`Apple M4 (G16G B1)`), and glmark2-es2-wayland completed its full suite on the native display. Mesa is GravityLinux's `26.3.0~devel-103` with a local fix for compressed textures, installed by replacing one library file rather than as a package; a Mesa package update would overwrite it. |
| GPU thermal control | Tested in LIM2 | A thermal zone uses SMC TVS1 at 45 °C and the GPU firmware's CLTM P-state limit, with the lowest allowed cap P3. From the first nonzero cooling state through the end of the 20-minute run, TVS1 measured 44.77–45.11 °C. [Section 4](04-gpu.md) defines the sample window and links the raw evidence. |
| External displays | Not working | The external display controllers (dcpext) stay disabled: when the bootloader enabled them, the boot stalled. |
| Keyboard and trackpad | Working | The trackpad repeatedly failed to start its analog front end (AFE) on the first Linux boot after macOS. The underlying AFE state was not directly measured. The series now applies the AFE power sequence from the device's ADT before sending firmware; the trackpad started on the first attempt in both cold boots after macOS tested on 18 October 2026. At shutdown, the MTP coprocessor can leave a crash report that Linux does not fully parse; shutdown still completes. |
| Wi-Fi | Working | |
| Bluetooth | Working | I played music over Bluetooth headphones. |
| Speakers | Partly working | Both woofers play in stereo through their two TAS2764 amplifiers, behind a −30 dB volume ceiling and the thermal limiter of the Mac mini driver; J713's own speaker-protection parameters are unknown. The tested `snd_t8132_speaker.ceiling_dvc=60` boot argument selects −30 dB; the source default is −10 dB. The audio controller (MCA) layout was read from J713's own audio-coprocessor firmware. The tweeters stay disabled: without a crossover they could be damaged. |
| Headphone jack | Not working | The retained macOS route uses an audio NCO; the corresponding clock description/control path is missing in this Linux setup. |
| Microphones | Not working | Not started. |
| Camera | Not working | The kernel has no Apple ISP driver. |
| Suspend | Not validated | |
| CPU idle | Experimental, opt-in | WFI through a J713 path added to Asahi's cpuidle-apple driver, enabled with `cpuidle_apple.j713_deepwfi=1`. It also works alongside the native display. |
| CPU frequency scaling | Not active | The driver is built as a module, and no kernel modules are installed (checked on 18 October 2026). |
| Reboot | Working | |
| Power-off | Restarts instead | Power-off goes through the SMC. The restart is consistent with the driver's documented behaviour when the PMU shutdown flag is missing; the flag itself has not been read back. Setting that flag means writing PMU NVMEM, and that work is parked. Before 18 October, power-off hung. |
| RTC | Not active | The device tree lacks the RTC's PMU NVMEM description. The PMU research is parked. The time is still right in normal use, because NTP sets it once Wi-Fi connects; before that it starts wrong, as the panel clock in the 27 September desktop photo shows. |

## Kernel source

The runtime-source checkpoint is `03f9eeaebba4`, 35 commits on GravityLinux's M4
kernel. The first 19 reproduce the recorded audio0 baseline tree
(`ce4dee3c894ca7bcb8de99afee306851cf789e74`). Two scope commits follow.
The next 11 add the GPU clamp, native display, AFE power sequence, SMC power-off,
stereo woofers and `configs/j713-s2e.config`; that S2e source checkpoint is
`9f1bdfa7baf3`. Its recorded tree and configuration comparison matched the
19 October build.

The last three runtime-source commits add the cooling device, privileged queue
priority and the TVS1 thermal DT. KWin's actual queue class was not recorded in
LIM2, so the priority change is not treated as a measured explanation for desktop
FPS. The approximately 30 FPS observation was specific to the synthetic stress workload;
normal desktop use reaches 60–61 FPS on the counter, and games run normally. I have not yet built and booted
the kernel from the current publication checkout.

## Kept out of both repositories

Apple firmware (Wi-Fi, Bluetooth, trackpad), boot images (their initramfs layers contain that firmware) and device
identifiers.
