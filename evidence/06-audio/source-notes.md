# Audio source notes

Kernel series for J713:

| Commit | Change |
| --- | --- |
| `e3fb4ad6ed80` | T8132 MCA functional groups at `0x100` spacing; mapped count taken from the clock list |
| `730d55758419` | Shared SDZ handling and amplifier protection shutdown |
| `94a092a4481f` | Bind both woofers, prefixed DAPM routes and two output ports |
| `992d6548aefe` | J713 woofer DT nodes and routing |
| `2f45f687d9b5` | Matching S2e configuration |

The source inspected is in `sound/soc/apple/mca.c`, `sound/soc/codecs/tas2764.c`,
`sound/soc/apple/t8132/` and `arch/arm64/boot/dts/apple/t8132-j713.dts`.

The source describes clock/sync/port units at `0x2000 + n*0x100`, serializers at `0x6000 + n*0x100`, and the
second port's registers at `0x2160/0x2164/0x2168`. The tests behind that layout are the S2e playback of
19 October and, on 27 October, the O1 window dump and the blind stride A/B (`30970c659133`). It is not an
assertion that capture or every MCA unit has been brought up.

The inherited protection model uses Mac mini assumptions, not J713 calibration. `ceiling_dvc=60` is the
tested −30 dB ceiling; the source default of 20 is −10 dB. Omitting the argument does not reproduce the tested
setting. The protection banner's power figures are model parameters, not measured acoustic or electrical
output from J713.

S1 through S2d results below are retained engineering observations and photo transcriptions. The 23 October
ALSA/PipeWire files are original passive capture outputs. Their successful parsing does not re-run playback.

## Implementation locations

Kernel runtime-source revision `90ea22e57db4340957715a012ab9b859d3199ffb`; baseline `3b85d81f656af14d0fc4bea3eef87fe040c424f9`. The links below point at fixed source revisions.

- [`sound/soc/apple/mca.c`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/sound/soc/apple/mca.c): unit mapping, bclk_ratio and serializer/port routing.
- [`sound/soc/apple/t8132/pcm.c`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/sound/soc/apple/t8132/pcm.c): speaker_fe_init(), speaker_be_init(), copy path and ceiling_dvc.
- [`sound/soc/codecs/tas2764.c`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/sound/soc/codecs/tas2764.c): TDM slot programming and shared shutdown handling.
- [`arch/arm64/boot/dts/apple/t8132-j713.dts`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/arch/arm64/boot/dts/apple/t8132-j713.dts): codec ordering, GPIO proxy and woofer nodes.
