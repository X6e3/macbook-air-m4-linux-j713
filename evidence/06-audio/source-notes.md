# Audio source notes

Prepared kernel series for J713:

| Commit | Change |
| --- | --- |
| `f5c99791b26a` | T8132 MCA functional groups at `0x100` spacing; mapped count taken from the clock list |
| `2c8a4035bf10` | Shared SDZ handling and amplifier protection shutdown |
| `22e83f1105cb` | Bind both woofers, prefixed DAPM routes and two output ports |
| `afe93dc25c8f` | J713 woofer DT nodes and routing |
| `122a53ed92cf` | Matching S2e configuration |

The source inspected is in `sound/soc/apple/mca.c`, `sound/soc/codecs/tas2764.c`,
`sound/soc/apple/t8132/` and `arch/arm64/boot/dts/apple/t8132-j713.dts`.

J713's AOP firmware supplied the layout and names used to interpret the MCA blocks. The resulting source
describes clock/sync/port units at `0x2000 + n*0x100`, serializers at `0x6000 + n*0x100`, and the extra output
port's pad registers at `0x2160/0x2164/0x2168`. This page records the derived interpretation, not firmware bytes.
It is not an assertion that capture or every MCA unit has been brought up.

The inherited protection model uses Mac mini assumptions, not J713 calibration. `ceiling_dvc=60` is the
tested −30 dB ceiling; the source default of 20 is −10 dB. Omitting the argument does not reproduce the tested
setting. The protection banner's power figures are model parameters, not measured acoustic or electrical
output from J713.

S1 through S2d results below are retained engineering observations and photo transcriptions. The 23 October
ALSA/PipeWire files are original passive capture outputs. Their successful parsing does not re-run playback.

## Implementation locations

Kernel runtime-source revision `e4daceaff3bd7d42cf25d7ccadb941421321b12e`; baseline `3b85d81f656af14d0fc4bea3eef87fe040c424f9`. The links below point at fixed source revisions.

- [`sound/soc/apple/mca.c`](https://github.com/X6e3/j713-linux/blob/e4daceaff3bd7d42cf25d7ccadb941421321b12e/sound/soc/apple/mca.c): unit mapping, bclk_ratio and serializer/port routing.
- [`sound/soc/apple/t8132/pcm.c`](https://github.com/X6e3/j713-linux/blob/e4daceaff3bd7d42cf25d7ccadb941421321b12e/sound/soc/apple/t8132/pcm.c): speaker_fe_init(), speaker_be_init(), copy path and ceiling_dvc.
- [`sound/soc/codecs/tas2764.c`](https://github.com/X6e3/j713-linux/blob/e4daceaff3bd7d42cf25d7ccadb941421321b12e/sound/soc/codecs/tas2764.c): TDM slot programming and shared shutdown handling.
- [`arch/arm64/boot/dts/apple/t8132-j713.dts`](https://github.com/X6e3/j713-linux/blob/e4daceaff3bd7d42cf25d7ccadb941421321b12e/arch/arm64/boot/dts/apple/t8132-j713.dts): codec ordering, GPIO proxy and woofer nodes.
