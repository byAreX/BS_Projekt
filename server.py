#!/usr/bin/env python3
"""DriveSphere local kiosk host. Standard library only; never run as root."""
import argparse
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import signal
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
SERVER_PORT = 8765
PREVIEW = True
CONFIG = {}
PROCESSES = {}
LOCK = threading.Lock()


def command(args, timeout=8):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    output = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout + result.stderr).strip()
    if result.returncode or 'Failed' in output or 'not available' in output:
        raise ValueError(output[-400:] or 'Systembefehl fehlgeschlagen.')
    return output


def available(name):
    return not PREVIEW and bool(shutil.which(name))


def carplay_command():
    args = CONFIG.get('carplay_command', [])
    if not isinstance(args, list) or not all(isinstance(a, str) and a for a in args):
        return []
    return args


def touch_home_available():
    return (not PREVIEW and bool(os.environ.get('WAYLAND_DISPLAY'))
            and touch_home_dependencies())


@lru_cache(maxsize=1)
def touch_home_dependencies():
    try:
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/touch-home.py'), '--check'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def launch(name, args):
    with LOCK:
        if name in PROCESSES and PROCESSES[name].poll() is None:
            raise ValueError('Die Anwendung ist bereits geöffnet.')
        PROCESSES[name] = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL)


def start_carplay(args):
    if not touch_home_available():
        raise ValueError('Touch-Home ist nicht verfügbar. GTK Layer Shell und Wayland prüfen.')
    with LOCK:
        current = PROCESSES.get('carplay')
        if current and current.poll() is None:
            raise ValueError('Die Anwendung ist bereits geöffnet.')
        env = {**os.environ, 'DRIVESPHERE_TOKEN': TOKEN, 'DRIVESPHERE_PORT': str(SERVER_PORT)}
        home = subprocess.Popen([sys.executable, str(ROOT / 'scripts/touch-home.py')],
                                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, env=env)
        with selectors.DefaultSelector() as selector:
            selector.register(home.stdout, selectors.EVENT_READ)
            ready = bool(selector.select(timeout=4)) and home.stdout.readline().strip() == b'READY'
        home.stdout.close()
        if not ready or home.poll() is not None:
            if home.poll() is None:
                home.terminate()
            raise ValueError('Touch-Home konnte nicht gestartet werden. Wayland-Sitzung prüfen.')
        try:
            carplay = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL)
        except Exception:
            home.terminate()
            raise
        PROCESSES['carplay'] = carplay
        PROCESSES['touch-home'] = home


def stop_carplay():
    with LOCK:
        process = PROCESSES.get('carplay')
        if not process or process.poll() is not None:
            raise ValueError('CarPlay läuft nicht mehr.')
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
    home = PROCESSES.get('touch-home')
    if home and home.poll() is None:
        home.terminate()


