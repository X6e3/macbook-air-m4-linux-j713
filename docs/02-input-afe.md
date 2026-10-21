# 2.3 The AFE power sequence

18 October 2026.

After the display worked natively, I went back to the trackpad. I did not want to keep plugging in a mouse;
that day I did not even have one. I had solved DAPF, so why not this.

First boots had been unreliable since the first night; my notebook lists first and second boots separately for
that reason. That is a separate problem. This one was specific: on the first boot after macOS the trackpad did
not start, and after a quick Linux reboot it did. For three weeks that reboot was my workaround.

## The pattern in the journal

I write every image to the ESP from macOS, so a boot that runs a different image from the one before is always
a first boot after macOS. In the [15 boots of 15–18 October](../evidence/02-input/afe/before/), all 7 such boots failed with
"Failed to attach to AFE" and "No HINT_L". Of the 8 boots that repeated the previous image, 6 started the
trackpad and 2 did not; those two probably followed macOS as well, but the journal cannot show it.
The reset retry from October failed the same way on every attempt.

## Three ideas that were wrong

**The reset line.** The ADT gives the AFE a reset line through the SMC. I logged its level before the start and
released it (N2). It read the same on the failing first boot after macOS and on the working reboot right after
([IMG_0181 and IMG_0182](../evidence/02-input/afe/photo-transcriptions.md)). The level was not the difference.

**The startup chime.** The chime plays at power-on, and that has a cost; I wondered whether it left the AFE in a
bad state. I muted it and cold-booted. The trackpad still failed.

**Cold power.** If the cause were simply starting from power-off, a Linux power-off followed by a power-on would
fail too. I ran it in this order: first boot after macOS (failed), reboot (worked), power off from Linux,
power on straight into Linux. Linux could not power the machine off yet, so I held the power button. The
trackpad worked. The difference was not cold power but what macOS leaves behind when it shuts down.

The chime and power-off tests are my observations; their logs are not in this repository yet.

## What macOS does

macOS's own log for two of its boots that day showed the order: it powers the trackpad interface off, powers it
back on about 50 ms later, and only then bootloads the AFE. I did not keep that log. The ADT says the same thing:
the multi-touch node's `power-sequence` is `function-afe-reset`, level 0, 50 ms, level 1
([ADT excerpt](../evidence/02-input/afe/adt-multitouch.txt)). Linux never ran it.

## The fix

N3 does what the ADT says, once, before it sends the firmware: the line goes low for 50 ms, then high for 50 ms
([driver](https://github.com/X6e3/j713-linux/commit/34145116ac02f300a5e956c567fe004ede072ab6), [device tree](https://github.com/X6e3/j713-linux/commit/1ba89fda006e77e68ae64312356517a63b08e906)).
Nothing else changed.

On the first boot after macOS the trackpad came up on the first attempt. The 124 ms between the
reset line's log entry and the firmware is the pulse, and READY followed at 4.70 s
([IMG_0183](../evidence/02-input/afe/photo-transcriptions.md)). N4, built on N3, did the same at 4.66 s
([IMG_0184](../evidence/02-input/afe/photo-transcriptions.md)). Before the fix, that kind of boot had failed 7 times out of 7.

## What this does and does not show

- Two first boots after macOS with the fix, against 7 without it. The numbers are small; the contrast is what
  counts. Later boots with the fix are in Fedora's journal and can be added.
- The chime and power-off tests are my observations.
- Why the AFE needs the pulse after macOS and not after a Linux reboot, I do not know. macOS runs the sequence on
  every boot; now Linux does too.

## Evidence

- [Boots of 15–18 October](../evidence/02-input/afe/before/): the MTP and AFE lines of each boot, oldest first.
- [Screen photographs of 18 October](../evidence/02-input/afe/photo-transcriptions.md), transcribed; the photographs are kept private.
- [ADT excerpt](../evidence/02-input/afe/adt-multitouch.txt): the multi-touch node's reset function and sequences.
- The [manifest](../evidence/02-input/afe/manifest.json) records the sources, hashes and masking. `make afe` regenerates the
  [summary](../data/02-input/afe_summary.json); `make check` verifies the hashes, each boot's outcome and the
  photographs' timings.
