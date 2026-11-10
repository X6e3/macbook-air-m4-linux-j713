#!/bin/bash
# J713 O2 test on Linux (O12b image only): which region_c word limits the GPU, and in what steps. The O12b kernel
# lets debugfs asahi_m4/probe_XX lower one of the words the open-source driver initialises at start (+0x84 +0x88
# +0x8c +0x90 +0x94 +0x98, never above its start value, 1000 for words that start at 0; writing 4294967295 gives
# the word back). live_XX read the words back; region_c_changed counts words of the page that differ from what Linux
# wrote, i.e. whether the GPU firmware writes into region_c.
#
#   sudo -v; bash o-gpu.sh observe   read only: 60 s idle, 150 s gl-burn, 60 s cool-down, no writes
#   sudo -v; bash o-gpu.sh dose      A/B/A: 45 s phases, A = every word at its start value, B = one word lowered.
#                                    +0x8c in steps of 50 from 950 to 50, the other words at three or two levels
#                                    each, all B phases in random order. About 55 minutes of load.
#
# Logged once a second: every SMC temperature and power, the GPU cooling state, live_*, region_c_changed/first.
# During dose the GPU thermal zone is switched off (and its cooling state set to 0) so that A really is the start
# value; it is switched back on at the end or on Ctrl+C. Instead the load is paused while any SoC sensor is at or
# above 90 C and resumes at 75 C; the phase clock only runs while the load runs. Safety stop (load ends, every word
# given back, zone back on): any SoC sensor >= 95 C or TVS1 >= 70 C. Writes only result-o-gpu-<mode>-<time>/ here.
set -u
MODE=${1:-}
case "$MODE" in observe|dose) ;; *) echo "usage: bash o-gpu.sh observe|dose"; exit 2 ;; esac
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/result-o-gpu-$MODE-$(date +%Y%m%d-%H%M%S)
D=/sys/kernel/debug/asahi_m4
BIN=/tmp/gl-burn-o12b
PHASE=45
SOC_STOP=95000 TVS1_STOP=70000 SOC_PAUSE=90000 SOC_RESUME=75000 # millidegrees C
WORDS=(84 88 8c 90 94 98)
RELEASE=4294967295
unset LIBGL_ALWAYS_SOFTWARE GALLIUM_DRIVER MESA_LOADER_DRIVER_OVERRIDE

grep -q 'x6e3\.v=6boot-o12b' /proc/cmdline || { echo "STOP: not the O12b image ($(grep -o 'x6e3\.v=[^ ]*' /proc/cmdline))"; exit 1; }
HW=$(grep -lx 'SMC TVS1' /sys/class/hwmon/hwmon*/temp*_label 2>/dev/null | head -1)
[ -n "$HW" ] || { echo "STOP: no 'SMC TVS1' sensor"; exit 1; }
HW=$(dirname "$HW")
CDEV=$(grep -lx 'asahi-gpu' /sys/class/thermal/cooling_device*/type 2>/dev/null | head -1)
CDEV=${CDEV:+$(dirname "$CDEV")}
ZONE=
if [ -n "$CDEV" ]; then
    for z in /sys/class/thermal/thermal_zone*; do
        for l in "$z"/cdev[0-9]*; do [ "$(readlink -f "$l")" = "$(readlink -f "$CDEV")" ] && ZONE=$z; done
    done
fi
sudo -v || { echo "STOP: sudo is needed for debugfs"; exit 1; }
sudo test -w "$D/probe_8c" -a -r "$D/region_c_changed" || { echo "STOP: $D/probe_8c missing. Is this the O12b kernel?"; exit 1; }
[ "$MODE" = observe ] || [ -n "$ZONE" ] || { echo "STOP: no thermal zone drives the asahi-gpu cooling device"; exit 1; }
mkdir -p "$OUT"

