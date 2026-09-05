#!/usr/bin/env python3
"""Apply the reviewed desktop polish files with drift checks and backups."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    home = Path.home()
    for key, expected in [('XDG_CONFIG_HOME',home/'.config'),('XDG_STATE_HOME',home/'.local/state')]:
        if os.environ.get(key) and Path(os.environ[key]) != expected:
            parser.error(f'{key} differs from this desktop snapshot. No files changed.')
    entries = json.loads((ROOT/'manifests/ui-polish-files.json').read_text())
    for entry in entries:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            parser.error('Invalid install manifest path')
        source = ROOT/'dotfiles'/relative
        if not source.is_file():
            parser.error(f'Missing source: {source}')
        if digest(home/relative) not in (entry['before'], digest(source), *entry.get('previous', [])):
            parser.error(f'Local edits need merging: {home/relative}. No files changed.')
    print(f'{"Install" if args.apply else "Would install"} {len(entries)} desktop files. Keep the current theme.')
    if not args.apply:
        print('Dry run only. Add --apply to install.')
        return
    backup = home/'.local/state/custom-linux-backups'/('ui-polish-'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir(parents=True,mode=0o700)
    preserve = [Path(e['path']) for e in entries]
    preserve += [Path(p) for p in ['.config/mako/config','.config/btop/themes/obsidian-current.theme','.config/starship.toml','.local/state/obsidian-ember/current-theme','.local/state/obsidian-ember/current-wallpaper']]
    preserve += [Path('.config/obsidian-ember/current')/p for p in ('waybar.css','rofi.rasi','hyprland.conf','kitty.conf')]
    absent = []
    for relative in preserve:
        current = home/relative
        if current.is_file():
            target = backup/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(current,target)
        else:
            absent.append(str(relative))
    (backup/'previously-absent.json').write_text(json.dumps(absent,indent=2)+'\n')
    print(f'Backup: {backup}',flush=True)
    for entry in entries:
        relative = Path(entry['path'])
        target = home/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'dotfiles'/relative,target)
    subprocess.run([str(home/'.local/bin/obsidian-theme'),'restore'],check=True)
    print('Desktop polish installed. Open the menu with Super+Alt+Space.')


if __name__ == '__main__':
    main()
