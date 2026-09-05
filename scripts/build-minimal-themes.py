#!/usr/bin/env python3
"""Build original palettes, vector wallpapers, PNGs, and a local theme gallery."""
from pathlib import Path
import html
import subprocess

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / 'dotfiles/.config/obsidian-ember/themes'
PALETTES = [
    ('moss-stone', 'Moss Stone', 'dark', 'Charcoal, soft sage, and warm stone.',
     ['191d1b', '222824', '303a33', '48554b', 'e0e5dc', 'a6b2a7', 'b1c59e', 'b1c59e', 'e3a19b', '191d1b'],
     ['303a33', 'e3a19b', 'b1c59e', 'd3bd91', '9eb9c5', 'bcaac5', '9fc3b8', 'd1d9ce',
      '95a294', 'efb3ac', 'c4d5b4', 'e0cda7', 'b3cbd5', 'cebcd6', 'b5d5cb', 'edf0e8']),
    ('slate-tide', 'Slate Tide', 'dark', 'Blue slate with a pale sea-glass accent.',
     ['191f26', '232c35', '303d49', '4a5d6b', 'e0e6eb', 'a4b3bf', 'a2c5d4', 'a2c5d4', 'e4a3a4', '191f26'],
     ['303d49', 'e4a3a4', 'a9c3ad', 'd6c09b', 'a2c5d4', 'c0afd0', '9fcac5', 'cfdae2',
      '96a8b6', 'efb8b8', 'bed4c0', 'e5d2b1', 'b9d6e1', 'd1c1de', 'b6dcd6', 'edf1f4']),
    ('clay-linen', 'Clay Linen', 'light', 'Warm paper, dark ink, and quiet terracotta.',
     ['f2eee5', 'e8e2d7', 'ddd4c6', 'b4a594', '383b35', '595d54', '884c3b', '884c3b', 'a23737', 'fffaf2'],
     ['383b35', 'a23737', '426349', '775b20', '3c6079', '765270', '326863', '50554b',
      '686c61', 'a84237', '496a43', '80601f', '466985', '80557b', '38716b', '30362f']),
    ('plum-ash', 'Plum Ash', 'dark', 'Smoky neutrals with a restrained lilac accent.',
     ['211e24', '2b2730', '3c3542', '5c5064', 'e8e0e9', 'b9acbf', 'c5b0ce', 'c5b0ce', 'e7a4ad', '211e24'],
     ['3c3542', 'e7a4ad', 'b5c2a6', 'd4bf9e', 'a9bbd0', 'c5b0ce', 'a3c4bf', 'ddd1df',
      'ab9bb2', 'f0b6be', 'c8d2bc', 'e2cfb2', 'becde0', 'd7c5df', 'b9d7d1', 'f2ebf3']),
]
KEYS = 'BG PANEL HOVER BORDER TEXT MUTED ACCENT ACCENT2 DANGER CONTRAST'.split()


def palette(row):
    slug, name, mode, description, colors, ansi = row
    return dict(zip(KEYS, colors)) | {f'C{i}': c for i, c in enumerate(ansi)}


def wallpaper(p, index):
    """Flat vector compositions: large quiet fields and a single muted motif."""
    bg, panel, hover, border = [p[k] for k in ('BG', 'PANEL', 'HOVER', 'BORDER')]
    shapes = [
        f'<circle cx="1850" cy="720" r="290" fill="#{hover}"/>'
        f'<path d="M0 1350 Q700 1080 1330 1290 T2560 1130 V1664 H0Z" fill="#{panel}"/>'
        f'<path d="M0 1450 Q800 1190 1530 1410 T2560 1280 V1664 H0Z" fill="#{bg}"/>',
        f'<path d="M1660 1120 V690 a270 270 0 0 1 540 0 V1120Z" fill="#{panel}"/>'
        f'<path d="M1740 1120 V690 a190 190 0 0 1 380 0 V1120Z" fill="#{hover}"/>'
        f'<path d="M0 1220 H2560" stroke="#{border}" stroke-opacity=".35" stroke-width="2"/>',
        f'<circle cx="1880" cy="740" r="280" fill="#{panel}"/>'
        f'<path d="M1630 1090 H2200 V900 Q1950 780 1630 900Z" fill="#{hover}"/>'
        f'<path d="M0 1320 Q900 1200 1500 1340 T2560 1260 V1664 H0Z" fill="#{panel}"/>',
        f'<circle cx="1870" cy="790" r="310" fill="#{hover}"/>'
        f'<circle cx="1990" cy="690" r="290" fill="#{bg}"/>'
        f'<path d="M0 1390 Q900 1110 1600 1390 T2560 1230 V1664 H0Z" fill="#{panel}"/>',
    ][index]
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="2560" height="1664" viewBox="0 0 2560 1664"><rect width="2560" height="1664" fill="#{bg}"/>{shapes}</svg>\n'


