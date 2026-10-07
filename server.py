#!/usr/bin/env python3
"""DriveSphere local kiosk host. Standard library only; never run as root."""
import argparse
from functools import lru_cache
import json
import os
from pathlib import Path
import pty
import re
import secrets
import select
import selectors
import signal
import shutil
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
SERVER_PORT = 8765
PREVIEW = True
CONFIG = {}
PROCESSES = {}
LOCK = threading.Lock()
BLUETOOTHCTL = 'bluetoothctl'
ADDRESS = re.compile(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}')
SCAN_SECONDS = 20
SCAN = None
SCAN_STARTED = None
PAIRING = None
CARPLAY_START_SECONDS = 45
CARPLAY_STARTED = float('-inf')


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
            and bool(shutil.which('wlrctl')) and touch_home_dependencies())


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


# LIVI's launcher hands its window to a nested compositor and exits, so CarPlay is found by
# its window (labwc foreign-toplevel via wlrctl) instead of by the launched process.
def carplay_window():
    match = CONFIG.get('carplay_window', 'app_id:dev.f-io.livi')
    return match if isinstance(match, str) and re.fullmatch(r'(app_id|title):[\w.-]+', match) else ''


def carplay_window_action(action, *matches):
    window = carplay_window()
    if not window or not shutil.which('wlrctl'):
        return False
    try:
        return subprocess.run(['wlrctl', 'toplevel', action, window, *matches], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def carplay_starting():
    return time.monotonic() - CARPLAY_STARTED < CARPLAY_START_SECONDS


def carplay_running():
    process = PROCESSES.get('carplay')
    return (bool(process and process.poll() is None) or carplay_starting()
            or carplay_window_action('find'))


def start_touch_home():
    home = PROCESSES.get('touch-home')
    if home and home.poll() is None:
        return
    env = {**os.environ, 'DRIVESPHERE_TOKEN': TOKEN, 'DRIVESPHERE_PORT': str(SERVER_PORT),
           'DRIVESPHERE_CARPLAY_WINDOW': carplay_window(),
           'DRIVESPHERE_CARPLAY_START_SECONDS': str(CARPLAY_START_SECONDS)}
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
    PROCESSES['touch-home'] = home


def start_carplay(args):
    """Start CarPlay, or bring an already running CarPlay window back to the front."""
    global CARPLAY_STARTED
    if not touch_home_available():
        raise ValueError('Touch-Home ist nicht verfügbar. GTK Layer Shell, wlrctl und Wayland prüfen.')
    with LOCK:
        if carplay_window_action('find'):
            start_touch_home()
            if not carplay_window_action('focus'):
                raise ValueError('CarPlay-Fenster konnte nicht nach vorne geholt werden.')
            return False
        process = PROCESSES.get('carplay')
        if carplay_starting() or (process and process.poll() is None):
            raise ValueError('CarPlay startet noch. Bitte kurz warten.')
        start_touch_home()
        try:
            PROCESSES['carplay'] = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL)
        except Exception:
            PROCESSES.pop('touch-home').terminate()
            raise
        CARPLAY_STARTED = time.monotonic()
        return True


def hide_carplay():
    if not carplay_window_action('minimize'):
        raise ValueError('CarPlay-Fenster nicht gefunden.')


