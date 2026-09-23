#!/usr/bin/env python3
"""Add DriveSphere to labwc autostart without replacing existing entries."""
from pathlib import Path
import shlex
import shutil

root = Path(__file__).resolve().parents[1]
target = Path.home() / '.config/labwc/autostart'
target.parent.mkdir(parents=True, exist_ok=True)
old = target.read_text() if target.exists() else ''
marker = '# DriveSphere launcher'
if marker in old:
    print(f'DriveSphere ist bereits eingetragen: {target}')
else:
    if target.exists():
        backup = target.with_name('autostart.before-drivesphere')
        if not backup.exists():
            shutil.copy2(target, backup)
    line = 'bash ' + shlex.quote(str(root / 'scripts/kiosk.sh')) + ' &'
    target.write_text(old.rstrip() + '\n\n' + marker + '\n' + line + '\n')
    print(f'Autostart eingetragen: {target}\nZum Entfernen die letzten zwei DriveSphere-Zeilen löschen.')
