# 2.1 Getting MTP through startup

28 September 2026, MacBook Air 13-inch M4 / J713 / T8132.

I started with the existing MTP driver work, but my internal keyboard and trackpad did not come up. I traced the path from the DART and ASC startup to RTKit wake, then separated the failure into two steps: missing DAPF initialization and the remaining wake-sequence timeout.

This page uses four archived kernel exports: one A1 boot, two B1 boots, and one early B2 boot. It does not establish a boot success rate. I checked the original exports against my archive before making the redacted copies published here.

## Logs and source lineage

| Record | Full kernel export | Reported original source | Experiment |
| --- | --- | --- | --- |
| A1 | [667 lines](../evidence/02-input/logs/a1-kernel.txt) | `7.1.13-x6e3-g6fe561aa9c3b` | [soc: apple: snapshot J713 MTP DAPF rules before ASC startup](https://github.com/X6e3/j713-linux/commit/e52913a79073ebf881ca3b3c2c3752675849a109) |
| B1 | [646 lines](../evidence/02-input/logs/b1-kernel.txt) | `7.1.13-x6e3-gfb942ac4976a` | [soc: apple: program J713 MTP DAPF rules before ASC startup](https://github.com/X6e3/j713-linux/commit/0ebac09cb3bc4b2fe3edbc41030da73f2d6c9dd9) |
| B1-REPEAT | [651 lines](../evidence/02-input/logs/b1-repeat-kernel.txt) | `7.1.13-x6e3-gfb942ac4976a` | [soc: apple: program J713 MTP DAPF rules before ASC startup](https://github.com/X6e3/j713-linux/commit/0ebac09cb3bc4b2fe3edbc41030da73f2d6c9dd9) |
| B2 | [707 lines](../evidence/02-input/logs/b2-kernel.txt) | `7.1.13-x6e3-g0196caa938be` | [soc: apple: remove the experimental MTP RUN-to-wake delay](https://github.com/X6e3/j713-linux/commit/48100bc278cf81b30c33aa501a40662e39473ebc) |

The release strings and command-line variant markers in the logs identify each experiment; they are not a bit-identical rebuild of the binaries. The linked commits come from the cleaned-up history in j713-linux, so their IDs differ from the hashes in the release strings.

## 1. Find what the failing driver could not tell me

I added DART register/IRQ snapshots and RTKit startup tracing rather than treating every timeout as the same failure. The archived bootloader source skipped `dapf_init_all()` on T8132, with a comment attributing the skip to an SError. That source fact made the missing DAPF state worth testing; the comment alone did not prove the SError's underlying cause.

The [frozen bootloader excerpts](../evidence/02-input/bootloader-context.txt) record the T8132 guard and the existing `dapf_init_t8110a()` write order. DAPF setup already existed in m1n1; this work investigated the missing J713 handoff and applied it to the MTP startup path.

## 2. A1 — observe before writing

I first read the nine dart-mtp DAPF entries without programming them. The [result line](../evidence/02-input/logs/a1-kernel.txt#L385) reports **0/9** literal matches against the J713 ADT policy. After RUN, the trace reached **100005 DART IRQs** by the [-62 wake return](../evidence/02-input/logs/a1-kernel.txt#L460).

The MTP instance timed out waiting for the **endpoint map**. This capture has no MTP protocol-initialization line. The NVMe RTKit initialization elsewhere in the same export belongs to a different device and is not MTP success.

## 3. B1 — program the board's rules, then check the next boundary

I programmed the nine J713 ADT rules at `0x394810000` before ASC RUN, following the archived m1n1 `dapf_init_t8110a()` order: r4, start, end, r0, r20 for each entry.

The [first B1 readback](../evidence/02-input/logs/b1-kernel.txt#L404) reports **8/9** literal matches. Rule 7 was written with end `0x390eee000` and read back as `0x390eee003`. The result is eight literal matches with a recorded rule-7 difference; the precise field semantics remain open.

The DART IRQ counter was **0** at wake return. MTP reached [RTKit protocol v12](../evidence/02-input/logs/b1-kernel.txt#L407), then [timed out waiting for the IOP power ACK](../evidence/02-input/logs/b1-kernel.txt#L414) with wake `-62`. The [second B1 capture](../evidence/02-input/logs/b1-repeat-kernel.txt) shows the same progression.

That changed the failure boundary: the earlier IRQ/endpoint-map failure was no longer the observed stop, but MTP startup was not yet complete. Both B1 exports still contain the experimental 10 ms RUN-to-wake delay.

## 4. B2 — remove the experimental delay

I removed the 10 ms delay while keeping the DAPF programming. The [B2 wake trace](../evidence/02-input/logs/b2-kernel.txt#L413) returned **0**, followed by ["MTP Says Hello"](../evidence/02-input/logs/b2-kernel.txt#L414). The log records the [internal keyboard input device](../evidence/02-input/logs/b2-kernel.txt#L464) and the firmware's ["Keyboard ready"](../evidence/02-input/logs/b2-kernel.txt#L477) message.

These observations support the startup result. The log establishes device registration and firmware readiness. Physical typing is a separate user observation; the firmware ACK timing model remains incomplete.

## 5. What this early B2 boot did not finish

The [trackpad firmware and HID continuation](02-input-trackpad.md) follows the subsequent firmware installation, driver configuration and physically confirmed cursor milestone, with its own evidence and AFE follow-up.

This same B2 export records [a `-2` firmware-load failure](../evidence/02-input/logs/b2-kernel.txt#L664) for `apple/tpmtfw-j713.bin`. The multi-touch device appears in enumeration, but this capture does not demonstrate a working trackpad pointer. Firmware installation, HID report handling and the later intermittent AFE failures are subsequent work.

The working keyboard/trackpad status reported for October 2026 includes that later work. It must not be projected backward onto this first B2 capture.

## 6. What another platform investigation can reuse

I traced the J713 failure across the DART/DAPF and RTKit boundaries, initialized the missing board policy, and recorded the resulting state transitions. The programming machinery and write order came from existing m1n1 code. My contribution here is the J713 diagnosis, integration and hardware experiment sequence. [m1n1's DAPF source](https://github.com/AsahiLinux/m1n1/blob/main/src/dapf.c) provides background; the frozen excerpt above identifies the version I investigated.

The reusable part is the method:

1. Inspect the bootloader handoff for skipped initialization.
2. Obtain that board's own policy and identify the actual register window.
3. Snapshot before writing and compare field by field.
4. Apply a bounded change and read back the result.
5. Follow each boundary separately: DART activity, RTKit protocol, power ACK, firmware, HID registration and actual input.
6. Preserve failed boots as well as the successful transition.

This is a hypothesis-generating method for future Apple Silicon bring-up, including possible M5/M6 investigations. I have not tested those platforms here. Their addresses, rule layouts, protection semantics and startup requirements must be established independently; the J713 table is not a portable policy for them.

## Reproduce and inspect

- Run `make mtp` to regenerate [the summary](../data/02-input/mtp_summary.json).
- Run `make check` to verify the published log hashes, reported kernel/variant lineage, per-rule counts and stored summary, alongside the first-boot checks.
- The parser selects MTP's `394600000.mtp` instance explicitly and does not borrow NVMe's protocol messages.
- [The manifest](../evidence/02-input/manifest.json) records original and published SHA-256 values, line counts and redaction counts; [the checksum file](../evidence/02-input/SHA256SUMS) covers the published logs.

The original exports remain private and unchanged. Only identity substitutions were made: UUID-shaped strings, journal hostname/machine-id and the compiler user/host tuple. No diagnostic lines were dropped, reordered or retimed. Fixed UEFI GUIDs were uniformly masked with the UUID policy as well; not every replaced value was a personal identifier. That comparison needs the private originals, so it cannot be re-run from this repository.

The quoted bootloader source in `evidence/02-input/bootloader-context.txt` retains its MIT license; [the original license text](../evidence/02-input/LICENSE.m1n1.MIT) is included. This page and the derived data use the repository's text/data license. The log text is evidence, not firmware code or a firmware distribution.
