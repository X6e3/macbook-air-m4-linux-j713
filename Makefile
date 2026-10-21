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

# Before every commit: identity scan, original Stage 1 bytes and Stage 2 publication integrity.
data/stage2/mtp_summary.json: analysis/stage2_mtp.py evidence/stage2/manifest.json $(wildcard evidence/stage2/logs/*.txt)
	$(PY) analysis/stage2_mtp.py

mtp: data/stage2/mtp_summary.json

data/stage2/trackpad_summary.json: analysis/stage2_trackpad.py evidence/stage2/trackpad/manifest.json $(wildcard evidence/stage2/trackpad/*.txt) $(wildcard evidence/stage2/trackpad/*.md) evidence/stage2/trackpad/b3-config.diff
	$(PY) analysis/stage2_trackpad.py

trackpad: data/stage2/trackpad_summary.json

data/stage3/wifi_summary.json: analysis/stage3_wifi.py evidence/stage3/manifest.json $(wildcard evidence/stage3/*.txt) $(wildcard evidence/stage3/*.md) evidence/stage3/early-layer-verification.json
	$(PY) analysis/stage3_wifi.py

wifi: data/stage3/wifi_summary.json

check:
	$(PY) tools/scan_identifiers.py
	cd evidence/stage1/logs && $(SHA) -c SHA256SUMS.original
	cd evidence/stage2 && $(SHA) -c SHA256SUMS
	$(PY) analysis/stage2_mtp.py --check
	cd evidence/stage2/trackpad && $(SHA) -c SHA256SUMS
	$(PY) analysis/stage2_trackpad.py --check
	cd evidence/stage3 && $(SHA) -c SHA256SUMS
	$(PY) analysis/stage3_wifi.py --check

.PHONY: all fig01 mtp trackpad wifi check
