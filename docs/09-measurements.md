# 9. Measuring the MCA layout, the speaker sides and the GPU limit

27 October 2026. Test kernel O12b, and LR1 for the speaker sides.

By 26 October both woofers played and the GPU limit held `TVS1` at 45 °C, but two parts of that work rested on
values I had not fully measured on this machine: the MCA's `0x100` unit stride, and which of the `region_c` words
limit the GPU. To do the
hardware side properly I needed measurements, so on 27 October I tested both on J713 itself. The same day the
listening tests showed that left and right were crossed.

## The test kernel and its safety limits

O12b is a test kernel with measurement tools for the MCA window and the `region_c` words
(`7.1.13-x6e3-o12b`, [plan and order](../evidence/09-measurements/o12b-README.txt)). For the listening tests a
second image raised the speaker ceiling from −30 dB to −10 dB: one boot argument,
`snd_t8132_speaker.ceiling_dvc=20` instead of `60`, one byte apart. −10 dB is the driver's default, but J713 had
never played at it, and the protection model's parameters are the Mac mini's. So the test sounds were short (the
"Front Left" and "Front Right" voices, about 1.5 s each, and later 6-second bursts of pink noise), the tweeters
stayed off and the amplifiers' protection stayed on. Before each trial both amplifiers were bound again, and a trial
whose amplifier faulted played nothing more.

## The MCA window (O1)

With silence playing, [`o-mca.sh map`](../evidence/09-measurements/o-mca.sh) read the MCA's register window in
0x400-byte chunks, outward from the driver's own groups, each chunk twice. Reads from `0x8c00` on stall the bus:
the first run hung there and the next stopped short of it ([state](../evidence/09-measurements/map/state.txt)).
From `0x0000` to `0x8bff` all 35 chunks read back the same both times ([chunks](../evidence/09-measurements/map/)).

In the page of clock, sync and port registers, six blocks `0x100` apart, `0x2000` to `0x2500`, each hold a
register at `+0x04`, and nothing is set from `0x2600` on. Unit 1's port registers at `0x2160`, `0x2164` and
`0x2168` hold the same values as unit 0's at `0x2060` to `0x2068`: port 1 is set up. The serializer page repeats the same way: 17 blocks from
`0x6000` to `0x7000`, each with registers at `+0x04` and `+0x84`.
[`o1-period.py`](../evidence/09-measurements/o1-period.py), which scores every period from `0x20` to `0x800` without
a list of candidates, gives `0x100` for the page that holds the driver's groups
([result](../evidence/09-measurements/map/o1-period.json)).

## A blind test of the stride

The stride test played the speakers at `0x100` (A) and at the other candidates (B): `0x80` and `0x200`, half and
twice `0x100`; `0x400`, the period the map found in another page; and `0xc000`, the stride the driver had assumed
before. `0x4000`, the cluster stride of other Apple MCA variants, was left out: its unit 1 serializer would sit at
`0xa000`, past the end of the readable window. A negative control (C) used `0x100` with a single unit. Every B and
C trial came between two A trials, in random order. Each trial played "Front Left" on channel 1 and "Front Right"
on channel 2, one after the other in random order, and I answered only whether I heard each one. Kernel messages
stayed off the console, so nothing on the screen showed the stride.

The complete run, at 17:18 ([trials](../evidence/09-measurements/stride/ab-trials.txt),
[verdict](../evidence/09-measurements/stride/verdict.txt)):

| Stride | Trials | Result |
| --- | ---: | --- |
| `0x100` (A) | 6 | both voices heard every time, no fault |
| `0x80` | 1 | amplifier fault |
| `0x200` | 1 | amplifier fault |
| `0x400` | 1 | amplifier fault |
| `0xc000` | 1 | no speaker card |
| `0x100`, one unit (C) | 1 | no speaker card |

The runs before it failed in the test itself: at 01:22 a broken trial list, at 16:54 and 17:03 sounds that did not
play, and at 17:05 an amplifier fault in a B trial that stayed latched and silenced the A trials after it. Since
then the script binds both amplifiers again before every trial. Those runs are kept
([earlier runs](../evidence/09-measurements/stride/earlier/)).

## Left and right

Each run started with a side check that was not blind: a voice said "Front Left", then "Front Right", and I said
where I heard it. "Front Left" came from the right. By ear I was not sure at first; I caught myself doubting what I
heard.

I tried a phone next ([phone recordings](../evidence/09-measurements/sides/phone/)). With an app that logs the sound
level, I held the phone 55 mm from one edge, the width of three fingers, which I checked with calipers, played the
left noise and the right noise, then did the same at the other edge. The phone did not separate the sides: its
levels are uncalibrated, and where the two noises can be told apart in the recordings they differ by 0.4 to 4.6 dB.

The amplifiers were not the cause. Each reads back the slot it was given: the left woofer's amplifier (`0x38`)
slot 0, the right one's (`0x3b`) slot 1 ([register dump](../evidence/09-measurements/sides/regs-20261027-191026.txt)).
So the crossing happens before them.

