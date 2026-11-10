# TL2 — AGX selective sampling / resource lifetime

32 textures, each DXT5 1024×1024 with 11 mip levels; fresh process/EGL context per condition.
**Checkpoint:** after the selected draws and `glFinish`, BEFORE `glReadPixels`, `glDeleteTextures`, or context destruction.
Counts are Gallium resource objects reported by `ASAHI_MESA_DEBUG=resource`; physical BO reclamation is not measured.

| Case | Draws | Old 4 MiB: New | Old destroyed by checkpoint | **Old live** | Full 5.34 MiB live | Retained target MiB | Pixel | Result |
|---|---:|---:|---:|---:|---:|---:|---|---|
| A | 0 | 32 | 0 | **32** | 32 | 299.00 | `0,0,0,255` | matches model |
| B | 1 | 32 | 1 | **31** | 32 | 295.00 | `255,255,255,255` | matches model |
| C | 16 | 32 | 16 | **16** | 32 | 235.00 | `255,255,255,255` | matches model |
| D | 32 | 32 | 32 | **0** | 32 | 171.00 | `255,255,255,255` | matches model |
| E | 0 | 0 | 0 | **0** | 32 | 171.00 | `0,0,0,255` | matches model |

**Interpretation rule:** A versus B from TL1 showed finish alone did not release the old resource; TL2 tests whether first sampling releases the old 4 MiB resource on a per-texture basis.
A linear 32→31→16→0 result supports draw-associated validation; it does not prove a Mesa leak or reclaimable physical RAM.
If E produces no old resource, setting MAX_LEVEL before the first mip upload avoids transient single-level allocations in this controlled path. Xonotic behavior still needs separate attribution.
