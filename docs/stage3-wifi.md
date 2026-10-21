# Stage 3 — Bringing the internal Wi-Fi online

2 October 2026 — MacBook Air 13-inch M4 / J713 / T8132, Broadcom BCM4388.

After the internal-input milestone, I wanted to stay in Fedora and continue development there. I followed the Wi-Fi path through driver configuration, PCIe enumeration, the correct firmware environment, firmware availability during early boot, and finally the networking userspace and an actual connection.

The resulting evidence is a sequence of different outcomes, not one patch that made everything work. Kernel/runtime exports establish the early failure boundaries and the first interface. Build records and read-only archive checks establish the early-firmware arrangement. Three retained photographs establish the connection and package downloads.

## 1. Enable the existing platform chain

I based `wifi-pcie1` on the working `mtp-hid-b3` source. I kept the HID drivers enabled and changed the Wi-Fi/PCIe configuration rather than replacing the driver or guessing a board type.

The seven deliberately enabled symbols were:

```text
CONFIG_MFD_MACSMC=y
CONFIG_GPIO_MACSMC=y
CONFIG_PCIE_APPLE=y
CONFIG_CFG80211=y
CONFIG_RFKILL=y
CONFIG_BRCMFMAC=y
CONFIG_BRCMFMAC_PCIE=y
```

The [archived configuration diff](../evidence/stage3/pcie-config.diff) also contains four resolved additions or changes: `BRCMUTIL`, `BRCMFMAC_PROTO_MSGBUF`, `CRYPTO_SHA256` and `PCIE_APPLE_MSI_DOORBELL_ADDR`. Comparing the full archived configurations confirms those eleven changed symbols, with `HID_APPLE=y` and `HID_MAGICMOUSE=y` preserved. The retained B3, wifi-pcie1 and wifi-persist1 DTBs compare byte-for-byte equal.

The existing board description linked SMC GPIO, the PCIe port's regulator/power control, Apple PCIe and the Broadcom device. The [first boot export](../evidence/stage3/pcie-firstboot.txt#L346) shows macsmc-gpio initialization, PCIe link-up, Wi-Fi `14e4:4434`, then brcmfmac enabling the device and requesting firmware. So the configured path reached the device.

It stopped at a precise boundary:

```text
Direct firmware load for brcm/brcmfmac4388c0-pcie.bin failed with error -2
```

## 2. Identify J713's firmware from its own platform evidence

The requested filename contained `4388c0`, but the [preserved J713 macOS metadata](../evidence/stage3/macos-firmware-selection.txt) identified chip stepping `C2`, module `M=WLMT m=4.9 V=a`, platform `garden` and firmware FWID `01-974167da`.

I matched that with the J713 firmware source: `C-4388__s-C2/garden.trx` resolves to `guam.trx`. The [selection record](../evidence/stage3/firmware-identity.txt) ties the board's `garden`/X3 metadata and macOS FWID to those exact bytes. The driver's BCM4388 revision mapping explains why Linux requests the `4388c0` filename; that filename does not identify this machine's stepping by itself.

The selected `.bin` was unchanged Apple firmware, 1,857,979 bytes, with SHA-256:

```text
157342936222282f3f08b068b1b00b2131f2aaa4200ebd646f58508f5defc364
```

I made it available under the name the existing driver requests. I did not modify the firmware or substitute another board's firmware identity.

## 3. Keep the failed bin-only test and the successful full-environment test

In `wifi-fw-identity1`, the installed `.bin` hash matched, but after a runtime rebind the firmware did not initialize. The [kernel export](../evidence/stage3/bin-only-kernel.txt) records `FW failed to initialize`; the [runtime report](../evidence/stage3/bin-only-runtime.txt) ends with `driver=none wlan=none`.

The missing-file failure had been removed. Initialization was a later boundary. In this driver's source, NVRAM presence also controls population of firmware footer data. These records do not establish an authentication or signature-rejection cause for the timeout.

For `wifi-fwset1`, I supplied the matching J713 environment:

| Linux suffix | Selected source |
| --- | --- |
| `.bin` | garden → guam firmware |
| `.txt` | garden/X3, WLMT 4.9, vendor a NVRAM |
| `.clm_blob` | garden CLM data |
| `.txcap_blob` | garden transmit-capability data |
| `.sig` | garden → guam signature |

The platform calibration remained on its existing ADT → m1n1 → device-tree path; its bytes are not published here.

The [full-environment kernel export](../evidence/stage3/fwset-kernel.txt) shows TxCap loading, platform calibration loading and:

```text
Firmware: BCM4388/6 ... FWID 01-974167da
wld0: renamed from wlan0
```

That FWID matches the recorded macOS firmware. The [runtime report](../evidence/stage3/fwset-runtime.txt) records `driver=brcmfmac wlan=wld0` about two seconds after rebind. NetworkManager was inactive and the new interface was down; scanning and association were deliberately outside that checkpoint.

This comparison establishes failure with `.bin` alone and success with the complete supplied environment. It does not isolate NVRAM, signature, footer or other accompanying data as the sole cause.

## 4. Make the same files available when normal boot needs them

