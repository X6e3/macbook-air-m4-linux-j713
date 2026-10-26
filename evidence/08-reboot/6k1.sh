#!/bin/bash
# J713 6boot-K1 test on Linux (6boot-K1 image only). Two questions:
#  1. Does the K1 payload boot behind 6boot's stage 2 as it does behind P2T m1n1 (6boot handoff record in
#     /chosen, Wi-Fi board type and antenna SKU, Wi-Fi, Bluetooth, speaker card, TVS1 thermal zone)?
#  2. Reboot count: does a reboot from Linux stall again, as one did on 26 Oct with K1 behind P2T?
# Every run appends one line per boot to boots.log next to this script; a boot that never reaches Linux leaves
# no line, so Can notes those by hand (which logo, small die = stage 1, big die = 6boot stage 2).
#
#   bash 6k1.sh check        no root: one line in boots.log plus result-<time>/check.txt
#   sudo bash 6k1.sh next    the same check, then reboot with the desktop running (KWin on the GPU)
#   sudo bash 6k1.sh next-nogpu
#                            from a text console (Ctrl+Alt+F3), not the desktop: stop SDDM so that nothing holds
#                            the GPU, then reboot. A/B against `next`: does the GPU's state at reboot decide
#                            whether the next stage 1 stalls?
#   bash 6k1.sh gpu          no root, as the desktop user: GPU driver log, DRM devices, Mesa renderer
# Before each reboot the script leaves a note; the next check asks whether that reboot stalled and logs the answer
# with the mode, so the A/B count needs no notes by hand.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PENDING=$HERE/pending

ask_previous() {   # log how the last scripted reboot went
  local mode from ans
  [ -f "$PENDING" ] || return 0
  read -r mode from < "$PENDING"
  ans=
  while [ "$ans" != e ] && [ "$ans" != h ]; do
    read -r -p "Last reboot ($mode, from boot $from): did it stall at the small die? (e/h) " ans < /dev/tty
  done
  printf '%s reboot mode=%s from=%s stalled=%s\n' "$(date '+%F %T')" "$mode" "$from" \
    "$([ "$ans" = e ] && echo yes || echo no)" | tee -a "$HERE/boots.log"
  rm -f "$PENDING"
}

gpu_holders() {   # processes that have the GPU render node open
  ls -l /proc/[0-9]*/fd 2>/dev/null | grep -c 'renderD128'
}

reboot_now() {   # reboot_now <mode>
  echo "$1@$(sed -n 's/.*x6e3\.v=\([^ ]*\).*/\1/p' /proc/cmdline) $(cut -c1-8 /proc/sys/kernel/random/boot_id)" > "$PENDING"
  echo "Rebooting in 5 s (Ctrl-C stops it)..."; sleep 5
  sync; systemctl reboot
}

dtval() {   # dtval <node glob> <property>
  local f
  f=$(find /proc/device-tree/ -path "*/$1/$2" 2>/dev/null | head -1)
  [ -n "$f" ] && tr -d '\0' < "$f" || echo "(none)"
}

check() {
  local out tag bt sku wifi hci spk zone recs boot up
  ask_previous
  out=$HERE/result-$(date +%Y%m%d-%H%M%S)-check
  mkdir -p "$out"
  tag=$(sed -n 's/.*x6e3\.v=\([^ ]*\).*/\1/p' /proc/cmdline)
  bt=$(dtval 'wifi@0,0' 'brcm,board-type'); sku=$(dtval 'wifi@0,0' 'apple,antenna-sku')
  wifi=$(nmcli -t -f DEVICE,TYPE,STATE device 2>/dev/null | awk -F: '$2 == "wifi" {print $3; exit}')
  hci=$(ls /sys/class/bluetooth 2>/dev/null | grep -c '^hci')
  spk=$(grep -c 'T8132Speaker' /proc/asound/cards 2>/dev/null)
  zone=$(grep -lx 'tvs1-thermal' /sys/class/thermal/thermal_zone*/type 2>/dev/null | wc -l)
  recs=$(ls /proc/device-tree/chosen/ 2>/dev/null | grep -cE '^(x6e3|xboot),')
  boot=$(cat /proc/sys/kernel/random/boot_id)
  up=$(cut -d' ' -f1 /proc/uptime)
  {
    echo "== system"; uname -a; cat /proc/cmdline
    echo "== handoff records in /chosen"; ls /proc/device-tree/chosen/ 2>/dev/null | grep -E '^(x6e3|xboot),' || echo "(none)"
    echo "== DT"; echo "wifi board-type: $bt"; echo "wifi antenna-sku: $sku"
    echo "== devices"; echo "wifi: ${wifi:-none}"; echo "bluetooth hci: $hci"; echo "T8132Speaker card: $spk"; echo "tvs1-thermal zone: $zone"
    echo "== kernel errors (first 20)"
    { journalctl -k -b 0 -p err --no-pager 2>/dev/null || dmesg -l err 2>/dev/null; } | head -20
  } > "$out/check.txt" 2>&1
  printf '%s boot=%s tag=%s up=%ss records=%s bt=%s sku=%s wifi=%s hci=%s speaker=%s tvs1=%s\n' \
    "$(date '+%F %T')" "${boot:0:8}" "${tag:-none}" "$up" "$recs" "$bt" "$sku" "${wifi:-none}" "$hci" "$spk" "$zone" \
    | tee -a "$HERE/boots.log"
  echo "details: $out/check.txt"
  case "$tag" in
  6boot-k1-root2) ;;
  6boot-k1nogpu-root2) echo "NOTE: GPU-off test image; the desktop runs on llvmpipe on purpose" ;;
  *) echo "NOTE: this is not a 6boot-K1 image (x6e3.v=${tag:-none})" ;;
  esac
}

