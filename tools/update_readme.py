#!/usr/bin/env python3
"""Copy a generated figure caption into README.md between its markers.

    <!-- fig01:begin -->  ...generated, do not edit...  <!-- fig01:end -->

    python3 tools/update_readme.py fig01
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
name = sys.argv[1]
readme = (ROOT / "README.md").read_text()
caption = (ROOT / f"figures/out/{name}-caption.md").read_text().strip()
pattern = re.compile(rf"(<!-- {name}:begin -->).*?(<!-- {name}:end -->)", re.S)
assert pattern.search(readme), f"README.md has no {name} markers"
(ROOT / "README.md").write_text(pattern.sub(lambda m: m.group(1) + "\n" + caption + "\n" + m.group(2), readme))
print(f"README.md: {name} caption updated")
