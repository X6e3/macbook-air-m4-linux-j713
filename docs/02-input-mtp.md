# 2.1 Getting MTP through startup

28 September 2026.

After the first night I could boot Fedora and reach KDE, but only with a USB keyboard. The two USB-C
ports did not behave the same: the rear one, next to MagSafe, worked; the front one, nearest the trackpad,
was unreliable (X63 and X3e in my notebook). The internal keyboard and trackpad did not work at all.

On J713 both sit behind MTP, a coprocessor that Linux has to start. I started from Josh Rodd's MTP,
DockChannel, DART and RTKit work for the 15-inch Air (J715). It did not bring MTP up on J713.

## What I saw

With iBoot, the trackpad clicked as soon as I pressed the power button. With our kernels the click
stopped. Linux was starting MTP and breaking it. My [notebook](../evidence/02-input/notebook-20260928.md)
for that day starts with "trackpad is not clickable".

## Narrowing it down

I wrote down a broad hypothesis (a shared ownership problem across M4 blocks) and tried to falsify it
rather than confirm it. Most of it did not hold. My research then led to the m1n1 source: it skips
`dapf_init_all()` on T8132, with a comment blaming an SError, while the J713 ADT describes nine DAPF rules
for dart-mtp. Nobody was programming them. The [frozen bootloader excerpts](../evidence/02-input/bootloader-context.txt)
record that guard and m1n1's existing write order.

Three earlier boots of the same kernel family (wide1) had timing traces. These kernels wait 10 ms between RUN
and the RTKit wake call, a delay I had added to pull the two apart. Across the three boots, the DART interrupt
storm began 221–223 µs after ASC RUN, approximately 10.4 ms before the first logged host-to-MTP mailbox
transmission ([1](../evidence/02-input/logs/wide1-1-dmesg.txt#L386), [2](../evidence/02-input/logs/wide1-2-dmesg.txt#L386), [3](../evidence/02-input/logs/wide1-3-dmesg.txt#L386)).
So the storm started before Linux's first logged mailbox message, which rules that message out as what set it
off. It does not rule out the mailbox mechanism as a whole, and on its own it does not show why MTP never
answered. The DART interrupts and the mailbox messages are separate events. In every interrupt the trace
dumped, the DART's error register read 0, so the trace does not show what raised them.

## A1: read before writing

I read the nine dart-mtp DAPF entries [without writing anything](https://github.com/X6e3/j713-linux/commit/e52913a79073ebf881ca3b3c2c3752675849a109).
[0 of 9](../evidence/02-input/logs/a1-kernel.txt#L385) matched the ADT. After RUN, the
DART's interrupt line fired 100,005 times, Linux timed out waiting for MTP's endpoint map, and
[wake returned -62](../evidence/02-input/logs/a1-kernel.txt#L460).

## B1: write the board's own rules

Same image, [one change](https://github.com/X6e3/j713-linux/commit/0ebac09cb3bc4b2fe3edbc41030da73f2d6c9dd9): program the nine ADT rules at
0x394810000 before RUN, in the order m1n1 uses for t8110a.

[8 of 9](../evidence/02-input/logs/b1-kernel.txt#L404) read back exactly. Rule 7's end came back as
0x390eee003 instead of 0x390eee000; I do not know what the low bits mean. The interrupt storm was gone.
MTP said hello for the first time and agreed on [RTKit protocol 12](../evidence/02-input/logs/b1-kernel.txt#L407).
Then it [timed out waiting for the IOP power ACK](../evidence/02-input/logs/b1-kernel.txt#L414), and wake
returned -62 again. A [second boot](../evidence/02-input/logs/b1-repeat-kernel.txt) did the same.

## B2: remove one more thing

Both B1 boots still had a 10 ms delay between RUN and wake. We had added it in an earlier experiment to see
whether timing mattered; the wide1 kernels carry it too. I kept the DAPF code,
[removed the delay](https://github.com/X6e3/j713-linux/commit/48100bc278cf81b30c33aa501a40662e39473ebc) and touched nothing else.

[Wake returned 0](../evidence/02-input/logs/b2-kernel.txt#L413). MTP printed
["MTP Says Hello"](../evidence/02-input/logs/b2-kernel.txt#L414), the kernel registered the
[internal keyboard](../evidence/02-input/logs/b2-kernel.txt#L464), and the firmware reported
["Keyboard ready"](../evidence/02-input/logs/b2-kernel.txt#L477).

I checked the shell with the USB keyboard first, then typed on the internal keyboard. It worked; my notebook
page ends with "KEYBOARD WORKED". The trackpad clicked, but the pointer did not move: the same log shows its
[firmware request failing with -2](../evidence/02-input/logs/b2-kernel.txt#L664). That is
[section 2.2](02-input-trackpad.md).

## What this does and does not show

- Seven kernel logs: three wide1 boots, A1, two B1 boots and B2. They show a sequence, not a success rate.
- The B2 log shows MTP starting and the keyboard registering. Typing on it is my own observation.
- The DAPF mechanism and its write order come from m1n1 ([source](https://github.com/AsahiLinux/m1n1/blob/main/src/dapf.c)).
  What I did was find that J713 needed it, apply it at the right point, and test it one change at a time.

I went one layer at a time: read before writing, change one thing per boot, and keep the failed boots as
well as the working one.

## Evidence

- Logs: [A1](../evidence/02-input/logs/a1-kernel.txt), [B1](../evidence/02-input/logs/b1-kernel.txt),
  [B1 repeat](../evidence/02-input/logs/b1-repeat-kernel.txt), [B2](../evidence/02-input/logs/b2-kernel.txt),
  wide1 [1](../evidence/02-input/logs/wide1-1-dmesg.txt), [2](../evidence/02-input/logs/wide1-2-dmesg.txt),
  [3](../evidence/02-input/logs/wide1-3-dmesg.txt).
- The [manifest](../evidence/02-input/manifest.json) records each log's source, original and published
  SHA-256 and what was masked: hostname, UUIDs, the compiler's user/host and the journal machine ID. Nothing
  else was changed. The wide1 logs were recovered from a verified image of my first Fedora root.
- `make mtp` regenerates [the summary](../data/02-input/mtp_summary.json) from the logs; `make check`
  verifies the hashes, the kernel lineage, the DAPF counts and the wide1 timing.

The quoted bootloader source keeps its MIT license; [the license text](../evidence/02-input/LICENSE.m1n1.MIT)
is included.
