# 2.2 From missing firmware to a moving trackpad cursor

28–29 September 2026, with follow-up until 7 October.

After [B2](02-input-mtp.md) the internal keyboard worked and the trackpad clicked, but it did not move the
pointer. At first KDE saw my USB keyboard, a Lucky65 V3, as the mouse.

## The firmware it asked for

The B2 log shows the trackpad asking for `apple/tpmtfw-j713.bin` and
[failing with -2](../evidence/02-input/logs/b2-kernel.txt#L664). I took the firmware from this machine's own
macOS: the `Multitouch.img4` in its Preboot volume, converted with Gravity's existing `MultitouchFWCollection`
converter. The [extraction record](../evidence/02-input/trackpad/firmware-extraction.txt) has the hashes; the firmware is Apple's and is
not in this repository. I installed it on the Fedora root and changed nothing else.

With the firmware in place, the [journal](../evidence/02-input/trackpad/journal-timeline.txt#L25) shows the interface starting, the
firmware being sent, a reset, and "Touch MT ready". In debugfs I watched 68-byte HID reports with ID `0x75`
change as I touched the trackpad. The data was arriving. Nothing turned it into a pointer: no driver claimed
it, so the kernel used `hid-generic`.

## Two config symbols

The decoder already existed. [`hid-magicmouse`](https://github.com/X6e3/j713-linux/blob/cb738fe4f905f40b25e7d486c98656948bd4e1ef/drivers/hid/hid-magicmouse.c) handles this report, and
[`hid-apple`](https://github.com/X6e3/j713-linux/blob/cb738fe4f905f40b25e7d486c98656948bd4e1ef/drivers/hid/hid-apple.c) the keyboard side. I enabled both (B3):

```text
CONFIG_HID_APPLE=y
CONFIG_HID_MAGICMOUSE=y
```

I enabled the keyboard driver as well, not only the trackpad's. Both sit under the same MTP parent, and leaving
the keyboard without its driver would have changed the system I was testing. The [config diff](../evidence/02-input/trackpad/b3-config.diff)
contains exactly these two symbols; the [build manifest](../evidence/02-input/trackpad/b3-manifest.txt) shows the rest of the image
unchanged.

## The first B3 boot: still no pointer

libinput could not open the trackpad: `Operation now in progress`. Following the open path into the
[DockChannel HID driver](https://github.com/X6e3/j713-linux/blob/cb738fe4f905f40b25e7d486c98656948bd4e1ef/drivers/hid/dockchannel-hid/dockchannel-hid.c) showed where that came from: a previous start
was still marked as running. The real failure came earlier, and the [journal](../evidence/02-input/trackpad/journal-timeline.txt#L115)
shows it:

```text
Firmware sent and reset
→ Failed to attach to AFE
→ No HINT_L
→ AFE[0] bootload failed
→ no READY
→ start timed out
→ later opens: already starting / EINPROGRESS
```

The AFE is the trackpad's analog front end. If MTP cannot boot it, nothing above it can work. A patch that
retried the open was ready; I decided not to build it, because waiting differently could not start an AFE that
never reported READY. I read the journals first instead. Of the seven B2 boots with the firmware, five reached
READY about 235–238 ms after reset and two failed to attach to the AFE. Same kernel, different result.

## The cursor

On a later boot of the same B3 image the AFE started. Multi-touch reached READY, the keyboard kept working,
and I moved the KDE cursor with the internal trackpad. I recorded it that night but not its boot ID, so I do not
tie it to a journal block.

## Reboots

That night no reboot finished on its own. Shutdown went as far as the NVMe and stopped, and each time I held
the power button. Sometimes an MTP crash report (`Crtk`) appeared on the way down. I tried to find what
triggered it, one variable at a time: a text console or the desktop, touching the trackpad or not
([notebook](../evidence/02-input/trackpad/notebook-20260929.md)). None of them alone triggered it, and it did not happen every time.
The crash report is still open; it does not stop the next boot.

## October

On 2 October I added a [bounded reset retry](https://github.com/X6e3/j713-linux/commit/3ef84e7cbcd64a54930a7d87ef18f458f95d9f76): up to three READY
windows, with the existing reset states repeated between them. On 4 October I added
[logging of the interface's GPIO declarations](https://github.com/X6e3/j713-linux/commit/08c88cc2ed18933bd5da3d6fd0e6c8e689af8d33) to see what the
firmware announced. Neither fixed it. On 7 October one boot [still failed](../evidence/02-input/trackpad/afe-fail-20261007.txt#L105) after
both retries while another [reached READY](../evidence/02-input/trackpad/afe-ready-20261007.txt#L104); their kernels differ, so they are
not a controlled pair.

For three weeks my workaround was a quick forced reboot after the first boot; on the second boot the trackpad
came up. That turned out to be the clue; the fix is [section 2.3](02-input-afe.md).

## What this does and does not show

- The two-symbol change, the AFE failure chain and the seven-boot count come from the retained journal records
  and archived build files.
- The changing raw reports and the cursor movement are my own observations; their raw output was not kept.
- AFE start was not reliable in this period. Gestures, haptics driven from Linux, suspend and a clean shutdown
  are not covered.

Apple wrote the firmware. The converter and the HID decoders were existing work, and Josh Rodd's MTP changes
gave the driver support. My part was finding what J713 needed, preparing its firmware, isolating the
configuration, tracing the failed open back to the AFE, and testing it on the machine, keeping the failing boots
as well as the working ones.

## Evidence

- [Firmware extraction record](../evidence/02-input/trackpad/firmware-extraction.txt): hashes only, no firmware.
- [Journal timeline](../evidence/02-input/trackpad/journal-timeline.txt): B2 boots before and after the firmware, and the first B3 boot.
- [B3 config diff](../evidence/02-input/trackpad/b3-config.diff) and [build manifest](../evidence/02-input/trackpad/b3-manifest.txt).
- October exports: [failure](../evidence/02-input/trackpad/afe-fail-20261007.txt), [success](../evidence/02-input/trackpad/afe-ready-20261007.txt).
- [Notebook page, 29 September](../evidence/02-input/trackpad/notebook-20260929.md).
- The [manifest](../evidence/02-input/trackpad/manifest.json) lists each file's source and hashes. `make trackpad` regenerates the
  [timeline summary](../data/02-input/trackpad_summary.json); `make check` verifies the hashes, line counts and
  the derived timeline.
