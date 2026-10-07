#!/bin/bash
# Wayland session for DriveSphere: labwc reads only our config, so no desktop, panel or wallpaper starts.
exec labwc -C "${XDG_CONFIG_HOME:-$HOME/.config}/drivesphere/labwc"
