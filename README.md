# DriveSphere · Motorrad-Startmenü für Raspberry Pi

Bedienbare Oberfläche für ein 800 × 480 Pixel großes Touchdisplay auf Raspberry Pi OS. Der Pi startet das Menü als Chromium-Kiosk; Bluetooth und Audio werden lokal gesteuert. LIVI liefert CarPlay. Zwischen CarPlay und Menü wird gewechselt, ohne dass LIVI beendet wird; dafür werden GTK, Layer Shell und `wlrctl` benötigt.

## Installation auf Pi 5 mit Raspberry Pi OS Lite Trixie

`scripts/install.sh` installiert in einem Lauf die offizielle Raspberry-Pi-Wayland-Desktopbasis, die Menü-Abhängigkeiten, Plymouth und LIVI 8.3.0. Es richtet Autologin in eine eigene DriveSphere-Sitzung ohne Desktop ein (siehe [Start ohne Desktop](#start-ohne-desktop)), speichert LIVI als CarPlay-Anwendung und deaktiviert LIVIs eigenen Autostart. Dafür benötigt der Pi Internet; `sudo` fragt gegebenenfalls einmal nach deinem Passwort. Vorher wichtige Änderungen auf dem Pi sichern.

Diesen Projektordner auf den Pi kopieren, zum Beispiel nach `~/DriveSphere`. Dann als normaler Pi-Benutzer ausführen:

```sh
cd ~/DriveSphere
bash scripts/install.sh
sudo reboot
```

Der Standardlauf ist für deinen CarPlay-Dongle vorgesehen. Er aktiviert **keine MFi-I²C-Verdrahtung**, keinen LIVI-Bootsplash und keine spezielle RGB/VGA-Pixelwiederholung. Falls später stattdessen ein am GPIO angeschlossener MFi-Coprozessor verwendet wird, lässt sich `bash scripts/install.sh --mfi` nutzen. Die Displayauflösung von 800 × 480 muss für das konkrete Display eingestellt werden; das Skript verändert keine unbekannten HDMI-Timings.

Das Skript lädt den [offiziellen LIVI-Installer](https://github.com/f-io/LIVI#installation) und die AppImage fest in Version **8.3.0** im Desktop-Modus. LIVI 9.0.0 hat die Unterstützung für die Hersteller-Firmware von USB-CarPlay-Dongles entfernt; ein Dongle müsste dafür erst auf „LIVI Link“ umgeflasht werden. LIVI wird unter `~/LIVI/LIVI.AppImage` abgelegt, die installierte Version in `~/LIVI/.drivesphere-version` vermerkt. Ist bei einem erneuten Lauf bereits 8.3.0 installiert, wird der Download übersprungen; jede andere Version wird ersetzt. Die tatsächliche CarPlay-Verbindung hängt weiterhin von der Unterstützung deines Dongles und dem iPhone ab und muss am Pi getestet werden.

Nach dem Neustart zeigt [Plymouth](boot/README.md) beim Linux-Start den Fortschrittsbalken. Chromium öffnet danach direkt das Menü ohne zweite Animation. Unter **Einstellungen → System** die Prüfungen ansehen. Bluetooth-Kopplung, Audioausgabe, CarPlay und den Wechsel mit der Home-Taste mit den echten Geräten testen. Für Wartung öffnet `Strg+Alt+T` ein Terminal; mit `Alt+F4` lässt sich der Kiosk schließen und mit `bash scripts/kiosk.sh` wieder starten.

Falls LIVI an einem anderen Ort installiert ist, `python3 scripts/configure-carplay.py -- /absoluter/pfad/zur/anwendung [argumente...]` verwenden und einen eigenen LIVI-Autostart deaktivieren. DriveSphere erkennt die laufende Anwendung an ihrem Fenster; bei einer anderen Anwendung als LIVI `carplay_window` und `carplay_process` anpassen (siehe [Zwischen CarPlay und Menü wechseln](#zwischen-carplay-und-menü-wechseln)).

## Start ohne Desktop

Damit nach dem Plymouth-Balken nicht kurz der Raspberry-Pi-Desktop mit Hintergrundbild und Taskleiste erscheint, startet der Pi eine eigene Wayland-Sitzung **DriveSphere**. `scripts/install-session.sh` (von `install.sh` aufgerufen) richtet sie ein:

- `/usr/local/bin/drivesphere-session` startet labwc mit `labwc -C ~/.config/drivesphere/labwc`. labwc liest dann nur diesen Ordner; Hintergrundbild (`pcmanfm-pi`) und Taskleiste (`wf-panel-pi`) aus dem Desktop-Autostart starten nicht.
- `~/.config/drivesphere/labwc/autostart` startet nur `kanshi` (falls vorhanden, für die Bildschirmeinstellungen) und `scripts/kiosk.sh`. `environment` übernimmt Tastaturlayout und Variablen aus `/etc/xdg/labwc/environment` und `~/.config/labwc/environment`. Die Dateien werden bei jeder Installation neu erzeugt; eigene Änderungen dort gehen dabei verloren.
- `rc.xml` behält labwcs Standard-Tastenkürzel (z. B. `Alt+F4`, `Alt+Tab`) und ergänzt **`Strg+Alt+T`** für das Terminal `foot`.
- `/usr/share/wayland-sessions/drivesphere.desktop` meldet die Sitzung an, und in `/etc/lightdm/lightdm.conf` wird `autologin-session=drivesphere` gesetzt. Die vorherige Sitzung wird in `/var/lib/drivesphere/previous-autologin-session` gespeichert.
- Ein DriveSphere-Eintrag aus älteren Installationen in `~/.config/labwc/autostart` wird entfernt.

Die Sitzung verweist über den Autostart auf den Projektordner. Wird er verschoben, `bash scripts/install-session.sh` erneut ausführen.

**Wartung:** Tastatur anschließen, `Strg+Alt+T` öffnet ein Terminal über dem Kiosk. Dort lassen sich z. B. Logs prüfen oder `bash scripts/kiosk.sh` nach einem `Alt+F4` wieder starten.

**Zurück zum normalen Desktop:**

```sh
cd ~/DriveSphere
bash scripts/install-session.sh --restore
sudo reboot
```

Danach startet wieder die vorherige Desktop-Sitzung, ohne automatischen Kiosk. Ein erneutes `bash scripts/install-session.sh` aktiviert die DriveSphere-Sitzung wieder.

Am Pi prüfen: Kaltstart ohne sichtbaren Desktop, Touch im Menü und in LIVI, Tastaturlayout im Terminal sowie Auflösung und Drehung. Fehlt etwas, das sonst der Desktop-Autostart gestartet hat, in `/etc/xdg/labwc/autostart` nachsehen und es bei Bedarf in `scripts/install-session.sh` ergänzen. Zwischen Plymouth und dem ersten Chromium-Bild kann noch kurz ein leerer Hintergrund sichtbar sein.

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
  → Raspberry Pi OS meldet sich automatisch in der DriveSphere-Sitzung an (kein Desktop)
  → Autostart öffnet DriveSphere im Chromium-Kiosk
  → Logo + animierter Ladebalken
  → Startmenü
      ├─ CarPlay → LIVI starten bzw. wieder nach vorne holen; Home in CarPlay schickt LIVI in den Hintergrund
      └─ Einstellungen → Bluetooth / Audio / Display / System
```

Die Browseranimation dient nur der Vorschau ohne Plymouth. Auf dem Pi übernimmt das [native Plymouth-Theme](boot/README.md) den Ladebalken während des Linux-Starts. Es zeigt Plymouths geschätzten Bootfortschritt; die grafische Sitzung und Chromium können danach noch kurz laden.

## Betrieb und Wartung

DriveSphere läuft als normaler Desktopbenutzer und lauscht nur auf `127.0.0.1`. Schreibende API-Aufrufe prüfen Origin und ein Sitzungstoken. Die Oberfläche benötigt im Betrieb kein Internet. `config.json` bleibt bei erneuter Installation erhalten. Die App nutzt weder root für den Kiosk noch einen öffentlichen Webserver.

## Bluetooth, Cardo und Musik

- **Neues Gerät koppeln** öffnet einen eigenen Touch-Bildschirm. Cardo in den Kopplungsmodus setzen; der Pi sucht 20 Sekunden lang und listet gefundene Geräte. Antippen koppelt, vertraut und verbindet das Gerät. Verlangt es einen Code, zeigt DriveSphere ihn zum Bestätigen an oder bietet ein Ziffernfeld für die PIN. Die Kopplung steuert ein interaktives `bluetoothctl` über ein Pseudoterminal.
- **Erweiterte Bluetooth-Verwaltung öffnen** startet weiterhin Blueman als Notlösung.
- Bereits gekoppelte Geräte erscheinen im Menü. **Verbinden / Trennen** und **Entfernen** (zweimal tippen) verwenden BlueZ über `bluetoothctl`. Ein eingeschalteter, funktionierender Bluetooth-Adapter wird vorausgesetzt.
- **Audioausgang wählen** öffnet `pavucontrol`. Das Headset als Standardausgabe und gegebenenfalls als Ausgabe der laufenden LIVI-Anwendung auswählen. Anschließend schließen.
- Der Lautstärkeregler steuert den PipeWire-Standardausgang über `wpctl`. Er ist ohne Audiozugriff deaktiviert. Das Ändern der Lautstärke hebt eine vorhandene Stummschaltung auf.
- Das iPhone wird über die eingerichtete CarPlay-Lösung verbunden. Die Headset-Kopplung allein stellt keine CarPlay-Verbindung her. Musik, Navigation und Anrufe müssen mit LIVI, iPhone und Cardo gemeinsam am Pi getestet werden.
- **Oberfläche dimmen** ändert nur die Helligkeit der Menüdarstellung; die HDMI-Hintergrundbeleuchtung und die native CarPlay-Oberfläche bleiben davon unabhängig.

## Zwischen CarPlay und Menü wechseln

LIVI läuft nach dem ersten Start im Hintergrund weiter; das iPhone bleibt verbunden, Musik und Navigationsansagen laufen weiter.

- **CarPlay → Menü:** Über CarPlay liegt unten rechts die Taste **⌂ Home**. Sie minimiert das LIVI-Fenster; danach ist das DriveSphere-Menü vorne. Die Taste erscheint nur, solange LIVI das aktive Fenster ist.
- **Menü → CarPlay:** Läuft CarPlay bereits, holt ein Tipp auf die CarPlay-Kachel LIVI sofort wieder nach vorne. Auf der CarPlay-Seite heißt die Taste dann **Zu CarPlay wechseln**.
- **Beenden:** Nur über **CarPlay beenden** auf der CarPlay-Seite. Das beendet LIVI vollständig; beim nächsten Start verbindet sich das iPhone neu.

Technik: LIVI 8.3.0 startet unter Linux einen eigenen eingebetteten Compositor (`livi-compositor`) und beendet den aufgerufenen Prozess sofort wieder. DriveSphere erkennt CarPlay deshalb am Fenster statt am Prozess. Minimieren, Nach-vorne-Holen und die Prüfung, ob LIVI aktiv ist, laufen über `wlrctl` und das Fensterprotokoll von labwc. Beim Beenden wird `livi-compositor` des eigenen Benutzers beendet. Nach dem Start gilt CarPlay bis zu 45 Sekunden als „startet“, bis das Fenster erscheint.

In `config.json` lassen sich beide Werte für eine andere CarPlay-Anwendung anpassen:

```json
{
  "carplay_window": "app_id:dev.f-io.livi",
  "carplay_process": "livi-compositor"
}
```

`carplay_window` ist ein `wlrctl`-Ausdruck (`app_id:…` oder `title:…`), `carplay_process` der Prozessname, der beim Beenden gestoppt wird (höchstens 15 Zeichen). Fehlen die Einträge, gelten die LIVI-Werte oben. Die Fenster-ID lässt sich am Pi prüfen, während LIVI läuft: `wlrctl toplevel find app_id:dev.f-io.livi && echo gefunden`.

Am Pi prüfen: ob Ton und Navigation im Hintergrund weiterlaufen, ob LIVI nach dem Nach-vorne-Holen sofort wieder das CarPlay-Bild zeigt und ob nach Home das Menü den Touch-Fokus bekommt. Der Weg über LIVIs eigenes „App“-Symbol im CarPlay-Dock führt derzeit noch in LIVIs Oberfläche; dort führt Home unten rechts ebenfalls zurück ins Menü.

Die nativen Bluetooth- und Audiodialoge öffnen als eigene Fenster und werden durch Schließen verlassen.

## Prüfung und Projektumfang

```sh
python3 -m unittest discover -s tests -v
```

Browserprüfung optional mit Playwright: `python3 -m pip install playwright`, `python3 -m playwright install chromium`, dann bei laufendem Menüserver `python3 tests/browser_check.py`. Screenshots werden unter `artifacts/` gespeichert.

Enthalten: Bootanimation, Hauptmenü, Einstellungen, lokale Hardwareanbindung und Installationsskripte für Pi OS Lite Trixie. Hardwareabhängige Funktionen sind ohne Pi, Bluetooth-Adapter, Display, iPhone und LIVI nicht end-to-end geprüft. Verkaufswebsite und Stromversorgung sind laut Projektdatei separate Aufgaben und nicht Bestandteil dieses Menüs. Das 3D-druckbare Gehäuse liegt unter [`enclosure/`](enclosure/README.md).

Vor Abnahme am Pi prüfen: Kaltstart und Anzeige bei 800 × 480, Lesbarkeit und Touchziele, Systemcheck, Headset koppeln und erneut verbinden, Audioausgabe nach Neustart, CarPlay starten, mit der eingeblendeten Home-Taste zum Menü wechseln und über die CarPlay-Kachel ohne Verbindungsabbruch zurück, Musik/Navigation/Telefonie. Die originale Logodatei liegt unverändert unter `web/assets/drivesphere.png`.
