# 10. Xonotic, the crash on REL2 and compressed textures in GPU memory

28 October 2026. Kernels REL2 and REL3, Fedora 44, Mesa `26.3.0~devel-103.gravity.x6e3.1`.

I wanted a game that would load the GPU hard, with a lot of particle effects. Searching online I came across Xonotic,
which is old, well optimised and open source. I had never played it. I unpacked Fedora's 0.8.6 packages onto my
external disk and ran the game from there. That night I played it on and off for two and a half to three hours,
counting the match on REL3 in the morning, and before long I was playing because I liked it: bunnyhopping round the
maps with the internal keyboard and my own mouse, a Logitech G Pro Superlight 2. The internal trackpad works for it
too. On public servers the regulars beat me soundly.

## Software rendering first, then the GPU

The first launches, between 03:01 and 03:08, drew on the CPU: the game logs name `llvmpipe` as the renderer, once
through zink. In the first weeks, when the desktop still ran on llvmpipe ([section 4](04-gpu.md)), I had set Mesa to
render in software for safety. Part of that setting was still in place, and in the excitement of the game I had
forgotten it: I started looking for the cause, and the [EGL debug log](../evidence/10-xonotic/game/egl-wsi-debug.log)
saved at 03:13 is that search. Once I remembered and flipped that one value, the game ran on the GPU, and the log
that ends at 03:55 names `Apple M4 (G16G B1)`. On llvmpipe I saw 5–28 FPS; on the GPU, at 1920×1200 full screen, the
frame rate stayed at about 250–410 FPS. Neither figure was logged.

The game logs have two maps from those hours ([game logs](../evidence/10-xonotic/game/)): boil against five bots on
llvmpipe, and warfare against five bots on the GPU, where the log has me drawing first blood and making a triple
frag. The sound came from the two woofers, a little muffled, as expected with the tweeters off
([section 6](06-audio.md)). The case stayed at its usual temperature.

## The crash on REL2

While I played, the game's memory kept growing. Then the game dropped out to a black screen, KWin reported that it
had failed, and the desktop came back on llvmpipe. I saved the journal straight away; the
[excerpt](../evidence/10-xonotic/journal/excerpt.txt) has its kernel, KWin and Xonotic lines. Linux sees 15.4 GiB of
memory on this machine.

| Time | What the journal shows |
| --- | --- |
| 04:02:56 | The GPU driver fails an order-4 allocation in the submit ioctl for Xonotic, and the game aborts (signal 6). 0.52 GiB is free, under the kernel's own minimum of 0.55 GiB, and 9.30 GiB is unevictable. While systemd-coredump saves the crash, the kernel's out-of-memory killer runs and stops it. |
| 04:09:39 | The same failure in the next run, with 0.41 GiB free and 9.08 GiB unevictable; the game aborts again. |
| 04:12:50 | An order-4 failure again, this time while the driver unmaps a buffer that is being closed: `G16: failed to unbind closed GEM object: ENOMEM`. Xonotic crashes (signal 11), and KWin aborts after `DRM_IOCTL_ASAHI_SUBMIT render failed: Input/output error`. The out-of-memory killer runs again and stops another desktop application. |
| 04:12:51 | The restarted KWin cannot bind GPU memory (`DRM_IOCTL_ASAHI_VM_BIND failed`, 34 times), and Mesa's zink fallback finds no device. |

The journal does not name the renderer the desktop came back on; that it was llvmpipe is what I saw. The kernel trace
shows where the allocation fails: the driver copies the VM's list of mappings into every job it submits, one 48-byte
entry per mapping, in a kmalloc vector that grows by doubling. With a few thousand buffers that copy needs 256 KiB of
physically contiguous memory, order 4 on 16 KiB pages, on every submit. Each time it failed, free memory was below
the kernel's own minimum and more than 9 GiB could not be reclaimed, and an allocation that large is the first to
fail. Unmapping builds a list that grows the same way, which is the failure at 04:12:50.

## The reruns with Mesa's buffer dump

From 05:05 I ran the game again in a 1281×800 window with Mesa's buffer dump on, to see where the memory goes
([reruns](../evidence/10-xonotic/rel2-runs/)):

| Run | Map | Render-target buffers, first dump → peak | All buffers at the peak | Available memory, start → lowest | End |
| --- | --- | --- | --- | --- | --- |
| lowres | dance | 111 MiB in 68 → 8.0 GiB in 1,709 | 8.1 GiB in 2,246 | 10.30 → 0.91 GiB | the same order-4 failure, at 05:05:41 |
| rt-test | boil | 77.5 MiB in 37 → 4.8 GiB in 1,444 | 4.8 GiB in 1,927 | 9.93 → 3.93 GiB | a safety stop at 05:17:28, while the map was still loading |

Almost all of the memory is in the dump's render-target category. A third run at 05:14 was stopped before the map
loaded. Most of Xonotic's textures are DXT-compressed: its data has 1,207 DDS files.

## The fix: REL3