def build():
    cards = []
    preview = []
    for i, row in enumerate(PALETTES):
        slug, name, mode, description, _, _ = row
        p = palette(row)
        folder = THEMES / slug
        (folder / 'wallpapers').mkdir(parents=True, exist_ok=True)
        (folder / 'palette').write_text(f'THEME_NAME="{name}"\nMODE="{mode}"\nOPACITY="1.0"\n' + ''.join(f'{k}="{v}"\n' for k, v in p.items()))
        svg = folder / 'wallpapers' / 'quiet.svg'
        png = svg.with_suffix('.png')
        svg.write_text(wallpaper(p, i))
        subprocess.run(['rsvg-convert', '-o', str(png), str(svg)], check=True)
        swatches = ''.join(f'<span style="background:#{p[k]}" title="{k}: #{p[k]}"></span>' for k in ('BG', 'PANEL', 'MUTED', 'TEXT', 'ACCENT'))
        cards.append(f'''<button class="choice" data-slug="{slug}" data-palette='{html.escape(__import__('json').dumps(p), quote=True)}' data-description="{description}" data-name="{name}" onclick="choose(this)"><span class="swatches">{swatches}</span><strong>{name}</strong><small>{description}</small></button>''')
        x, y = (i % 2) * 800, (i // 2) * 620
        # A deliberately labelled mockup, not a screenshot of a live desktop.
        inner = wallpaper(p, i).split('>', 1)[1].rsplit('</svg>', 1)[0]
        preview.append(f'''<g transform="translate({x} {y})"><rect width="800" height="620" fill="#{p['BG']}"/><svg x="16" y="16" width="768" height="480" viewBox="0 0 2560 1664">{inner}</svg><rect x="34" y="30" width="732" height="25" rx="4" fill="#{p['PANEL']}"/><text x="48" y="48" fill="#{p['ACCENT']}" font-size="13">OMA    1   2   3</text><text x="630" y="48" fill="#{p['TEXT']}" font-size="13">Sat  09:41</text><rect x="62" y="142" width="425" height="235" rx="8" fill="#{p['BG']}" stroke="#{p['ACCENT']}"/><text x="85" y="182" fill="#{p['MUTED']}" font-size="14">~/workspace</text><text x="85" y="218" fill="#{p['ACCENT']}" font-size="17">❯ a little room to think</text><text x="85" y="255" fill="#{p['TEXT']}" font-size="15">Clear text. Quiet surroundings.</text><text x="85" y="290" fill="#{p['C4']}" font-size="14">const balance = 'less, but enough';</text><text x="34" y="538" fill="#{p['TEXT']}" font-size="27">{name}</text><text x="34" y="573" fill="#{p['MUTED']}" font-size="16">{description}</text></g>''')
    out = ROOT / 'screenshots'
    svg = out / 'minimal-themes.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1240" font-family="DejaVu Sans, sans-serif">' + ''.join(preview) + '</svg>')
    subprocess.run(['rsvg-convert', '-o', str(out / 'minimal-themes.png'), str(svg)], check=True)
    gallery = ROOT / 'themes.html'
    gallery.write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quiet desktop themes</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#151917;color:#e0e5dc}*{box-sizing:border-box}body{margin:0 auto;padding:48px 24px;max-width:1180px}header{margin-bottom:32px}h1{font-size:clamp(32px,5vw,52px);font-weight:500;letter-spacing:-.04em;margin:8px 0}p{color:#a6b2a7;line-height:1.6}.choices{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.choice{border:1px solid #404a41;border-radius:10px;padding:18px;background:#202621;text-align:left;color:inherit;cursor:pointer}.choice[aria-pressed=true]{outline:2px solid #b1c59e;outline-offset:3px}.choice:focus-visible{outline:3px solid #e0e5dc;outline-offset:3px}.choice strong,.choice small{display:block}.choice small{color:#b3bdb3;line-height:1.5;margin-top:6px}.swatches{display:flex;margin-bottom:16px}.swatches span{width:24px;height:24px;border:1px solid #ffffff30;border-radius:50%;margin-right:5px}.desktop{--bg:#191d1b;--panel:#222824;--text:#e0e5dc;--muted:#a6b2a7;--accent:#b1c59e;--border:#48554b;position:relative;aspect-ratio:1.54;margin-top:30px;border-radius:12px;border:1px solid #404a41;overflow:hidden;background:var(--bg);color:var(--text);font:14px ui-monospace,monospace}.wallpaper{position:absolute;width:100%;height:100%;object-fit:cover}.bar{position:absolute;top:12px;left:12px;right:12px;display:flex;gap:8px;justify-content:space-between}.bar span{padding:7px 12px;background:var(--bg);border:1px solid var(--border);border-radius:5px}.accent{color:var(--accent)}.terminal{position:absolute;left:6%;top:27%;width:54%;min-height:42%;padding:24px;background:var(--bg);border:1px solid var(--accent);border-radius:9px;line-height:1.9}.muted{color:var(--muted)}.notice{position:absolute;right:3%;top:12%;padding:16px;background:var(--panel);border:1px solid var(--border);border-radius:8px;font-size:12px}.caption{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-top:20px}code{display:block;padding:14px;background:#222824;color:#c7d4be;border-radius:6px;overflow-wrap:anywhere}footer{font-size:13px;margin-top:32px;color:#a6b2a7}a{color:#b1c59e}@media(max-width:750px){.choices{grid-template-columns:repeat(2,1fr)}.desktop{font-size:10px}.terminal{padding:12px;width:75%;top:35%}.notice{font-size:9px}.caption{display:block}.bar span{padding:5px}.bar .status{display:none}}
