# Xonotic source notes

- Kernel REL2, `7.1.13-x6e3-rel2`, booted at 01:27:52 on 28 October 2026; the journal's first lines name it. REL3
  is REL2 plus `784e8e030a0b` (`7.1.13-x6e3-rel3`).
- Xonotic 0.8.6 from Fedora's `xonotic-0.8.6-7.fc43.aarch64` and `xonotic-data-0.8.6-7.fc44.noarch` packages,
  unpacked onto the external disk and run from there (`/mnt/x63r/games/xonotic/root/usr/bin/xonotic-sdl` in the
  journal). The game logs report the build as `Xonotic Linux 00:00:00 Jul 25 2025 - release`. Its data file
  `xonotic-20230620-data.pk3` lists 1,207 `.dds` files (`unzip -l`).
- `game/`: the game's console output, saved by me as it ran. `engine.log`, `zink-test.log` and `wayland-test.log`
  are the first launches on llvmpipe, `egl-wsi-debug.log` is the Wayland debug output from looking for the reason,
  and `xonotic-agx-gameplay.log` is the bot match on the GPU. A sixth log, from a public server, is not published.
- `rel2-runs/`: the three reruns from 05:05 to 05:17, each with the game's output (Mesa's buffer dump, and in
  rt-test also its resource log), the available memory, the kernel log where there was a failure, and my stop time.
- `journal/excerpt.txt` was written from the saved journal by `journal/excerpt.py`. The private originals, saved
  from 04:18 to 04:29:
  - `full-boot.log` (`journalctl -b`): `b417ff7061b2b1ab5f488972a1e5dd18b74b79f14742b53913d114e377fcd4da`
  - `kernel.log`: `a5977e69a1d5968bfdc6dee6f860c32474bbb470a201e6f396839b79cf869546`
  - `all-events.log`: `98afe31dac60c84aeb40db7f505153415f0cfbd06079f0ed505c24be654be93f`
- The excerpt leaves out the two kernel lines at 04:12:50 that name the application the out-of-memory killer
  stopped, with that application's other messages. It was not Xonotic, KWin or part of the desktop shell.
- Times are the machine's local time, as the journal printed them. Sizes in the journal are in kB and converted with 1 GiB = 1,048,576 kB.
