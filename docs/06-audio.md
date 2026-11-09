# 6. Stereo woofers

18–19 October 2026, with a userspace check on 23 October.

The audio0 kernel had only opened the I2C controller for a look. J713 has four amplifiers, but that did not tell
me how to get sound to them. I started with one woofer, then worked through stereo.

The base already had Niklas Sheth's J773g T8132 speaker and protection path and the TAS2764 codec driver, which
handles the SN012776 amplifiers. The J713 changes extend the MCA mapping and stereo routing, handle the shared
amplifier shutdown line and add the board's device-tree nodes
([source notes](../evidence/06-audio/source-notes.md)).

## One woofer first

I built the audio chain into the kernel, since this installation had no kernel modules installed. S1 enabled the
left woofer, and I heard its test tone. I kept a −30 dB digital ceiling (`snd_t8132_speaker.ceiling_dvc=60`) and
left both tweeters disabled. The question was whether sound reached the woofer, not whether J713 had a calibrated
full-volume speaker system.

## The shared shutdown line

Adding the right amplifier exposed a shared GPIO. Both woofers use the same SDZ shutdown line, `pinctrl_ap`
pin 15. The GPIO proxy was a module, so the two amplifier probes kept deferring.

I built the proxy in. The line works by votes: releasing one amplifier's vote does not pull SDZ low while another
still holds it high. So the protection path now shuts down every bound amplifier when one fails, and the DAPM
routes use the amplifiers' `Left Woofer` and `Right Woofer` prefixes.

The stereo card then registered, but the right amplifier reported a fault. Diagnostic output showed
`reg 0x42 = 0x04` on address `0x3b`: a bad TDM clock. Protection shut both amplifiers down.

## The second MCA port

I went back to J713's own macOS routing data. The speaker's clock and transmit masks were `3`, selecting ports
0 and 1. The Mac mini's one-port arrangement was not enough for this board.

The ADT does not describe the MCA layout in enough detail, and the single `0xc000` cluster assumed before had left
the right amplifiers with a bad clock. S2e maps a second unit `0x100` above the first: clock/sync/port units at
`0x2000 + n*0x100`, serializers at `0x6000 + n*0x100`, the number of units taken from the clock list. Unit 0
supplies the DMA stream, and unit 1 drives port 1 through its registers at `0x2160`, `0x2164` and `0x2168`, where
the right amplifiers sit. With S2e I heard the left and right test tones on their own sides, then desktop sounds
and music ([observations](../evidence/06-audio/observations.md)).

On 27 October I checked that layout on the machine itself with a test kernel (O1). A dump of the whole MCA window
shows the block at `0x2000` repeating every `0x100`, six times, and reads from `0x8c00` on stall the bus. In a blind
A/B against `0x80`, `0x200`, `0x400` and `0xc000`, only `0x100` played both woofers without an amplifier fault
([30970c659133](https://github.com/X6e3/j713-linux/commit/30970c65913333a6a4f0951515268b892e63f040)).

## From samples to amplifier slots

One front-end PCM stream feeds one back-end link per amplifier. The J713 device tree's two `apple,codec`
phandles give two channels. `speaker_fe_init()` sets the CPU side to transmit mask 3 with two 32-bit slots, and
`speaker_be_init()` gives codec `i` the mask `1 << i`, so the left and right amplifiers take different slots of
the same stream. The TAS2764 callback programs its TDM slot from the first selected bit.

The front end also asks for a BCLK ratio of 250, not 64: a 12 MHz bit clock at 48 kHz. The frame is longer than
the two 32-bit slots, and the MCA clock divider follows that ratio. PipeWire's `s24-32le` describes how samples
are stored in userspace, not the TDM framing on the wire.

## PipeWire and the ceiling

The [23 October snapshot](../evidence/06-audio/pactl-sinks.json) shows PipeWire with a stereo sink at 48 kHz,
signed 24-bit samples in 32-bit little-endian words. The [parameter readback](../evidence/06-audio/ceiling-dvc.txt)
is still 60, the −30 dB ceiling. The sink was suspended when I captured it; this was a look at the running
system, not another playback test.

The protection component processes samples on the copy path and models voice-coil heating and attenuation; it
refuses mmap so that nothing bypasses that processing. The J713 change extends its shutdown to every bound
amplifier. The model and its numbers come from the Mac mini. I do not know J713's excursion, thermal or
crossover parameters, so I have not removed the ceiling, and PipeWire's volume control does not change that.
The source default also differs from what I tested: `ceiling_dvc` defaults to 20 half-dB steps, −10 dB, so
leaving out the boot argument makes the speakers 20 dB louder than anything tested here.

## What this does and does not show

The left and right tones and the music are what I heard. There is no logic-analyser trace of the TDM signal,
and playback exercised only the route in use, not every serializer or capture. The protection banner's 145 mW
peak and 900 mW continuous figures are model parameters, not measured output.

The tweeters, the headphone jack and the microphones do not work. On macOS the jack's route uses the `anco`
audio NCO with a 3.072 MHz clock, and this Linux setup has no description or control path for that NCO. That is
the dependency I know of; it does not rule out others.

Apple wrote the audio firmware. The speaker and protection path is Niklas Sheth's, and the TAS2764 and MCA
drivers come from Linux and Asahi. My part was the one-then-two woofer bring-up, tracing the shared SDZ and TDM
clock faults, finding the second port and the MCA layout in J713's own data, and the S1–S2e tests.

## Evidence

- [Observations](../evidence/06-audio/observations.md): what the screen showed and what I heard, S1 to S2e; the
  photographs stay private.
- 23 October snapshot: [ALSA cards](../evidence/06-audio/alsa-cards.txt), [PCM](../evidence/06-audio/alsa-pcm.txt),
  [PipeWire sink](../evidence/06-audio/pactl-sinks.json) and [parameter readback](../evidence/06-audio/ceiling-dvc.txt).
- [Source notes](../evidence/06-audio/source-notes.md) and the [manifest](../evidence/06-audio/manifest.json).
  Apple firmware and private audio profiles are not included.
