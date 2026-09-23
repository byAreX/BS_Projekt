#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then
  echo 'Dieses Skript ist für Raspberry Pi OS. Vorschau: python3 server.py' >&2
  exit 1
fi
if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  echo 'Bitte innerhalb der grafischen Desktop-Sitzung starten.' >&2
  exit 1
fi
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/drivesphere-${UID}.lock"
flock -n 9 || exit 0
browser="$(command -v chromium || command -v chromium-browser || true)"
if [[ -z "$browser" ]]; then
  echo 'Chromium fehlt. Bitte zuerst installieren.' >&2
  exit 1
fi
python3 server.py --hardware &
server_pid=$!
cleanup() { kill "$server_pid" 2>/dev/null || true; }
trap cleanup EXIT
ready=false
for attempt in {1..40}; do
  kill -0 "$server_pid" 2>/dev/null || { echo 'Menüserver konnte nicht starten.' >&2; exit 1; }
  if curl --silent --fail http://127.0.0.1:8765/api/status >/dev/null; then ready=true; break; fi
  sleep .25
done
if [[ "$ready" != true ]]; then echo 'Menüserver antwortet nicht.' >&2; exit 1; fi
kiosk_url='http://127.0.0.1:8765'
if [[ -f /etc/drivesphere/linux-boot-splash ]]; then
  kiosk_url+='?boot=skip'
fi
"$browser" --kiosk --no-first-run --noerrdialogs --disable-session-crashed-bubble \
  --user-data-dir="${XDG_CONFIG_HOME:-$HOME/.config}/drivesphere/chromium" \
  --window-size=800,480 "$kiosk_url"
