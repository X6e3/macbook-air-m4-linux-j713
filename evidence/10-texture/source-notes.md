# Texture lifetime source notes

- Kernel REL3, `7.1.13-x6e3-rel3` (`Image.gz` hash prefix `16c6344c`): REL2 plus the commit that keeps the GPU
  driver's mapping lists in kvmalloc memory. The texture paths here are Mesa's; the kernel change does not touch them.
- Mesa `26.3.0~devel-103.gravity.x6e3.1` (`tl1-system.txt`, `tl2-system.txt`), renderer "Apple M4 (G16G B1)" in every
  `.out` file. Run as the desktop user; run as root, EGL had picked llvmpipe in an earlier attempt, which is not here.
- Each case has three files: `.out` (what the program reports, including the read-back pixel), `.log` (stderr: the
  `TLn ns=… stage=…` phase markers and Mesa's `New:`/`Destroy:` resource lines) and `.status` (the exit status).
- `summarize-tl1.py` and `summarize-tl2.py` wrote the two summaries on the device. `analysis/texture.py` recomputes
  the results from the logs on its own, matching resources by their handle `H:`.
- The TL2 checkpoint is the `checkpoint_before_delete` marker, after the draws and `glFinish`.
