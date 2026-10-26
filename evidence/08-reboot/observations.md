# Reboot observations, 26 October 2026

A start that stalls in stage 1 never reaches Linux, so it leaves no line in any log. The rows below are the
starts I recorded by watching the screen, and the starts that only a later journal listing shows. Starts that
the scripts logged themselves are in `6k1-boots.log` and `auto-boots.log` and are not repeated here.

A stall looked the same every time: the small die logo of stage 1, fully drawn, and nothing after it. Stage 2's
large die normally follows in under two seconds. I waited between about 15 seconds and 3 minutes; no key brought
it back, only switching the Mac off with the power button and on again.

| run | start | count | stalled | how it was recorded |
|---|---|---:|---:|---|
| k1 | reboot from Linux | 1 | 1 | Boot B of the K1 Wi-Fi test, after the firmware files were renamed; I waited 15–20 s |
| k1 | cold start | 1 | 0 | Boot C, the power cycle after boot B; same image and files |
| 6boot-k1 | reboot from Linux | 7 | 2 | The 3rd and the 6th start stalled; the seven boots reached are in `6k1-boots.log`, the seventh reboot (from 0e545bfd to 84238d50) in `journalctl --list-boots` |
| 6boot-k1 | cold start | 2 | 0 | The power cycles after those two stalls |
| env | reboot from Linux | 1 | 1 | The reboot after I renamed the environment file that forced software rendering |
| env | cold start | 2 | 1 | The power cycle after that stall stalled too; the next power cycle booted |
| nogpu | cold start | 1 | 0 | The power cycle after the stall from 2c228c54 (the reboot itself is logged) |
| dongle-free | reboot from Linux | 1 | 1 | The third reboot of the loop; I was away for at least 2–3 minutes and found it on the small die |
| dongle-free | cold start | 1 | 0 | The power cycle after it |

The `env` starts happened between 15:29 and 17:01 on the 6boot-K1 image with the dongle attached; I did not
note the exact times. The rows add up to what I wrote down during the day: 7 stalls before the traced stage 1.
