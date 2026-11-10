#!/bin/bash
# J713 left/right, blind, by ear at the edges of the machine. Each trial is one fresh aplay start that plays two
# bursts of the same pink noise, one on channel 1 (front left) and one on channel 2 (front right), in random order.
# For each burst the listener says at which edge of the machine it is louder; which burst was which channel is only
# shown at the end. Half of the trials bind the speaker card, MCA and amplifiers again first, half reuse them.
#
#   sudo bash /mnt/x63r/j713-diag/o12b/side/lr-blind.sh
#
# What the answers separate:
#   every trial swapped -> channel 1 always reaches the right speaker: a fixed swap
#   every trial normal  -> no swap on this path
#   both kinds          -> the channels land in a different slot from one start to the next
# A trial in which both bursts are called the same side, or "?", is not used. If normal and swapped follow the order
# of the bursts exactly, the answers followed the order (always "first left"), not the speakers: inconclusive.
# Read only for every device except the usual unbind/bind; PipeWire is stopped for the test and started at the end.
set -u
[ "$(id -u)" = 0 ] || { echo "STOP: run with sudo"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/result-lr-blind-$(date +%Y%m%d-%H%M%S)
N=10
P=/sys/module/snd_soc_apple_mca/parameters
MCA_DRV=/sys/bus/platform/drivers/apple-mca
AMP_DRV=/sys/bus/i2c/drivers/tas2764
SPK_DRV=/sys/bus/platform/drivers/j773g-speaker SPK=speaker-audio
DEV=$(basename "$(ls -d /sys/bus/platform/devices/*.i2s 2>/dev/null | head -1)")
AMPS=$(cd "$AMP_DRV" 2>/dev/null && ls -d [0-9]*-00* 2>/dev/null)
USER1000=$(getent passwd 1000 | cut -d: -f1)

card() { awk '/T8132Speaker/ {print $1; exit}' /proc/asound/cards; }
as_user() { runuser -u "$USER1000" -- env XDG_RUNTIME_DIR=/run/user/1000 "$@"; }
pw_stop() { as_user systemctl --user stop pipewire-pulse.socket pipewire.socket wireplumber pipewire-pulse pipewire 2>/dev/null; }
pw_start() { as_user systemctl --user start pipewire.socket pipewire-pulse.socket wireplumber 2>/dev/null; }
rebind() {   # card, MCA and amplifiers bound again (driver defaults); 0 when the speaker card is back
    local a
    echo "$SPK" > "$SPK_DRV/unbind" 2>/dev/null
    echo "$DEV" > "$MCA_DRV/unbind" 2>/dev/null
    for a in $AMPS; do echo "$a" > "$AMP_DRV/unbind" 2>/dev/null; done
    sleep 0.5
    for a in $AMPS; do echo "$a" > "$AMP_DRV/bind" 2>>"$OUT/bind-errors.txt"; done
    echo "$DEV" > "$MCA_DRV/bind" 2>>"$OUT/bind-errors.txt" || return 1
    echo "$SPK" > "$SPK_DRV/bind" 2>>"$OUT/bind-errors.txt"
    for _ in $(seq 20); do [ -n "$(card)" ] && return 0; sleep 0.5; done
    return 1
}
ask() {   # ask <prompt>: l, r or ?
    local a
    while :; do
        read -r -p "$1 [l/r/?] " a < /dev/tty
        case "$a" in l|L) echo l; return ;; r|R) echo r; return ;; '?') echo '?'; return ;; esac
    done
}

[ -n "$DEV" ] && [ -n "$AMPS" ] && [ -e "$SPK_DRV/$SPK" ] || { echo "STOP: the speaker devices are not bound"; exit 1; }
[ -n "$(card)" ] || { echo "STOP: no T8132Speaker card"; exit 1; }
mkdir -p "$OUT"
trap pw_start EXIT
# On the O12b kernel: back to the driver's own stride and unit count.
[ -w "$P/t8132_unit_stride" ] && { echo 0 > "$P/t8132_unit_stride"; echo 0 > "$P/t8132_max_units"; }
pw_stop; sleep 1

SEED=$(od -An -N4 -tu4 /dev/urandom | tr -d ' ')
echo "$SEED" > "$OUT/seed.txt"
python3 -I - "$OUT" "$SEED" "$N" <<'PY'
import math, random, struct, sys
out, seed, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
RATE = 48000
rnd = random.Random(seed)
# Pink noise (Paul Kellet's filter), the same 4 s for every burst, 50 ms fades, RMS 0.1, peaks clipped at 0.4.
b = [0.0] * 7
noise = []
for _ in range(4 * RATE):
    w = rnd.uniform(-1, 1)
    b[0] = 0.99886 * b[0] + w * 0.0555179; b[1] = 0.99332 * b[1] + w * 0.0750759
    b[2] = 0.96900 * b[2] + w * 0.1538520; b[3] = 0.86650 * b[3] + w * 0.3104856
    b[4] = 0.55000 * b[4] + w * 0.5329522; b[5] = -0.7616 * b[5] - w * 0.0168980
    noise.append(sum(b[:6]) + b[6] + w * 0.5362); b[6] = w * 0.115926
