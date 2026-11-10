#!/bin/bash
# Read only: which TDM slot and which ASI1 source each speaker amplifier uses. Nothing is written to any device.
# Saves everything to side/regs-<time>.txt next to this script and prints the same.
#
#   sudo bash /mnt/x63r/j713-diag/o12b/side/regs.sh
#
# TAS2764 TDM_CFG2 (0x0a): bits 5:4 ASI1 source (0 I2C-offset, 1 Left, 2 Right, 3 (L+R)/2), 3:2 RX word, 1:0 RX slot len.
# TAS2764 TDM_CFG3 (0x0c): bits 7:4 right slot, 3:0 left slot.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/regs-$(date +%Y%m%d-%H%M%S).txt
SRC=("I2C-offset" "Left" "Right" "(L+R)/2")

{
date; uname -r; grep -o 'x6e3\.v=[^ ]*' /proc/cmdline
echo; echo "== sound cards"; cat /proc/asound/cards
for c in $(sed -n 's/^ *\([0-9]\+\) \[.*/\1/p' /proc/asound/cards); do
    echo; echo "== card $c: ASI1 controls"
    amixer -c "$c" contents 2>&1 | grep -i -A8 'ASI1' || echo "(no ASI1 control)"
done

for R in /sys/kernel/debug/regmap/*-00[3][89abc]/registers; do
    [ -r "$R" ] || continue
    a=$(basename "$(dirname "$R")")
    get() { sed -n "s/^0*$1: \([0-9a-f]\+\)$/\1/p" "$R" | head -1; }
    c2=$(get 0a) c3=$(get 0c) c0=$(get 08) c1=$(get 09)
    echo; echo "== $a  (CFG0 08=${c0:-?} CFG1 09=${c1:-?} CFG2 0a=${c2:-?} CFG3 0c=${c3:-?})"
    if [ -n "$c2" ] && [ -n "$c3" ]; then
        v2=$((16#$c2)) v3=$((16#$c3))
        echo "   ASI1 source : ${SRC[$(( (v2 >> 4) & 3 ))]}"
        echo "   left slot   : $(( v3 & 15 ))"
        echo "   right slot  : $(( (v3 >> 4) & 15 ))"
        echo "   I2C offset  : $(( 16#${a#*-} - 0x38 ))"
    fi
done

echo; echo "== device tree: speaker amplifiers"
for n in $(grep -l . /proc/device-tree/soc*/i2c*/*@3[89abc]/sound-name-prefix /proc/device-tree/*/i2c*/*@3[89abc]/sound-name-prefix 2>/dev/null); do
    d=$(dirname "$n")
    echo "$(basename "$d"): prefix '$(tr -d '\0' < "$n")'"
    for p in "$d"/*slot* "$d"/*tdm* "$d"/*channel*; do
        [ -e "$p" ] && echo "   $(basename "$p") = $(od -An -tx1 "$p" | tr -s ' ')"
    done
done

echo; echo "== full register dumps"
for R in /sys/kernel/debug/regmap/*-00[3][89abc]/registers; do
    [ -r "$R" ] && { echo "-- $R"; head -40 "$R"; }
done
} 2>&1 | tee "$OUT"
echo; echo "saved $OUT"
