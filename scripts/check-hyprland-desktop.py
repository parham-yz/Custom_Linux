#!/usr/bin/python3
"""Read-only acceptance check for the restored native Hyprland desktop."""
import json
from pathlib import Path
import subprocess


def hypr(*args):
    return subprocess.check_output(['/usr/bin/hyprctl', *args], text=True).strip()


assert not hypr('configerrors'), hypr('configerrors')
config = (Path.home() / '.config/hypr/hyprland.lua').read_text()
binds = json.loads(hypr('-j', 'binds'))
expected = sum(line.startswith('hl.bind(') for line in config.splitlines())
assert expected >= 100 and len(binds) == expected, (len(binds), expected)
for mask, key in [(64, 'Return'), (64, 'Space'), (65, 'Space'), (68, 'B')]:
    assert any(b['modmask'] == mask and b['key'] == key for b in binds), (mask, key)
layers = json.loads(hypr('-j', 'layers'))
for output, data in layers.items():
    surfaces = [s for items in data['levels'].values() for s in items]
    assert any(s['namespace'] == 'wallpaper' and s['alpha'] > 0 for s in surfaces), output
    bars = [s for s in surfaces if s['namespace'] == 'waybar' and s['alpha'] > 0]
    assert len(bars) == (1 if output == 'eDP-1' else 0), (output, bars)
services = ['obsidian-hyprland-session.target', 'xdg-desktop-portal.service',
            'xdg-desktop-portal-hyprland.service', 'obsidian-power.service', 'obsidian-idle.service']
subprocess.run(['systemctl', '--user', 'is-active', '--quiet', *services], check=True)
# is-active succeeds if any unit is active; check each individually too.
for service in services:
    subprocess.run(['systemctl', '--user', 'is-active', '--quiet', service], check=True)
print(f'PASS: {len(binds)} shortcuts, wallpaper on {len(layers)} outputs, built-in-only bar, clean config and active services')
