# 4. GPU rendering and the thermal limit

6–23 October 2026. Apple M4 GPU, G16G B1.

The first desktop ran on llvmpipe. Firefox and window movement were slow. I wanted the GPU drawing the desktop
and running applications, so recognising its ID was only the start. Once it rendered, the next question was what
happened when it ran hot.

The G16 driver, its firmware interface and the Mesa driver come from GravityLinux, built on Asahi's DRM and Mesa
work. They already initialised the M4 firmware, mapped its memory and submitted work. The J713 changes are in
four places: the bootloader's performance table, the kernel's handling of that table, one Mesa copy path, and
later a thermal limit with a queue-priority change. The [source notes](../evidence/04-gpu/source-notes.md)
separate the baseline from each diff.

## Ten groups, not eleven

J713's ADT has one `perf-states` table with sixteen frequency/voltage rows and a matching `perf-states-sram`
table ([selected properties](../evidence/04-gpu/adt-performance.json)). The first row has frequency zero. A
separate `gpu-num-perf-states` reads 15; it is not the table's length.

Gravity's `dt_set_gpu_t8132_perf()` groups consecutive rows that share a core voltage. For each group it keeps
the lowest and highest frequency, their original row indices, and the core and SRAM voltages. On J713 that gives
ten groups: rows `0`, `1`, `2`, `3`, `4–5`, `6–7`, `8–9`, `10–11`, `12–13`, `14–15`. The last one is
1326/1470 MHz. In row order the frequencies do not only go up (1056 MHz is followed by 1053 MHz at the next
voltage), so both ladders and the original indices have to be kept. Ten groups are ten table entries, not ten
voltage rails.

The baseline accepted only eleven groups. The J713 [bootloader diff](../evidence/04-gpu/bootloader-gpu1.patch) also
accepts ten groups ending at 1470 MHz. It keeps the eleven-group calibration tables and derives J713's relative
tables with integer arithmetic (`relative_b` is 0 through group 3):

```text
relative_a[i] = 100 * f[i] * V[i]^2 / (f[top] * V[top]^2)
relative_b[i] = 100 * (f[i] - f[3]) / (f[top] - f[3])
```

These are models, not measured curves. The maximum power came out as `37237 * 79 / 100 * 8 / 10 = 23533` mW:
the Mac mini's value, scaled by a guess. That number comes back below.

The loader writes each ladder as big-endian FDT cells. The `sgx` properties it copies as `apple,sgx-*` keep
their raw bytes, and the kernel reads those as little-endian words; the two must not be mixed up. The memory
regions, firmware version and the rest of the GPU handoff were already in Gravity's loader. The ten-group change
fits into that path.

## Matching kernel tables

