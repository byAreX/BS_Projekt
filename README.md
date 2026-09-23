# DriveSphere · Motorrad-Startmenü

Bedienbare Oberfläche für ein 800 × 480 Pixel großes Touchdisplay am Raspberry Pi 4. Verwendet das bereitgestellte Original-Logo. Die Browservorschau benötigt keine externen Schriftarten, CDNs oder Laufzeitpakete. Für die dauerhafte Touch-Home-Taste auf dem Pi werden GTK und Layer Shell benötigt.

## Vorschau am Computer

```sh
python3 server.py
```

Dann **http://127.0.0.1:8765** öffnen. Die Bootanimation läuft etwa 3,4 Sekunden und wechselt zum Startmenü. Mit „Bootanimation“ lässt sie sich erneut zeigen. `Esc` führt zurück; Tastatur und Touch werden unterstützt. Die Vorschau verbindet keine Geräte und startet kein CarPlay. Nacht-/Tagansicht und Oberflächendimmung funktionieren und werden im Browser gespeichert.

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

Die Browseranimation ist ein Anwendungssplash nach dem Desktopstart. Zusätzlich liegt jetzt ein **natives Plymouth-Theme für euren Linux-Start auf Raspberry Pi OS Trixie** bei: [Einrichtung des Linux-Bootscreens](boot/README.md). Nach dessen Installation überspringt der Kiosk die Browseranimation und öffnet direkt das Hauptmenü. Die normale Mac-Vorschau behält ihre Animation. Ein lückenloser Übergang ab der Firmwarephase ist damit noch nicht zugesichert und muss am Pi geprüft werden.

## Raspberry Pi einrichten

Voraussetzung: Raspberry Pi OS **64 Bit mit Desktop und labwc**, Display im Querformat auf **800 × 480**, funktionierende USB-Toucheingabe. Desktop-Autologin in den Pi-Einstellungen aktivieren. Die Bildschirmauflösung über die Displayeinstellungen bzw. die Anleitung des konkreten HDMI-Displays einstellen; hier werden keine unbekannten HDMI-Timings geschrieben.

1. Diesen Ordner auf den Pi kopieren, beispielsweise nach `~/DriveSphere`.
2. Benötigte Pakete im Terminal installieren:

   ```sh
   sudo apt update
   sudo apt install python3 chromium curl bluez blueman pipewire wireplumber libspa-0.2-bluetooth pavucontrol python3-gi gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1
   ```

   PipeWire und WirePlumber müssen in der angemeldeten Desktop-Sitzung laufen. Bestehende Audioinstallationen zunächst prüfen, nicht parallel mehrere Audioserver einrichten.

3. LIVI separat installieren und mit eurem iPhone und dem **konkreten Dongle-Modell** testen. Die bereitgestellte Projektdatei nennt LIVI und Carlinkit, legt aber keine LIVI-Version und kein eindeutig verifiziertes Dongle-Modell fest. Die aktuelle [LIVI-Dokumentation](https://github.com/f-io/LIVI) beschreibt inzwischen auch native CarPlay-Verbindungen mit MFi-Authentifizierung. Prüft deshalb vor der Installation, ob eure Version den gewählten Dongle tatsächlich unterstützt. Dieses Projekt installiert oder emuliert CarPlay nicht.
4. Konfiguration anlegen:

   ```sh
   cd ~/DriveSphere
   cp config.example.json config.json
   ```

   In `config.json` den **bei euch getesteten ausführbaren Startbefehl** hinterlegen, als JSON-Liste mit einem Argument pro Eintrag. Beispiel mit einem selbst angelegten Startskript:

   ```json
   { "carplay_command": ["/home/DEIN_BENUTZER/bin/start-livi"] }
   ```

   Platzhalter ersetzen. Ein Startskript muss ausführbar sein, die nötige Arbeitsumgebung setzen und die Anwendung am Ende mit `exec` im Vordergrund ausführen. Kein `&`, kein bereits laufender LIVI-Autostart: DriveSphere verwaltet den gestarteten Prozess. Keine Shell-Befehle oder `~` in die JSON-Liste schreiben. Ohne Konfiguration bleibt die Starttaste deaktiviert.

5. Im Pi-Desktop testen:

   ```sh
   bash scripts/kiosk.sh
   ```

   Unter **Einstellungen → System** zeigt der Systemcheck, ob CarPlay-Startbefehl, Bluetooth, Audio und Touch-Home bereit sind. CarPlay wird nur gestartet, wenn die Touch-Home-Abhängigkeiten in der Wayland-Sitzung verfügbar sind. In der laufenden CarPlay-Anwendung erscheint unten rechts eine **Home-Taste** (116 × 58 Pixel). Sie beendet den von DriveSphere gestarteten Vordergrundprozess und führt zum Menü zurück. Teste Position und Sichtbarkeit mit genau deiner LIVI-Version auf dem Pi.

6. Erst nach erfolgreichem Test den Autostart eintragen:

   ```sh
   python3 scripts/install-autostart.py
   ```

   Das Skript ergänzt `~/.config/labwc/autostart` und sichert eine vorhandene Datei. Es verändert keine Systemdienste. Beim nächsten Anmelden/Booten startet das Menü. Andere Desktopumgebungen benötigen ihren eigenen Autostartmechanismus. Grundlage: [offizielle Raspberry-Pi-Kioskanleitung](https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/).

Mit `Alt+F4` lässt sich das Kioskfenster für Wartung schließen. DriveSphere läuft als normaler Desktopbenutzer, **nicht als root**, und lauscht ausschließlich auf `127.0.0.1`. Schreibende API-Aufrufe prüfen Origin und ein Sitzungstoken. Das Menü benötigt kein Internet.

## Bluetooth, Cardo und Musik

- **Neues Gerät koppeln** öffnet die native Blueman-Verwaltung. Cardo in den Kopplungsmodus setzen, suchen, koppeln und bei Bedarf vertrauen. PIN-/Bestätigungsdialoge übernimmt Blueman. Danach das Fenster schließen. Die native Verwaltung ist noch nicht im großen DriveSphere-Touchdesign gestaltet.
- Bereits gekoppelte Geräte erscheinen im Menü. **Verbinden / Trennen** verwendet BlueZ über `bluetoothctl`. Ein eingeschalteter, funktionierender Bluetooth-Adapter wird vorausgesetzt.
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

Enthalten: Bootanimation, Hauptmenü, Einstellungen, lokale Hardwareanbindung und Autostartvorbereitung. Hardwareabhängige Funktionen sind ohne Pi, Bluetooth-Adapter, Display, iPhone und LIVI nicht end-to-end geprüft. Verkaufswebsite, Stromversorgung und Gehäuse sind laut Projektdatei separate Aufgaben und nicht Bestandteil dieses Menüs.

Vor Abnahme am Pi prüfen: Kaltstart und Anzeige bei 800 × 480, Lesbarkeit und Touchziele, Systemcheck, Headset koppeln und erneut verbinden, Audioausgabe nach Neustart, CarPlay starten und mit der eingeblendeten Home-Taste zurückkehren, Musik/Navigation/Telefonie. Die originale Logodatei liegt unverändert unter `web/assets/drivesphere.png`.
