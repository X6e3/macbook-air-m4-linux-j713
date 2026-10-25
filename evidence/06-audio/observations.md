# Speaker observations

The photographs stay private. These notes keep what the screen showed apart from what I heard.

| Image | Retained observation |
| --- | --- |
| S1, 18 October | I heard the left woofer's test tone. |
| S2 | The two amplifier probes repeatedly deferred; no speaker card appeared. |
| S2b | Amplifiers bound; card creation failed on `OUT(*) -> Speaker`. |
| S2c | Card appeared; opening playback triggered protection. |
| S2d | Right amplifier `0x3b`: `protection fault check: reg 0x42 = 0x04`; `speaker fault: amp-fault`. The driver shut down the amplifiers. |
| S2e, 19 October | A one-channel request was rejected because the card was stereo. The subsequent two-channel request completed. I heard the left and right tones on their own sides, then desktop sounds and music in Firefox. |

I checked IMG_0203 2 and IMG_0204 again on 24 October. They show:

```text
x6e3.v=s2e-st-root2
speaker limiter: ceiling -30.0 dB, 145 mW peak, 900 mW continuous, ramp to -0.0 dB
speaker-test -D hw:0,0 -c 2 -r 48000 -F S24_LE -t sine -f 440 -l 1
0 - Front Left
1 - Front Right
Time per period = 5.957128
```

The earlier one-channel command and its rejection remain visible in the same photographs. The later fault
search shown on screen returns the limiter banner and no speaker-fault line. A photo cannot show that a tone
was audible; that part is what I heard during this test. The banner's 145/900 mW are the inherited model's
parameters, not J713's measured output power.