rms = math.sqrt(sum(x * x for x in noise) / len(noise))
fade = RATE // 20
noise = [max(-0.4, min(0.4, x * 0.1 / rms)) * min(1, i / fade, (len(noise) - 1 - i) / fade) for i, x in enumerate(noise)]
sil = lambda s: [0.0] * int(s * RATE)
for order in ('12', '21'):
    with open(f'{out}/sound-{order}.raw', 'wb') as f:
        def burst(ch):
            for x in noise:
                s = int(x * 8388607)
                f.write(struct.pack('<ii', s if ch == 1 else 0, s if ch == 2 else 0))
        def gap(s):
            f.write(b'\0' * 8 * int(s * RATE))
        gap(0.7); burst(int(order[0])); gap(2.0); burst(int(order[1])); gap(0.5)
# The plan: half of each order, half with a fresh bind, in random order.
plan = [(o, r) for o in ('12', '21') for r in (1, 0)] * (n // 4) + [('12', 1), ('21', 0)] * ((n % 4) // 2)
rnd.shuffle(plan)
with open(f'{out}/plan.txt', 'w') as f:
    for o, r in plan:
        f.write(f'{o} {r}\n')
PY
[ -s "$OUT/sound-12.raw" ] && [ -s "$OUT/plan.txt" ] || { echo "STOP: the sounds could not be made"; exit 1; }
{ uname -r; grep -o 'x6e3\.v=[^ ]*\|ceiling_dvc=[0-9]*' /proc/cmdline; cat "$P/t8132_unit_stride" "$P/t8132_max_units" 2>/dev/null
  for a in $AMPS; do echo "$a: $(grep -E '^0*(0a|0c):' /sys/kernel/debug/regmap/$a/registers 2>/dev/null | tr '\n' ' ')"; done; } > "$OUT/system.txt"

echo "trial rebind order first second faults" > "$OUT/trials.txt"
echo
echo "$N trials. Each plays two 4-second bursts of the same noise with 2 s between them."
echo "The speakers sit at the two ends of the hinge. During each burst move your ear from the Esc corner"
echo "to the Touch ID corner and back, then say for each burst where it was louder: l (Esc), r (Touch ID),"
echo "or ? if you could not tell."
t=0
while read -r order rb; do
    t=$((t + 1))
    if [ "$rb" = 1 ]; then rebind || { echo "$t $rb $order nocard - -" >> "$OUT/trials.txt"; echo "trial $t: no speaker card"; continue; }; fi
    c=$(card)
    echo
    read -r -p "Trial $t/$N: press Enter, then listen. " _ < /dev/tty
    before=$(dmesg | wc -l)
    aplay -D "hw:$c,0" -t raw -f S24_LE -c 2 -r 48000 "$OUT/sound-$order.raw" > "$OUT/play-$t.txt" 2>&1
    dmesg | tail -n +$((before + 1)) > "$OUT/dmesg-$t.txt"
    faults=$(grep -ciE 'fault|protect|error|bad tdm|clock' "$OUT/dmesg-$t.txt")
    if grep -qiE 'error|failed|unable|not available' "$OUT/play-$t.txt"; then
        echo "$t $rb $order play-error - $faults" >> "$OUT/trials.txt"; echo "trial $t: aplay failed, see play-$t.txt"; continue
    fi
    a1=$(ask "  first burst louder at")
    a2=$(ask "  second burst louder at")
    echo "$t $rb $order $a1 $a2 $faults" >> "$OUT/trials.txt"; sync
done < "$OUT/plan.txt"

python3 -I - "$OUT/trials.txt" <<'PY' | tee "$OUT/verdict.txt"
import sys
rows = [l.split() for l in open(sys.argv[1]).read().splitlines()[1:]]
print('trial rebind  order  first second  channel 1  channel 2  mapping')
kinds = []
for t, rb, order, a1, a2, faults in rows:
    if a1 not in 'lr' or a2 not in 'lr' or len(a1) != 1:
        print(f'{t:>5} {rb:>6}  {order:>5}  {a1:>5} {a2:>6}  {"":9}  {"":9}  not used ({a1})'); continue
    side = {order[0]: a1, order[1]: a2}          # channel -> heard side
    m = 'normal' if (side['1'], side['2']) == ('l', 'r') else 'swapped' if (side['1'], side['2']) == ('r', 'l') else 'same side'
    print(f'{t:>5} {rb:>6}  {order:>5}  {a1:>5} {a2:>6}  {side["1"]:>9}  {side["2"]:>9}  {m}')
    if m != 'same side':
        kinds.append((m, order, rb))
use = len(kinds)
nm = sum(k == 'normal' for k, _, _ in kinds); sw = use - nm
print(f'\nusable trials: {use} of {len(rows)}; normal {nm}, swapped {sw}')
for name, idx in (('order', 1), ('rebind', 2)):
    for v in sorted({k[idx] for k in kinds}):
        sub = [k[0] for k in kinds if k[idx] == v]
        print(f'  {name} {v}: normal {sub.count("normal")}, swapped {sub.count("swapped")}')
if use < 6:
    print('INCONCLUSIVE: fewer than 6 usable trials')
elif sw == use:
    print('FIXED SWAP: channel 1 reached the right speaker and channel 2 the left one in every trial')
elif nm == use:
    print('NO SWAP: channel 1 reached the left speaker and channel 2 the right one in every trial')
elif all((k == 'normal') == (o == '12') for k, o, _ in kinds) or all((k == 'normal') == (o == '21') for k, o, _ in kinds):
    print('INCONCLUSIVE: the answers follow the order of the bursts, not the channels')
else:
    print('START-DEPENDENT: the same channel reached different speakers on different starts')
PY
echo "saved $OUT"