gpu() {   # Is the GPU driver up, and which renderer does Mesa pick? Run it as the desktop user, not with sudo.
  local out
  out=$HERE/result-$(date +%Y%m%d-%H%M%S)-gpu
  mkdir -p "$out"
  {
    echo "== system"; uname -r; grep -o 'x6e3\.v=[^ ]*' /proc/cmdline; echo "user: $(id -un), session: ${XDG_SESSION_TYPE:-none}"
    echo "== GPU driver log"
    { journalctl -k -b 0 --no-pager 2>/dev/null || dmesg 2>/dev/null; } | grep -E 'asahi|G16' | tail -40
    echo "== DRM devices"; ls -l /dev/dri 2>&1
    for c in /sys/class/drm/card* /sys/class/drm/renderD*; do
      [ -e "$c/device/driver" ] && echo "$(basename "$c"): $(basename "$(readlink "$c/device/driver")")"
    done
    echo "== renderer"
    if command -v glxinfo >/dev/null 2>&1; then glxinfo -B 2>&1 | grep -iE 'renderer|version string|accelerated'; else echo "(no glxinfo)"; fi
    if command -v eglinfo >/dev/null 2>&1; then eglinfo -B 2>&1 | grep -iE 'renderer|driver' | head -8; else echo "(no eglinfo)"; fi
    echo "== variables that force software rendering"
    env | grep -E '^(LIBGL_ALWAYS_SOFTWARE|GALLIUM_DRIVER|MESA_LOADER_DRIVER_OVERRIDE|MESA_GL_VERSION_OVERRIDE)=' || echo "(none in this shell)"
    grep -sHE 'LIBGL_ALWAYS_SOFTWARE|GALLIUM_DRIVER|MESA_LOADER_DRIVER_OVERRIDE' /etc/environment /etc/profile.d/* \
      "$HOME"/.bashrc "$HOME"/.bash_profile "$HOME"/.profile "$HOME"/.config/environment.d/* 2>/dev/null || echo "(none in profile files)"
    echo "== Mesa"; rpm -qa 2>/dev/null | grep -E '^mesa-(dri-drivers|libGL|vulkan-drivers)' | sort
  } > "$out/gpu.txt" 2>&1
  cat "$out/gpu.txt"
  echo "saved: $out/gpu.txt"
}

case "${1:-}" in
check) check ;;
gpu) gpu ;;
next)
  [ "$(id -u)" = 0 ] || { echo "STOP: run with sudo"; exit 1; }
  check
  echo "GPU render node holders: $(gpu_holders)"
  reboot_now desktop
  ;;
next-nogpu)
  [ "$(id -u)" = 0 ] || { echo "STOP: run with sudo"; exit 1; }
  case "$(tty)" in /dev/tty[0-9]*) ;; *) echo "STOP: run this from a text console (Ctrl+Alt+F3), not from the desktop"; exit 1 ;; esac
  check
  systemctl stop sddm
  for i in 1 2 3 4 5 6 7 8 9 10; do [ "$(gpu_holders)" = 0 ] && break; sleep 1; done
  n=$(gpu_holders)
  echo "GPU render node holders after stopping SDDM: $n" | tee -a "$HERE/boots.log"
  [ "$n" = 0 ] || { echo "STOP: something still holds the GPU; not rebooting (sudo systemctl start sddm brings the desktop back)"; exit 1; }
  reboot_now nogpu
  ;;
*) echo "usage: bash 6k1.sh check | bash 6k1.sh gpu | sudo bash 6k1.sh next | sudo bash 6k1.sh next-nogpu"; exit 2 ;;
esac
