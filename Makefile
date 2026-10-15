# evidence/ -> analysis/ -> data/ -> figures/ -> README.md
# Python 3 standard library only. PNGs need rsvg-convert, or Quick Look on macOS.
PY  ?= python3 -I
SHA ?= shasum -a 256

all: fig01

data/stage1/dtb_diff.txt: analysis/stage1_dtb_diff.py analysis/fdt.py $(wildcard evidence/stage1/dtb/*.dtb)
	$(PY) analysis/stage1_dtb_diff.py > /dev/null

data/stage1/boot_ab_summary.json: analysis/stage1_boot_ab.py $(wildcard evidence/stage1/logs/boot-*.txt) evidence/stage1/image-parts.csv
	$(PY) analysis/stage1_boot_ab.py > /dev/null

fig01: data/stage1/dtb_diff.txt data/stage1/boot_ab_summary.json figures/fig01_console_ab.py figures/style.py
	$(PY) figures/fig01_console_ab.py
	$(PY) tools/rasterize.py figures/out/fig01-light.svg figures/out/fig01-light@2x.png 1920
	$(PY) tools/rasterize.py figures/out/fig01-dark.svg figures/out/fig01-dark@2x.png 1920
	$(PY) tools/update_readme.py fig01

# before every commit: no identity or secrets, and the evidence logs are the original bytes
check:
	$(PY) tools/scan_identifiers.py
	cd evidence/stage1/logs && $(SHA) -c SHA256SUMS.original

.PHONY: all fig01 check
