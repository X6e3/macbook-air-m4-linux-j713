# 2.2 From missing firmware to a moving trackpad cursor

28–29 September 2026, with AFE follow-up from 2–7 October. MacBook Air 13-inch M4 / J713 / T8132.

After the [B2 MTP startup experiment](02-input-mtp.md), I could use the internal keyboard, but the trackpad still did not move the KDE cursor. I followed the remaining path in stages: the board-specific firmware, raw HID reports, the driver that decodes those reports, and the interface's READY/open lifecycle.

The evidence is not all the same kind. The retained journal timeline shows firmware requests, reset, READY and AFE errors. Archived build files identify the configuration experiment. Raw-report changes, sysfs bindings and the physical cursor movement are my own observations at the machine; their raw output was not kept.

## 1. Give the driver the firmware it actually requests

The early B2 export requests `apple/tpmtfw-j713.bin` and [fails with error -2](../evidence/02-input/logs/b2-kernel.txt#L664). Creating a multi-touch HID device was not enough to make its firmware start.

I obtained the source from this J713's own macOS Preboot FUD `Multitouch.img4`. I used the existing, unmodified Gravity `MultitouchFWCollection` converter from installer commit `6420623289fe7544cb8589b658355e57f0290fcc`. The [preserved extraction receipt](../evidence/02-input/trackpad/firmware-extraction.txt) records:

| Item | Recorded result |
| --- | --- |
| Source system | macOS 27.0, build 26A428 |
| Source IMG4 | 118962 bytes; SHA-256 `e1d897a345eee46afb4f2d228c6b7ab6d5ed5371f1a283306ecab535f507e9f3` |
| IM4P | type `mtfw`; 111535 bytes; SHA-256 `f27e6714b952598ec525581029e33524d235a8e3c8d361fa6a142b5984dce53f` |
| Output | `apple/tpmtfw-j713.bin`; 80524 bytes |
| Output SHA-256 | `9fcbef0cff6a3b7733a4df626c9eba859b66c8e5053557924b8020a67ef48b17` |

The personalized IM4M manifest was not extracted. The firmware itself is not included here. These are historical extraction results, not a new extraction or a new hardware test.

I installed the generated file at `/lib/firmware/apple/tpmtfw-j713.bin` in the Fedora root filesystem. In the captured B2 boot, the request happened after the root filesystem was mounted, when userspace opened the device. This experiment did not require changing the initramfs, kernel, DTB or bootloader.

## 2. Establish that the firmware and raw data path are alive

With the same B2 kernel and the firmware added, the [archived journal timeline](../evidence/02-input/trackpad/journal-timeline.txt#L25) shows successful boots progressing through:

```text
Starting interface multi-touch
Sending firmware for multi-touch
Resetting multi-touch
New AFE[0] cbor image received
Interface multi-touch is now ready
Touch MT ready
```

I also saw changing 68-byte HID reports with report ID `0x75` in a debugfs capture while touching the trackpad. That capture was not kept.

The B2 configuration did not enable `CONFIG_HID_MAGICMOUSE`, and the device was using `hid-generic`. Firmware acceptance and changing raw reports therefore established progress through the transport and HID core, but had not yet produced a working pointer.

## 3. Enable the existing MTP report decoder without losing the keyboard

I inspected the HID paths in the B2 source. [`hid-magicmouse`](https://github.com/X6e3/j713-linux/blob/48100bc278cf81b30c33aa501a40662e39473ebc/drivers/hid/hid-magicmouse.c) already had the BUS_HOST MTP path and report ID `0x75`. Its probe accepts the mouse-type child. [`hid-apple`](https://github.com/X6e3/j713-linux/blob/48100bc278cf81b30c33aa501a40662e39473ebc/drivers/hid/hid-apple.c) provides the corresponding keyboard-type path.

That meant the next experiment was a configuration change. I did not write a new report decoder. I enabled both drivers:

```text
CONFIG_HID_APPLE=y
CONFIG_HID_MAGICMOUSE=y
```

The [archived B2-to-B3 diff](../evidence/02-input/trackpad/b3-config.diff) contains exactly those two symbol changes. Comparing the full archived configurations confirms that two-symbol delta, and the retained B2 and B3 DTBs are byte-for-byte equal.

I called the experiment **mtp-hid-b3**. Its internal artifact name was `mtp-dapf-b3b`; it did not introduce another DAPF change. The [archived build manifest](../evidence/02-input/trackpad/b3-manifest.txt) records the same source commit as B2, `0196caa938be7c2dccee67af1875df0d4c005093`, and the unchanged m1n1/initramfs parts. Their equality is recorded in the manifest; this page does not claim a fresh verification of every original boot-image part.

| Artifact | Recorded SHA-256 |
| --- | --- |
| B3 boot image | `3526355ab776e795b0d3970c11adab54da51a52daa82ab790883ca777692d887` |
| B3 kernel | `19877142607d3737e05bec6d02a2764c7b5fa3eef86705a0ddb3e2ce555d312f` |
| B3 configuration | `7d9617922e566774fccedd3bc4b707d7fa88a02b6f3895aff43427dd6e78ac16` |

Because the source commit was unchanged, the release string still identified the B2 lineage. The variant marker and artifact/configuration hashes distinguish this build.

In that boot's runtime checks, multi-touch was bound to `magicmouse`, the keyboard to `apple`, and the keyboard remained usable. The trackpad input device existed and exposed ABS/multi-touch capabilities. These findings ruled out a missing driver binding or missing input-device registration as the explanation for that boot's remaining failure.

## 4. Follow the first error instead of patching the last symptom

The first B3 boot still had no pointer. libinput reported `Operation now in progress` when opening `/dev/input/event0`.

I traced the open path through evdev, input, `magicmouse_open`, `hid_hw_open`, `dchid_open` and `dchid_start_interface` in the [B2 DockChannel HID source](https://github.com/X6e3/j713-linux/blob/48100bc278cf81b30c33aa501a40662e39473ebc/drivers/hid/dockchannel-hid/dockchannel-hid.c). The last function returns `-EINPROGRESS` when `iface->starting` is already set. That explained the userspace error, but not why the interface had failed to become ready.

The [journal comparison](../evidence/02-input/trackpad/journal-timeline.txt#L115) supplied the earlier failure:

```text
Firmware sent and reset
→ Failed to attach to AFE
→ No HINT_L
→ AFE[0] bootload failed
→ no multi-touch READY
→ start timed out
→ later opens encounter already starting / EINPROGRESS
```

The retained B2-with-firmware records already contain the same AFE failure before either HID driver was enabled. Of those seven selected B2 boots, five reached READY and two failed to attach to AFE. The successful records reached READY about 235–238 ms after reset, within the existing two-second window. This is a description of that selected set, not a general reliability estimate.

I therefore kept the proposed `mtp-hid-open1` change as a proposal and did not build it as the cursor fix. Waiting differently on `EINPROGRESS` would not make an AFE that never reported READY start working. The B2 raw-report observation also did not prove reports reached magicmouse during the failing B3 boot.

## 5. Confirm the result with the actual trackpad

On a later boot of the **same mtp-hid-b3 artifact**, the AFE started successfully. Multi-touch reached READY, the input device could be opened, the keyboard kept working, and I moved the KDE cursor with the internal trackpad.

This is a hardware observation, not an inference from device enumeration. I did not record the boot ID or a log of that first success, so I do not tie it to a journal block.

This established working internal keyboard and trackpad input on the successful startup path. It did not establish reliable AFE startup on every boot, gesture coverage, Linux-controlled haptics, suspend or clean shutdown.

## 6. Keep the later reliability work separate

On 2 October I added a bounded [multi-touch reset retry](https://github.com/X6e3/j713-linux/commit/8bfa2f66c594c9cb375f819704ead7ff971e23fd): up to three READY wait windows, with the existing reset states 0 then 2 repeated between attempts. On 4 October I added [logging for interface GPIO declarations](https://github.com/X6e3/j713-linux/commit/148143f31346657372aef00ef211273a6b5fd0c7), to investigate what the firmware announced. That diagnostic change did not add a host GPIO reset.

The [7 October failure export](../evidence/02-input/trackpad/afe-fail-20261007.txt#L105) still shows AFE attach failure, both retries and the final timeout. A [successful export from the same day](../evidence/02-input/trackpad/afe-ready-20261007.txt#L104) reaches READY and `Touch MT ready`. Their kernels differ, so I do not present them as a single-variable controlled experiment; source comparison shows changes in the board's GPU node and GPU driver files, with no changes to the MTP/DockChannel/RTKit helper path.

The retries were an attempted recovery, not a cure. On 18 October I traced the first-boot failure to the AFE state macOS leaves behind; applying the power sequence from the device's ADT before sending firmware fixed it in both cold boots after macOS that I tested that day. That work will follow as its own record. The separate `Crtk` crash report at shutdown remains open.

## Attribution and inspection

Apple authored the firmware. The firmware collection/conversion machinery and HID decoders were existing work; Josh Rodd's MTP changes provided incorporated driver support. My contribution was identifying the J713 requirements, preparing and validating its firmware, isolating the driver configuration, tracing failed opens back to AFE startup, testing the complete path on the machine, and retaining both successful and failed outcomes.

Run `make trackpad` to regenerate the [derived timeline](../data/02-input/trackpad_summary.json), and `make check` to verify the retained evidence hashes and stored results. The [manifest](../evidence/02-input/trackpad/manifest.json) lists each retained file with its original and published hash. The originals remain private and unchanged; this repository contains no firmware binary or personalized manifest.
