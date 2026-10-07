#!/usr/bin/env python3
"""Small Wayland overlay above the CarPlay window: Home sends CarPlay to the background."""
import json
import os
import subprocess
import sys
import time
import threading
from urllib.request import Request, urlopen

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import GLib, Gtk, GtkLayerShell  # noqa: E402


if '--check' in sys.argv:
    raise SystemExit(0)

PORT = os.environ['DRIVESPHERE_PORT']
TOKEN = os.environ['DRIVESPHERE_TOKEN']
BASE = f'http://127.0.0.1:{PORT}'
WINDOW = os.environ['DRIVESPHERE_CARPLAY_WINDOW']
START_SECONDS = float(os.environ.get('DRIVESPHERE_CARPLAY_START_SECONDS', '45'))


def request(path, data=None):
    headers = {}
    if data is not None:
        headers = {'Content-Type': 'application/json', 'Origin': BASE,
                   'X-DriveSphere-Token': TOKEN}
    req = Request(BASE + path, data=json.dumps(data).encode() if data is not None else None,
                  headers=headers)
    with urlopen(req, timeout=8) as response:
        return json.load(response)


def window_found(*matches):
    try:
        return subprocess.run(['wlrctl', 'toplevel', 'find', WINDOW, *matches], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    window = Gtk.Window(title='DriveSphere Home')
    window.set_decorated(False)
    GtkLayerShell.init_for_window(window)
    GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.BOTTOM, True)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.RIGHT, True)
    GtkLayerShell.set_margin(window, GtkLayerShell.Edge.BOTTOM, 12)
    GtkLayerShell.set_margin(window, GtkLayerShell.Edge.RIGHT, 12)
    GtkLayerShell.set_exclusive_zone(window, 0)

    button = Gtk.Button(label='⌂  Home')
    button.set_size_request(116, 58)
    button.get_style_context().add_class('suggested-action')
    window.add(button)

    def hide():
        button.set_sensitive(False)
        def send():
            try:
                request('/api/carplay/hide', {})
            except Exception as exc:
                print(f'Touch-Home: {exc}', file=sys.stderr)
            GLib.idle_add(button.set_sensitive, True)
        threading.Thread(target=send, daemon=True).start()

    started = time.monotonic()
    seen = False

    # Show the button only while CarPlay is the active window; quit once CarPlay has closed.
    def follow_carplay():
        nonlocal seen
        if window_found():
            seen = True
            if window_found('state:active'):
                window.show_all()
            else:
                window.hide()
        elif seen or time.monotonic() - started > START_SECONDS:
            Gtk.main_quit()
            return False
        else:
            window.hide()
        return True

    button.connect('clicked', lambda _button: hide())
    window.connect('destroy', Gtk.main_quit)
    print('READY', flush=True)
    GLib.timeout_add(700, follow_carplay)
    Gtk.main()


if __name__ == '__main__':
    main()
