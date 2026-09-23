#!/usr/bin/env python3
"""Small Wayland overlay that stays reachable above a fullscreen CarPlay window."""
import json
import os
import sys
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


def request(path, data=None):
    headers = {}
    if data is not None:
        headers = {'Content-Type': 'application/json', 'Origin': BASE,
                   'X-DriveSphere-Token': TOKEN}
    req = Request(BASE + path, data=json.dumps(data).encode() if data is not None else None,
                  headers=headers)
    with urlopen(req, timeout=8) as response:
        return json.load(response)


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

    def stop():
        button.set_sensitive(False)
        def send():
            try:
                request('/api/carplay/stop', {})
                GLib.idle_add(Gtk.main_quit)
            except Exception as exc:
                print(f'Touch-Home: {exc}', file=sys.stderr)
                GLib.idle_add(button.set_sensitive, True)
        threading.Thread(target=send, daemon=True).start()

    def check_running():
        try:
            if not request('/api/status')['carplay']['running']:
                Gtk.main_quit()
                return False
        except Exception:
            pass
        return True

    button.connect('clicked', lambda _button: stop())
    window.connect('destroy', Gtk.main_quit)
    window.show_all()
    print('READY', flush=True)
    GLib.timeout_add_seconds(2, check_running)
    Gtk.main()


if __name__ == '__main__':
    main()
