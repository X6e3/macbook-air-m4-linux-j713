# Reboot source notes

## Boot chain

iBoot starts stage 1, the small m1n1 object in the Linux volume's boot policy. Stage 1 draws the small die logo,
starts the NVMe controller with its own driver, reads `m1n1/boot.bin` from the EFI partition and jumps into it.
`boot.bin` is stage 2 (P2T m1n1 or 6boot) followed by the device tree, kernel and initramfs. Stage 2 draws the
large die logo. Every stall in this section happened with the small die on screen and before the large one.

## Images

Boot images are not published (their initramfs layers contain vendor firmware). SHA-256:

- K1: `2724e13542d6bdb730da354a48f9f7de67aa6fce11a34423352f8e1ea35a3c44`, P2T m1n1 stage 2 with the LIM2 kernel and
  the K1 device tree (`5fd2368f6a79e5e0f8577aeaec080247d999c75e77899748448ff6db5913e598`), which adds the Wi-Fi
  board type.
- 6boot-K1: `1c0fb1b99fe8a2f643209416dda660931ad01bbd39ecb1bd63fe6692cfd077ba`, the same payload behind 6boot's
  stage 2. Kernel command-line tag `6boot-k1-root2`.
- 6boot-K1 without GPU: `d4fdc72f2b693ca5a898ed389dcceeeb53c6d15af3a392f1282594c3211b7b5c`, tag
  `6boot-k1nogpu-root2`. The GPU node's compatible string is renamed, so the GPU driver never binds and the GPU
  firmware never starts. Setting the node's status to disabled would not have worked: stage 2 sets it to okay.

## Stage 1 objects

- Before the trace, `aec6f182636f102b431c79606aad44af933e7950cc3a755548c50df95f63862b`, installed on 21 October.
  It is the stage 1 installed on 26 September
  (`354c1826a053405453f04a6c039c1afd66f69d9e98e4c741932b11abc142d25c`) with only its three logo pixel arrays
  replaced by the die; code, variables and padding are byte-identical. The 26 September object was built by the
  installer's build script in my own build VM at the time, from m1n1 `950e6b7` in GravityLinux's bootloader tree;
  its embedded build paths point into that VM. It is not a binary from GravityLinux's releases.
- Traced, `aecfdd4e44a314775a62cb24e19efdcf71eb282d7e3f514bac490a0912d22b2d`, installed on 26 October in
  One True recoveryOS with `kmutil configure-boot`. The same source, built in the current build VM (clang/LLVM
  22.1.8, rustc 1.99.0) with the installer's flags (`RELEASE=1 CHAINLOADING=1 NO_DISPLAY=1`), the die logo and
  [`stage1-trace.diff`](stage1-trace.diff). From the logo to the jump into `boot.bin`, every step prints one line
  with the time since stage 1 started.
- Control, not yet run: `db236e1be1300107296058d2e61b0e98f6c479fdf2112888f8c8406e3521f33a`, the same build without
  the trace.

The September VM's compiler versions were not recorded. Built in today's VM, the unmodified source gives an object
of the same size and version tag as the September one, but 73,621 of its bytes differ.

Linux cannot see which stage 1 ran. That the traced stage 1 was in place for the runs from boot 575a5871 on comes
from the `kmutil` run and from its lines on the screen, which I saw scroll under the die in six of the boots; in
the others the screen stayed plain.

`kmutil configure-boot` refused in ordinary recoveryOS, and in One True recoveryOS it failed with
`code pairing (17)` while macOS was the startup disk. It worked after I made the Linux volume the startup disk
first.

## The two logs

`6k1-boots.log` is written by [`6k1.sh`](6k1.sh). Each `boot=` line is one boot that reached Linux; its time is
the Linux clock, which starts wrong after a reboot (there is no RTC driver) and lags until NTP sets it, so those
times are approximate. `bt=` is the Wi-Fi board type from the device tree, `sku=` the antenna SKU, `speaker=2`
the two lines one sound card has in `/proc/asound/cards`. In the first eight lines `records=0` is a script error:
it looked for `x6e3,*` properties, while 6boot's handoff record is `/chosen/xboot,handoff-record`; the copy here
counts both. From 17:04 the script asked after each boot whether the reboot before it stalled and logged the answer
as a `reboot mode=… stalled=` line.

`auto-boots.log` is written by [`reboot-loop.sh`](reboot-loop.sh), run by a systemd service at every boot while a
loop is set up. It waits for NTP before it logs, so these times are real (`ntp=yes`). `reboot from X: Ns` is the
time from the reboot command to the next logged line; more than 75 s would print `stall?`. In the dongle-free run
the stalled reboot has no entry: the next line is the loop being set up again. The copy of the script here is the version that wrote the lines from
18:37 on; earlier lines come from earlier versions without the `ac=` to `prev_last:` fields, which waited
60 s before each reboot instead of 15 s. The loop counter does not start from 0 in the first traced run, so the
tallies use the `reboot from …` entries, not the counter. `kerr=10` and `prev_wdt=1` are the same on every line
and mark nothing; these fields were added after the last stall, so they never saw one.

The check results that `6k1.sh` saved next to its log are not published: they contain the network name and the
Wi-Fi MAC address.

## Source reading, not a measurement

GravityLinux's bootloader repository has a later commit, `3c5b962` "fb: map the full VRAM reservation as
Normal-NC". Its message says that mapping only the visible framebuffer as Normal-NC leaves the rest of the VRAM
reservation cacheable, which can trigger `UNEXP_RT_HIT_DIR`. m1n1 `950e6b7`, which both stage-1 objects
above are built from, maps only the visible framebuffer size, and so does 6boot's stage 2. Whether this has
anything to do with the stalls is not tested.
