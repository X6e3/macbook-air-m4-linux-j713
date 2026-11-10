#!/usr/bin/env bash
# TL2: compile then run each variation as a separate, unprivileged process.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
R=$(mktemp -d "$HERE/tl2-result-$(date +%Y%m%d-%H%M%S)-XXXX")
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
    -o "$TMP/tl2" "$HERE/tl2.c" -lEGL -lGLESv2 \
    > "$R/build.txt" 2>&1; then
  cat "$R/build.txt" >&2
  echo "FAIL: compilation; result=$R" >&2
  exit 1
fi
errors=0
for scenario in A B C D E; do
  printf 'Running TL2-%s\n' "$scenario"
  if env -u LIBGL_ALWAYS_SOFTWARE -u GALLIUM_DRIVER \
      ASAHI_MESA_DEBUG=resource timeout 90 \
      "$TMP/tl2" "$scenario" > "$R/$scenario.out" 2> "$R/$scenario.log"; then
    echo 'status=0' > "$R/$scenario.status"
  else
    code=$?
    printf 'status=%d\n' "$code" > "$R/$scenario.status"
    printf 'WARNING: TL2-%s exit=%d; see %s\n' "$scenario" "$code" "$R/$scenario.log" >&2
    tail -12 "$R/$scenario.log" >&2
    errors=$((errors+1))
  fi
  if ! grep -q '^renderer=Apple M4' "$R/$scenario.out"; then
    printf 'WARNING: TL2-%s did not confirm Apple M4 renderer\n' "$scenario" >&2
    errors=$((errors+1))
  fi
done
python3 -I "$HERE/summarize-tl2.py" "$R" | tee "$R/SUMMARY.md"
(
  cd "$R"
  sha256sum ./*.out ./*.log ./*.status system.txt build.txt \
    ../tl2.c ../run-tl2.sh ../summarize-tl2.py > SHA256SUMS
)
printf '\nresult: %s\n' "$R"
if ((errors)); then
  printf 'WARNING: %d run/renderer checks failed. Preserve logs.\n' "$errors" >&2
  exit 1
fi