</style><header><span>FOUR PALETTES / ONE DESKTOP</span><h1>A little room to think.</h1><p>Muted color, readable text, and original geometric wallpapers. Select a palette to explore the desktop mockup.</p></header><nav class="choices" aria-label="Theme palettes">''' + ''.join(cards) + '''</nav><div class="desktop" id="desktop"><img class="wallpaper" id="wallpaper" alt="Minimal geometric wallpaper"><div class="bar"><span class="accent">OMA &nbsp; 1 &nbsp; 2 &nbsp; 3</span><span>Sat, 05 Sep &nbsp; 09:41</span><span class="status">Wi-Fi &nbsp; 82%</span></div><div class="notice"><span class="accent">All settled</span><br><br>Your workspace is ready.</div><div class="terminal"><span class="muted">~/workspace</span><br><span class="accent">❯ a little room to think</span><br><br>Clear text. Quiet surroundings.<br><span class="muted">One palette across the desktop.</span><br><span class="accent">❯</span> ▏</div></div><div class="caption"><div><h2 id="name"></h2><p id="description"></p></div><code id="command"></code></div><footer>This is an illustrative preview; your existing bar layout and shortcuts stay in place. Switch installed themes with Super + Ctrl + Shift + Space. <a href="THEMES.md">Installation and details</a>.</footer><script>
function choose(button){const p=JSON.parse(button.dataset.palette);document.querySelectorAll('.choice').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));const desktop=document.getElementById('desktop');for(const key of ['BG','PANEL','TEXT','MUTED','ACCENT','BORDER'])desktop.style.setProperty('--'+key.toLowerCase(),'#'+p[key]);document.getElementById('wallpaper').src='dotfiles/.config/obsidian-ember/themes/'+button.dataset.slug+'/wallpapers/quiet.png';document.getElementById('name').textContent=button.dataset.name;document.getElementById('description').textContent=button.dataset.description;document.getElementById('command').textContent='obsidian-theme set '+button.dataset.slug}choose(document.querySelector('.choice'));
</script></html>''')


if __name__ == '__main__':
    build()
