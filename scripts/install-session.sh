#!/bin/bash
# Boot into a labwc session that only runs the DriveSphere kiosk instead of the Raspberry Pi desktop.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ "$(uname -s)" != Linux ]] || [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'Dieses Skript benötigt einen Raspberry Pi mit Raspberry Pi OS Trixie.' >&2
  exit 1
fi
if [[ "$EUID" -eq 0 ]]; then
  echo 'Als normaler Pi-Benutzer starten, nicht mit sudo. Das Skript nutzt sudo intern.' >&2
  exit 1
fi
if [[ "${1:-}" != '' && "${1:-}" != '--restore' ]] || [[ $# -gt 1 ]]; then
  echo 'Aufruf: install-session.sh [--restore]' >&2; exit 1
fi
lightdm_conf=/etc/lightdm/lightdm.conf
if [[ ! -f "$lightdm_conf" ]] || ! grep -Eq '^autologin-user=' "$lightdm_conf"; then
  echo 'Desktop-Autologin ist nicht aktiv. Zuerst sudo raspi-config nonint do_boot_behaviour B4 ausführen.' >&2
  exit 1
fi
state_dir=/var/lib/drivesphere
previous_session="$state_dir/previous-autologin-session"
current="$(sed -n 's/^autologin-session=//p' "$lightdm_conf" | head -n 1)"

set_session() {
  if [[ -z "$1" ]]; then
    sudo sed -i '/^autologin-session=/d' "$lightdm_conf"
  elif grep -q '^autologin-session=' "$lightdm_conf"; then
    sudo sed -i "s/^autologin-session=.*/autologin-session=$1/" "$lightdm_conf"
  elif grep -q '^\[Seat:\*\]' "$lightdm_conf"; then
    sudo sed -i "/^\[Seat:\*\]/a autologin-session=$1" "$lightdm_conf"
  else
    echo "[Seat:*] fehlt in $lightdm_conf. Autologin-Konfiguration prüfen." >&2
    exit 1
  fi
}

if [[ "${1:-}" == '--restore' ]]; then
  [[ -f "$previous_session" ]] || { echo 'Keine vorherige Sitzung gespeichert.' >&2; exit 1; }
  previous="$(cat "$previous_session")"
  [[ "$previous" =~ ^[a-zA-Z0-9_.-]*$ ]] || { echo 'Ungültiger gespeicherter Sitzungsname.' >&2; exit 1; }
  set_session "$previous"
  sudo rm -f "$previous_session"
  echo 'Raspberry-Pi-Desktop wiederhergestellt. Nach dem Neustart startet wieder der normale Desktop.'
  echo 'DriveSphere dort bei Bedarf mit bash scripts/kiosk.sh öffnen.'
  exit 0
fi

command -v labwc >/dev/null || { echo 'labwc fehlt.' >&2; exit 1; }
[[ "$current" =~ ^[a-zA-Z0-9_.-]*$ ]] || { echo 'Unerwarteter Sitzungsname in lightdm.conf.' >&2; exit 1; }
if [[ ! -f "$previous_session" && "$current" != drivesphere ]]; then
  sudo install -d -m 755 "$state_dir"
  printf '%s\n' "$current" | sudo tee "$previous_session" >/dev/null
fi

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/drivesphere/labwc"
mkdir -p "$config_dir"
{
  echo '# Von DriveSphere erzeugt; wird bei jeder Installation überschrieben.'
  echo 'command -v kanshi >/dev/null && kanshi &'
  echo "bash $(printf '%q' "$PWD/scripts/kiosk.sh") &"
} > "$config_dir/autostart"
cat > "$config_dir/rc.xml" <<'EOF'
<?xml version="1.0"?>
<!-- Von DriveSphere erzeugt; wird bei jeder Installation überschrieben. -->
<labwc_config>
  <keyboard>
    <default />
    <keybind key="C-A-t">
      <action name="Execute" command="foot" />
    </keybind>
  </keyboard>
</labwc_config>
EOF
# Keep keyboard layout and other variables the Pi desktop session would have loaded.
cat /etc/xdg/labwc/environment "$HOME/.config/labwc/environment" 2>/dev/null > "$config_dir/environment" || true

# Older installs started the kiosk from the desktop autostart; the new session replaces that.
if [[ -f "$HOME/.config/labwc/autostart" ]]; then
  sed -i '/^# DriveSphere launcher$/,+1d' "$HOME/.config/labwc/autostart"
fi

sudo install -m 755 scripts/session.sh /usr/local/bin/drivesphere-session
sudo tee /usr/share/wayland-sessions/drivesphere.desktop >/dev/null <<'EOF'
[Desktop Entry]
Name=DriveSphere
Comment=DriveSphere-Kiosk ohne Raspberry-Pi-Desktop
Exec=/usr/local/bin/drivesphere-session
Type=Application
EOF
set_session drivesphere
echo 'DriveSphere-Sitzung eingerichtet. Nach dem Neustart erscheint direkt das Menü ohne Desktop.'
echo 'Wartung: Strg+Alt+T öffnet ein Terminal. Zurück zum Desktop: bash scripts/install-session.sh --restore'