The failure is in the kernel driver. In
[784e8e030a0b](https://github.com/X6e3/j713-linux/commit/784e8e030a0b3e179ae2fb3734bca949597b1cce) the driver keeps
its mapping lists in kvmalloc memory, which can fall back to vmalloc, built from single pages, and sizes the submit
and unmap copies once from the current length. REL3 is REL2 with that commit (`7.1.13-x6e3-rel3`). On REL3 a full
match finished and the game exited normally, without the allocation failure. Before REL3 I had to quit the game to
get the memory back; since then I have not had to. That is one match and my use since, not an A/B, and the change
removes this failure; it does not make the game use less memory.

## Where the memory goes: compressed textures (TL1, TL2)

Two controlled experiments, TL1 and TL2, show what the current Mesa path does with a DXT texture on J713. Both upload
DXT5 textures of 1024×1024 with 11 mip levels, one level at a time, and log every Gallium resource with
`ASAHI_MESA_DEBUG=resource` between phase markers; every case runs in its own process and EGL context ([TL1
source](../evidence/10-texture/tl1.c), [TL2 source](../evidence/10-texture/tl2.c)).

## What one texture becomes

The Apple9 path in this Mesa cannot sample DXT formats, so the state tracker stores the texture decompressed, as
`r8g8b8a8_unorm`. The full chain takes 0x558000 bytes, 5.34 MiB, against 1.33 MiB of DXT5 data: 4.01 times as much.

With the default minification filter, the upload of level 0 creates a single-level resource of 4 MiB first; the
upload of level 1 creates the full chain next to it. The old resource is not dropped at that point.

## When the single-level resource goes (TL1)

Seven scenarios with one texture each ([summary](../evidence/10-texture/tl1-summary.md)):

| Scenario | Order | Single-level resource destroyed at |
| --- | --- | --- |
| A | upload, delete | delete |
| B | upload, `glFinish`, delete | delete |
| C | upload, draw, delete | first draw |
| D | upload, draw, `glFinish`, delete | first draw |
| E | upload, draw, unbind, `glFinish`, delete | first draw |
| O | the order of the earlier reproducer | first draw |
| V | a white texture, drawn and read back | first draw |

`glFinish` alone does not release it; the first draw that samples the texture does. V read back 255, 255, 255, 255,
so the texture was really sampled.

## Per texture (TL2)

32 textures, a chosen number of them drawn, counted after the draws and `glFinish`, before any readback or delete
([summary](../evidence/10-texture/tl2-summary.md)). The expected counts were written down before the run.

| Case | Drawn | Single-level resources live | Full chains live | Live |
| --- | ---: | ---: | ---: | ---: |
| A | 0 | 32 | 32 | 299 MiB |
| B | 1 | 31 | 32 | 295 MiB |
| C | 16 | 16 | 32 | 235 MiB |
| D | 32 | 0 | 32 | 171 MiB |
| E | 0, `GL_TEXTURE_MAX_LEVEL` set before the upload | 0 | 32 | 171 MiB |

All five match. Each first draw releases that texture's single-level resource and no other. With
`GL_TEXTURE_MAX_LEVEL` set before level 0, Mesa allocates the full chain at once and the single-level resource never
exists.

## What this does and does not show

The journal lines show where the allocation failed and what KWin reported. The black screen, the desktop on llvmpipe
and both frame rates are what I saw; nothing logged them. REL3 rests on one match and my use since. The buffer dump
counts the buffers Mesa holds, and the TL counts are Gallium resource objects: they do not show when the memory
behind them returns to the system, so none of this is called a leak. A texture that is uploaded but not yet drawn
costs 9.34 MiB here instead of 1.33 MiB. How much of Xonotic's 8 GiB comes from these two effects is not measured:
that needs to know which textures the game samples and when. [`xonotic.py`](../analysis/xonotic.py) and
[`texture.py`](../analysis/texture.py) recompute every number on this page from the evidence, and `make check`
verifies them.

## Evidence

- Game logs: [the first launches, the bot matches and the EGL debug log](../evidence/10-xonotic/game/). The log from
  the public server is left out: it holds the server's address.
- Crash: [journal excerpt](../evidence/10-xonotic/journal/excerpt.txt) and the
  [filter that wrote it](../evidence/10-xonotic/journal/excerpt.py). The full journal stays private, because it also
  holds other programs' messages; its hash is in the source notes.
- Reruns: [game, memory, kernel and event logs](../evidence/10-xonotic/rel2-runs/).
- TL1 and TL2: [sources, logs and summaries](../evidence/10-texture/),
  [TL1 summary](../evidence/10-texture/tl1-summary.md), [TL2 summary](../evidence/10-texture/tl2-summary.md).
- [Source notes for the game](../evidence/10-xonotic/source-notes.md) and
  [for TL1 and TL2](../evidence/10-texture/source-notes.md),
  [Xonotic summary](../data/10-xonotic/xonotic_summary.json),
  [texture summary](../data/10-texture/texture_summary.json).
