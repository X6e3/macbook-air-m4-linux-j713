#!/bin/bash
# J713 side check on Linux, for a phone sound meter (phyphox, Audio Amplitude) at one corner of the machine.
# Plays noise-left, noise-right, noise-right, noise-left through PipeWire with 15 s of silence after each, so that
# each file comes once early and once late, and logs the speaker driver's limiter state twice a second.
#   bash /mnt/x63r/j713-diag/o12b/side/side.sh left      (phone at the left corner; then again with: right)
set -u
POS=${1:-}
case "$POS" in left|right) ;; *) echo "usage: bash side.sh left|right   (where the phone is)"; exit 2 ;; esac
F=$(cd "$(dirname "$0")" && pwd)
ST=/sys/bus/platform/devices/speaker-audio/state
OUT=$F/result-side-$POS-$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
{ uname -r; grep -o 'ceiling_dvc=[0-9]*' /proc/cmdline; wpctl status 2>/dev/null | sed -n '/Sinks:/,/Sources:/p'; } > "$OUT/system.txt"
(while :; do echo "$(date +%s.%N | cut -c1-14) $(cat "$ST" 2>/dev/null)"; sleep 0.5; done) > "$OUT/state.txt" &
LOGGER=$!
trap 'kill $LOGGER 2>/dev/null' EXIT
echo "Start phyphox now (▶). The first sound comes in 5 s; the whole run takes about 90 s."
sleep 5
for f in noise-left noise-right noise-right noise-left; do
    echo "$(date +%s.%N | cut -c1-14) $f" >> "$OUT/order.txt"
    echo "playing $f"
    pw-play "$F/$f.wav" 2>>"$OUT/pw-play-errors.txt"
    sleep 15
done
echo "done; stop phyphox and export. Saved $OUT"
