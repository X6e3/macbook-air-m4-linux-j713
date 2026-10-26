# GPU source and record notes

Prepared 24 October 2026. Source references below identify the local kernel series prepared for `X6e3/j713-linux`.
They do not assert that the remote repository already contains those commits.

| Change | Commit | Source |
| --- | --- | --- |
| J713 GPU boot tables, ten-group ladder, derived relative-power tables and estimated maximum power | Archived `gpu1` source diff | `src/kboot_gpu.c` in `m1n1-gpu1-vs-950e6b7.diff` |
| Variable voltage-group count, 5..11 instead of exactly 11 | `112ccab096d4ee4c84625231c8f4334673eb73b7` | `drivers/gpu/drm/asahi/g16_platform.rs`, `g16.rs`, firmware tables |
| J713 GPU node | `ac8c8c8678ef` | `arch/arm64/boot/dts/apple/t8132-j713.dts` |
| Early priority clamp | `e0aebdf0ff63` | G16 queue creation; its original black-screen explanation is not treated as a proven cause |
| CLTM cooling device | `7945e7a1692b` | `drivers/gpu/drm/asahi/g16_cooling.c`, Rust runtime integration |
| Later queue-class change | `69ab407a8c3a` | G16 queue creation; actual KWin class was not captured in LIM2 |
| TVS1 thermal zone, 45 °C, maximum cooling state 6 | `03f9eeaebba4` | `arch/arm64/boot/dts/apple/t8132-j713.dts` |

The probe prints ten driver table steps. The original ADT has sixteen performance-state entries grouped into
ten voltage groups. Neither number is a count of GPU cores.

The kernel change in `112ccab096d4` spans `asahi_m4.rs`, `g16_platform.rs`, `g16.rs` and `g16_power.rs`.
It updates ladder validation, iteration, maximum-frequency selection and the highest-step indices supplied
to firmware tables. The archived bootloader diff supplies the corresponding J713 table generation. The
subsequent Mesa copy/allocation fixes and CLTM cooling-device implementation address buffer handling and
runtime thermal control separately from boot-time table generation.

The compression fix is the archived `mesa-103-apple9-compression.patch`, applied to Gravity's
`mesa-26.3.0~devel-103`. It changes the Apple9 compression allocation/import and staging-copy paths in
`agx_pipe.c` and `agx_blit.c`. The successful cold-session library hash is recorded in `cold-session-result.json`.
The library loaded during LIM2 was not hashed by that test.

Context priority in the same Mesa source: `agx_create_context()` in `src/gallium/drivers/asahi/agx_pipe.c`
starts from `DRM_ASAHI_PRIORITY_MEDIUM`, switches to LOW only for `PIPE_CONTEXT_PRIORITY_LOW`, and leaves
HIGH/REALTIME as a TODO ("High/realtime need us to handle errors since we might not have permission"). It never
passes priority 2 or 3 to `agx_create_command_queue()`, so through this OpenGL path the `CAP_SYS_NICE` branch of
`69ab407a8c3a` is not reached. Whether KWin used another path during LIM2 was not recorded.

The early Fedora Mesa queue/address diagnosis and the unsuccessful priority hypothesis come from the retained
6 October investigation. `QUEUE_CREATE` output inspected separately was from an EGL diagnostic, not a captured
KWin request. It must not be used to infer KWin's requested priority. The excerpts included here establish the
probe configuration and later Mesa tests; they do not independently reproduce that earlier address diagnosis.

The later performance probe is the 7 October `render-wfi5-1046` run. Its notifications are on simpledrm.
The rejected native10 candidate and the earlier approximately 35/s measurements belong to the preceding
investigation and are not a controlled comparison against native DCP.

`stress-load.c` is an archived diagnostic program, included for inspection and reproducibility of the workload.
It is not executed by `make check`. One loop iteration makes four offscreen draws and calls `glFinish`;
the program's draws/s counter counts those draws. It does not count panel presentations.

LIM2 includes both the P3 cooling floor and the queue-class change. It is not an isolated test of either change.
The summary's regulated interval starts at the first nonzero cooling state; the full 20-minute mean is reported
separately.

Desktop frame rate: in normal use KWin's counter shows 60 FPS, sometimes 61, and games run normally. The
approximately 30 FPS was only under the synthetic GPU stress load. These are my readings of the counter, not
values from the thermal sample tables.

Bootloader tables: the archived bootloader derives J713's relative-power tables from `f*V*V`
normalised to the top step and from the frequency range above step 3. They are modelled values. The probe
reports the generated table maximum, not an operating-frequency measurement. The baseline texture test's
1 GiB service limit and lack of global OOM are recorded in the retained 6 October GPU test report; its
published output records allocation failures, SIGSEGV, a 1 GiB peak and a 583 ms runtime.

In the selected macOS capture, timestamp `1792682335` has `MaxGPUAbsolutePower=6246` after `26250`,
with a same-second `TVS1=45.02`. `CLTMPerfMax` remains `65536` in every selected row. That column is not
proof of the Linux `region_c + 0x8c` field's behaviour; AG2 is the separate experiment for that field.

## Implementation locations

Kernel runtime-source revision `03f9eeaebba478bc0994c0c87163dfb9710e8f55`; baseline `3b85d81f656af14d0fc4bea3eef87fe040c424f9`. The links below point at fixed source revisions.

- [`drivers/gpu/drm/asahi/g16_platform.rs`](https://github.com/X6e3/j713-linux/blob/03f9eeaebba478bc0994c0c87163dfb9710e8f55/drivers/gpu/drm/asahi/g16_platform.rs): ladder(), Platform::new(), top_frequency(): common active count, preserved raw ADT bytes.
- [`drivers/gpu/drm/asahi/g16_power.rs`](https://github.com/X6e3/j713-linux/blob/03f9eeaebba478bc0994c0c87163dfb9710e8f55/drivers/gpu/drm/asahi/g16_power.rs): firmware power/performance fields; model defaults are not measurements.
- [`drivers/gpu/drm/asahi/g16_drm.rs`](https://github.com/X6e3/j713-linux/blob/03f9eeaebba478bc0994c0c87163dfb9710e8f55/drivers/gpu/drm/asahi/g16_drm.rs): queue request validation and priority mapping.
- [`drivers/gpu/drm/asahi/g16_runtime.rs`](https://github.com/X6e3/j713-linux/blob/03f9eeaebba478bc0994c0c87163dfb9710e8f55/drivers/gpu/drm/asahi/g16_runtime.rs): apply_thermal_limit() and flush(): updates on nonempty publication, error logged without stopping work.
- [`drivers/gpu/drm/asahi/g16_cooling.c`](https://github.com/X6e3/j713-linux/blob/03f9eeaebba478bc0994c0c87163dfb9710e8f55/drivers/gpu/drm/asahi/g16_cooling.c): global cooling state, registration and unregister.

The Gravity baseline already contains the G16 firmware graph and runtime files listed above. The scope comes
from comparing that baseline with the individual J713 diffs.
The bootloader baseline is retained Gravity m1n1 `950e6b7`. Its original grouping, raw-ADT copying and
reserved-memory handoff remain in the J713 source; the selected `bootloader-gpu1.patch` shows the changed
acceptance/model/serialization values only.

`adt-performance.json` is an offline numeric extraction of the retained J713 `sgx` properties, not a new
measurement. Its original dump hash is recorded, but the identifying dump stays private. The original and
published hashes for this selection therefore have different meanings. The Mesa patch is copied unchanged
from the retained artifact. A matching source tree is not a reproducible binary build: the complete build log
and an RPM are not retained. See `THIRD_PARTY.md` for source licenses.