give_back() { local w; for w in "${WORDS[@]}"; do echo $RELEASE | sudo -n tee "$D/probe_$w" > /dev/null; done; }
ZONE_MODE=$( [ -n "$ZONE" ] && cat "$ZONE/mode" 2>/dev/null )
zone_back() { [ -n "$ZONE" ] && [ -n "$ZONE_MODE" ] && echo "$ZONE_MODE" | sudo -n tee "$ZONE/mode" > /dev/null; }
opp=$(for n in /sys/firmware/devicetree/base/*opp* /sys/firmware/devicetree/base/*/*opp*; do
          case "$n" in (*gpu*|*GPU*|*agx*) echo "$(basename "$n") $(ls -d "$n"/opp* 2>/dev/null | wc -l)";; esac
      done 2>/dev/null)
{ uname -a; cat /proc/cmdline; echo "hwmon: $HW ($(cat "$HW/name"))"; echo "cooling: ${CDEV:-none} zone: ${ZONE:-none} mode: ${ZONE_MODE:-?}"
  echo "GPU OPP tables (name, entries): ${opp:-none found}"
  for w in "${WORDS[@]}"; do echo "live_$w before: $(sudo cat "$D/live_$w")"; done
  echo "region_c_changed before: $(sudo cat "$D/region_c_changed") first: $(sudo cat "$D/region_c_first")"; } > "$OUT/system.txt"
cat "$OUT/system.txt"

cols=() names=()
for f in "$HW"/temp*_input "$HW"/power*_input; do
    [ -e "$f" ] || continue
    cols+=("$f"); names+=("$(tr ' ' '_' < "${f%_input}_label")")
done
soc=() tvs1=
for i in "${!names[@]}"; do
    case ${names[$i]} in SoC_*) soc+=("$i") ;; SMC_TVS1) tvs1=$i ;; esac
done
dbg=(); for w in "${WORDS[@]}"; do dbg+=("$D/live_$w"); done; dbg+=("$D/region_c_changed" "$D/region_c_first")
echo "t ${names[*]} cooling ${WORDS[*]/#/live_} region_c_changed region_c_first" > "$OUT/sensors.txt"
sample() {
    local line f c
    line=$(date +%s)
    for f in "${cols[@]}"; do line+=" $(cat "$f" 2>/dev/null || echo NA)"; done
    c=NA; [ -n "$CDEV" ] && c=$(cat "$CDEV/cur_state" 2>/dev/null || echo NA)
    f=$(sudo -n cat "${dbg[@]}" 2>/dev/null | tr '\n' ' ')
    [ "$(wc -w <<< "$f")" = 8 ] || f="NA NA NA NA NA NA NA NA"
    echo "$line $c $f"
}
hottest_soc() {
    local v i x m=0; read -r -a v <<< "$1"
    for i in "${soc[@]}"; do x=${v[$((i + 1))]}; [[ $x =~ ^[0-9]+$ ]] && (( x > m )) && m=$x; done
    echo $m
}
too_hot() {
    local v x; read -r -a v <<< "$1"
    (( $(hottest_soc "$1") >= SOC_STOP )) && { echo "SoC $(hottest_soc "$1")"; return 0; }
    x=${v[$((tvs1 + 1))]}; [[ $x =~ ^[0-9]+$ ]] && (( x >= TVS1_STOP )) && { echo "TVS1 $x"; return 0; }
    return 1
}

gcc -O2 -Wall -o "$BIN" "$HERE/gl-burn.c" -lEGL -lGLESv2 || { echo "STOP: gl-burn did not build"; exit 1; }
"$BIN" 1 > "$OUT/check.txt" 2>&1 || { echo "STOP: gl-burn check failed:"; cat "$OUT/check.txt"; exit 1; }

# The plan: B phases in random order, each between two A phases. A: every word at its start value.
start84=$(sudo cat "$D/live_84")
SEED=$(od -An -N4 -tu4 /dev/urandom | tr -d ' ')
PLAN=()
if [ "$MODE" = dose ]; then
    read -r -a PLAN <<< "$(python3 -I -c '
