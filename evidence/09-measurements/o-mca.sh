#!/bin/bash
# J713 O1 test on Linux (O12b image only): the T8132 MCA unit layout, from the register window and the speakers.
#
#   sudo bash o-mca.sh map     read the MCA register window while silence plays (no sound), in 0x400 chunks
#                              from the driver's own register groups outward, then find the repeat period of
#                              each 4 KiB page with o1-period.py. Resumable: a chunk that hung the machine marks
#                              the end of the readable window in that direction on the next run.
#   sudo bash o-mca.sh rwmap   only if map finds no period: per word, which bits can be written (all ones, then
#                              zeros, then the old value back), from the driver's own groups to the end of the
#                              window. Asks first.
#   sudo bash o-mca.sh ab      A/B/A with the speakers. A = the period of the page holding the driver's groups;
#                              B = the other periods map found, half and twice A, the 0x4000 cluster stride of
#                              the other Apple MCA variants and the 0xc000 this driver assumed before; C = A with
#                              one unit (negative control). The B and C trials come in random order, each between
#                              two A trials. Each trial plays the "Front Left" voice on channel 1 and the "Front
#                              Right" voice on channel 2 (pink noise if the voice files are missing), one after the
#                              other in random order; you answer only whether you heard it. Channel 1 reaches only the left
#                              amplifiers' TDM slot and channel 2 only the right ones', so a silent channel 2 means
#                              the right amplifiers are not running. Before the first trial a voice says "Front
#                              Left" and "Front Right" (not blind) to check which side is which. Resumable: run it
#                              again after a hang and it carries on in the same order; a trial that hung is recorded.
#
# Safety: the speaker driver's -30 dB ceiling and the amplifiers' protection stay on; tweeters stay off. Before each
# trial both amplifiers are bound again, which clears a protection shutdown from the trial before. A trial whose
# amplifier faults gets no further tones. PipeWire is stopped for the test and started again at the end.
set -u
MODE=${1:-}
case "$MODE" in map|rwmap|ab) ;; *) echo "usage: sudo bash o-mca.sh map|rwmap|ab"; exit 2 ;; esac
[ "$(id -u)" = 0 ] || { echo "STOP: run with sudo"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
MAP=$HERE/map
P=/sys/module/snd_soc_apple_mca/parameters
DBG=/sys/kernel/debug/apple_mca_o1
MCA_DRV=/sys/bus/platform/drivers/apple-mca
AMP_DRV=/sys/bus/i2c/drivers/tas2764
SPK_DRV=/sys/bus/platform/drivers/j773g-speaker SPK=speaker-audio
CHUNK=0x400

grep -q 'x6e3\.v=6boot-o12b' /proc/cmdline || { echo "STOP: not the O12b image"; exit 1; }
[ -w "$P/t8132_unit_stride" ] && [ -w "$P/t8132_max_units" ] || { echo "STOP: O1 parameters missing. Is this the O12b kernel?"; exit 1; }
[ -e "$DBG/window" ] || { echo "STOP: $DBG missing"; exit 1; }
DEV=$(basename "$(ls -d /sys/bus/platform/devices/*.i2s 2>/dev/null | head -1)")
[ -n "$DEV" ] || { echo "STOP: no MCA device"; exit 1; }
AMPS=$(cd "$AMP_DRV" 2>/dev/null && ls -d [0-9]*-00* 2>/dev/null)
[ -n "$AMPS" ] || { echo "STOP: no amplifiers bound to $AMP_DRV"; exit 1; }
[ -e "$SPK_DRV/$SPK" ] || { echo "STOP: $SPK is not bound to $SPK_DRV"; exit 1; }
SIZE=$(python3 -I -c 'import sys; print(int.from_bytes(open(sys.argv[1], "rb").read()[-8:], "big"))' \
    "/sys/bus/platform/devices/$DEV/of_node/reg")
DEFAULT_START=$(awk '{print $1}' "$DBG/range")
USER1000=$(getent passwd 1000 | cut -d: -f1)
mkdir -p "$MAP"

as_user() { runuser -u "$USER1000" -- env XDG_RUNTIME_DIR=/run/user/1000 "$@"; }
pw_stop() { as_user systemctl --user stop pipewire-pulse.socket pipewire.socket wireplumber pipewire-pulse pipewire 2>/dev/null; }
pw_start() { as_user systemctl --user start pipewire.socket pipewire-pulse.socket wireplumber 2>/dev/null; }
card() { awk '/T8132Speaker/ {print $1; exit}' /proc/asound/cards; }
hex() { printf '%#06x' "$1"; }
LOUD=$(cat /sys/module/printk/parameters/ignore_loglevel)
restore() {
    [ -n "${AP:-}" ] && kill "$AP" 2>/dev/null
    echo 0 > "$P/o1_allow_writes" 2>/dev/null
    echo "$LOUD" > /sys/module/printk/parameters/ignore_loglevel
    pw_start
}
trap restore EXIT

bind_all() {   # bind_all <stride> <units>: card, MCA and amplifiers bound again; 0 when the speaker card is back
    # The speaker driver latches a fault until its device is bound again, the amplifiers theirs until they are.
    local a
    echo "$SPK" > "$SPK_DRV/unbind" 2>/dev/null
    echo "$DEV" > "$MCA_DRV/unbind" 2>/dev/null
    for a in $AMPS; do echo "$a" > "$AMP_DRV/unbind" 2>/dev/null; done
    sleep 0.5
    for a in $AMPS; do echo "$a" > "$AMP_DRV/bind" 2>>"$OUT/bind-errors.txt"; done
    echo "$1" > "$P/t8132_unit_stride"; echo "$2" > "$P/t8132_max_units"
    echo "$DEV" > "$MCA_DRV/bind" 2>>"$OUT/bind-errors.txt" || return 1
    echo "$SPK" > "$SPK_DRV/bind" 2>>"$OUT/bind-errors.txt"
    for _ in $(seq 20); do [ -n "$(card)" ] && return 0; sleep 0.5; done
    return 1
}
silence() {   # silence on|off: a stream of zeros keeps the MCA clocks and power domains up
    if [ "$1" = on ]; then
        local c; c=$(card); [ -n "$c" ] || return 1
        aplay -q -D "hw:$c,0" -t raw -f S24_LE -c 2 -r 48000 /dev/zero 2>>"$OUT/aplay-errors.txt" &
        AP=$!; sleep 1; kill -0 "$AP" 2>/dev/null
    else
        kill "$AP" 2>/dev/null; wait "$AP" 2>/dev/null; AP=
    fi
}
chunks_from() {   # chunk starts from <first> to the end of the window, nearest to the driver's groups first
    python3 -I -c '
import sys
start, size, step, first = (int(a, 0) for a in sys.argv[1:])
c = [x for x in range(first, size, step)]
print(" ".join(hex(x) for x in sorted(c, key=lambda x: (abs(x - start), x))))' "$DEFAULT_START" "$SIZE" "$CHUNK" "$1"
}
scan() {   # scan <state file> <kind>: kind map reads the window twice, kind rw probes it
    local state=$1 kind=$2 c n b s=$((DEFAULT_START))
    for c in $(chunks_from "$3"); do
        c=$(hex "$c")
        grep -qx "ok $c\|bad $c" "$state" 2>/dev/null && continue
        if grep -qx "start $c" "$state" 2>/dev/null; then
            echo "bad $c" >> "$state"; sync
            echo "chunk $c stopped the machine last time: the readable window ends there on that side"; continue
        fi
        for b in $(awk '$1 == "bad" {print $2}' "$state" 2>/dev/null); do   # beyond a chunk that hung: skip
            if (( b > s && c > b )) || (( b < s && c < b )); then continue 2; fi
        done
        silence on || { echo "STOP: silence did not start"; return 1; }
        echo "start $c" >> "$state"; sync
        if [ "$kind" = map ]; then
            echo "$c $CHUNK" > "$DBG/range"
            cat "$DBG/window" > "$MAP/chunk-$c-a.txt" 2>&1; sleep 0.2
            cat "$DBG/window" > "$MAP/chunk-$c-b.txt" 2>&1
            n=$(grep -c ': ' "$MAP/chunk-$c-b.txt")
        else
            echo "$c $CHUNK" > "$DBG/rwprobe" && cat "$DBG/rwprobe" > "$MAP/rw-$c.txt"
            n=$(grep -c ': ' "$MAP/rw-$c.txt" 2>/dev/null)
        fi
        echo "ok $c" >> "$state"; sync
        echo "chunk $c: $n lines"
        silence off
    done
}

OUT=$HERE/result-o-mca-$MODE-$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"
{ uname -a; cat /proc/cmdline; echo "MCA $DEV, window $(hex "$SIZE"), driver groups start at $DEFAULT_START"
  echo "amplifiers: $AMPS"; cat /proc/asound/cards; } > "$OUT/system.txt"
n0=$(dmesg | wc -l)
pw_stop

if [ "$MODE" = map ]; then
    bind_all 0 0 || { echo "STOP: no speaker card"; exit 1; }
    echo "reading the window $(hex 0)-$(hex $((SIZE - 1))) while silence plays"
    scan "$MAP/state.txt" map 0
    dmesg | tail -n +$((n0 + 1)) > "$OUT/dmesg.txt"
    python3 -I "$HERE/o1-period.py" --start "$DEFAULT_START" "$MAP" | tee "$OUT/period.txt"
    echo "saved $MAP and $OUT"; exit 0
fi

if [ "$MODE" = rwmap ]; then
    echo "rwmap writes all ones and zeros into every word from $DEFAULT_START to the end of the window and puts"
    echo "the old value back. The registers below $DEFAULT_START are left out. Run it only if map found no period."
    read -r -p "Type yes to go on: " a < /dev/tty; [ "$a" = yes ] || exit 1
    bind_all 0 0 || { echo "STOP: no speaker card"; exit 1; }
    echo 1 > "$P/o1_allow_writes"
    scan "$MAP/rwstate.txt" rw "$DEFAULT_START"
    echo 0 > "$P/o1_allow_writes"
    dmesg | tail -n +$((n0 + 1)) > "$OUT/dmesg.txt"
    python3 -I "$HERE/o1-period.py" --start "$DEFAULT_START" --rw "$MAP" | tee "$OUT/period.txt"
    echo "saved $MAP and $OUT"; exit 0
fi

# ab
AB_STATE=$MAP/ab-state.txt AB_TRIALS=$MAP/ab-trials.txt
read -r A B_EXTRA <<< "$(python3 -I -c '
import json, sys
r = json.load(open(sys.argv[1]))
print(hex(r["period"]) if r.get("period") else "", ",".join(hex(p) for p in r.get("others", [])))' \
    "$MAP/o1-period.json" 2>/dev/null)"
[ -n "$A" ] || { echo "STOP: no period in $MAP/o1-period.json; run map first"; exit 1; }
if [ -s "$AB_STATE" ]; then
    SEED=$(awk '$1 == "seed" {print $2; exit}' "$AB_STATE"); echo "carrying on with the earlier trial order"
else
    SEED=$(od -An -N4 -tu4 /dev/urandom | tr -d ' ')
    echo "seed $SEED" > "$AB_STATE"
    echo "trial kind stride units card tone1 heard1 tone2 heard2 faults" > "$AB_TRIALS"; sync
fi
# The end of the readable window: the first chunk above the driver's groups whose read hung the machine.
READABLE=$(python3 -I -c '
import sys
s = int(sys.argv[1], 0)
try:
    bad = [int(l.split()[1], 16) for l in open(sys.argv[2]) if l.startswith("bad ")]
except OSError:
    bad = []
above = sorted(b for b in bad if b > s)
print(above[0] if above else "")' "$DEFAULT_START" "$MAP/state.txt")
read -r -a TRIALS <<< "$(python3 -I -c '
import random, sys
a, size, seed = int(sys.argv[1], 0), int(sys.argv[2], 0), int(sys.argv[3])
extra = [int(x, 0) for x in sys.argv[4].split(",") if x]
readable = int(sys.argv[5]) if sys.argv[5] else size
TX = 0x6000   # the TX serializer group, the highest of the driver T8132 groups
b, skipped = [], []
for s in extra + [a // 2, a * 2, 0x4000, 0xc000]:
    if s < 0x20 or s % 0x20 or s > size or s == a or f"B:{s:#x}:0" in b or s in skipped:
        continue
    if 2 * s <= size and TX + s >= readable:   # unit 1 would sit where reads hang the machine
        skipped.append(s)
        continue
    b.append(f"B:{s:#x}:0")
for s in skipped:
    print(f"left out: stride {s:#x}, its unit 1 serializer at {TX + s:#x} is past the readable end {readable:#x}",
          file=sys.stderr)
x = b + [f"C:{a:#x}:1"]
random.Random(seed).shuffle(x)
seq = [f"A:{a:#x}:0"]
for t in x:
    seq += [t, f"A:{a:#x}:0"]
print(" ".join(seq))' "$A" "$SIZE" "$SEED" "$B_EXTRA" "$READABLE" 2> "$OUT/left-out.txt")"
cat "$OUT/left-out.txt"
for x in "${TRIALS[@]}"; do [[ $x =~ ^[ABC]:0x[0-9a-f]+:[01]$ ]] || { echo "STOP: bad trial entry '$x'"; exit 1; }; done
echo "N" > /sys/module/printk/parameters/ignore_loglevel   # kernel messages would show the stride on the console
where=(none left right both)
ask_side() {
    local a=""; while [[ ! $a =~ ^[0-3]$ ]]; do read -r -p "$1 Where did you hear it? 1=left 2=right 3=both 0=none: " a < /dev/tty; done
    echo "${where[$a]}"
}
ask_heard() {
    local a=""; while [[ ! $a =~ ^[01]$ ]]; do read -r -p "$1 Did you hear it? 1=yes 0=no: " a < /dev/tty; done
    [ "$a" = 1 ] && echo heard || echo silent
}
# The sounds are made here in the hardware's own format (S24_LE in 32 bits, 48 kHz, two channels), one file per
# channel with the other channel silent, and played with aplay like the silence of map. speaker-test could not
# play the 16-bit voice files on this card, not even through plughw.
make_sound() {   # make_sound <channel> <wav> <out>
    python3 -I - "$@" <<'PY'
import random, struct, sys, wave
ch, src, out = int(sys.argv[1]), sys.argv[2], sys.argv[3]
RATE = 48000
try:
    w = wave.open(src)
    width, chans, rate = w.getsampwidth(), w.getnchannels(), w.getframerate()
    raw = w.readframes(w.getnframes())
    if width == 2:
        vals, scale = struct.unpack(f'<{len(raw) // 2}h', raw), 32768.0
    elif width == 1:
        vals, scale = [b - 128 for b in raw], 128.0
    else:
        raise ValueError(f'{width}-byte samples')
    mono = [sum(vals[i:i + chans]) / chans / scale for i in range(0, len(vals), chans)]
    if rate != RATE:
        mono = [mono[min(int(i * rate / RATE), len(mono) - 1)] for i in range(int(len(mono) * RATE / rate))]
    print(f'sound {ch}: {src}, {len(mono) / RATE:.2f} s')
except (OSError, ValueError, wave.Error) as e:
    rnd = random.Random(ch)
    mono = [rnd.uniform(-0.5, 0.5) for _ in range(RATE * 2)]
    print(f'sound {ch}: no voice from {src} ({e}); two seconds of noise instead')
pad = [0.0] * (RATE // 4)
with open(out, 'wb') as f:
    for x in pad + mono + pad:
        s = int(max(-1.0, min(1.0, x)) * 8388607)
        f.write(struct.pack('<ii', s if ch == 1 else 0, s if ch == 2 else 0))
PY
}
make_sound 1 /usr/share/sounds/alsa/Front_Left.wav "$OUT/sound-1.raw" >> "$OUT/system.txt" 2>&1
make_sound 2 /usr/share/sounds/alsa/Front_Right.wav "$OUT/sound-2.raw" >> "$OUT/system.txt" 2>&1
[ -s "$OUT/sound-1.raw" ] && [ -s "$OUT/sound-2.raw" ] || { echo "STOP: the sounds could not be made"; exit 1; }
play() {   # play <channel> <log>: 0 if aplay played the whole sound
    aplay -D "hw:$c,0" -t raw -f S24_LE -c 2 -r 48000 "$OUT/sound-$1.raw" > "$2" 2>&1 \
        && ! grep -qiE 'error|failed|unable|not available' "$2"
}
if ! grep -q '^calibration ' "$AB_STATE"; then
    bind_all 0 0 || { echo "STOP: no speaker card"; exit 1; }
    c=$(card)
    echo "Side check, not blind: put your ear close to one edge of the machine, then the other."
    echo "Channel 1: a voice says \"Front Left\"."
    play 1 "$OUT/calibration-1.txt" || { echo "STOP: the sound did not play; see $OUT/calibration-1.txt"; exit 1; }
    fl=$(ask_side "The voice saying \"Front Left\".")
    echo "Channel 2: a voice says \"Front Right\"."
    play 2 "$OUT/calibration-2.txt" || { echo "STOP: the sound did not play; see $OUT/calibration-2.txt"; exit 1; }
    fr=$(ask_side "The voice saying \"Front Right\".")
    echo "calibration $fl $fr" >> "$AB_STATE"; sync
fi
echo "${#TRIALS[@]} trials, two sounds each (the voices). Answer only whether you heard it."
for i in "${!TRIALS[@]}"; do
    IFS=: read -r kind stride units <<< "${TRIALS[$i]}"
    t=$((i + 1))
    grep -qx "done $t" "$AB_STATE" && continue
    if grep -qx "start $t" "$AB_STATE"; then
        echo "$t $kind $stride $units froze - - - - -" >> "$AB_TRIALS"; echo "done $t" >> "$AB_STATE"; sync
        echo "trial $t stopped the machine last time; recorded"; continue
    fi
    echo; echo "== trial $t/${#TRIALS[@]}"
    echo "start $t" >> "$AB_STATE"; sync
    m0=$(dmesg | wc -l)
    echo "O1 trial $t" > /dev/kmsg
    if ! bind_all "$stride" "$units"; then
        echo "$t $kind $stride $units none - - - - -" >> "$AB_TRIALS"; echo "done $t" >> "$AB_STATE"; sync
        echo "(no speaker card this time)"
        dmesg | tail -n +$((m0 + 1)) > "$OUT/dmesg-trial-$t.txt"; continue
    fi
    c=$(card)
    order=$(python3 -I -c 'import random, sys; print(*random.Random(sys.argv[1]).sample([1, 2], 2))' "$SEED-$t")
    res=() n=0
    for ch in $order; do
        n=$((n + 1))
        if dmesg | tail -n +$((m0 + 1)) | grep -qiE 'fault|protection'; then res+=("$ch" skipped); continue; fi
        echo "Sound $n..."
        if play "$ch" "$OUT/play-$t-$ch.txt"; then
            res+=("$ch" "$(ask_heard "Sound $n of trial $t.")")
        else
            res+=("$ch" play-error); echo "(the sound did not play; recorded, not asked)"
        fi
    done
    faults=$(dmesg | tail -n +$((m0 + 1)) | grep -ciE 'fault|protection')
    dmesg | tail -n +$((m0 + 1)) > "$OUT/dmesg-trial-$t.txt"
    echo "$t $kind $stride $units $c ${res[*]} $faults" >> "$AB_TRIALS"; echo "done $t" >> "$AB_STATE"; sync
done
echo; echo "== back to the default"
bind_all 0 0 && echo "default bound again" || echo "WARNING: the speaker card did not come back; a reboot restores it"
dmesg | tail -n +$((n0 + 1)) > "$OUT/dmesg.txt"
cp "$AB_STATE" "$AB_TRIALS" "$OUT/"
python3 -I - "$AB_TRIALS" "$AB_STATE" <<'EOF' | tee "$OUT/verdict.txt"
import sys
rows = [l.split() for l in open(sys.argv[1]).read().splitlines()[1:]]
cal = next((l.split()[1:] for l in open(sys.argv[2]) if l.startswith('calibration ')), ['-', '-'])
print(f'side check: "Front Left" heard {cal[0]}, "Front Right" heard {cal[1]}')
played = lambda r: r[4] not in ('none', 'froze')
heard = lambda r: dict(zip((r[5], r[7]), (r[6], r[8]))) if played(r) else {}
def both(r):   # both channels heard, no fault
    h = heard(r)
    return h.get('1') == 'heard' and h.get('2') == 'heard' and r[9] == '0'
print(f"{'trial':>5} {'kind':>4} {'stride':>7} {'units':>5}  channel 1 (port 0 amp)  channel 2 (port 1 amp)  faults")
for r in rows:
    h = heard(r)
    what = {'none': 'no speaker card', 'froze': 'machine hung'}.get(r[4]) or f"{h.get('1', '-'):21}  {h.get('2', '-'):22}"
    print(f"{r[0]:>5} {r[1]:>4} {r[2]:>7} {r[3]:>5}  {what}  {r[9] if played(r) else ''}")
a = [r for r in rows if r[1] == 'A']; b = [r for r in rows if r[1] == 'B']; c = [r for r in rows if r[1] == 'C']
ok_a = bool(a) and all(both(r) for r in a)
ok_b = not any(both(r) for r in b)
ok_c = bool(c) and all(r[4] == 'none' or (played(r) and heard(r).get('2') != 'heard') for r in c)
errors = [r[0] for r in rows if 'play-error' in r and r[9] == '0']   # after a fault the stream is stopped on purpose
print(f"A ({a[0][2] if a else '?'}): both channels heard in every trial, no fault: {'yes' if ok_a else 'NO'}")
print(f"B: no other stride gets both channels heard without a fault: {'yes' if ok_b else 'NO'}")
print(f"C (A with one unit): no speaker card, or channel 2 silent: {'yes' if ok_c else 'NO'}"
      " (the speaker card needs the second port's DAI, so one unit usually means no card)")
if errors:
    print(f"INVALID: the sound did not play, without a fault, in trial(s) {', '.join(errors)}")
print('PASS' if ok_a and ok_b and ok_c and not errors else 'NOT PASSED')
EOF
echo "saved $OUT"
