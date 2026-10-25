#!/bin/sh
# J713 GPU power under macOS, for the Linux GPU max-power value (an estimate today: 23533 mW).
# 10 s idle, then N s (default 120) of full Metal compute load, sampled every second by powermetrics.
# Read-only for the system: it writes only result-<time>/ next to this script.
#
#   sudo sh gpu-power-j713.sh [seconds of load, default 120]
set -eu
N=${1:-120}
: "${SUDO_USER:?run with sudo}"
D=$(cd "$(dirname "$0")" && pwd)
OUT="$D/result-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
caffeinate -dimsu -w $$ & # no display, idle or system sleep until this script exits
{ sysctl -n hw.model; sw_vers; pmset -g batt | head -2; pmset -g | grep -i lowpowermode; } > "$OUT/system.txt"
SRC=$(pmset -g batt | head -1 | sed "s/.*'\(.*\)'.*/\1/")

sudo -u "$SUDO_USER" "$D/smc-read" watch $((N + 15)) > "$OUT/smc.txt" &
SMC=$!
/usr/bin/powermetrics --samplers gpu_power,thermal -i 1000 -n 10 > "$OUT/idle.txt"
sudo -u "$SUDO_USER" "$D/gpu-load" $((N + 5)) > "$OUT/load.txt" 2>&1 &
LOAD=$!
sleep 2
/usr/bin/powermetrics --samplers gpu_power,thermal -i 1000 -n "$N" > "$OUT/loaded.txt"
wait "$LOAD" "$SMC" # not a bare wait: caffeinate is a child too, and it waits for this script
chown -R "$SUDO_USER" "$OUT"
grep -h 'GPU Power' "$OUT/loaded.txt" | awk -v src="$SRC" '{v=$3+0; s+=v; n++; if (v>m) m=v} END {printf "%s, loaded: %d samples, peak %d mW, mean %d mW\n", src, n, m, s/n}'
grep -h 'Current pressure' "$OUT/loaded.txt" | sort | uniq -c
awk 'NR == 1 {for (i = 2; i <= NF; i++) k[i] = $i; next}
     {for (i = 2; i <= NF; i++) {if ($i > m) {m = $i; mk = k[i]} if (k[i] ~ /^Tg/ && $i > g) g = $i}}
     END {printf "GPU sensors (Tg*) peak %.1f C, hottest sensor %s %.1f C\n", g, mk, m}' "$OUT/smc.txt"
echo "saved $OUT"