import random, sys
s84, seed = int(sys.argv[1]), int(sys.argv[2])
b = [f"8c:{v}" for v in range(950, 0, -50)]
b += [f"84:{s84 * p // 100}" for p in (75, 50, 25)]
b += [f"{w}:{v}" for w in ("88", "90", "94", "98") for v in (750, 500, 250)]
random.Random(seed).shuffle(b)
print(" ".join(b))' "$start84" "$SEED")"
fi
echo "$SEED" > "$OUT/seed.txt"
seq_=("A")
for b in "${PLAN[@]}"; do seq_+=("$b" "A"); done
[ "$MODE" = observe ] && seq_=("load")
NPH=${#seq_[@]}
if [ "$MODE" = observe ]; then LOAD=150; else LOAD=$(( PHASE * NPH * 3 )); fi

echo "60 s idle..."
for _ in $(seq 60); do sample >> "$OUT/sensors.txt"; sleep 1; done
if [ "$MODE" = dose ]; then
    echo disabled | sudo -n tee "$ZONE/mode" > /dev/null; echo 0 | sudo -n tee "$CDEV/cur_state" > /dev/null
fi
"$BIN" "$LOAD" > "$OUT/load.txt" 2>&1 &
BURN=$!
START=$(date +%s); echo "$START" > "$OUT/load-start.txt"
finish() { kill -CONT "$BURN" 2>/dev/null; kill "$BURN" 2>/dev/null; give_back; zone_back; }
trap 'finish; echo "stopped by hand" | tee -a "$OUT/load.txt"; exit 130' INT TERM
echo "load (Ctrl+C stops it, gives every word back and switches the thermal zone back on). Output: $OUT"
phase=-1 loaded=0 paused=0
while kill -0 "$BURN" 2>/dev/null; do
    line=$(sample); echo "$line" >> "$OUT/sensors.txt"
    if stop=$(too_hot "$line"); then
        finish; echo "SAFETY STOP after $(( $(date +%s) - START )) s: $stop m°C" | tee -a "$OUT/load.txt"; break
    fi
    hot=$(hottest_soc "$line")
    if [ "$paused" = 0 ] && (( hot >= SOC_PAUSE )); then
        kill -STOP "$BURN"; paused=$(date +%s); echo "[$(date +%T)] paused at SoC $hot m°C"
    elif [ "$paused" != 0 ] && (( hot <= SOC_RESUME )); then
        kill -CONT "$BURN"; echo "$paused $(date +%s)" >> "$OUT/pauses.txt"; paused=0; echo "[$(date +%T)] resumed"
    fi
    if [ "$paused" = 0 ]; then
        if [ "$MODE" = dose ]; then
            p=$(( loaded / PHASE ))
            [ "$p" -ge "$NPH" ] && break
            if [ "$p" != "$phase" ]; then
                phase=$p; sudo -n -v
                if [ "${seq_[$p]}" = A ]; then give_back; label=A
                else IFS=: read -r w v <<< "${seq_[$p]}"; give_back; echo "$v" | sudo -n tee "$D/probe_$w" > /dev/null; label="+0x$w=$v"; fi
                echo "$(date +%s) $label" >> "$OUT/phases.txt"
                echo "[$(date +%T)] phase $((p + 1))/$NPH: $label"
            fi
        fi
        loaded=$((loaded + 1))
    fi
    sleep 1
done
[ "$paused" != 0 ] && echo "$paused $(date +%s)" >> "$OUT/pauses.txt"
finish; wait "$BURN" 2>/dev/null
trap - INT TERM
echo "cool-down..."
for _ in $(seq 60); do sample >> "$OUT/sensors.txt"; sleep 1; done
sudo dmesg | grep -E 'G16: O2' > "$OUT/dmesg-o2.txt"
{ for w in "${WORDS[@]}"; do echo "live_$w after: $(sudo cat "$D/live_$w")"; done
  echo "region_c_changed after: $(sudo cat "$D/region_c_changed") first: $(sudo cat "$D/region_c_first")"
  echo "zone mode after: $(cat "$ZONE/mode" 2>/dev/null)"; } >> "$OUT/system.txt"
python3 -I "$HERE/o-gpu-summary.py" "$OUT"
echo "saved $OUT"
