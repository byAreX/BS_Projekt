# DriveSphere · Motorrad-Startmenü für Raspberry Pi

Bedienbare Oberfläche für ein 800 × 480 Pixel großes Touchdisplay auf Raspberry Pi OS. Der Pi startet das Menü als Chromium-Kiosk; Bluetooth und Audio werden lokal gesteuert. LIVI liefert CarPlay. Für eine dauerhafte Home-Taste über LIVI werden GTK und Layer Shell benötigt.

## Installation auf Pi 5 mit Raspberry Pi OS Lite Trixie

`scripts/install.sh` installiert in einem Lauf die offizielle Raspberry-Pi-Wayland-Desktopbasis, die Menü-Abhängigkeiten, Plymouth und LIVI 8.3.0. Es richtet Desktop-Autologin und den DriveSphere-Kiosk-Autostart ein, speichert LIVI als CarPlay-Anwendung und deaktiviert LIVIs eigenen Autostart. Dafür benötigt der Pi Internet; `sudo` fragt gegebenenfalls einmal nach deinem Passwort. Vorher wichtige Änderungen auf dem Pi sichern.

Diesen Projektordner auf den Pi kopieren, zum Beispiel nach `~/DriveSphere`. Dann als normaler Pi-Benutzer ausführen:

```sh
cd ~/DriveSphere
bash scripts/install.sh
sudo reboot
```

Der Standardlauf ist für deinen CarPlay-Dongle vorgesehen. Er aktiviert **keine MFi-I²C-Verdrahtung**, keinen LIVI-Bootsplash und keine spezielle RGB/VGA-Pixelwiederholung. Falls später stattdessen ein am GPIO angeschlossener MFi-Coprozessor verwendet wird, lässt sich `bash scripts/install.sh --mfi` nutzen. Die Displayauflösung von 800 × 480 muss für das konkrete Display eingestellt werden; das Skript verändert keine unbekannten HDMI-Timings.

