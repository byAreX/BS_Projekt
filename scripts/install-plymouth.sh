#!/bin/bash
# Install the DriveSphere Plymouth theme on Raspberry Pi OS Trixie.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ "$(uname -s)" != Linux ]] || [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'Dieses Skript benötigt einen Raspberry Pi mit Raspberry Pi OS Trixie.' >&2
  exit 1
fi
if [[ "$EUID" != 0 ]]; then echo 'Auf dem Pi mit sudo bash scripts/install-plymouth.sh starten.' >&2; exit 1; fi
if [[ "${1:-}" != '' && "${1:-}" != '--restore' ]] || [[ $# -gt 1 ]]; then
  echo 'Aufruf: install-plymouth.sh [--restore]' >&2; exit 1
fi
for executable in plymouth-set-default-theme update-initramfs; do
  command -v "$executable" >/dev/null || { echo "$executable fehlt. Siehe boot/README.md." >&2; exit 1; }
done
state_dir=/var/lib/drivesphere
previous_theme="$state_dir/previous-plymouth-theme"
splash_state="$state_dir/splash-was-enabled"
marker=/etc/drivesphere/linux-boot-splash
if [[ "${1:-}" == '--restore' ]]; then
  [[ -s "$previous_theme" ]] || { echo 'Kein vorheriges Theme gespeichert.' >&2; exit 1; }
  theme="$(cat "$previous_theme")"
  [[ "$theme" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Ungültiger gespeicherter Theme-Name.' >&2; exit 1; }
  plymouth-set-default-theme -R "$theme"
  if [[ -f "$splash_state" ]] && [[ "$(cat "$splash_state")" == no ]]; then
    raspi-config nonint do_boot_splash 1
  fi
  rm -f "$marker"
  echo 'Vorheriges Theme wiederhergestellt. Die Browseranimation ist wieder aktiv.'
  exit 0
fi
if ! grep -Eq '^VERSION_CODENAME="?trixie"?$' /etc/os-release; then
  echo 'Vorbereitet für Trixie. Für andere Versionen zuerst die Bootkonfiguration prüfen.' >&2; exit 1
fi
model="$(tr -d '\0' </proc/device-tree/model)"
case "$model" in
  *'Raspberry Pi 5 '*) kernel_suffix=_2712 ;;
  *'Raspberry Pi 4 '*) kernel_suffix=8 ;;
  *) echo 'Dieses Theme ist für Raspberry Pi 4 und 5 vorbereitet.' >&2; exit 1 ;;
esac
if [[ ! -s "/boot/firmware/kernel${kernel_suffix}.img" || ! -s "/boot/firmware/initramfs${kernel_suffix}" ]]; then
  echo "Kernel oder Initramfs für dieses Pi-Modell fehlt: kernel${kernel_suffix}.img / initramfs${kernel_suffix}." >&2
  exit 1
fi
if ! grep -Eq '^[[:space:]]*auto_initramfs=1([[:space:]]|$)' /boot/firmware/config.txt; then
  echo 'auto_initramfs=1 fehlt in /boot/firmware/config.txt. Bootkonfiguration zuerst prüfen.' >&2
  exit 1
fi
theme_dir=/usr/share/plymouth/themes/drivesphere
current_theme="$(plymouth-set-default-theme)"
if [[ ! -s "$previous_theme" ]]; then
  if [[ ! "$current_theme" =~ ^[a-zA-Z0-9_-]+$ || "$current_theme" == drivesphere ]]; then
    echo 'Das vorherige Theme konnte nicht eindeutig ermittelt werden.' >&2; exit 1
  fi
  install -d -m 755 "$state_dir"
  printf '%s\n' "$current_theme" > "$previous_theme"
  if grep -Eq '(^|[[:space:]])splash([[:space:]]|$)' /boot/firmware/cmdline.txt; then
    printf 'yes\n' > "$splash_state"
  else
    printf 'no\n' > "$splash_state"
  fi
fi
install -d -m 755 "$theme_dir"
install -m 644 boot/drivesphere/drivesphere.plymouth boot/drivesphere/drivesphere.script \
  boot/drivesphere/track.png boot/drivesphere/accent.png web/assets/drivesphere.png "$theme_dir/"
newly_enabled=false
if ! grep -Eq '(^|[[:space:]])splash([[:space:]]|$)' /boot/firmware/cmdline.txt; then
  raspi-config nonint do_boot_splash 0
  newly_enabled=true
fi
if ! plymouth-set-default-theme -R drivesphere; then
  if [[ "$newly_enabled" == true ]]; then raspi-config nonint do_boot_splash 1 || true; fi
  plymouth-set-default-theme -R "$(cat "$previous_theme")" || true
  echo 'Initramfs-Aktualisierung fehlgeschlagen. Nicht neu starten; Fehler prüfen und mit --restore zurücksetzen.' >&2
  exit 1
fi
install -d -m 755 /etc/drivesphere
touch "$marker"
echo 'DriveSphere-Plymouth installiert. Beim nächsten Start wird die Browseranimation übersprungen.'
echo 'Jetzt einen Kaltstart und den Übergang zum Menü am Display prüfen.'
