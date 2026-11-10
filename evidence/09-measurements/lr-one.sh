#!/bin/bash
# J713 left/right, blind, by ear at the two ends of the hinge. Each trial is one fresh aplay start that plays ONE
# 6-second burst of pink noise, on channel 1 (front left) or channel 2 (front right), in random order. There is no
# second burst, so no order to answer by (lr-blind.sh had one, and its answers followed it). The listener says at
# which end it is louder; the channel is only shown at the end. Half of the trials bind the speaker card, MCA and
# amplifiers again first, half reuse them.
#
#   sudo bash /mnt/x63r/j713-diag/o12b/side/lr-one.sh
#
# What the answers separate (U = usable trials, "?" is not used):
#   every answer on one side      -> the answers do not depend on the channel: inconclusive
#   swap-consistent in >= U-1     -> FIXED SWAP: channel 1 reaches the Touch ID end, channel 2 the Esc end
#   normal-consistent in >= U-1   -> NO SWAP
#   anything else                 -> MIXED: per channel and per rebind counts show whether it follows the start
# Read only for every device except the usual unbind/bind; PipeWire is stopped for the test and started at the end.
set -u
[ "$(id -u)" = 0 ] || { echo "STOP: run with sudo"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/result-lr-one-$(date +%Y%m%d-%H%M%S)
N=12
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
# Pink noise (Paul Kellet's filter), the same 6 s for every burst, 50 ms fades, RMS 0.1, peaks clipped at 0.4.
b = [0.0] * 7
noise = []
for _ in range(6 * RATE):
    w = rnd.uniform(-1, 1)
    b[0] = 0.99886 * b[0] + w * 0.0555179; b[1] = 0.99332 * b[1] + w * 0.0750759
    b[2] = 0.96900 * b[2] + w * 0.1538520; b[3] = 0.86650 * b[3] + w * 0.3104856
    b[4] = 0.55000 * b[4] + w * 0.5329522; b[5] = -0.7616 * b[5] - w * 0.0168980
    noise.append(sum(b[:6]) + b[6] + w * 0.5362); b[6] = w * 0.115926
rms = math.sqrt(sum(x * x for x in noise) / len(noise))
fade = RATE // 20
noise = [max(-0.4, min(0.4, x * 0.1 / rms)) * min(1, i / fade, (len(noise) - 1 - i) / fade) for i, x in enumerate(noise)]
sil = lambda s: [0.0] * int(s * RATE)
for ch in (1, 2):
    with open(f'{out}/sound-{ch}.raw', 'wb') as f:
        f.write(b'\0' * 8 * int(0.7 * RATE))
        for x in noise:
            s = int(x * 8388607)
            f.write(struct.pack('<ii', s if ch == 1 else 0, s if ch == 2 else 0))
        f.write(b'\0' * 8 * int(0.5 * RATE))
# The plan: half on each channel, half of each with a fresh bind, in random order.
plan = [(str(c), r) for c in (1, 2) for r in (1, 0)] * (n // 4) + [('1', 1), ('2', 0)] * ((n % 4) // 2)
rnd.shuffle(plan)
with open(f'{out}/plan.txt', 'w') as f:
    for o, r in plan:
        f.write(f'{o} {r}\n')
PY
[ -s "$OUT/sound-1.raw" ] && [ -s "$OUT/plan.txt" ] || { echo "STOP: the sounds could not be made"; exit 1; }
{ uname -r; grep -o 'x6e3\.v=[^ ]*\|ceiling_dvc=[0-9]*' /proc/cmdline; cat "$P/t8132_unit_stride" "$P/t8132_max_units" 2>/dev/null
  for a in $AMPS; do echo "$a: $(grep -E '^0*(0a|0c):' /sys/kernel/debug/regmap/$a/registers 2>/dev/null | tr '\n' ' ')"; done; } > "$OUT/system.txt"

echo "trial rebind channel answer faults" > "$OUT/trials.txt"
echo
echo "$N trials. Each plays ONE 6-second burst of noise."
echo "The speakers sit at the two ends of the hinge. During the burst move your ear from the Esc corner"
echo "to the Touch ID corner and back, then say where it was louder: l (Esc), r (Touch ID), or ? if unsure."
t=0
while read -r ch rb; do
    t=$((t + 1))
    if [ "$rb" = 1 ]; then rebind || { echo "$t $rb $ch nocard -" >> "$OUT/trials.txt"; echo "trial $t: no speaker card"; continue; }; fi
    c=$(card)
    echo
    read -r -p "Trial $t/$N: press Enter, then listen. " _ < /dev/tty
    before=$(dmesg | wc -l)
    aplay -D "hw:$c,0" -t raw -f S24_LE -c 2 -r 48000 "$OUT/sound-$ch.raw" > "$OUT/play-$t.txt" 2>&1
    dmesg | tail -n +$((before + 1)) > "$OUT/dmesg-$t.txt"
    faults=$(grep -ciE 'fault|protect|error|bad tdm|clock' "$OUT/dmesg-$t.txt")
    if grep -qiE 'error|failed|unable|not available' "$OUT/play-$t.txt"; then
        echo "$t $rb $ch play-error $faults" >> "$OUT/trials.txt"; echo "trial $t: aplay failed, see play-$t.txt"; continue
    fi
    a=$(ask "  louder at")
    echo "$t $rb $ch $a $faults" >> "$OUT/trials.txt"; sync
done < "$OUT/plan.txt"

python3 -I - "$OUT/trials.txt" <<'PY' | tee "$OUT/verdict.txt"
import sys
rows = [l.split() for l in open(sys.argv[1]).read().splitlines()[1:]]
print('trial rebind channel answer  mapping')
use = []
for t, rb, ch, a, faults in rows:
    if a not in ('l', 'r'):
        print(f'{t:>5} {rb:>6} {ch:>7} {a:>6}  not used'); continue
    m = 'normal' if (ch, a) in (('1', 'l'), ('2', 'r')) else 'swapped'
    print(f'{t:>5} {rb:>6} {ch:>7} {a:>6}  {m}')
    use.append((ch, rb, a, m))
U = len(use); S = sum(m == 'swapped' for *_, m in use); N = U - S
print(f'\nusable trials: {U} of {len(rows)}; normal {N}, swapped {S}')
for ch in ('1', '2'):
    sub = [a for c, _, a, _ in use if c == ch]
    print(f'  channel {ch}: Esc (l) {sub.count("l")}, Touch ID (r) {sub.count("r")}')
for rb in ('0', '1'):
    sub = [m for _, r, _, m in use if r == rb]
    print(f'  rebind {rb}: normal {sub.count("normal")}, swapped {sub.count("swapped")}')
if U < 8:
    print('INCONCLUSIVE: fewer than 8 usable trials')
elif len({a for _, _, a, _ in use}) == 1:
    print('INCONCLUSIVE: every answer was the same side, whatever the channel')
elif S >= U - 1:
    print(f'FIXED SWAP: channel 1 at the Touch ID end and channel 2 at the Esc end in {S} of {U} trials')
elif N >= U - 1:
    print(f'NO SWAP: channel 1 at the Esc end and channel 2 at the Touch ID end in {N} of {U} trials')
else:
    print('MIXED: no fixed mapping; see the channel and rebind counts')
PY
echo "saved $OUT"