In [112ccab096d4](https://github.com/X6e3/j713-linux/commit/112ccab096d4ee4c84625231c8f4334673eb73b7),
`ladder()` keeps arrays of capacity eleven but accepts an active length of 5–11, the same for every ladder.
`Platform.states` records that length, validation reads only the active entries, and `top_frequency()` takes
`freq_a[states - 1]`. The firmware builders use the same count: fields that were fixed at 10 become
`states - 1`, and the power-control builder uses `100 * (states - 1)`. For J713 that is 9 and 900.

The [probe record](../evidence/04-gpu/probe.txt) shows the GPU with ten steps and a 1470 MHz maximum. Firmware
execution was off in that boot; 1470 MHz is the top of the table, not a clock I measured.

A login screen did not mean a working desktop. Fedora's Mesa failed to create a GPU queue: its USC address did not
match the one the kernel required. Gravity's Mesa got past that. An earlier queue-priority clamp did not fix the
black screen, and I do not credit it with that.

## A texture upload that kept allocating

With Gravity's Mesa, I narrowed KWin's failure down to a 273×273 RGBA8 texture upload. `agx_transfer_map()`
stages a write to compressed storage in a linear resource, and unmapping submits a staging blit. When
`asahi_copy_texture()` cannot handle the compressed layout, `agx_resource_copy_region()` falls back to
`util_resource_copy_region()`, which maps the destination again, and that map needs another staging blit. The
allocations repeat because the fallback ends up back where it started.

The [Mesa patch](../evidence/04-gpu/mesa-103-apple9-compression.patch) keeps the unsupported layout out of
Apple9's direct-render path. `agx_compression_allowed()` returns false, the compressed modifier is filtered out
of modifier queries and rejected as unsupported, and compressed imports are refused before anything is
allocated. Its assertions before the CPU fallback document the rule, but they are compiled out of the release
build I tested.

The [original reproducer](../evidence/04-gpu/baseline-repro.log), run in a service limited to 1 GiB, reached that
limit and crashed with SIGSEGV after 583 ms. With the fix, the [same upload test](../evidence/04-gpu/patched-repro.log)
ran 1,000 uploads, checked all 74,529 pixels each time and reported no GL error. A separate
[180-second KWin session](../evidence/04-gpu/cold-session-result.json) ran on `Apple M4 (G16G B1)` with no GPU
errors, with the library at SHA-256 `75ef3ba0063a917d63ea4a9cd236c26fb51839b06521b8f511710192b890d36f`. That
library was copied into the system, not installed from a package; a Mesa update can replace it.

## Rendering is not presenting

By 7 October KWin rendered on the M4, but simpledrm still put the picture on the panel. Windows tore when I moved
them: the compositor's 8-bit output was converted on the CPU into the 10-bit boot framebuffer. A native 10-bit
Mesa candidate passed offscreen pixel checks but made the desktop visibly worse, so I reverted it. A later
[Wayland probe](../evidence/04-gpu/presentation-probe.txt) counted 476 presentation events at about 47.65 per
second, with KWin still on the [M4 renderer](../evidence/04-gpu/presentation-kwin-renderer.txt). Those are
presentation notifications on simpledrm, not the panel's refresh. The native display is [section 5](05-display.md).

## Under sustained load nothing held it back

Once games ran, I checked sustained load. The TG1 run put a full-screen fragment load on the GPU for 30 minutes
with no limit: 2560×1600, 1,024 multiply-adds per pixel, four draws and then `glFinish`, over and over
([source](../evidence/04-gpu/stress-load.c)). The rate never moved, 59.32–59.65 draws/s
([log](../evidence/04-gpu/tg1-load.txt)). The SMC's GPU power reading, `PP1b`, had a median of 8.95 W. The hottest
SoC sensor, `TCMz`, went from 59.1 to 97.3 °C, and that 97.3 was the last sample of the load: it was still
climbing ([sensors](../evidence/04-gpu/tg1-sensors.txt)).

The 23,533 mW cap never came into play; the GPU drew about 9 W. The GPU's own SMC temperature keys were no help
either. All eighteen kept the same value for the whole 30 minutes, nine at 0.1 °C and nine at −4.5 °C, apart from
four single zero samples, so none of them could drive a limit.

A real game showed the same thing. SuperTuxKart ran its benchmark loop at a typical 218–220 fps. 415 s into the
loop `TCMz` reached 100.1 °C and my test script's safety stop closed the game
([runs](../evidence/04-gpu/stk-bench.txt), [sensors](../evidence/04-gpu/stk-sensors.txt)).

## What macOS does on this machine

I ran a 900-second Metal load on macOS on J713 and logged the SMC with it
([run](../evidence/04-gpu/macos-load.txt), [SMC columns](../evidence/04-gpu/macos-smc.txt)). The SMC key `TVS1`
reached 45.0 °C 486 s into the load and stayed between 45.00 and 45.38 °C until the load ended.

A one-hour run the day before covered a longer stretch
([SMC log](../evidence/04-gpu/macos-1h-smc.txt), [run](../evidence/04-gpu/macos-1h-load.txt),
[script](../evidence/04-gpu/macos-1h-run.sh)). From minute 15 to minute 60, `TVS1` stayed between 44.93 and
45.16 °C, mean 45.01, while `TCMz` moved between 74.4 and 98.5 °C.

So on this machine macOS holds `TVS1` at 45 °C under a sustained GPU load. It does not chase the hottest die
sensor: `TCMz` reached 113.6 °C while `TVS1` was held.

## Finding a limit that works on Linux

Next I tested two things under Linux: whether `TVS1` can be read without macOS, and which of the GPU's power
words the firmware responds to. At boot, Gravity's G16 driver writes the GPU's maximum power to `region_c + 0x84`
and 1000 to `+0x88`, `+0x8c` and `+0x98`. The AG1 kernel added the TVS sensors and a debug knob that writes the
word at `+0x88`, which I first treated as a power budget in milliwatts.

`TVS1` was live: 33.5 to 48.3 °C over the run, 649 distinct values, past 45 °C at +227 s
([sensors](../evidence/04-gpu/ag1-sensors.txt)). The budget was not. The kernel logged every write, 7,000, 26,250,
3,500 and 26,250 mW ([kernel messages](../evidence/04-gpu/ag1-dmesg-ag1.txt), [phases](../evidence/04-gpu/ag1-phases.txt)),
and in every phase the GPU drew 8.70–9.05 W at 59.6 draws/s ([log](../evidence/04-gpu/ag1-load.txt)).

AG2 tried the words at `+0x8c` and `+0x90` as P-state limits, written as P-state ×100; with ten P-states, 1000
reads as no limit ([phases](../evidence/04-gpu/ag2-phases.txt),
[sensors](../evidence/04-gpu/ag2-sensors.txt), [log](../evidence/04-gpu/ag2-load.txt),
[kernel messages](../evidence/04-gpu/ag2-dmesg-ag2.txt)). Medians over the last 45 s of each 90 s phase:

| Setting | GPU power (`PP1b`) | draws/s |
| --- | ---: | ---: |
| Boot values | 8.73 W | 59.6 |
| `+0x8c` = 600 | 4.63 W | 47.5 |
| `+0x8c` = 300 | 2.07 W | 32.4 |
| `+0x90` = 600 | 8.94 W | 59.6 |

The limit at `+0x8c` worked, and fast. One second after writing 600, `PP1b` had dropped from 8.77 to 4.85 W; two
seconds after writing 1000 back it was above 8.5 W, both times. Writing `+0x90` changed nothing.

## The limiter

The limiter connects the limit at `+0x8c` to Linux's thermal framework
([12bffb3103b2](https://github.com/X6e3/j713-linux/commit/12bffb3103b224feec9bb47f141f11167c985f5e),
[90ea22e57db4](https://github.com/X6e3/j713-linux/commit/90ea22e57db4340957715a012ab9b859d3199ffb)). A thermal
zone reads `TVS1` every second, with a passive trip at 45 °C and the step-wise governor. A small C cooling device
holds the state the thermal core asks for. Before the Rust runtime publishes new GPU work, it reads that state
and writes the limit to the firmware: state 0 writes 1000, no limit; state `s` writes `100 * (9 - s)`.

The first version, [LIM1](../evidence/04-gpu/lim1-sensors.txt), allowed every state down to 8, which is P1. It held
`TVS1` at 44.75–45.14 °C. But while `TVS1` was above the trip and still rising, the governor added one state per
second, and `TVS1` reacts slowly, so episodes ran all the way down to P1. The worst 10 seconds fell to 25.4 draws/s
([log](../evidence/04-gpu/lim1-load.txt)). LIM2 changed only the device tree: the cooling map stops at state 6,
so the lowest cap is P3.

[LIM2](../evidence/04-gpu/lim2-sensors.txt) ran the same 20-minute load, 65,972 draws with no GL error
([log](../evidence/04-gpu/lim2-load.txt)). Cooling first engaged at +359 s. From there to the end of the load,
next to macOS once it held `TVS1`:

| | LIM2 on Linux | macOS, Metal load |
| --- | ---: | ---: |
| `TVS1` | 44.77–45.11 °C, median 44.98 | 45.00–45.38 °C |
| Mean GPU power | 6.87 W (`PP1b`) | not recorded |
| Highest `TCMz` | 89.5 °C, whole load | 113.6 °C |
| Worst 10 s | 34.5 draws/s (LIM1: 25.4) | |

The cooling device was active in 42.5% of those samples: Linux holds `TVS1` by alternating full speed with
capped episodes. Without a limit,
`TCMz` had reached 97.3 °C in TG1 and 100.1 °C in SuperTuxKart.

## The desktop under that load

In normal use the desktop runs at 60 FPS, the counter sometimes showing 61, and games run normally. The stress
load was different. During LIM1 the desktop dropped to 1–2 FPS from the first second of the load, before any
throttling. HIGH and REALTIME queue requests were clamped to MEDIUM, the same firmware class as applications, so
I suspected KWin's frames were waiting behind the load.

The LIM2 kernel carried a queue-priority change that lets a caller with `CAP_SYS_NICE` that asks for HIGH or
REALTIME use firmware class 1 and the scheduler's High priority; other callers stay at class 2 or 3. With that
kernel, moving windows during the load showed up to 28–30 FPS. Later builds do not carry the change.

I have not shown that the priority change caused it. Reading Gravity's Mesa afterwards, its OpenGL context path
asks the kernel only for LOW or MEDIUM; HIGH and REALTIME are a TODO there (see the
[source notes](../evidence/04-gpu/source-notes.md)). So KWin's request may never reach the new branch. The LIM2
record has neither KWin's queue class nor the hash of the Mesa library it loaded.

## What this does and does not show

1470 MHz is the top of the table, not a clock I measured, and the 23,533 mW maximum is a scaled estimate that
never bound under these loads. AG1's writes to `+0x88` (3,500 to 26,250) and AG2's 600 at `+0x90` changed nothing.
On 27 October a dose test (O2) lowered each word the driver sets, and the two next to them, one at a time under
full load: `+0x88`, `+0x8c` and `+0x98` act as the same limit, with no effect from 900 up, and `+0x84`, `+0x90`
and `+0x94` do nothing
([7187959dc040](https://github.com/X6e3/j713-linux/commit/7187959dc04073b2f928d9d324d61717517ac055)). So AG1's
values were all above the range where `+0x88` acts.

The limiter has two weak points I know of. It writes the limit when the runtime publishes new GPU work, not on a
timer of its own, and a failed write is only logged. The thermal zone also points at hwmon channel 5, which is
`TVS1` only as long as every sensor before it registers. I tested it with one synthetic load for 20 minutes;
games, suspend and other workloads with the limiter on are not covered yet.

macOS ran a Metal load and Linux an OpenGL one, so I compare the two only roughly. The 1–2 → 28–30 FPS change is what I saw
at the machine; its cause is not established. The Mesa fix is a copied library, not a package.

Apple wrote the firmware. The G16 driver, its firmware interface and the Mesa driver are GravityLinux's, on top of
Asahi's work, and Linux's thermal framework runs the control loop. My part was the J713 side: the ten-group table
and the kernel's handling of it, isolating the Mesa copy failure, measuring what macOS holds on this machine,
finding which word works under Linux, and the limiter's design and tests.

## Evidence

- Tables and probe: [ADT properties](../evidence/04-gpu/adt-performance.json),
  [bootloader diff](../evidence/04-gpu/bootloader-gpu1.patch), [probe](../evidence/04-gpu/probe.txt).
- Mesa: [patch](../evidence/04-gpu/mesa-103-apple9-compression.patch), [before](../evidence/04-gpu/baseline-repro.log),
  [after](../evidence/04-gpu/patched-repro.log), [KWin session](../evidence/04-gpu/cold-session-result.json).
- Presentation on simpledrm: [probe](../evidence/04-gpu/presentation-probe.txt),
  [renderer](../evidence/04-gpu/presentation-kwin-renderer.txt).
- No limit: TG1 [sensors](../evidence/04-gpu/tg1-sensors.txt) and [log](../evidence/04-gpu/tg1-load.txt);
  SuperTuxKart [runs](../evidence/04-gpu/stk-bench.txt), [sensors](../evidence/04-gpu/stk-sensors.txt) and
  [start time](../evidence/04-gpu/stk-start.txt).
- macOS: [run](../evidence/04-gpu/macos-load.txt), [start time](../evidence/04-gpu/macos-load-start.txt),
  [SMC columns](../evidence/04-gpu/macos-smc.txt); one-hour run
  [SMC log](../evidence/04-gpu/macos-1h-smc.txt), [run](../evidence/04-gpu/macos-1h-load.txt) and
  [script](../evidence/04-gpu/macos-1h-run.sh).
- Budget and limits: AG1 [sensors](../evidence/04-gpu/ag1-sensors.txt), [phases](../evidence/04-gpu/ag1-phases.txt),
  [log](../evidence/04-gpu/ag1-load.txt), [start](../evidence/04-gpu/ag1-load-start.txt),
  [kernel messages](../evidence/04-gpu/ag1-dmesg-ag1.txt); AG2 [sensors](../evidence/04-gpu/ag2-sensors.txt),
  [phases](../evidence/04-gpu/ag2-phases.txt), [log](../evidence/04-gpu/ag2-load.txt),
  [start](../evidence/04-gpu/ag2-load-start.txt), [kernel messages](../evidence/04-gpu/ag2-dmesg-ag2.txt).
- Limiter: LIM1 [sensors](../evidence/04-gpu/lim1-sensors.txt), [log](../evidence/04-gpu/lim1-load.txt),
  [start](../evidence/04-gpu/lim1-load-start.txt); LIM2 [sensors](../evidence/04-gpu/lim2-sensors.txt),
  [log](../evidence/04-gpu/lim2-load.txt), [start](../evidence/04-gpu/lim2-load-start.txt).
- The [manifest](../evidence/04-gpu/manifest.json) labels each file with its run and archive path.
  `make later-stages` regenerates the [summary](../data/04-07-summary.json) the numbers above come from; `make check`
  verifies the hashes and recomputes it.
