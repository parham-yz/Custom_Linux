#!/usr/bin/env python3
"""Install this theme collection, preserving the rest of the desktop setup."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SLUGS = ('moss-stone', 'slate-tide', 'clay-linen', 'plum-ash')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='install files; otherwise show a dry run')
    parser.add_argument('--theme', choices=SLUGS, help='also activate this theme')
    args = parser.parse_args()
    home = Path.home()
    # The existing switcher writes some app paths directly under ~/.config.
    for key, default in (('XDG_CONFIG_HOME', home / '.config'), ('XDG_STATE_HOME', home / '.local/state')):
        if os.environ.get(key) and Path(os.environ[key]) != default:
            parser.error(f'{key} differs from this desktop snapshot; no files changed')
    files = [Path('.local/bin/obsidian-theme'), Path('.config/obsidian-ember/theme-templates/kitty.conf.tpl')]
    for slug in SLUGS:
        folder = ROOT / 'dotfiles/.config/obsidian-ember/themes' / slug
        files.extend(p.relative_to(ROOT / 'dotfiles') for p in sorted(folder.rglob('*')) if p.is_file())
    # Refuse to overwrite unrelated local switcher/template edits.
    for relative in files[:2]:
        path = home / relative
        desired = (ROOT / 'dotfiles' / relative).read_text()
        baseline = desired.replace('  OPACITY="0.92"\n', '').replace('CONTRAST OPACITY C0', 'CONTRAST C0').replace('background_opacity {{OPACITY}}\n', '')
        if not path.is_file() or path.read_text() not in (baseline, desired):
            parser.error(f'Local file needs manual merging: {path}. No files changed.')
    print(f'{"Install" if args.apply else "Would install"} {len(files)} files for: {", ".join(SLUGS)}')
    if args.theme:
        print(f'Activate: {args.theme}')
    if not args.apply:
        print('Dry run only. Add --apply to install.')
        return
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = home / '.local/state/custom-linux-backups' / ('minimal-themes-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    preserve = list(files)
    if args.theme:
        preserve += [Path(p) for p in ('.config/mako/config', '.config/btop/themes/obsidian-current.theme', '.config/starship.toml', '.local/state/obsidian-ember/current-theme', '.local/state/obsidian-ember/current-wallpaper')]
        preserve += [Path('.config/obsidian-ember/current') / p for p in ('waybar.css', 'rofi.rasi', 'kitty.conf', 'hyprland.conf')]
    absent = []
    for relative in preserve:
        source = home / relative
        if source.is_file():
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            absent.append(str(relative))
    (backup / 'previously-absent.json').write_text(json.dumps(absent, indent=2) + '\n')
    for relative in files:
        target = home / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'dotfiles' / relative, target)
    print(f'Backup: {backup}', flush=True)
    if args.theme:
        subprocess.run([str(home / '.local/bin/obsidian-theme'), 'set', args.theme], check=True)
    print('Installed. Switch with Super+Ctrl+Shift+Space or obsidian-theme switch.')


if __name__ == '__main__':
    main()
