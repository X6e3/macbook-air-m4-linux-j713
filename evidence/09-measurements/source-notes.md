# Section 9 source notes

All runs are from 27 October 2026 on J713; times are local (UTC+3). The archive copies are on X63-R under
`j713-diag/o12b/`; `manifest.json` gives each file's archive path and the hashes before and after publication.

Kernels: O12b (`7.1.13-x6e3-o12b`, `Image.gz` hash prefix `16158df0`) is a test kernel with measurement tools for
the MCA window and the `region_c` words. Its −10 dB image differs from the −30 dB one in one byte, the boot argument
`snd_t8132_speaker.ceiling_dvc=20` instead of `60`. LR1 (`7.1.13-x6e3-lr1`) adds the speaker slot change that is
[33948ddae209](https://github.com/X6e3/j713-linux/commit/33948ddae20966d190932836a37a5883d28fcc72) in j713-linux.
The `x6e3.v` tag in each `system.txt` names the image that ran.

- `map/`: `o-mca.sh map`, each 0x400-byte chunk read twice (`-a`, `-b`); `state.txt` records the chunk that hung
  (`0x8c00`) on the first run; `o1-period.json` is `o1-period.py`'s output for these chunks.
- `stride/`: the complete blind run of 17:18. `ab-trials.txt` holds one line per trial; `verdict.txt` is the
  device's summary and `verdict-recomputed.txt` the same table recomputed from `ab-trials.txt`. `left-out.txt` says
  why `0x4000` was not tried. `stride/earlier/` keeps the trial and state files of the runs at 01:22, 16:54, 17:03
  and 17:05 and the verdicts of 16:54, 17:03 and 17:05; those runs failed in the test itself.
- `sides/regs-20261027-191026.txt`: the amplifiers' configuration registers on O12b, read back before the fix.
- `sides/lr-blind/` (19:40, O12b) and `sides/lr-one/` (19:45, LR1): trials, plans, seeds, the device's verdicts and
  my reviews of them (`verdict-review.txt`, written on the Mac the same evening; the device's `verdict.txt` is kept
  as it was written).
- `sides/phone/`: four recordings from the Audio Amplitude app on an iPhone (Apple iPhone16,2, iOS 27.2,
  app 1.2.1), 18:04–18:29. The first two are the reference on macOS (played with `afplay`), the last two are O12b
  before the LR1 fix (played with `pw-play`); `recordings.csv` says where the phone lay and what was played.
  `phone-1-1805` and `phone-2-1807` are two exports of one recording. The app exports about the last 20 s, so the
  18:05 export holds the left-corner part and the 18:07 export only its last segment, the right-corner part. Each
  export is a spreadsheet; its sound-level sheet and its start and pause events are published as CSV with the values
  unchanged. The app's calibration offset was 0 dB, so the levels are relative. The device sheet holds no identifier
  beyond the model and the iOS version.
- `sides/phone/photos/`: two photos of the setup, taken with the same phone on macOS right after the reference:
  the phone at the right corner, then at the left one. The app still shows the last level of the 18:07 export,
  −60.3 dB. The files carry no camera, time or location data; 18:08 is when they were created on the Mac, and the
  phone's clock in them reads 18:07 and 18:08.
- `dose/`: `o-gpu.sh dose`, 01:36, an hour under `gl-burn` with the thermal zone off. `phases.txt` lists each
  phase's start and setting, `pauses.txt` the seconds the load stood still, `seed.txt` the order's seed.

Redactions: the root file system UUID (as `[UUID]`) in `dose/system.txt` and `stride/system.txt`, and the host
name (as `[HOST]`) there and in `stride/dmesg.txt`. The sound files of the listening tests (`.raw`) are not published.