def status():
    devices, bt_error, volume = [], None, None
    if available('bluetoothctl'):
        try:
            output = command(['bluetoothctl', 'devices', 'Paired'], timeout=3)
            connected = command(['bluetoothctl', 'devices', 'Connected'], timeout=3)
            for address, name in re.findall(r'^Device ([0-9A-Fa-f:]{17}) (.+)$', output, re.M)[:20]:
                is_connected = bool(re.search(r'^Device ' + re.escape(address) + r' ', connected, re.M | re.I))
                devices.append(dict(address=address, name=name, connected=is_connected))
        except (ValueError, subprocess.TimeoutExpired) as exc:
            bt_error = 'Bluetooth nicht erreichbar. Prüfe Adapter und Bluetooth-Dienst.'
    else:
        bt_error = 'Bluetooth ist noch nicht installiert oder hier nicht verfügbar.'
    if available('wpctl'):
        try:
            output = command(['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'], timeout=3)
            match = re.search(r'Volume: ([0-9.]+)', output)
            if match:
                volume = 0 if '[MUTED]' in output else min(100, round(float(match[1]) * 100))
        except (ValueError, subprocess.TimeoutExpired):
            pass
    args = carplay_command()
    process = PROCESSES.get('carplay')
    configured = bool(args and shutil.which(args[0]))
    running = bool(process and process.poll() is None)
    home_ready = touch_home_available()
    checks = [
        dict(name='CarPlay-Startbefehl', ok=configured,
             detail='Bereit.' if configured else 'config.json und den ausführbaren Startbefehl prüfen.'),
        dict(name='Bluetooth', ok=bt_error is None,
             detail='Erreichbar.' if bt_error is None else bt_error),
        dict(name='Audioausgang', ok=volume is not None,
             detail='PipeWire-Standardausgang erreichbar.' if volume is not None else 'PipeWire, WirePlumber und den Standardausgang prüfen.'),
        dict(name='Bluetooth-Verwaltung', ok=available('blueman-manager'),
             detail='Bereit.' if available('blueman-manager') else 'blueman installieren.'),
        dict(name='Audioverwaltung', ok=available('pavucontrol'),
             detail='Bereit.' if available('pavucontrol') else 'pavucontrol installieren.'),
        dict(name='Touch-Home', ok=home_ready,
             detail='Overlay kann gestartet werden.' if home_ready else 'Wayland, python3-gi und gir1.2-gtklayershell-0.1 prüfen.'),
    ]
    return dict(token=TOKEN, preview=PREVIEW, checks=checks,
                carplay=dict(configured=configured, running=running, touch_home=home_ready),
                bluetooth=dict(devices=devices, error=bt_error, manager=available('blueman-manager')),
                audio=dict(volume=volume, manager=available('pavucontrol')))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def respond(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'")
        super().end_headers()

    def do_GET(self):
        if not self.valid_host():
            return self.respond({'error':'Ungültiger Host.'}, 403)
        if self.path == '/api/status':
            return self.respond(status())
        if self.path.startswith('/api/'):
            return self.respond({'error':'Unbekannte Aktion.'}, 404)
        super().do_GET()

    def do_POST(self):
        origin = self.headers.get('Origin')
        allowed = (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}')
        if not self.valid_host() or origin not in allowed or not secrets.compare_digest(self.headers.get('X-DriveSphere-Token', ''), TOKEN):
            return self.respond({'error':'Lokaler Zugriff erforderlich.'}, 403)
        if PREVIEW:
            return self.respond({'error':'Hardwarefunktionen sind in der Vorschau deaktiviert.'}, 409)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('Ungültige Anfrage.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Ungültige Anfrage.')
            if self.path == '/api/carplay':
                args = carplay_command()
                if not args:
                    raise ValueError('Bitte zuerst carplay_command in config.json einrichten.')
                start_carplay(args)
                message = 'CarPlay gestartet. Die Home-Taste am Display bringt dich zurück.'
            elif self.path == '/api/carplay/stop':
                stop_carplay()
                message = 'CarPlay beendet. Das Startmenü ist wieder erreichbar.'
            elif self.path == '/api/pair':
                launch('bluetooth', ['blueman-manager'])
                message = 'Bluetooth-Verwaltung geöffnet. Headset koppeln, dann dieses Fenster schließen.'
            elif self.path == '/api/audio-manager':
                launch('audio', ['pavucontrol'])
                message = 'Audioverwaltung geöffnet. Wähle dein Headset als Standardausgabe.'
            elif self.path == '/api/volume':
                value = data.get('value')
                if type(value) is not int or not 0 <= value <= 100:
                    raise ValueError('Lautstärke muss zwischen 0 und 100 liegen.')
                command(['wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@', f'{value}%'])
                command(['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', '0'])
                message = ''
            elif self.path == '/api/bluetooth':
                address = data.get('address', '')
                if not isinstance(address, str) or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', address) or type(data.get('connect')) is not bool:
                    raise ValueError('Ungültiges Bluetooth-Gerät.')
                paired = command(['bluetoothctl', 'devices', 'Paired'])
                if not re.search(r'^Device ' + re.escape(address) + r' ', paired, re.M | re.I):
                    raise ValueError('Gerät zuerst über die Bluetooth-Verwaltung koppeln.')
                command(['bluetoothctl', 'connect' if data['connect'] else 'disconnect', address], timeout=15)
                message = 'Headset verbunden.' if data['connect'] else 'Verbindung getrennt.'
            else:
                return self.respond({'error':'Unbekannte Aktion.'}, 404)
            self.respond({'message':message})
        except FileNotFoundError:
            self.respond({'error':'Die benötigte Anwendung wurde nicht gefunden. Prüfe die Installation.'}, 400)
        except subprocess.TimeoutExpired:
            self.respond({'error':'Keine Antwort vom Gerät. Prüfe die Verbindung und versuche es erneut.'}, 504)
        except (ValueError, OSError) as exc:
            self.respond({'error':str(exc)}, 400)


def main():
    global PREVIEW, CONFIG, SERVER_PORT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hardware', action='store_true', help='Lokale Linux-Hardwarefunktionen aktivieren')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if args.hardware and sys.platform != 'linux':
        parser.error('--hardware benötigt Linux / Raspberry Pi OS.')
    PREVIEW = not args.hardware
    config = ROOT / 'config.json'
    if config.exists():
        CONFIG = json.loads(config.read_text())
        if not isinstance(CONFIG, dict):
            parser.error('config.json muss ein JSON-Objekt enthalten.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    SERVER_PORT = server.server_port
    def terminate(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    print(f'DriveSphere: http://127.0.0.1:{args.port} ({"Vorschau" if PREVIEW else "Hardware"})', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        with LOCK:
            for process in PROCESSES.values():
                if process.poll() is None:
                    process.terminate()


if __name__ == '__main__':
    main()
