# 5. The internal display through DCP

18 October 2026. J713, 2560×1600 at 60 Hz below the notch.

The GPU was rendering, but simpledrm still put the picture on the panel through the boot framebuffer. I wanted
the display controller, DCP, to drive the panel itself. My first DCP images stalled during startup; the next
ones reached Linux with a black screen. Those turned out to be two separate problems.

The Apple DRM driver from Asahi and Gravity already handles RTKit, DCP's services and KMS, and the base includes
Josh Rodd's J715 panel support for 26.6 firmware. The J713 changes select the internal path, describe the
panel, start it at a nonzero brightness and keep the display PHY powered after the boot framebuffer goes away.
The [source notes](../evidence/05-display/source-notes.md) separate them from the existing driver.

## D4: leave the external controllers out

My device tree had the external DCP nodes disabled, but the bootloader turns them on when their aliases exist.
I removed the `dcpext0` and `dcpext1` aliases so that only the internal controller would start.

[D4](../evidence/05-display/d4-kernel.txt) reached `DCP booted`, selected 2560×1600 at 60 Hz, registered
`appledrmfb` and ran `/init`. The stall was gone, but the screen stayed black. Why the external controllers
stalled the boot I did not test; DAPF setup and power domains are both still possible.

## D5: brightness was zero, and something else

D4 logs `brightness value: 0` and `dbv: 0`. With 26.6 firmware the driver no longer receives an initial
brightness, so it starts at zero on purpose and leaves the rest to userspace. The J713 change starts the panel
at 30% of the panel description's 500-nit maximum, a 150-nit request.

[D5](../evidence/05-display/d5-kernel.txt) logged the nonzero value, but the desktop still did not appear. Right
after the kernel disabled unused power domains, a DPTX FIFO error showed up. D5 was also built with Rust 1.99.0
instead of 1.98.1, so D4 to D5 was not a single-variable change.

## D6–D8: the PHY lost its power during the handover

[D6](../evidence/05-display/d6-kernel.txt) added `pd_ignore_unused`. The log shows that it took effect, and the
FIFO error stayed anyway. On this kernel the provider's `of_genpd_sync_state` path can still switch a domain
off; `pd_ignore_unused` only guards the unused-domain worker.

The DPTX PHY's power domain was held by the boot framebuffer, not by DCP. When appledrm takes over, it removes
the conflicting framebuffer device before registering its own. The last reference to the PHY's domain went with
simpledrm while DCP still needed it. [D7](../evidence/05-display/d7-kernel.txt) tested that by marking
`dptx_phy` always on. The FIFO error disappeared and I had the desktop on the panel.

Always-on was only a diagnostic. [D8](../evidence/05-display/d8-kernel.txt) dropped it and gave `ps_dptx_phy` to
the DCP node's `power-domains` instead. The display still worked, with no FIFO error in the log.

| Image | Brightness request | PHY handling | FIFO error lines |
| --- | --- | --- | ---: |
| D4 | Zero | No DCP reference | 1 |
| D5 | 30% | No DCP reference | 1 |
| D6 | 30% | `pd_ignore_unused` | 1 |
| D7 | 30% | Diagnostic `always-on` | 0 |
| D8 | 30% | Domain assigned to DCP | 0 |

The [image-part hashes](../evidence/05-display/image-parts.json) show that D5, D7 and D8 use the same stage2 and
kernel/initramfs bytes and the same arguments apart from the image label; only the device tree changes between
them. D6 adds the power-management argument.

## Mode and notch

The [D8 log](../evidence/05-display/d8-kernel.txt) reports a 64-pixel notch and selects 2560×1600 at 60 Hz, with
a pixel clock of 277042 kHz, totals of 2640×1749 and `vrr:0`. The panel itself is 2560×1664, which also appears
in a firmware surface message and in [Apple's specifications](https://support.apple.com/en-gb/122209). The two
numbers agree: unless `show_notch` is set, the driver's mode parser subtracts `apple,notch-height` from the
active height, and the swap path places the picture below the notch. J713's device tree supplies the 64 pixels.

In D8, simpledrm registers at 0.046 s, Apple DRM at 0.223 s, the panel mode is selected at 0.225 s, and AGX
registers its DRM device at 1.230 s. An early `Creating default FB surface failed` warning is in the log; the
display initialised after it in the same boot.

## The daily image

N1 carried the D8 arrangement into the daily kernel. Its [boot lines](../evidence/05-display/n1-kernel-selected.txt)
show the native mode, the appledrm framebuffer and the opt-in WFI path in the same boot.

On D8 I ran the full glmark2-es2-wayland suite in an 800×600 window. It finished with a score of 3427
([transcription](../evidence/05-display/observations.md)). Later I played games on N1. The
[SuperTuxKart log](../evidence/05-display/n1-stk.log) identifies the M4 renderer and records the black_forest
benchmark: 4,414 frames in 38.141 s, with the game's Typical / Mostly Steady / Steady figures at 108 / 91 / 55 FPS.
The result screen shows a 2560×1470 window at 100% render resolution, dynamic lighting on, and anti-aliasing,
image-based lighting, ambient occlusion and shadows off. The log also says `--gfx-preset=2` was invalid, so that
option did not set those values.

## What this does and does not show

The cause of the external-controller stall is untested, and D4 to D5 changed the compiler as well as the
brightness. 150 nits is a request to the firmware, not a light measurement. The glmark2 and SuperTuxKart
numbers are rendering results, not panel refresh.

External displays stay disabled. This covers J713's internal panel, not display support on every M4 machine,
and it does not cover long-term reliability or suspend.

Apple wrote the DCP firmware. The driver is Asahi's and Gravity's, with Josh Rodd's panel support. My part was
separating the stall from the black screen, tracking down the brightness and PHY power causes, and the D4–D8
tests.

## Evidence

- Kernel logs: [D4](../evidence/05-display/d4-kernel.txt), [D5](../evidence/05-display/d5-kernel.txt),
  [D6](../evidence/05-display/d6-kernel.txt), [D7](../evidence/05-display/d7-kernel.txt),
  [D8](../evidence/05-display/d8-kernel.txt), [N1 boot lines](../evidence/05-display/n1-kernel-selected.txt).
- [Image-part hashes](../evidence/05-display/image-parts.json) for the D5/D7/D8 comparison.
- [SuperTuxKart log](../evidence/05-display/n1-stk.log) and the [screen transcriptions](../evidence/05-display/observations.md);
  the photographs stay private.
- [Source notes](../evidence/05-display/source-notes.md) and the [manifest](../evidence/05-display/manifest.json).
  The logs are copies with identity substitutions; no boot image or firmware is included. `make later-stages`
  regenerates the [summary](../data/04-07-summary.json), including the FIFO counts and the D5/D7/D8 comparison.