Das Skript lädt den [offiziellen LIVI-Installer](https://github.com/f-io/LIVI#installation) und die AppImage fest in Version **8.3.0** im Desktop-Modus. LIVI 9.0.0 hat die Unterstützung für die Hersteller-Firmware von USB-CarPlay-Dongles entfernt; ein Dongle müsste dafür erst auf „LIVI Link“ umgeflasht werden. LIVI wird unter `~/LIVI/LIVI.AppImage` abgelegt, die installierte Version in `~/LIVI/.drivesphere-version` vermerkt. Ist bei einem erneuten Lauf bereits 8.3.0 installiert, wird der Download übersprungen; jede andere Version wird ersetzt. Die tatsächliche CarPlay-Verbindung hängt weiterhin von der Unterstützung deines Dongles und dem iPhone ab und muss am Pi getestet werden.

Nach dem Neustart zeigt [Plymouth](boot/README.md) beim Linux-Start den Fortschrittsbalken. Chromium öffnet danach direkt das Menü ohne zweite Animation. Unter **Einstellungen → System** die Prüfungen ansehen. Bluetooth-Kopplung, Audioausgabe, CarPlay und die Home-Taste mit den echten Geräten testen. Mit `Alt+F4` lässt sich der Kiosk für Wartung schließen; `bash scripts/kiosk.sh` startet ihn wieder.

Falls LIVI an einem anderen Ort installiert ist, `python3 scripts/configure-carplay.py -- /absoluter/pfad/zur/anwendung [argumente...]` verwenden und einen eigenen LIVI-Autostart deaktivieren. DriveSphere erwartet einen Vordergrundprozess; ein Wrapper-Skript muss die Anwendung mit `exec` starten.

## Vorschau am Computer

```sh
python3 server.py
```

Dann **http://127.0.0.1:8765** öffnen. Die Bootanimation läuft etwa 3,4 Sekunden und wechselt automatisch zum Startmenü. Sie hat keine Überspringen- oder Wiederholen-Taste. `Esc` führt aus Unterseiten zurück; Tastatur und Touch werden unterstützt. Die Vorschau verbindet keine Geräte und startet kein CarPlay. Nacht-/Tagansicht und Oberflächendimmung funktionieren und werden im Browser gespeichert.

Wenn macOS beim System-Python die Xcode-Lizenz verlangt, kann eine vorhandene Command-Line-Tools-Python-Installation verwendet werden:

```sh
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9 server.py
```

## Ablauf

```text
Raspberry Pi einschalten
  → Raspberry Pi OS startet die grafische Sitzung
  → Autostart öffnet DriveSphere im Chromium-Kiosk
  → Logo + animierter Ladebalken
  → Startmenü
      ├─ CarPlay → eingerichtete LIVI-Anwendung starten; Touch-Home beendet sie
      └─ Einstellungen → Bluetooth / Audio / Display / System
```

Die Browseranimation dient nur der Vorschau ohne Plymouth. Auf dem Pi übernimmt das [native Plymouth-Theme](boot/README.md) den Ladebalken während des Linux-Starts. Es zeigt Plymouths geschätzten Bootfortschritt; die grafische Sitzung und Chromium können danach noch kurz laden.

## Betrieb und Wartung

DriveSphere läuft als normaler Desktopbenutzer und lauscht nur auf `127.0.0.1`. Schreibende API-Aufrufe prüfen Origin und ein Sitzungstoken. Die Oberfläche benötigt im Betrieb kein Internet. Der Autostart wird unter `~/.config/labwc/autostart` eingetragen; beim ersten Einrichten wird eine vorhandene Datei als `autostart.before-drivesphere` gesichert. `config.json` bleibt bei erneuter Installation erhalten. Die App nutzt weder root für den Kiosk noch einen öffentlichen Webserver.

## Bluetooth, Cardo und Musik

- **Neues Gerät koppeln** öffnet einen eigenen Touch-Bildschirm. Cardo in den Kopplungsmodus setzen; der Pi sucht 20 Sekunden lang und listet gefundene Geräte. Antippen koppelt, vertraut und verbindet das Gerät. Verlangt es einen Code, zeigt DriveSphere ihn zum Bestätigen an oder bietet ein Ziffernfeld für die PIN. Die Kopplung steuert ein interaktives `bluetoothctl` über ein Pseudoterminal.
- **Erweiterte Bluetooth-Verwaltung öffnen** startet weiterhin Blueman als Notlösung.
- Bereits gekoppelte Geräte erscheinen im Menü. **Verbinden / Trennen** und **Entfernen** (zweimal tippen) verwenden BlueZ über `bluetoothctl`. Ein eingeschalteter, funktionierender Bluetooth-Adapter wird vorausgesetzt.
- **Audioausgang wählen** öffnet `pavucontrol`. Das Headset als Standardausgabe und gegebenenfalls als Ausgabe der laufenden LIVI-Anwendung auswählen. Anschließend schließen.
- Der Lautstärkeregler steuert den PipeWire-Standardausgang über `wpctl`. Er ist ohne Audiozugriff deaktiviert. Das Ändern der Lautstärke hebt eine vorhandene Stummschaltung auf.
- Das iPhone wird über die eingerichtete CarPlay-Lösung verbunden. Die Headset-Kopplung allein stellt keine CarPlay-Verbindung her. Musik, Navigation und Anrufe müssen mit LIVI, iPhone und Cardo gemeinsam am Pi getestet werden.
- **Oberfläche dimmen** ändert nur die Helligkeit der Menüdarstellung; die HDMI-Hintergrundbeleuchtung und die native CarPlay-Oberfläche bleiben davon unabhängig.

LIVI und die beiden Systemdialoge öffnen als eigene Fenster. Ob sie den Fokus über dem Kiosk erhalten, muss unter eurem labwc geprüft werden. Die separate Touch-Home-Taste nutzt Wayland Layer Shell, damit sie auch über einem Vollbildfenster erreichbar bleibt. Sie setzt voraus, dass das konfigurierte Startskript LIVI im Vordergrund mit `exec` ausführt. Ob die Taste mit eurer konkreten LIVI-Version über CarPlay liegt und ob das Fenster danach den Fokus korrekt ans Menü zurückgibt, muss am Pi geprüft werden. Die nativen Bluetooth- und Audiodialoge werden weiterhin durch Schließen verlassen.

## Prüfung und Projektumfang

```sh
python3 -m unittest discover -s tests -v
```

Browserprüfung optional mit Playwright: `python3 -m pip install playwright`, `python3 -m playwright install chromium`, dann bei laufendem Menüserver `python3 tests/browser_check.py`. Screenshots werden unter `artifacts/` gespeichert.

Enthalten: Bootanimation, Hauptmenü, Einstellungen, lokale Hardwareanbindung und Installationsskripte für Pi OS Lite Trixie. Hardwareabhängige Funktionen sind ohne Pi, Bluetooth-Adapter, Display, iPhone und LIVI nicht end-to-end geprüft. Verkaufswebsite, Stromversorgung und Gehäuse sind laut Projektdatei separate Aufgaben und nicht Bestandteil dieses Menüs.

Vor Abnahme am Pi prüfen: Kaltstart und Anzeige bei 800 × 480, Lesbarkeit und Touchziele, Systemcheck, Headset koppeln und erneut verbinden, Audioausgabe nach Neustart, CarPlay starten und mit der eingeblendeten Home-Taste zurückkehren, Musik/Navigation/Telefonie. Die originale Logodatei liegt unverändert unter `web/assets/drivesphere.png`.
