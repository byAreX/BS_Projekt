#!/usr/bin/env python3
"""Set the executable used by DriveSphere to start a CarPlay application."""
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
config_path = root / 'config.json'


def main():
    args = sys.argv[1:]
    if args and args[0] == '--':
        args = args[1:]
    if not args:
        raise SystemExit('Aufruf: python3 scripts/configure-carplay.py -- /absoluter/pfad/zur/anwendung [argumente...]')
    executable = args[0]
    if not os.path.isabs(executable) or not Path(executable).is_file() or not os.access(executable, os.X_OK):
        raise SystemExit('Der erste Eintrag muss eine vorhandene, ausführbare Datei mit absolutem Pfad sein.')
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    if not isinstance(config, dict):
        raise SystemExit('config.json muss ein JSON-Objekt enthalten.')
    config['carplay_command'] = args
    temporary = config_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    os.chmod(temporary, 0o600)
    temporary.replace(config_path)
    print(f'CarPlay-Startbefehl gespeichert: {executable}')
    print('Ein laufendes DriveSphere-Menü danach neu starten.')


if __name__ == '__main__':
    main()
