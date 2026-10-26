# 3. Bringing the internal Wi-Fi online

2 October 2026. MacBook Air 13-inch M4, Broadcom BCM4388.

With the keyboard and trackpad working, the machine was usable, but it was offline. Everything it needed came
on a USB stick. That morning I also moved Fedora to a new 20 GiB root; the first one had only 6 GiB. The
image names from then on end in `-root2`.

## The driver asks for firmware

I built on the trackpad kernel and enabled the existing platform chain: SMC GPIO, Apple PCIe and the Broadcom
driver ([config diff](../evidence/03-wifi/pcie-config.diff)). The board's device tree already described the Wi-Fi's power and
PCIe port. On the [first boot](../evidence/03-wifi/pcie-firstboot.txt#L346) the PCIe link came up, the Broadcom device
(`14e4:4434`) appeared, and the driver asked for a file that was not there:

```text
Direct firmware load for brcm/brcmfmac4388c0-pcie.bin failed with error -2
```

## Which firmware

My rule from the start was that J713 itself is the authority: whatever this machine reports while it runs
decides, not another board. The ready path was the Mac mini's firmware (`paradise.trx`). I did not want it: it
was another board's, with a different firmware ID (`01-40b8d11f`).

J713 said something else. Its ADT names the Wi-Fi module `garden`, with antenna X3. macOS's driver on this
machine reports chip stepping C2, module `WLMT 4.9 a`, and a running firmware ID of `01-974167da`
([macOS metadata](../evidence/03-wifi/macos-firmware-selection.txt)). In this machine's firmware folder `garden.trx` points to
`guam.trx`, and `guam.trx` carries the same ID ([selection record](../evidence/03-wifi/firmware-identity.txt)). Linux asks for a
`4388c0` file because of how it maps the chip's revision; that name does not describe this machine.

## One file, then the whole set

I tried the smallest change first: the exact, unmodified `guam.trx` under the name Linux asks for, nothing else.
The file loaded, but [the firmware did not start](../evidence/03-wifi/bin-only-kernel.txt)
([runtime](../evidence/03-wifi/bin-only-runtime.txt)).

Then I gave it the rest of J713's own set from the same folder: NVRAM, regulatory (CLM) data, transmit
capability data and the signature. The firmware started with ID `01-974167da`, the same one macOS runs, and the
interface `wld0` appeared ([kernel](../evidence/03-wifi/fwset-kernel.txt), [runtime](../evidence/03-wifi/fwset-runtime.txt)). Which of the extra
files was the one that mattered, I did not separate.

The firmware went from macOS to Fedora on that USB stick. Its label was GUAM4388: the firmware and the chip.

## Early enough

On a normal boot the driver asks for the firmware at 1.040 s; `/init` starts at 1.055 s and the root filesystem is
mounted at 1.056 s ([timestamps](../evidence/03-wifi/pcie-firstboot.txt#L433)). Files on the root arrive too late. I put the five
files into the initramfs as a separate layer next to the unchanged base
([manifest](../evidence/03-wifi/early-firmware-manifest.txt), [build](../evidence/03-wifi/persist-build-manifest.txt),
[checks](../evidence/03-wifi/early-layer-verification.json)).

In the same step I added [Michael Reeves's RSSI-only fallback](https://github.com/X6e3/j713-linux/commit/af077a25b566d364f6a8c4a82a2319515da6f4ff) for a
`join_pref` error the driver had shown; it keeps his authorship. That is two changes at once, so I do not credit
the result to either one alone.

On the [next normal boot](../evidence/03-wifi/normalboot-wifi-order.txt) the firmware loaded with the same ID and `wld0` was there at
2.34 s ([report](../evidence/03-wifi/normalboot-report.txt)).

## Online

The Fedora image had no NetworkManager, no Wi-Fi plugin and no supplicant. I prepared the seven packages offline
against the root's package database and carried them on the same stick ([hashes](../evidence/03-wifi/offline-package-hashes.txt),
[install script](../evidence/03-wifi/offline-install-script.txt)).

The [photographs of that afternoon](../evidence/03-wifi/photo-observations.md) show the rest. The scan listed 2.4 and 5 GHz
networks. The first connection attempt timed out after 90 seconds; the second one connected. DHCP gave an address
and a default route, and DNS answered. I pulled the Fedora repositories first, then installed Firefox. DNF
downloaded 143.5 MiB and finished. From then on I worked on the machine online.

## What this does and does not show

- Only `.bin` failed; the full set worked. Which extra file was required is not established.
- The early layer and the fallback went in together; neither one alone is credited.
- I do not know why the first connection attempt timed out. `ping` was not installed, so there is no ping result.
- 6 GHz, roaming and suspend are not covered.

Apple and Broadcom wrote the firmware. The driver and the platform support come from Linux, Asahi and Gravity, and
Michael Reeves wrote the fallback. My part was finding J713's own firmware set, separating the failure points,
getting the files in early enough and bringing up the missing userspace.

## Evidence

- Configuration and first boot: [config diff](../evidence/03-wifi/pcie-config.diff), [first boot](../evidence/03-wifi/pcie-firstboot.txt).
- Firmware identity: [macOS metadata](../evidence/03-wifi/macos-firmware-selection.txt), [selection record](../evidence/03-wifi/firmware-identity.txt).
- `.bin` only: [kernel](../evidence/03-wifi/bin-only-kernel.txt), [runtime](../evidence/03-wifi/bin-only-runtime.txt). Full set:
  [kernel](../evidence/03-wifi/fwset-kernel.txt), [runtime](../evidence/03-wifi/fwset-runtime.txt).
- Early layer: [firmware manifest](../evidence/03-wifi/early-firmware-manifest.txt), [build manifest](../evidence/03-wifi/persist-build-manifest.txt),
  [verification](../evidence/03-wifi/early-layer-verification.json). Normal boot: [Wi-Fi lines](../evidence/03-wifi/normalboot-wifi-order.txt),
  [report](../evidence/03-wifi/normalboot-report.txt).
- Userspace: [package hashes](../evidence/03-wifi/offline-package-hashes.txt), [install script](../evidence/03-wifi/offline-install-script.txt).
- Connection: [photograph transcription](../evidence/03-wifi/photo-observations.md); the photographs show network details and stay
  private.
- The [manifest](../evidence/03-wifi/manifest.json) labels each file. `make wifi` regenerates the
  [summary](../data/03-wifi/wifi_summary.json); `make check` verifies the hashes, line counts and the firmware
  timing and ID.
