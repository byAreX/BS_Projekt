#!/usr/bin/env bash
# Install DriveSphere and LIVI on Raspberry Pi OS Lite Trixie.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."

usage() {
  cat <<'EOF'
Aufruf: bash scripts/install.sh [--mfi]

Installiert Desktop, DriveSphere und die aktuelle LIVI-Release ohne Rückfragen.
--mfi aktiviert LIVIs I²C-Einrichtung für einen angeschlossenen MFi-Coprozessor.
Ohne --mfi bleibt diese Einrichtung aus (z. B. bei einem CarPlay-Dongle).
EOF
}

livi_mfi=no
case "${1:-}" in
  '') ;;
  --mfi) livi_mfi=yes; shift ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
if [[ $# -ne 0 ]]; then usage >&2; exit 2; fi

if [[ "$(uname -s)" != Linux ]] || [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'Installation nur auf einem Raspberry Pi möglich.' >&2
  exit 1
fi
if [[ "$EUID" -eq 0 ]]; then
  echo 'Als normaler Pi-Benutzer starten, nicht mit sudo. Das Skript nutzt sudo intern.' >&2
  exit 1
fi
if [[ "$(uname -m)" != aarch64 ]]; then
  echo 'Raspberry Pi OS 64 Bit wird benötigt.' >&2
  exit 1
fi
if ! grep -Eq '^VERSION_CODENAME="?trixie"?$' /etc/os-release; then
  echo 'Diese Installation ist für Raspberry Pi OS Trixie vorbereitet.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y rpd-wayland-core rpd-theme rpd-preferences \
  python3 chromium curl bluez blueman pipewire wireplumber \
  libspa-0.2-bluetooth pavucontrol python3-gi gir1.2-gtk-3.0 \
  gir1.2-gtklayershell-0.1 plymouth plymouth-themes initramfs-tools fonts-dejavu-core

if ! command -v labwc >/dev/null; then
  echo 'labwc fehlt nach der Paketinstallation.' >&2
  exit 1
fi

if [[ ! -x "$HOME/LIVI/LIVI.AppImage" || "$livi_mfi" == yes ]]; then
  # Pin installer code; the AppImage itself comes from LIVI's latest release.
  livi_revision=3ac92d6671810c75ee8df746aa87c40c0905c4b2
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl --fail --location --proto '=https' --tlsv1.2 \
    "https://raw.githubusercontent.com/f-io/LIVI/$livi_revision/scripts/install/install.sh" \
    --output "$installer"
  LIVI_INSTALLER_BRANCH="$livi_revision" LIVI_CHANNEL=release \
    LIVI_MFI="$livi_mfi" LIVI_SPLASH=no LIVI_HDMI_PR=no \
    bash "$installer" --desktop
else
  echo 'LIVI-AppImage bereits vorhanden; Download übersprungen.'
fi

bash scripts/finish-livi.sh
python3 scripts/install-autostart.py
sudo raspi-config nonint do_boot_behaviour B4
sudo bash scripts/install-plymouth.sh

echo
echo 'DriveSphere und LIVI sind installiert. Der Pi startet mit Plymouth-Bootbalken und Desktop-Autologin.'
echo 'Jetzt sudo reboot ausführen und Touchscreen, Audio und CarPlay mit dem iPhone prüfen.'
