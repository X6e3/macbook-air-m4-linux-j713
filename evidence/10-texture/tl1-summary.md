# TL1 — AGX resource lifetime, 1024² RGBA8

Instrument: `ASAHI_MESA_DEBUG=resource` with phase markers. Each scenario runs in a fresh process/context.
Note: New/Destroy refer to logged resource objects; these are not direct measurements of physical GPU memory reclamation.

| Scenario | Renderer | 4 MiB New→Destroy | 5.34 MiB New→Destroy | Old live at delete | Old live after finish | Status |
|---|---|---|---|---:|---:|---|
| A | Apple M4 (G16G B1) | 1 (upload_level_00_begin×1) → 1 (delete_begin×1) | 1 (upload_level_01_begin×1) → 1 (delete_begin×1) | 1 | 0 | status=0 |
| B | Apple M4 (G16G B1) | 1 (upload_level_00_begin×1) → 1 (delete_begin×1) | 1 (upload_level_01_begin×1) → 1 (delete_begin×1) | 1 | 0 | status=0 |
| C | Apple M4 (G16G B1) | 1 (upload_level_00_begin×1) → 1 (draw_begin×1) | 1 (upload_level_01_begin×1) → 1 (context_destroy_begin×1) | 0 | 0 | status=0 |
| D | Apple M4 (G16G B1) | 1 (upload_level_00_begin×1) → 1 (draw_begin×1) | 1 (upload_level_01_begin×1) → 1 (context_destroy_begin×1) | 0 | 0 | status=0 |
| E | Apple M4 (G16G B1) | 1 (upload_level_00_begin×1) → 1 (draw_begin×1) | 1 (upload_level_01_begin×1) → 1 (context_destroy_begin×1) | 0 | 0 | status=0 |
| O | Apple M4 (G16G B1) | 1 (upload_level_00_begin×1) → 1 (draw_begin×1) | 1 (upload_level_01_begin×1) → 1 (context_destroy_begin×1) | 0 | 0 | status=0 |
| V | Apple M4 (G16G B1) | 1 (upload_level_00_begin×1) → 1 (draw_begin×1) | 1 (upload_level_01_begin×1) → 1 (context_destroy_begin×1) | 0 | 0 | status=0 |

Verification pixel: `255,255,255,255`.


**Decision rule:** Compare A and B (finish without draw), C and D (finish after draw), D and E (unbind), then O (original order) and V (sampling/readback validation). Do not infer a leak simply because a resource survives to context cleanup. Check raw logs and phases before interpreting causality.
