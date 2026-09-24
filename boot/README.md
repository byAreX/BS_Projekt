# DriveSphere-Bootbalken auf Raspberry Pi 4 und 5

DriveSphere zeigt während des Linux-Starts ein natives Plymouth-Theme. Der Balken erhält seine Werte über `Plymouth.SetBootProgressFunction` vom Bootsystem. Er folgt dessen **geschätztem Fortschritt**, nicht einer festen 3,4-Sekunden-Animation. Eine genaue Prozentzahl bis zum fertigen Chromium-Menü kann Plymouth nicht liefern: Es endet beim Übergang zur grafischen Sitzung. Die frühe Firmwarephase liegt ebenfalls davor.

## Pi 5 mit Raspberry Pi OS Lite Trixie

Der [Hauptinstaller](../README.md) installiert Plymouth und das Theme automatisch. Auf dem Pi ausführen:

```sh
cd ~/DriveSphere
bash scripts/install.sh
sudo reboot
```

Das Skript prüft den Pi-5-Kernel `kernel_2712.img`, das dazugehörige `initramfs_2712` und `auto_initramfs=1`. Es aktiviert den Raspberry-Pi-Plymouth-Splash nur, wenn er noch ausgeschaltet ist, kopiert Theme und Logo und baut das Initramfs mit `plymouth-set-default-theme -R drivesphere` neu. Danach setzt es `/etc/drivesphere/linux-boot-splash`, damit Chromium direkt das Menü öffnet und keine zweite Browseranimation abspielt.

Der Plymouth-Balken zeigt den geschätzten **Linux-Start** an. Nach dem Ende von Plymouth können noch Desktop-Autologin und Chromium starten. Ein kurzer schwarzer Übergang oder ein sichtbarer Desktop ist möglich und muss am echten Display geprüft werden. Der Installer ändert keine Display-Timings.

## Manuell installieren und zurücksetzen

Auf einem bereits eingerichteten Pi 4 oder 5 mit Trixie kann das Theme auch einzeln installiert werden:

```sh
sudo apt-get install plymouth plymouth-themes initramfs-tools fonts-dejavu-core
sudo bash scripts/install-plymouth.sh
```

Zum Wiederherstellen des vorherigen Themes:

```sh
sudo bash scripts/install-plymouth.sh --restore
```

Das Skript merkt sich das vorherige Theme. War der Plymouth-Splash zuvor ausgeschaltet, wird er beim Wiederherstellen ebenfalls ausgeschaltet. Der Marker für den direkten Menüstart wird entfernt. Nach einer Änderung neu starten. Falls die Initramfs-Aktualisierung fehlschlägt, vor einem Neustart den Fehler beheben.

Die Theme-Darstellung und der Übergang müssen auf dem Pi geprüft werden; die Browserprüfung testet nur den direkten Menüstart nach Plymouth. Referenzen: [Raspberry-Pi-Bootkonfiguration](https://www.raspberrypi.com/documentation/computers/config_txt.html#auto_initramfs), [Raspberry-Pi-Splashscreen](https://www.raspberrypi.com/documentation/computers/configuration.html#configure-splash-screens) und [Debian Plymouth](https://manpages.debian.org/trixie/plymouth/plymouth-set-default-theme.1.en.html).
