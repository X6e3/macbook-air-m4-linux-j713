# evidence/ -> analysis/ -> data/ -> figures/ -> README.md
# Python 3 standard library only. PNGs need rsvg-convert, or Quick Look on macOS.
PY  ?= python3 -I
SHA ?= shasum -a 256

all: fig01

data/01-first-boot/dtb_diff.txt: analysis/dtb_diff.py analysis/fdt.py $(wildcard evidence/01-first-boot/dtb/*.dtb)
	$(PY) analysis/dtb_diff.py > /dev/null

data/01-first-boot/boot_ab_summary.json: analysis/boot_ab.py $(wildcard evidence/01-first-boot/logs/boot-*.txt) evidence/01-first-boot/image-parts.csv
	$(PY) analysis/boot_ab.py > /dev/null

fig01: data/01-first-boot/dtb_diff.txt data/01-first-boot/boot_ab_summary.json figures/fig01_console_ab.py figures/style.py
	$(PY) figures/fig01_console_ab.py
	$(PY) tools/rasterize.py figures/out/fig01-light.svg figures/out/fig01-light@2x.png 1920
	$(PY) tools/rasterize.py figures/out/fig01-dark.svg figures/out/fig01-dark@2x.png 1920
	$(PY) tools/update_readme.py fig01

# Before every commit: identity scan, original first-boot bytes and the published evidence of sections 2 and 3.
data/02-input/mtp_summary.json: analysis/mtp.py evidence/02-input/manifest.json $(wildcard evidence/02-input/logs/*.txt)
	$(PY) analysis/mtp.py

mtp: data/02-input/mtp_summary.json

data/02-input/trackpad_summary.json: analysis/trackpad.py evidence/02-input/trackpad/manifest.json $(wildcard evidence/02-input/trackpad/*.txt) $(wildcard evidence/02-input/trackpad/*.md) evidence/02-input/trackpad/b3-config.diff
	$(PY) analysis/trackpad.py

trackpad: data/02-input/trackpad_summary.json

data/03-wifi/wifi_summary.json: analysis/wifi.py evidence/03-wifi/manifest.json $(wildcard evidence/03-wifi/*.txt) $(wildcard evidence/03-wifi/*.md) evidence/03-wifi/early-layer-verification.json
	$(PY) analysis/wifi.py

wifi: data/03-wifi/wifi_summary.json

data/02-input/afe_summary.json: analysis/afe.py evidence/02-input/afe/manifest.json $(wildcard evidence/02-input/afe/before/*.txt) evidence/02-input/afe/photo-transcriptions.md
	$(PY) analysis/afe.py

afe: data/02-input/afe_summary.json

check:
	$(PY) tools/scan_identifiers.py
	cd evidence/01-first-boot/logs && $(SHA) -c SHA256SUMS.original
	cd evidence/02-input && $(SHA) -c SHA256SUMS
	$(PY) analysis/mtp.py --check
	cd evidence/02-input/trackpad && $(SHA) -c SHA256SUMS
	$(PY) analysis/trackpad.py --check
	cd evidence/02-input/afe && $(SHA) -c SHA256SUMS
	$(PY) analysis/afe.py --check
	cd evidence/03-wifi && $(SHA) -c SHA256SUMS
	$(PY) analysis/wifi.py --check

.PHONY: all fig01 mtp trackpad afe wifi check