def stop_carplay():
    global CARPLAY_STARTED
    with LOCK:
        process = PROCESSES.get('carplay')
        alive = bool(process and process.poll() is None)
        window = carplay_window_action('find')
        if not alive and not window and not carplay_starting():
            raise ValueError('CarPlay läuft nicht mehr.')
        CARPLAY_STARTED = float('-inf')
        if alive:
            process.terminate()
    if alive:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    name = CONFIG.get('carplay_process', 'livi-compositor')
    if isinstance(name, str) and re.fullmatch(r'[\w.-]{1,15}', name):
        subprocess.run(['pkill', '-TERM', '-u', str(os.getuid()), '-x', name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        for _ in range(20):
            if not carplay_window_action('find'):
                break
            time.sleep(.25)
        else:
            raise ValueError('CarPlay-Fenster ist noch offen. LIVI über seine Navigation beenden.')
    home = PROCESSES.get('touch-home')
    if home and home.poll() is None:
        home.terminate()


# bluetoothctl prints its agent prompts in colour and without a trailing newline.
TERMINAL_NOISE = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]|[\x01\x02\r]')
PAIR_EVENTS = [
    ('confirm', r'Confirm passkey (\d+)'),
    ('accept', r'Accept pairing|Authorize service'),
    ('pin', r'Enter (?:PIN code|passkey)'),
    ('display', r'\[agent\] (?:Passkey|PIN code): (\d+)'),
    ('paired', r'Pairing successful|AlreadyExists'),
    ('canceled', r'Request canceled'),
    ('failed', r'Failed to pair: \S+|Device \S+ not available'),
]


class PairingError(Exception):
    pass


def pairing_error(output):
    if 'Authentication' in output:
        return 'Kopplung abgelehnt. Code prüfen und erneut versuchen.'
    if 'not available' in output or 'ConnectionAttempt' in output:
        return 'Gerät nicht erreichbar. Kopplungsmodus am Gerät aktivieren und erneut versuchen.'
    return 'Kopplung fehlgeschlagen. Bitte erneut versuchen.'


class Pairing:
    """Drives an interactive bluetoothctl so pairing codes can be answered in the menu."""

    def __init__(self, address, name):
        self.address, self.name = address, name
        self.step, self.passkey, self.message = 'searching', None, ''
        self.reply, self.cancelled, self.buffer = None, False, ''
        self.master, terminal = pty.openpty()
        try:
            self.process = subprocess.Popen([BLUETOOTHCTL], stdin=terminal, stdout=terminal, stderr=terminal,
                                            env={**os.environ, 'TERM': 'dumb'}, start_new_session=True)
        except Exception:
            os.close(self.master)
            raise
        finally:
            os.close(terminal)
        threading.Thread(target=self.run, daemon=True).start()

    def state(self):
        return dict(address=self.address, name=self.name, step=self.step,
                    passkey=self.passkey, message=self.message)

    def active(self):
        return self.step not in ('done', 'failed')

    def answer(self, pin=None):
        if self.step == 'confirm':
            self.reply = 'yes'
        elif self.step == 'pin':
            if not isinstance(pin, str) or not re.fullmatch(r'\d{1,16}', pin):
                raise ValueError('Bitte einen Code aus Ziffern eingeben.')
            self.reply = pin
        else:
            raise ValueError('Es wird gerade kein Code abgefragt.')

    def cancel(self):
        self.cancelled = True

    def send(self, line):
        os.write(self.master, (line + '\n').encode())

    def expect(self, patterns, timeout):
        """Wait for the earliest match of any pattern; return (index, match) or (None, None)."""
        deadline = time.monotonic() + timeout
        while True:
            found = [(m.start(), i, m) for i, p in enumerate(patterns)
                     if (m := re.search(p, self.buffer, re.I))]
            if found:
                _, index, match = min(found, key=lambda f: f[:2])
                self.buffer = self.buffer[match.end():]
                return index, match
            remaining = deadline - time.monotonic()
            if remaining <= 0 or self.cancelled:
                return None, None
            if select.select([self.master], [], [], min(remaining, .5))[0]:
                try:
                    chunk = os.read(self.master, 4096)
                except OSError:
                    chunk = b''
                if not chunk:
                    raise PairingError('Bluetooth-Dienst nicht erreichbar.')
                self.buffer = (self.buffer + TERMINAL_NOISE.sub('', chunk.decode(errors='replace')))[-8000:]

    def run(self):
        try:
            self.expect([r'Agent (?:is already )?registered'], 5)
            self.send('default-agent')
            # A device found by an earlier scan may already have expired from BlueZ.
            self.send('scan on')
            self.expect([re.escape(self.address)], 10)
            self.send('scan off')
            self.step = 'pairing'
            self.send(f'pair {self.address}')
            deadline = time.monotonic() + 90
            while True:
                if self.cancelled:
                    return
                if self.reply is not None:
                    reply, self.reply = self.reply, None
                    self.buffer = ''  # drop prompt redraws that arrived before the answer
                    self.send(reply)
                    self.step, self.passkey = 'pairing', None
                if time.monotonic() > deadline:
                    raise PairingError('Keine Antwort vom Gerät. Bitte erneut versuchen.')
                index, match = self.expect([p for _, p in PAIR_EVENTS], 1)
                if index is None:
                    continue
                event = PAIR_EVENTS[index][0]
                if event in ('confirm', 'display'):
                    self.step, self.passkey = event, match[1]
                elif event == 'pin':
                    self.step, self.passkey = 'pin', None
                elif event == 'accept':
                    self.send('yes')
                elif event == 'paired':
                    break
                elif event == 'canceled':
                    raise PairingError('Die Kopplung wurde am Gerät abgebrochen.')
                else:
                    raise PairingError(pairing_error(match[0]))
            self.step, self.passkey = 'connecting', None
            self.send(f'trust {self.address}')
            self.expect([r'trust succeeded', r'Failed'], 5)
            self.send(f'connect {self.address}')
            index, _ = self.expect([r'Connection successful', r'Failed to connect'], 20)
            self.message = 'Verbunden.' if index == 0 else 'Gekoppelt. Tippe in der Geräteliste auf „Verbinden“.'
            self.step = 'done'
        except PairingError as exc:
            self.message, self.step = str(exc), 'failed'
        except Exception:
            self.message, self.step = 'Kopplung fehlgeschlagen. Bitte erneut versuchen.', 'failed'
        finally:
            if self.cancelled:
                self.message, self.step = 'Kopplung abgebrochen.', 'failed'
            try:
                self.send('quit')
            except OSError:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            os.close(self.master)


def stop_scan():
    if SCAN and SCAN.poll() is None:
        SCAN.terminate()


def start_scan():
    global SCAN, SCAN_STARTED
    with LOCK:
        if PAIRING and PAIRING.active():
            raise ValueError('Eine Kopplung läuft gerade.')
        if SCAN and SCAN.poll() is None:
            return
        SCAN = subprocess.Popen([BLUETOOTHCTL, '--timeout', str(SCAN_SECONDS), 'scan', 'on'],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        SCAN_STARTED = time.monotonic()


def start_pairing(address, name):
    global PAIRING
    with LOCK:
        if PAIRING and PAIRING.active():
            raise ValueError('Eine Kopplung läuft bereits.')
        stop_scan()
        PAIRING = Pairing(address, name)


def end_pairing():
    global PAIRING
    with LOCK:
        session, PAIRING = PAIRING, None
    if session:
        session.cancel()


def nearby(paired):
    """Named devices from the latest scan that are not paired yet."""
    if SCAN_STARTED is None or time.monotonic() - SCAN_STARTED > SCAN_SECONDS + 40:
        return []
    output = command([BLUETOOTHCTL, 'devices'], timeout=3)
    found = []
    for address, name in re.findall(r'^Device ([0-9A-Fa-f:]{17}) (.+)$', output, re.M):
        if address.upper() not in paired and name.replace('-', ':').upper() != address.upper():
            found.append(dict(address=address, name=name))
    return found[:12]


def status():
    devices, bt_error, volume, found = [], None, None, []
    if available('bluetoothctl'):
        try:
            output = command(['bluetoothctl', 'devices', 'Paired'], timeout=3)
            connected = command(['bluetoothctl', 'devices', 'Connected'], timeout=3)
            for address, name in re.findall(r'^Device ([0-9A-Fa-f:]{17}) (.+)$', output, re.M)[:20]:
                is_connected = bool(re.search(r'^Device ' + re.escape(address) + r' ', connected, re.M | re.I))
                devices.append(dict(address=address, name=name, connected=is_connected))
            found = nearby({d['address'].upper() for d in devices})
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
    configured = bool(args and shutil.which(args[0]))
    running = not PREVIEW and carplay_running()
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
             detail='Overlay kann gestartet werden.' if home_ready else 'Wayland, wlrctl, python3-gi und gir1.2-gtklayershell-0.1 prüfen.'),
    ]
    return dict(token=TOKEN, preview=PREVIEW, checks=checks,
                carplay=dict(configured=configured, running=running, touch_home=home_ready),
                bluetooth=dict(devices=devices, error=bt_error, manager=available('blueman-manager'),
                               scanning=bool(SCAN and SCAN.poll() is None), nearby=found,
                               pairing=PAIRING.state() if PAIRING else None),
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
                started = start_carplay(args)
                message = ('CarPlay gestartet. Die Home-Taste am Display bringt dich zurück.' if started
                           else 'CarPlay ist wieder im Vordergrund.')
            elif self.path == '/api/carplay/hide':
                hide_carplay()
                message = 'CarPlay läuft im Hintergrund weiter.'
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
                if not isinstance(address, str) or not ADDRESS.fullmatch(address) or type(data.get('connect')) is not bool:
                    raise ValueError('Ungültiges Bluetooth-Gerät.')
                paired = command(['bluetoothctl', 'devices', 'Paired'])
                if not re.search(r'^Device ' + re.escape(address) + r' ', paired, re.M | re.I):
                    raise ValueError('Gerät zuerst über „Neues Gerät koppeln“ koppeln.')
                command(['bluetoothctl', 'connect' if data['connect'] else 'disconnect', address], timeout=15)
                message = 'Headset verbunden.' if data['connect'] else 'Verbindung getrennt.'
            elif self.path == '/api/bluetooth/scan':
                start_scan()
                message = ''
            elif self.path == '/api/bluetooth/pair':
                address = data.get('address', '')
                if not isinstance(address, str) or not ADDRESS.fullmatch(address):
                    raise ValueError('Ungültiges Bluetooth-Gerät.')
                known = command([BLUETOOTHCTL, 'devices'])
                name = re.search(r'^Device ' + re.escape(address) + r' (.+)$', known, re.M | re.I)
                start_pairing(address.upper(), name[1] if name else address.upper())
                message = ''
            elif self.path == '/api/bluetooth/answer':
                session = PAIRING
                if not session:
                    raise ValueError('Es läuft keine Kopplung.')
                session.answer(data.get('pin'))
                message = ''
            elif self.path == '/api/bluetooth/cancel':
                end_pairing()
                message = ''
            elif self.path == '/api/bluetooth/remove':
                address = data.get('address', '')
                if not isinstance(address, str) or not ADDRESS.fullmatch(address):
                    raise ValueError('Ungültiges Bluetooth-Gerät.')
                paired = command(['bluetoothctl', 'devices', 'Paired'])
                if not re.search(r'^Device ' + re.escape(address) + r' ', paired, re.M | re.I):
                    raise ValueError('Dieses Gerät ist nicht gekoppelt.')
                command([BLUETOOTHCTL, 'remove', address])
                message = 'Gerät entfernt.'
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
        end_pairing()
        stop_scan()
        with LOCK:
            for process in PROCESSES.values():
                if process.poll() is None:
                    process.terminate()


if __name__ == '__main__':
    main()
