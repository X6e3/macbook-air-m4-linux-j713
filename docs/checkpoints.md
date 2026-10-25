# Checkpoints

Which build each result comes from. I put the kernel series together after several of these boots, so commit
dates are not experiment dates.

| Date and test | Build or state | Source | What it shows |
| --- | --- | --- | --- |
| 26–27 September, v3c–v6q | 21 archived initramfs logs; image-part hashes identify variants | First two J713 patches; later framebuffer scope change separate | Console attachment comparison; initial desktop used software rendering |
| 28 September, A1/B1/B2 | Four kernel exports, including B1 repeat | DAPF snapshot/programming and removal of the temporary RUN delay | Protocol progression and keyboard readiness; early B2 still lacks trackpad firmware |
| 28 September–7 October, MTP/HID and Wi-Fi | Trackpad config diff, journal selection and Wi-Fi build records | Existing HID drivers enabled; board firmware plus Reeves join fallback | Firmware/HID and connection results; intermittent AFE failures retained |
| 6–7 October, GPU and wfi4/wfi5 | Probe, Mesa reproducer/cold session, separate A/B/A power runs | Ten-group handoff and kernel handling; compression patch; register-saving WFI | Rendering and idle results through simpledrm, not native DCP |
| 15 October, audio0 | `7.1.13-x6e3-g58b57e3c745e-dirty` | First 19 curated commits, tree `85fe15f109379e80e8a16e176abd7aaef0860236` | Recovered source/config correspondence; not a bit-identical rebuild |
| 18 October, D4–D8 and N1–N4 | DCP logs/component comparison, AFE photo transcriptions | Brightness and DCP domain changes, AFE sequence, SMC DT node | Native internal display; two successful first boots after macOS with the reset sequence |
| 19 October, S2e | `7.1.13-x6e3-s2`; `configs/j713-s2e.config`; explicit −30 dB boot argument | `122a53ed92cf58482587a56d2352abc03608b0eb`, 33 commits above Gravity base | Functional display/stereo checkpoint; speaker observations are distinct from the source comparison |
| 23 October, LIM2 | `7.1.13-x6e3-pri1` with revised thermal DTB; 20-minute workload | `e4daceaff3bd7d42cf25d7ccadb941421321b12e`, 36 commits above base | TVS1 regulation in that workload; not the thermal behavior of S2e |
| 23 October, audio snapshot | Driver parameter 60, suspended PipeWire stereo sink | Passive running-system readback | Effective ceiling parameter and userspace format; no additional playback test |

The 33 and 36 commit counts belong to those two checkpoints and include their documentation and configuration
commits; later documentation commits make the branch longer without a new tested kernel. A kernel version
string alone does not identify the DTB, boot arguments, Mesa library or image. The S2e and LIM2 source and
configuration matches come from comparisons made at the time, not from new builds.
