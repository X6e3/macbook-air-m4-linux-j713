# Display source notes

Kernel series for J713:

- `d9ff26134b68`: `drivers/gpu/drm/apple/iomfb_template.c`, start firmware-26.6 panels at 30% of the
  configured maximum brightness.
- `f924414a091b`: `arch/arm64/boot/dts/apple/t8132-j713.dts`, remove external-controller aliases, enable the
  internal DCP path, describe the panel and give DCP the DPTX PHY's power domain.

The earlier D1 and D2 images were built, but no retained record establishes that they were booted. They are
not counted as failed hardware tests. D3's stalled boot was observed at the machine; there is no complete D3
kernel export in this evidence set.

The D4–D8 logs are retained kernel exports, copied with identity substitutions. The image-part hashes were
recomputed on 24 October from the preserved diagnostic images. No image, firmware or initramfs is published.
D5/D7/D8 kernel+initramfs and stage2 hashes match; the image-identifying argument changes, and so does the DTB.
D6 additionally has `pd_ignore_unused`.

The D4 and D5 builds differ in compiler as well as the brightness patch: Rust 1.98.1 versus 1.99.0.
The later DT-only comparisons reuse the same rebuilt kernel bytes.

## Implementation locations

Kernel runtime-source revision `90ea22e57db4340957715a012ab9b859d3199ffb`; baseline `3b85d81f656af14d0fc4bea3eef87fe040c424f9`. The links below point at fixed source revisions.

- [`drivers/gpu/drm/apple/dcp.c`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/drivers/gpu/drm/apple/dcp.c): firmware endpoint startup, notch and panel properties.
- [`drivers/gpu/drm/apple/parser.c`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/drivers/gpu/drm/apple/parser.c): mode active-height and sync adjustment for notch.
- [`drivers/gpu/drm/apple/iomfb_template.c`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/drivers/gpu/drm/apple/iomfb_template.c): res_is_main_display(), first brightness update, swap rectangle notch offset.
- [`drivers/gpu/drm/apple/apple_drv.c`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/drivers/gpu/drm/apple/apple_drv.c): conflicting framebuffer removal, DRM registration and client setup.
- [`drivers/pmdomain/core.c`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/drivers/pmdomain/core.c): unused worker versus of_genpd_sync_state().
- [`arch/arm64/boot/dts/apple/t8132-j713.dts`](https://github.com/X6e3/j713-linux/blob/90ea22e57db4340957715a012ab9b859d3199ffb/arch/arm64/boot/dts/apple/t8132-j713.dts): DCP power-domain consumer, internal path and panel description.

The base includes Josh Rodd's J715/26.6.2 panel support (`1a0bfae9821e`) and the existing Asahi/Gravity
DCP architecture. D8 logs a 64-pixel notch, a firmware surface height of 1664 and the adjusted 1600-line DRM
mode. `parser.c` and the swap path explain the crop; no physical panel measurement is claimed.
No retained DCP experiment establishes that DAPF programming was the external-controller fix.
