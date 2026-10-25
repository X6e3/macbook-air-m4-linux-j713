# Reproducing the analysis

These commands work only on the archived evidence. They do not boot anything, touch a device or run a load.
Run them from the repository root with Python 3.10 or newer, make and `shasum`. The analyses use only the
standard library. Do not run them with `-O`: their assertions are the checks.

```sh
make check
python3 -I analysis/boot_ab.py
python3 -I analysis/dtb_diff.py
make mtp trackpad afe wifi later-stages
python3 -I figures/fig01_console_ab.py
make check
```

The first `make check` only reads. The rest regenerates the derived tables, SVGs and captions; `make` can skip
targets that look current, so run a script directly to force it. `make fig01` also rasterises the two SVGs and
refreshes the README figure block. PNGs need `rsvg-convert` (librsvg2-tools on Linux), or Quick Look and `sips`
on macOS, and their bytes can differ between platforms. SVGs, captions, JSON and CSV come out the same for the
same inputs, and the README uses the SVGs.

## What a passing check means

The first-night parser checks the console timestamp against the same log's dmesg, recounts the PMGR failures,
resolves the framebuffer power-domain reference in the real DTBs and compares the stored CSV and JSON. The DTB
comparison resolves phandles before comparing. The A/B component equality is checked against the image-part
manifest; the boot images are not published, so a reader cannot recompute those hashes.

Sections 2–7 check each evidence file against its manifest and recompute the results and summaries. GPU table
counts come from the selected ADT properties and display modes from DCP's selected-mode lines. Time columns are
local to each test; the macOS and Linux runs are separate captures and are not synchronised.

A hash shows that a copy has not changed, not who made the data. `original_sha256` can only be checked where the
original file exists; the published copies, some redacted or reduced to selected columns, are covered by
`published_sha256`. Private images, firmware, identifying ADT dumps and photographs are not included. Source
notes are my explanations, not machine logs.

`tools/scan_identifiers.py` looks for known identity patterns in text and DTBs and for JPEG metadata. It catches
the usual leaks; it is not a complete secret scanner or a licence check.

## Source and hardware

The kernel repository is based on GravityLinux `3b85d81f656af14d0fc4bea3eef87fe040c424f9`. The
[checkpoint table](checkpoints.md) maps results to source stages; its commit links point at the published series,
not the original build IDs. The bootloader GPU diff and the Mesa compression patch are included as source, with
their upstream notices. This repository does not give you a complete reproducible kernel, Mesa or boot-image
build, and it does not redistribute firmware.

Three different things can be repeated: the analysis, with the commands above; the source reading, by following
the referenced changes; and the hardware tests, which need the machine, its firmware, the images, the
configuration and the original conditions.