The first boot requested the Broadcom firmware at **1.040717 s**, before `/init` at **1.055217 s** and the NVMe root mount at **1.055912 s**. These [monotonic timestamps](../evidence/stage3/pcie-firstboot.txt#L433) explained why installing the files only on the final root filesystem did not repair the original boot-time probe.

I prepared the `wifi-persist1` L2 early-firmware arrangement:

```text
one outer gzip member
└── unchanged base cpio + J713 Wi-Fi vendor cpio
```

The [firmware manifest](../evidence/stage3/early-firmware-manifest.txt) records the five files, their original sources, sizes and hashes. This placed them under `lib/firmware/brcm/` in the initramfs used by the built-in driver's early probe.

The [build manifest](../evidence/stage3/persist-build-manifest.txt) records a 1,564,160-byte base cpio plus a 1,965,568-byte vendor cpio, yielding a 3,529,728-byte combined initrd. I checked the private archives against it: the base prefix is identical, the outer gzip is one member, its output equals the concatenated archives, and all five vendor-file hashes match the manifest. The [verification metadata](../evidence/stage3/early-layer-verification.json) records these checks and contains no firmware.

## 5. Integrate the join-preference fallback and verify a normal boot

The successful runtime-rebind test still logged `Set join_pref error (-52)`. It had already created the interface, so this was a separate issue from firmware initialization.

I incorporated [Michael Reeves's existing RSSI-only fallback](https://github.com/X6e3/j713-linux/commit/30696b9c21f0593cfb6b653e8c85d36f0a7c4e5a), retaining his authorship. It retries an RSSI-only preference when the original `join_pref` request returns `-EBADE`; it does not retry every transport error.

`wifi-persist1` therefore had **two deliberate changes** relative to wifi-pcie1: the early-firmware layer and that source patch. I do not attribute the complete result to either one alone. The archived config is identical between those builds.

The later deployed derivative was `wifi-persist1-tp1-root2`: it selected the new Fedora root and included the separately documented trackpad reset retry. The [normal-boot report](../evidence/stage3/normalboot-report.txt) identifies that lineage. The frozen wifi-persist1 build manifest's `NOT DEPLOYED` label describes its earlier checkpoint, not the later derivative's state.

The [normal-boot Wi-Fi lines](../evidence/stage3/normalboot-wifi-order.txt) show the initial probe, TxCap/platform calibration, matching FWID and `wld0` creation at **2.344006 s**. The report records no Broadcom firmware ENOENT, no firmware-init failure and no final `Set join_pref error`. It does not log whether the first join-preference request succeeded or the fallback was taken on that boot.

`regulatory.db` was still missing in that early boot and NetworkManager was inactive. I retained those facts; they are separate from successfully loading the Broadcom firmware. The same report's AFE failures belong to the trackpad workstream.

## 6. Finish the userspace and use the connection

The Fedora image lacked NetworkManager, its Wi-Fi plugin and a supplicant. I prepared an offline Fedora 44 package set against that root's RPM database: NetworkManager, NetworkManager-libnm, NetworkManager-wifi, wpa_supplicant, libndp, iw and wireless-regdb. The [package hash list](../evidence/stage3/offline-package-hashes.txt) and [historical install script](../evidence/stage3/offline-install-script.txt) preserve that step. The script verifies hashes/signatures, installs from local packages with repositories disabled, then starts NetworkManager. It stores no connection credentials.

I then connected from Fedora and kept three photographs of it. The [identifier-free transcription](../evidence/stage3/photo-observations.md) records what is visible:

| Observation | Evidence |
| --- | --- |
| Scanning | 2.4 GHz and 5 GHz channel entries appear in the nmcli list. |
| Connection | The first attempt times out; a subsequent attempt reports successful activation and `wld0 wifi connected`. |
| Address configuration | The interface is UP with dynamic IPv4 /24 and global/link-local IPv6 addresses. |
| Routing | A default route on wld0 is marked `proto dhcp`. |
| DNS | `getent hosts google.com` returns an answer. |
| Actual use | DNF shows 143.5 MiB downloaded and a completed package transaction; Firefox is installed and open. |

This was the transition to using Fedora online for development.

I don't know why the first connection attempt timed out. `ping` was not installed, so the photos have no ping result. No 6 GHz, roaming or suspend/resume result is claimed.

## Attribution and verification

Apple/Broadcom supplied the firmware. Gravity/Asahi and Linux provided the platform and driver foundations; Michael Reeves authored the join-preference fallback. My contribution was identifying J713's actual firmware environment, isolating the configuration and failure boundaries, integrating the early-boot files, preserving source attribution, provisioning the missing userspace and verifying the connection on the machine.

Run `make wifi` to regenerate the [derived summary](../data/stage3/wifi_summary.json); `make check` verifies hashes, line counts, firmware timing/FWID agreement and stored results. The [manifest](../evidence/stage3/manifest.json) labels complete archived exports, selected excerpts, authored observations and derived metadata. Fourteen copied files were byte-matched to my archive before redaction.

Some device-generated wall-clock headers predate their kernel builds. I preserve them and use experiment lineage, monotonic timing and contemporaneous records for the sequence. The original photos remain private; this repository contains no network identifiers, credentials, firmware/NVRAM contents or calibration bytes.
