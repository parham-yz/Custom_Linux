#!/usr/bin/env python3
"""Check actual theme rendering in a disposable home and palette contrast."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build', ROOT / 'scripts/build-minimal-themes.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def luminance(color):
    rgb = [int(color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    linear = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
    return sum(x * y for x, y in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def main():
    for row in build.PALETTES:
        p = build.palette(row)
        checks = [('TEXT', 'BG'), ('TEXT', 'PANEL'), ('MUTED', 'BG'),
                  ('MUTED', 'PANEL'), ('MUTED', 'HOVER'), ('ACCENT', 'HOVER'),
                  ('CONTRAST', 'ACCENT'), ('CONTRAST', 'ACCENT2'), ('C15', 'HOVER')]
        for fg, bg in checks:
            value = contrast(p[fg], p[bg])
            assert value >= 4.5, (row[0], fg, bg, value)
        for key in ('C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10', 'C11', 'C12', 'C13', 'C14', 'C15'):
            assert contrast(p[key], p['BG']) >= 4.5, (row[0], key)
        print(f'{row[0]}: text {contrast(p["TEXT"], p["BG"]):.2f}:1; lowest UI text pair {min(contrast(p[a],p[b]) for a,b in checks):.2f}:1')
    with tempfile.TemporaryDirectory(prefix='obsidian-theme-check-') as tmp:
        home = Path(tmp)
        config = home / '.config/obsidian-ember'
        shutil.copytree(ROOT / 'dotfiles/.config/obsidian-ember/theme-templates', config / 'theme-templates')
        shutil.copytree(ROOT / 'dotfiles/.config/obsidian-ember/themes', config / 'themes')
        mock = home / 'bin'
        mock.mkdir()
        for cmd in ('notify-send', 'pkill', 'pgrep', 'hyprctl', 'makoctl'):
            path = mock / cmd
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        env = os.environ | {'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_STATE_HOME': str(home / '.local/state'), 'PATH': str(mock) + ':' + os.environ['PATH']}
        script = ROOT / 'dotfiles/.local/bin/obsidian-theme'
        for folder in sorted((config / 'themes').iterdir()):
            subprocess.run([str(script), 'set', folder.name], env=env, check=True, capture_output=True)
            assert (home / '.local/state/obsidian-ember/current-theme').read_text().strip() == folder.name
            wallpaper = Path((home / '.local/state/obsidian-ember/current-wallpaper').read_text().strip())
            assert wallpaper.is_file()
            for path in (config / 'current').iterdir():
                assert '{{' not in path.read_text(), path
            kitty = (config / 'current/kitty.conf').read_text()
            expected = '1.0' if folder.name in {r[0] for r in build.PALETTES} else '0.92'
            assert f'background_opacity {expected}\n' in kitty
            tomllib.loads((home / '.config/starship.toml').read_text())
            assert '{{' not in (home / '.config/btop/themes/obsidian-current.theme').read_text()
            assert '{{' not in (home / '.config/mako/config').read_text()
        print('All seven themes render through the real switcher; wallpaper/state and legacy opacity checks passed.')


if __name__ == '__main__':
    main()
