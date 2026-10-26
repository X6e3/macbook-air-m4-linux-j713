#!/bin/bash
# J713 reboot-loop test, run by j713-reboot-loop.service at every boot while a loop is set up.
# Each boot: mount X63-R, wait for NTP so the clock is real, log one line, wait 15 s (time to stop it), reboot.
# After the target number of reboots it disables itself. A boot that stalls in stage 1 needs a power cycle by
# hand; the next boot then shows a long gap since the reboot was started, and the line says "stall?".
#
# Stop it at any time before the next reboot: touch ~/STOP-REBOOT-LOOP   (or sudo bash install.sh stop)
set -u
STATE=/var/lib/j713-reboot-loop
MNT=/mnt/x63r
DIR=$MNT/j713-diag/auto
STALL_GAP=75    # seconds; a clean reboot reaches an NTP-synced next boot in well under a minute; the raw gap is logged too

[ -f "$STATE/target" ] || exit 0
target=$(cat "$STATE/target")
count=$(cat "$STATE/count" 2>/dev/null || echo 0)

if ! mountpoint -q "$MNT"; then
  mkdir -p "$MNT"
  for i in $(seq 1 15); do mount -t exfat -o uid=1000,gid=1000 -L X63-R "$MNT" 2>/dev/null && break; sleep 2; done
fi

stopped() {
  [ -e "$DIR/STOP" ] && return 0
  for f in /home/*/STOP-REBOOT-LOOP; do [ -e "$f" ] && return 0; done
  return 1
}

notify() {   # a desktop notification for the logged-in user (uid 1000); ignored if the desktop is not up
  local u
  u=$(getent passwd 1000 | cut -d: -f1)
  [ -n "$u" ] && [ -S /run/user/1000/bus ] || return 0
  runuser -u "$u" -- env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
    notify-send -u "${2:-normal}" -a "J713" "J713 reboot testi" "$1" >/dev/null 2>&1 || true
}

out() {   # one line to the local log and, when X63-R is there, to its copy
  echo "$*" >> "$STATE/boots.log"
  mountpoint -q "$MNT" && { mkdir -p "$DIR"; echo "$*" >> "$DIR/boots.log"; }
  echo "$*"
}

for i in $(seq 1 60); do [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = yes ] && break; sleep 2; done
ntp=$(timedatectl show -p NTPSynchronized --value 2>/dev/null)
now=$(date +%s)
boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id)
tag=$(sed -n 's/.*x6e3\.v=\([^ ]*\).*/\1/p' /proc/cmdline)
up=$(cut -d' ' -f1 /proc/uptime)
gpu=$(ls -l /proc/[0-9]*/fd 2>/dev/null | grep -c renderD128)
wifi=$(nmcli -t -f TYPE,STATE device 2>/dev/null | awk -F: '$1 == "wifi" {print $2; exit}')
# Conditions that might go with a stall: power source and charge, hottest SMC sensor, USB devices attached.
ac=$(cat /sys/class/power_supply/*/online 2>/dev/null | head -1)
bat=$(cat /sys/class/power_supply/*/capacity 2>/dev/null | head -1)
hot=$(cat /sys/class/hwmon/hwmon*/temp*_input 2>/dev/null | sort -n | tail -1)
usb=$(ls /sys/bus/usb/devices 2>/dev/null | grep -c '^[0-9]-[0-9.]*$')
# How the previous boot ended: kernel errors now, the shutdown watchdog warning and the last journal line before.
kerr=$(journalctl -k -b 0 -p err --no-pager -q 2>/dev/null | wc -l)
wdt=$(journalctl -k -b -1 --no-pager -q 2>/dev/null | grep -c 'watchdog did not stop')
last=$(journalctl -b -1 -n 1 -o cat --no-pager -q 2>/dev/null | tr -d '|' | cut -c1-70)

prev="first boot of the loop"
if [ -f "$STATE/pending" ]; then
  read -r t pboot pntp < "$STATE/pending"
  gap=$((now - t))
  if [ "$ntp" = yes ] && [ "$pntp" = yes ]; then
    verdict=clean; [ "$gap" -gt "$STALL_GAP" ] && verdict="stall?"
  else
    verdict="unknown (clock not synced)"
  fi
  prev="reboot from $pboot: ${gap}s -> $verdict"
  rm -f "$STATE/pending"
fi
out "$(date '+%F %T') loop $count/$target boot=$boot tag=${tag:-none} up=${up}s ntp=$ntp gpu_holders=$gpu wifi=${wifi:-none} ac=${ac:-?} bat=${bat:-?}% hot=$(( ${hot:-0} / 1000 ))C usb=$usb kerr=$kerr prev_wdt=$wdt | $prev | prev_last: ${last:-none}"

finish() {
  out "$(date '+%F %T') loop ended: $1"
  notify "DONE ✅ $1. Reboot yok, makine senin." critical
  rm -f "$STATE/target" "$STATE/pending"
  systemctl disable j713-reboot-loop.service >/dev/null 2>&1
  exit 0
}

[ "$count" -ge "$target" ] && finish "all $target reboots done"
stopped && finish "stopped by hand"

notify "$count/$target bitti, 15 sn sonra reboot. Durdurmak için: touch ~/STOP-REBOOT-LOOP"
sleep 15
stopped && finish "stopped by hand"

echo "$(date +%s) $boot $(timedatectl show -p NTPSynchronized --value 2>/dev/null)" > "$STATE/pending"
echo $((count + 1)) > "$STATE/count"
sync
systemctl --no-block reboot
