#!/usr/bin/env bash
# Run from a local writable directory on J713 Fedora, as user x6e3, never sudo.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
R=$(mktemp -d "$HERE/tl1-result-$(date +%Y%m%d-%H%M%S)-XXXX")
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
printf 'result=%s\n' "$R"
{
    date -Is
    uname -a
    rpm -q mesa-dri-drivers mesa-libEGL mesa-libGLES 2>/dev/null || true
    printf 'ASAHI_MESA_DEBUG=resource\n'
} > "$R/system.txt"
if ! gcc -O2 -g -Wall -Wextra -Werror=implicit-function-declaration \
     -o "$TMP/tl1" "$HERE/tl1.c" -lEGL -lGLESv2 \
     > "$R/build.txt" 2>&1; then
    echo 'Compilation failed:' >&2
    cat "$R/build.txt" >&2
    exit 1
fi
failures=0
for scenario in A B C D E O V; do
    printf 'Running TL1-%s\n' "$scenario"
    if env -u LIBGL_ALWAYS_SOFTWARE -u GALLIUM_DRIVER \
        ASAHI_MESA_DEBUG=resource timeout 60 \
        "$TMP/tl1" "$scenario" 1024 \
        > "$R/$scenario.out" 2> "$R/$scenario.log"; then
        printf 'status=0\n' > "$R/$scenario.status"
    else
        code=$?
        printf 'status=%s\n' "$code" > "$R/$scenario.status"
        echo "WARNING: TL1-$scenario exited $code; see $R/$scenario.log" >&2
        tail -20 "$R/$scenario.log" >&2
        failures=$((failures + 1))
    fi
    if ! grep -q '^renderer=Apple M4' "$R/$scenario.out"; then
        echo "WARNING: TL1-$scenario did not report Apple M4; do not interpret this as AGX evidence" >&2
    fi
done
python3 -I "$HERE/summarize-tl1.py" "$R" | tee "$R/SUMMARY.md"
(
    cd "$R"
    sha256sum ./*.out ./*.log ./*.status system.txt build.txt \
        ../tl1.c ../run-tl1.sh ../summarize-tl1.py > SHA256SUMS
)
printf '\nresult: %s\n' "$R"
if ((failures)); then
    printf '%s scenario(s) failed; all available logs are preserved in %s\n' "$failures" "$R" >&2
    exit 1
fi
