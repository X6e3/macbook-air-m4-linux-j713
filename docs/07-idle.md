# 7. CPU idle with WFI

7 October 2026, with a native-display follow-up on 18 October.

The early kernel kept idle CPUs polling. With all ten cores online that was not good enough for a laptop; I
wanted them to wait for work instead of spinning.

The M4 boot path leaves `CYC_OVRD` unchanged, so I could not assume the retention setup used on earlier chips.
I took m1n1's register-saving WFI sequence as the starting point for an opt-in idle path, added to Asahi's
`cpuidle-apple` driver and enabled with `cpuidle_apple.j713_deepwfi=1`.

## The idle path

Asahi's driver already has a plain architectural WFI state and a deeper path that changes `CYC_OVRD`, saves
registers and waits for a pending interrupt. The J713 path registers a separate two-state driver, POLL and
`J713 WFI`, selected on T8132 only when the read-only parameter is set. With the experimental `idle=nop` boot
argument, early idle still polls until cpuidle registers.

`j713_enter_wfi()` calls `cpu_pm_enter()` first and returns −1 if CPU PM refuses. Otherwise it enters cpuidle
context tracking, counts the entry and calls `j713_cpu_save_wfi()`. That helper pushes seven register pairs onto
the stack (`x30/x0`, then `x28/x29` down to `x18/x19`), executes `dsb sy; wfi`, restores them in reverse order and
returns. The caller counts the return, leaves context tracking and calls `cpu_pm_exit()`. Floating-point and
system-register state is left to the CPU PM notifiers. The helper does not write `CYC_OVRD` and does not use the
older helper's `ISR_EL1` wait loop. Saving those registers is a precaution taken from m1n1's `_deep_wfi_helper`
under Apple's CPU configuration; architectural WFI does not normally need it.

The wfi5 POLL state enables interrupts and spins until a reschedule is needed or the governor's polling time runs
out, checking the clock as it goes. That gives the governor a real polling state instead of one that returns at
once. The WFI state declares `exit_latency=10`, `target_residency=1000` and `power_usage=0`.

## WFI on, off and on again

I compared WFI enabled, disabled and enabled again within each boot. The script set the idle state's disable value
on all ten CPUs, checked the readback, waited 45 s and took 90 samples two seconds apart in each phase. Every
sample shows AC disconnected and the battery discharging, and both runs ended with the original settings restored.

| Run | A1: WFI, mean system W | B: polling, mean system W | A2: WFI, mean system W |
| --- | ---: | ---: | ---: |
| wfi4 | 6.531 | 11.801 | 6.507 |
| wfi5 | 6.144 | 9.171 | 6.090 |

In wfi5 the two WFI phases together average 6.117 W against 9.171 W while polling: 33.30% less whole-system power.
The number is the SMC's `TotalSystemPower` reading through hwmon; the script also saved signed battery power, AC
status and load average ([samples](../evidence/07-idle/aba-wfi5-1032/power.txt),
[state snapshots](../evidence/07-idle/aba-wfi5-1032/snapshots.txt), [run log](../evidence/07-idle/aba-wfi5-1032/run.log)).
The wfi4 run is a separate experiment ([samples](../evidence/07-idle/aba-wfi4-1003/power.txt),
[run log](../evidence/07-idle/aba-wfi4-1003/run.log)).

wfi5 also replaced wfi4's very short polling handler with a real polling loop, so the two B phases are not the
same baseline. I do not pool the runs or credit the difference between their WFI averages to that change alone;
display brightness and starting temperature were not held equal between the two boots.

## What this does and does not show

The state counters show WFI entries returning, and I kept using the desktop with the path on. The later
[N1 boot](../evidence/05-display/n1-kernel-selected.txt) runs it together with the native display. The tests show
the register-saving sequence working on J713, not that each saved register would otherwise be lost, and the
declared latency and zero power are not measured.

The power figures are the SMC's whole-system reading, not CPU power and not a calibrated meter. Suspend, CPU
frequency scaling, a physical sleep depth and a battery-life comparison with macOS are not covered. The parameter
has a J713 name, but the code matches T8132; no other board was tested.

The idle driver is Asahi's, and the register-saving pattern is m1n1's. My part was choosing to build on that
pattern for M4 and running the A/B/A comparisons.

## Evidence

- wfi5: [power samples](../evidence/07-idle/aba-wfi5-1032/power.txt),
  [state snapshots](../evidence/07-idle/aba-wfi5-1032/snapshots.txt), [run log](../evidence/07-idle/aba-wfi5-1032/run.log).
- wfi4: [power samples](../evidence/07-idle/aba-wfi4-1003/power.txt), [run log](../evidence/07-idle/aba-wfi4-1003/run.log).
- [Source notes](../evidence/07-idle/source-notes.md) and the [manifest](../evidence/07-idle/manifest.json).
  `make later-stages` recomputes all six phase means and both reductions in the [summary](../data/04-07-summary.json);
  `make check` verifies them.
