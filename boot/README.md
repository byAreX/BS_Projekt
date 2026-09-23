# DriveSphere als Linux-Bootscreen · Raspberry Pi OS Trixie

Das Theme in `drivesphere/` läuft in **Plymouth während des Linux-Starts**, bevor der Desktop und Chromium starten. Es zeigt das unveränderte transparente Logo auf dunklem Hintergrund, den Schriftzug „RIDE CONNECTED.“ und einen blauen, leicht pulsierenden Fortschrittsbalken.

Der Balken verwendet Plymouths **geschätzten Systemstartfortschritt**. Es gibt keine künstliche Wartezeit von 3,4 Sekunden. 100 Prozent bedeuten nicht, dass Bluetooth, LIVI oder das DriveSphere-Menü schon bereit sind. Systemnachrichten und Eingabeaufforderungen werden angezeigt; Passworteingaben werden maskiert.

## Auf dem Pi installieren

Ziel: **Raspberry Pi 4, Raspberry Pi OS Trixie 64 Bit mit Desktop**, regulärer `kernel8`-/`initramfs8`-Boot und HDMI-Display mit 800 × 480 Pixeln. Die Vorbereitung wurde am Mac erstellt; ein nativer Plymouth-Start konnte hier nicht ausgeführt werden.

1. Zuerst das Startmenü und seinen Desktop-Autostart gemäß [Projektanleitung](../README.md) einrichten.
2. Plymouth-Pakete installieren:

   ```sh
   sudo apt update
   sudo apt install plymouth plymouth-themes initramfs-tools fonts-dejavu-core
   ```

3. Den **normalen Raspberry-Pi-Bootsplash** aktivieren: `sudo raspi-config` öffnen und unter **System Options → Splashscreen** einschalten. Neu starten und prüfen, ob der normale grafische Linux-Bootscreen sichtbar ist. Alternativ steht der Schalter unter **Control Centre → System → Splash Screen**. Diese Schritte sind in der [Raspberry-Pi-Dokumentation](https://www.raspberrypi.com/documentation/computers/configuration.html#configure-splash-screens) beschrieben.
4. Im kopierten Projektordner das Theme installieren:

   ```sh
   cd ~/DriveSphere
   sudo bash scripts/install-plymouth.sh
   ```

   Falls der Projektordner anders heißt, den Pfad anpassen. Das Skript prüft Plattform, Trixie, den aktiven `splash`-Bootparameter und das erwartete Pi-4-Initramfs. Es kopiert Theme und Logo, merkt sich das vorherige Theme und aktiviert DriveSphere über `plymouth-set-default-theme -R drivesphere`. Die Option `-R` erneuert das Initramfs, siehe [Debian-Trixie-Handbuch](https://manpages.debian.org/trixie/plymouth/plymouth-set-default-theme.1.en.html).

5. Nur wenn die Installation erfolgreich endet, den Pi neu starten und den vollständigen Ablauf prüfen.

Das Installationsskript verändert weder `cmdline.txt` noch `config.txt`, Display-Timings, Autologin oder Systemdienste. Es setzt voraus, dass der Standardsplash bereits funktioniert. Fehlt `initramfs8` oder verwendet ihr einen anderen Kernel, zuerst die tatsächliche Bootkonfiguration prüfen. Bei Raspberry Pi bestimmt `auto_initramfs=1` die Zuordnung zwischen Kernel und Initramfs; siehe [offizielle Bootkonfiguration](https://www.raspberrypi.com/documentation/computers/config_txt.html#auto_initramfs).

## Übergang zum Menü

Nach erfolgreicher Installation existiert `/etc/drivesphere/linux-boot-splash`. `scripts/kiosk.sh` erkennt die Datei und öffnet die Oberfläche mit `?boot=skip`. So landet ihr direkt im Hauptmenü, ohne eine zweite Logoanimation.

```text
Einschalten → Firmware → Linux mit DriveSphere-Plymouth
           → Desktop-Autologin → DriveSphere-Startmenü
```

Der reguläre Displaymanager beendet Plymouth. Er wird hier nicht künstlich aufgehalten. Ein kurzer schwarzer Übergang oder ein sichtbarer Desktop ist deshalb möglich und muss mit eurem Display, labwc und Chromium am Pi beurteilt werden. Die allererste Firmwarephase wird vom Theme nicht ersetzt. Eine zusätzliche frühe statische Logoanzeige wäre ein eigener Einrichtungsschritt.

Am Mac bleibt die normale [Browservorschau](http://127.0.0.1:8765) mit ihrer Animation erhalten. Den **direkten Menüstart** könnt ihr mit [dieser URL](http://127.0.0.1:8765/?boot=skip) ansehen. „Bootanimation“ im Menü spielt weiterhin die Browserdemo ab, keinen Linux-Neustart.

## Zurück zum bisherigen Theme

```sh
cd ~/DriveSphere
sudo bash scripts/install-plymouth.sh --restore
```

Das stellt das zuvor gespeicherte Theme wieder her, erneuert das Initramfs und entfernt den Marker für den direkten Menüstart. Die Browseranimation ist danach wieder aktiv. Das DriveSphere-Theme bleibt als unbenutzte Datei installiert. Wenn eine Initramfs-Aktualisierung fehlschlägt, vor einem Neustart den Fehler beheben oder die Wiederherstellung ausführen.

Bei der Abnahme auf dem Pi prüfen: Logo und Lesbarkeit bei 800 × 480, Fortschrittsanzeige während des echten Starts, sichtbare Systemrückfragen, Übergang zum Menü ohne zweite Animation, Kaltstart sowie Wiederherstellung des vorherigen Themes. Die native Scriptsyntax und das Rendering benötigen noch einen Test mit Plymouth auf dem Pi; die Browserprüfung testet nur die Menüübergabe.
