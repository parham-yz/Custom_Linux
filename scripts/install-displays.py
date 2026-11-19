#!/usr/bin/python3
"""Install only the native Displays app and its narrowly scoped menu/config hooks."""
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
SHARE = '.local/share/obsidian-displays'
sys.path.insert(0, str(ROOT / 'dotfiles' / SHARE))
import backend


def integrate_config(text):
    include = 'source = ~/.config/hypr/obsidian-displays.conf'
    if include not in text:
        old = 'monitor = eDP-1, preferred, auto, 1.6\nmonitor = , preferred, auto, 1'
        if old not in text:
            raise RuntimeError('Monitor configuration differs from the inspected baseline; review before installing.')
        text = text.replace(old, include, 1)
    marker = '# Native Displays settings window'
    if marker not in text:
        text += '\n' + marker + '\nwindowrule = float on, match:class ^(org.obsidian.Displays|obsidian-displays)$\nwindowrule = center on, match:class ^(org.obsidian.Displays|obsidian-displays)$\n'
    return text


def integrate_menu(text):
    if "'󰍹  Displays'" not in text:
        text = text.replace("    '󰔡  Quick settings' \\\n", "    '󰍹  Displays' \\\n    '󰔡  Quick settings' \\\n", 1)
        text = text.replace('    *Quick\\ settings) exec "$0" toggle ;;', '    *Displays) obsidian-display-settings ;;\n    *Quick\\ settings) exec "$0" toggle ;;', 1)
    return text


def main():
    raw = backend.monitors()
    wanted = backend.snapshot(raw)
    backend.validate(wanted, raw)
    live_hypr = HOME / '.config/hypr/hyprland.lua'
    if not live_hypr.exists():
        live_hypr = HOME / '.config/hypr/hyprland.conf'
    live_menu = HOME / '.local/bin/obsidian-menu'
    if live_hypr.suffix == '.lua':
        new_hypr = live_hypr.read_text()
        if 'obsidian-displays.conf' not in new_hypr or 'obsidian-displays)$' not in new_hypr:
            raise RuntimeError('Native Hyprland config needs Displays integration; review before installing.')
    else:
        new_hypr = integrate_config(live_hypr.read_text())
    new_menu = integrate_menu(live_menu.read_text())
    backup = HOME / '.local/state/obsidian-ember/backups' / ('displays-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    paths = [SHARE + '/' + name for name in ['backend.py', 'app.py', 'style.css']]
    paths += ['.local/bin/obsidian-hyprctl', '.local/bin/obsidian-display-settings', '.local/share/applications/obsidian-displays.desktop']
    changed = paths + [str(live_hypr.relative_to(HOME)), '.config/hypr/obsidian-displays.conf', '.local/bin/obsidian-menu']
    for name in changed:
        target = HOME / name
        if target.exists():
            save = backup / name
            save.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, save)
    (backup / 'manifest.json').write_text(json.dumps(changed, indent=2))
    for name in paths:
        target = HOME / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'dotfiles' / name, target)
    if not backend.CONFIG.exists():
        backend.atomic_write(backend.CONFIG, backend.render(wanted))
    backend.atomic_write(live_hypr, new_hypr)
    backend.atomic_write(live_menu, new_menu)
    live_menu.chmod(0o755)
    backend.hypr('reload')
    errors = backend.hypr('configerrors').strip()
    if errors:
        for name in [str(live_hypr.relative_to(HOME)), '.local/bin/obsidian-menu']:
            shutil.copy2(backup / name, HOME / name)
        backend.hypr('reload')
        raise RuntimeError('Configuration restored after error: ' + errors)
    backend.settle(wanted)
    # Edit repository copies independently; preserve pre-existing live/repo differences.
    rp = ROOT / 'dotfiles/.config/hypr/hyprland.conf'
    rp.write_text(integrate_config(rp.read_text()))
    rp = ROOT / 'dotfiles/.local/bin/obsidian-menu'
    rp.write_text(integrate_menu(rp.read_text()))
    portable = ROOT / 'dotfiles/.config/hypr/obsidian-displays.conf'
    if not portable.exists():
        portable.write_text('# Defaults; Displays saves your confirmed layout here.\nmonitor = , preferred, auto, 1\nmonitor = eDP-1, preferred, auto, 1.6\n')
    subprocess.run(['update-desktop-database', str(HOME / '.local/share/applications')], check=False)
    print('Installed Displays. Existing monitor geometry retained. Backup:', backup)


if __name__ == '__main__':
    main()
