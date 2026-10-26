# Idle source notes

The kernel series records the idle implementation in `05a523037934`,
`drivers/cpuidle/cpuidle-apple.c`. The opt-in `j713_idle` driver has POLL and register-saving WFI states.
The enable argument is `cpuidle_apple.j713_deepwfi=1`. Its current SoC match is T8132, so the J713 parameter
name is not itself a board-only match.

The wfi4 and wfi5 experimental images use different polling handlers. wfi5 implements a loop until rescheduling
is needed or its polling time limit expires; it does not use wfi4's short return path. Each image's own
A1→B→A2 comparison is therefore kept separate.

Each `power.txt` row is: phase, Unix time, system power in microwatts, signed battery power in microwatts,
battery status, AC-online state, one-minute load average. The summary uses the system-power column. It does
not rename it CPU power or estimate battery life from it.

The run logs record the 45-second settling period, state readback, sample collection, restoration and failsafe
cancellation. The state snapshots are retained so the state transition can be inspected alongside the power
samples. No archived control script is executed by the repository's verification target.

The implementation comment in `05a523037934` identifies m1n1's `_deep_wfi_helper` as the register-saving
pattern. The retained bootloader source has the helper in `src/utils_asm.S`, called through `deep_wfi()`
from `src/smp.c`; its M4 feature entry does not enable `apple_sysregs_unlocked`, which gates the
`CYC_OVRD` write in `src/chickens.c`. The Linux change adds CPU PM/context-tracking integration, counters
and an opt-in cpuidle driver with a polling comparison state. These are source observations, not a new
measurement of register retention on the device.

## Implementation locations

Kernel runtime-source revision `03f9eeaebba478bc0994c0c87163dfb9710e8f55`; baseline `3b85d81f656af14d0fc4bea3eef87fe040c424f9`. The links below point at fixed source revisions.

- [`drivers/cpuidle/cpuidle-apple.c`](https://github.com/X6e3/j713-linux/blob/03f9eeaebba478bc0994c0c87163dfb9710e8f55/drivers/cpuidle/cpuidle-apple.c): j713_cpu_save_wfi(), j713_enter_wfi(), j713_enter_poll() and registration.