A blind test at 19:40 played two bursts per start, one on each channel in random order, and I said where each came
from ([lr-blind](../evidence/09-measurements/lr-blind.sh), [trials](../evidence/09-measurements/sides/lr-blind/trials.txt),
[review](../evidence/09-measurements/sides/lr-blind/verdict-review.txt)). Eight of my ten answers were the same pair,
right then left, whatever the order: the design let an answering habit pass for a result. Read with that habit in
mind, the answers point to a fixed swap.

LR1 gives each amplifier the other slot
([33948ddae209](https://github.com/X6e3/j713-linux/commit/33948ddae20966d190932836a37a5883d28fcc72)); the left
woofer's amplifier now reads back slot 1 and the right one's slot 0. The test at 19:45 played one burst per start,
so there was no order to answer by ([lr-one](../evidence/09-measurements/lr-one.sh),
[trials](../evidence/09-measurements/sides/lr-one/trials.txt),
[review](../evidence/09-measurements/sides/lr-one/verdict-review.txt)). To keep the answers simple I put my finger
on the machine and called the Esc end left and the Touch ID end right. Channel 1 came from the Esc end in 5 of 6
trials and channel 2 from the Touch ID end in 5 of 6: 10 of 12, which guessing reaches with a probability of 1.9%.
No trial had an amplifier fault or a kernel message. The rule written into the test before it ran asked for 11 of
12 for a fixed mapping, so its verdict is mixed; the two misses follow no channel, rebind or position. Listening
cannot tell an error of mine from a start that occasionally comes out the other way. That needs a sensor: the
internal microphones, once they work.

## The GPU limit (O2)

O2 lowered each `region_c` word Gravity's driver sets at boot (`+0x84`, `+0x88`, `+0x8c`, `+0x98`) and the two next
to them (`+0x90`, `+0x94`), one dose at a time, under a full GPU load for an hour
([`o-gpu.sh`](../evidence/09-measurements/o-gpu.sh), [phases](../evidence/09-measurements/dose/phases.txt),
[sensors](../evidence/09-measurements/dose/sensors.txt)). Every dose ran for about 50 s between two phases with no
limit, in random order. The thermal zone was off for the run; the load paused at an SoC temperature of 90 °C and
resumed at 75 °C, 24 times for 280 s in all, and the test would have stopped at 95 °C. Medians of the SMC's GPU
power `PP1b` over the last 25 s of load in each phase:

| Dose | `+0x88` | `+0x8c` | `+0x98` |
| ---: | ---: | ---: | ---: |
| 250 | 1.75 W | 1.76 W | 1.76 W |
| 500 | 3.69 W | 3.69 W | 3.70 W |
| 750 | 6.04 W | 6.06 W | 6.04 W |

`+0x8c` ran from 50 to 950 in steps of 50: 0.33 W at 50, rising at every step to 7.58 W at 850, then 8.71 W at 900
and 8.80 W at 950, the same as the phases with no limit (8.51–8.83 W). `+0x84` at 5,883 to 17,649 and `+0x90` and
`+0x94` at 250 to 750 changed nothing. The firmware never wrote `region_c` during the run. So `+0x88`, `+0x8c` and
`+0x98` act as one limit that does nothing from 900 up, and the kernel's name for it, taken from one of the three
words, was wrong; I renamed it after what it does
([7187959dc040](https://github.com/X6e3/j713-linux/commit/7187959dc04073b2f928d9d324d61717517ac055)).

## What this does and does not show

The window map shows which registers hold values in each block, not what every register does. The stride test is
one complete run: six A trials, and each other stride once. The side tests are my ears, and two of twelve answers
are still open. O2 is one load on one machine for an hour, and `PP1b` is the SMC's reading.
[`measurements.py`](../analysis/measurements.py) recomputes every number on this page from the evidence, and `make
check` verifies it.

## Evidence

- Plan, safety and test sources: [O12b plan](../evidence/09-measurements/o12b-README.txt),
  [`o-mca.sh`](../evidence/09-measurements/o-mca.sh), [`o1-period.py`](../evidence/09-measurements/o1-period.py),
  [`o-gpu.sh`](../evidence/09-measurements/o-gpu.sh), [`o-gpu-summary.py`](../evidence/09-measurements/o-gpu-summary.py),
  [`gl-burn.c`](../evidence/09-measurements/gl-burn.c), [`side.sh`](../evidence/09-measurements/side.sh),
  [`regs.sh`](../evidence/09-measurements/regs.sh).
- Window map: [chunks, state and periods](../evidence/09-measurements/map/).
- Stride: [complete run](../evidence/09-measurements/stride/), [earlier runs](../evidence/09-measurements/stride/earlier/).
- Sides: [register dump](../evidence/09-measurements/sides/regs-20261027-191026.txt),
  [two-burst test](../evidence/09-measurements/sides/lr-blind/), [one-burst test](../evidence/09-measurements/sides/lr-one/),
  [phone recordings](../evidence/09-measurements/sides/phone/).
- Dose: [run](../evidence/09-measurements/dose/).
- [Source notes](../evidence/09-measurements/source-notes.md), [manifest](../evidence/09-measurements/manifest.json),
  [summary](../data/09-measurements/measurements_summary.json).
