"""Hyprland display transactions, independent of the settings window."""
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

CONFIG = Path.home() / '.config/hypr/obsidian-displays.conf'
NAME = re.compile(r'^[A-Za-z0-9_.-]+$')
MODE = re.compile(r'^(\d+)x(\d+)@([\d.]+)(?:Hz)?$')


def hypr(*args):
    executable = str(Path.home() / '.local/bin/obsidian-hyprctl') if args[0] == 'keyword' else '/usr/bin/hyprctl'
    result = subprocess.run([executable, *args], capture_output=True, text=True, timeout=8)
    if result.returncode or (args[0] == 'keyword' and result.stdout.strip() != 'ok'):
        raise RuntimeError((result.stderr or result.stdout or 'Display command failed').strip())
    return result.stdout


def monitors():
    return json.loads(hypr('-j', 'monitors', 'all'))


def snapshot(raw):
    active = [m for m in raw if not m.get('disabled') and m.get('width', 0) > 0]
    ids = {m['id']: m['name'] for m in active}
    result = []
    for m in active:
        mirror = m.get('mirrorOf')
        if isinstance(mirror, int):
            mirror = ids.get(mirror, '')
        if mirror in (None, 'none', '-1'):
            mirror = ''
        result.append(dict(name=m['name'], width=m['width'], height=m['height'],
                           rate=m['refreshRate'], scale=m['scale'], x=m['x'], y=m['y'],
                           transform=m.get('transform', 0), mirror=mirror or ''))
    return result


def dimensions(m):
    w, h = m['width'] / m['scale'], m['height'] / m['scale']
    return (h, w) if m['transform'] % 2 else (w, h)


def validate(wanted, raw):
    active = {m['name']: m for m in raw if not m.get('disabled') and m.get('width', 0) > 0}
    names = [m['name'] for m in wanted]
    if len(names) != len(set(names)) or set(names) != set(active) or not names:
        raise ValueError('The connected displays changed. Refresh and try again.')
    for m in wanted:
        if not NAME.fullmatch(m['name']):
            raise ValueError('Unexpected display name.')
        if not all(isinstance(m[k], (int, float)) and math.isfinite(m[k]) for k in
                   ['width', 'height', 'rate', 'scale', 'x', 'y', 'transform']):
            raise ValueError('Invalid display setting.')
        if not (0.5 <= m['scale'] <= 4 and 1 <= m['rate'] <= 1000 and
                m['transform'] in range(8) and abs(m['x']) <= 32768 and abs(m['y']) <= 32768):
            raise ValueError('Display setting is outside the supported range.')
        options = active[m['name']].get('availableModes', [])
        parsed = [MODE.fullmatch(s) for s in options]
        current = active[m['name']]
        supported = [(current['width'], current['height'], current['refreshRate'])]
        supported += [(int(p[1]), int(p[2]), float(p[3])) for p in parsed if p]
        if not any(m['width'] == w and m['height'] == h and abs(m['rate'] - r) < 0.15 for w, h, r in supported):
            raise ValueError('That resolution or refresh rate is not advertised by the display.')
        if m['mirror']:
            if m['mirror'] not in active or m['mirror'] == m['name']:
                raise ValueError('Choose another connected display to mirror.')
            if next(x for x in wanted if x['name'] == m['mirror'])['mirror']:
                raise ValueError('A mirrored screen cannot be used as the mirror source.')
    normal = [m for m in wanted if not m['mirror']]
    if not normal:
        raise ValueError('Keep at least one extended display.')
    for i, a in enumerate(normal):
        aw, ah = dimensions(a)
        for b in normal[i + 1:]:
            bw, bh = dimensions(b)
            overlap_w = min(a['x'] + aw, b['x'] + bw) - max(a['x'], b['x'])
            overlap_h = min(a['y'] + ah, b['y'] + bh) - max(a['y'], b['y'])
            if overlap_w > 2 and overlap_h > 2:
                raise ValueError('Screens overlap. Drag them apart or choose a position preset.')


