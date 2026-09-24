#!/usr/bin/env bash
# Connect the upstream LIVI desktop installation to DriveSphere.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ "$EUID" -eq 0 ]]; then
  echo 'Als normaler Desktopbenutzer ausführen, nicht mit sudo.' >&2
  exit 1
fi
livi="$HOME/LIVI/LIVI.AppImage"
if [[ ! -f "$livi" || ! -x "$livi" ]]; then
  echo "LIVI fehlt unter $livi. Zuerst den offiziellen LIVI-Installer mit --desktop ausführen." >&2
  exit 1
fi
python3 scripts/configure-carplay.py -- "$livi"
autostart="$HOME/.config/autostart/LIVI.desktop"
if [[ -f "$autostart" ]]; then
  mv -- "$autostart" "$autostart.drivesphere-disabled"
  echo 'LIVI-Autostart deaktiviert; DriveSphere startet LIVI über die CarPlay-Taste.'
fi
echo 'Jetzt den Pi neu starten und den Start über DriveSphere prüfen.'
