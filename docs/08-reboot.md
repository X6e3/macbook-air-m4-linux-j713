# 8. Reboot stalls at the first-stage logo

26 October 2026.

During a Wi-Fi firmware test, a reboot from Linux stopped at the boot logo. By the evening it had happened seven
times. Every time, stage 1 had drawn its small die logo completely and stage 2's large die never followed; that
normally takes under two seconds. No key brought the machine back, only switching it off with the power button and
on again. A stalled start leaves no log, because the kernel never starts.

The boot chain is described in the [source notes](../evidence/08-reboot/source-notes.md): stage 1 is the small
m1n1 in the Linux volume's boot policy, and it reads stage 2 from the EFI partition with its own NVMe driver.

## How I counted

My test scripts logged the boots that reached Linux while they ran. Stalls leave no line, so I noted them at the
screen; the [observations](../evidence/08-reboot/observations.md) list every start that only my notes record.

| Stage 1 | Reboots from Linux | Stalled | Cold starts | Stalled |
| --- | ---: | ---: | ---: | ---: |
| Used until 26 October (`aec6f182`) | 20 | 6 | 7 | 1 |
| Rebuilt with on-screen tracing (`aecfdd4e`) | 27 | 0 | 0 | 0 |

The cold starts are the power cycles after a stall. The whole afternoon ran on the old stage 1, from the first stall
at about 13:27 to the last one at about 17:27; the traced runs took 18:35–19:09.

## What I ruled out

Each suspect predicted something I could test. One stall where a suspect said there would be none was enough to
drop it as the cause.

| Suspect | Test | Result |
| --- | --- | --- |
| The Wi-Fi test (K1) | Where the stall happens; the same payload behind the traced stage 1 | Not the cause |
| 6boot's stage 2 | The same | Not the cause |
| Only warm reboots from Linux | Watching cold starts | A cold start stalled |
| The GPU's state at reboot | An image on which the GPU never starts | 1 stall in 8 reboots |
| The USB-C hub I charge through | 15 reboots with the hub unplugged | The 3rd reboot stalled |

**The Wi-Fi test.** The first stall came right after I had renamed the Wi-Fi firmware files for the K1 test
(13:20–13:28), so that was my first suspect. But the K1 device tree is read only when stage 2 boots the kernel, and
the firmware files only by Linux, and the stall came before stage 2 drew anything. The cold start right after it
booted with the same image and files.

**6boot's stage 2.** That first stall had P2T m1n1 as stage 2; the next six had 6boot. Neither stage 2 had drawn
its logo when the machine stopped. The traced runs used the same 6boot image, payload and K1 device tree for all 27 reboots.

**Only warm reboots.** The first three stalls all followed a reboot from Linux, and none of the cold starts after
them stalled, so I suspected something Linux leaves behind at reboot. Then a cold start stalled: after I changed
the environment variables that forced software rendering, the reboot stalled, the power cycle after it stalled
too, and only the next one booted.

**The GPU.** My next suspect was the GPU: KWin renders on it in every session, and its firmware is still running
when Linux reboots. I built an image on which the GPU driver never binds and the GPU firmware never starts, and
predicted no stalls on it. It stalled once in 8 reboots (17:04–17:09); with the GPU on, it had stalled twice in 7.

**The hub.** I charge through a no-name USB-C hub, and I had read of an M1 Air that hung at startup until its hub
was removed. I unplugged it and let a script reboot the Mac by itself 15 times (17:22 on). The first two reboots were clean; the
third stalled, and I found it on the small die after at least two minutes away. The hub is not the only cause.
I did not test whether it makes stalls more likely.

**A correction.** My notes first called the old stage 1 "Gravity's stage-1 binary". That was wrong on two counts:
the cause was not known, and the binary is not theirs. The installer's build script built it in my own build VM
on 26 September, from m1n1 `950e6b7` in GravityLinux's bootloader tree; on 21 October I replaced only its logo.

## The traced stage 1

With the outside suspects gone, the stall was somewhere between the two logos: in stage 1 loading stage 2, or in
stage 2 before it draws. I rebuilt stage 1 from the same source with the installer's flags and added a trace: from
the logo to the jump into stage 2, each step prints one line on the screen, so a stall would leave its last step
visible, and a stall after the last line would be in stage 2 ([diff](../evidence/08-reboot/stage1-trace.diff)). I installed it in One True recoveryOS; `kmutil` only accepted
it after I made the Linux volume the startup disk first.

It never stalled. The loop rebooted the Mac 12 times and then 15 times, and every reboot reached an NTP-synced
Linux in 55–60 s ([loop log](../evidence/08-reboot/auto-boots.log)). In six of the boots I saw the trace lines
scroll under the die; in the others the screen stayed plain.

If both builds stalled equally often, all six reboot stalls landing in the old build's 20 reboots and none in the
traced build's 27 would happen by chance 0.36% of the time (one-sided Fisher test). The conditions were not the
same, though: the traced runs were on AC through a direct cable, with the hub unplugged and one USB device attached.
The only earlier run without the hub stalled once in 3 reboots.

## Still open

Two explanations fit. Either the September build misbehaves and today's build of the same source does not (they
were built with different compilers, and the unmodified rebuild differs from the September object in 73,621
bytes), or the trace's screen output changes the timing and hides a race. The control is the same rebuild without
the trace, `db236e1b`, for 15–30 reboots: stalls coming back point to timing, none point to the build.

A later GravityLinux bootloader commit, `3c5b962`, maps the whole VRAM reservation non-cacheable instead of only
the visible framebuffer, because the cacheable rest can trigger an `UNEXP_RT_HIT_DIR` error. m1n1 `950e6b7` and
6boot's stage 2 map only the visible part. That is a candidate, not a result. My next step is the same change in my
own stage 1 and stage 2, crediting that commit, and another reboot loop.

Whatever the control shows, the installer will ship a stage 1 that I build.

## What this does and does not show

The counts show that the traced build went through 27 reboots without a stall under these conditions. They do not
show the cause, and they do not show that users will never see a stall. The trace never captured a stall, so it
has not yet told me where one happens. Linux cannot see which stage 1 ran; that comes from the `kmutil` run and
the trace lines on the screen. The stalls without a log line are my notes, and the test assumes the reboots are
independent.

## Evidence

- [Observations](../evidence/08-reboot/observations.md): the starts only my notes record.
- [6boot-K1 and GPU-off log](../evidence/08-reboot/6k1-boots.log) with its script [`6k1.sh`](../evidence/08-reboot/6k1.sh);
  [reboot-loop log](../evidence/08-reboot/auto-boots.log) with [`reboot-loop.sh`](../evidence/08-reboot/reboot-loop.sh).
- [Stage-1 trace diff](../evidence/08-reboot/stage1-trace.diff), against m1n1 `950e6b7` (MIT, see
  [`LICENSE.m1n1.MIT`](../evidence/02-input/LICENSE.m1n1.MIT)).
- [Source notes](../evidence/08-reboot/source-notes.md) with image and stage-1 hashes, and the
  [manifest](../evidence/08-reboot/manifest.json). `make reboot` recomputes the tallies in the
  [summary](../data/08-reboot/reboot_summary.json); `make check` verifies them.