def rule(m):
    text = f"{m['name']},{m['width']}x{m['height']}@{m['rate']:.5f},{int(m['x'])}x{int(m['y'])},{m['scale']:g},transform,{int(m['transform'])}"
    return text + (f",mirror,{m['mirror']}" if m['mirror'] else '')


def render(wanted, previous=''):
    names = {m['name'] for m in wanted}
    lines = ['# Managed by Displays. Changes are saved only after confirmation.',
             'monitor = , preferred, auto, 1']
    if 'eDP-1' not in names:
        lines.append('monitor = eDP-1, preferred, auto, 1.6')
    for line in previous.splitlines():
        match = re.match(r'monitor\s*=\s*([A-Za-z0-9_.-]+),', line)
        if match and match[1] not in names and match[1] != 'eDP-1':
            lines.append(line)
    for m in sorted(wanted, key=lambda x: bool(x['mirror'])):
        lines.append('monitor = ' + rule(m))
    return '\n'.join(lines) + '\n'


def atomic_write(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + '.new')
    with tmp.open('w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def apply(wanted):
    for m in sorted(wanted, key=lambda x: bool(x['mirror'])):
        hypr('keyword', 'monitor', rule(m))


def matches(wanted, raw):
    actual = {m['name']: m for m in snapshot(raw)}
    for m in wanted:
        got = actual.get(m['name'])
        if got is None:
            return False
        for key in ('width', 'height', 'transform', 'mirror'):
            if got[key] != m[key]:
                return False
        if abs(got['rate'] - m['rate']) > 0.2 or abs(got['scale'] - m['scale']) > 0.02:
            return False
        if not m['mirror'] and (abs(got['x'] - m['x']) > 2 or abs(got['y'] - m['y']) > 2):
            return False
    return True


def settle(wanted, seconds=3):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if matches(wanted, monitors()):
            return
        time.sleep(0.15)
    raise RuntimeError('The display did not accept these settings. Previous settings restored.')


def transaction(directory, config=CONFIG, duration=20):
    """The worker survives window crashes; only explicit Keep writes configuration."""
    directory, config = Path(directory), Path(config)
    status = lambda **kw: atomic_write(directory / 'status.json', json.dumps(kw))
    before, committed = [], False
    old = config.read_text()
    lock = (directory.parent / 'display-change.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        status(state='error', message='Another display change is in progress.')
        lock.close()
        return
    try:
        wanted = json.loads((directory / 'request.json').read_text())
        raw = monitors()
        before = snapshot(raw)
        validate(wanted, raw)
        status(state='applying')
        apply(wanted)
        settle(wanted)
        deadline = time.time() + duration
        status(state='confirm', deadline=deadline)
        end = time.monotonic() + duration
        while time.monotonic() < end:
            if (directory / 'revert').exists():
                break
            if (directory / 'keep').exists():
                settle(wanted)
                if config.read_text() != old:
                    raise RuntimeError('Display configuration changed elsewhere; changes were not saved.')
                atomic_write(config.with_suffix('.conf.previous'), old)
                atomic_write(config, render(wanted, old))
                committed = True
                hypr('reload')
                settle(wanted)
                status(state='kept', message='Display settings saved.')
                lock.close()
                return
            time.sleep(0.2)
        reason = 'Previous display settings restored.'
    except Exception as exc:
        reason = str(exc)
    try:
        if committed:
            atomic_write(config, old)
            hypr('reload')
        if before:
            present = {m['name'] for m in monitors()}
            restore = [copy.deepcopy(m) for m in before if m['name'] in present]
            for m in restore:
                if m['mirror'] not in present:
                    m['mirror'] = ''
            apply(restore)
            settle(restore)
        status(state='reverted', message=reason)
    except Exception as exc:
        # Persistent configuration is still the old one. Reload is a final fallback.
        try:
            hypr('reload')
        except Exception:
            pass
        status(state='error', message=f'{reason} Recovery: {exc}. Reload the saved configuration if needed.')
    finally:
        lock.close()


if __name__ == '__main__':
    transaction(sys.argv[1])
