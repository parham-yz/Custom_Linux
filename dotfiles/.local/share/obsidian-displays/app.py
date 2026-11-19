#!/usr/bin/python3
"""Compact native display settings for the Obsidian Hyprland desktop."""
import copy
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, Gio, GLib, Pango
import backend

HERE = Path(__file__).resolve().parent


def box(vertical=True, spacing=8):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing)


def styled(widget, name):
    widget.get_style_context().add_class(name)
    return widget


def label(text, css=None):
    w = Gtk.Label(label=text, xalign=0)
    w.set_ellipsize(Pango.EllipsizeMode.END)
    return styled(w, css) if css else w


def title(m):
    return 'Built-in display' if m['name'].startswith('eDP') else (m.get('model') or m.get('description') or m['name'])


class Displays(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.obsidian.Displays', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.job = None
        self.dirty = False
        self.dragging = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title='Displays')
        self.window.set_default_size(800, 680)
        self.window.set_name('displays')
        self.window.connect('delete-event', self.closing)
        self.window.connect('key-press-event', self.keypress)
        header = Gtk.HeaderBar(title='Displays', show_close_button=True)
        header.set_subtitle('Arrange your screens and make them comfortable')
        self.window.set_titlebar(header)
        refresh = Gtk.Button.new_from_icon_name('view-refresh-symbolic', Gtk.IconSize.BUTTON)
        refresh.set_tooltip_text('Detect displays and discard unapplied changes')
        refresh.get_accessible().set_name('Detect displays')
        refresh.connect('clicked', lambda *_: self.refresh())
        header.pack_end(refresh)
        self.refresh_button = refresh
        content = box(spacing=12)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(content, 'set_margin_' + side)(20)
        self.window.add(content)
        self.summary = label('Reading displays…', 'muted')
        content.pack_start(self.summary, False, False, 0)
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_size_request(600, 190)
        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        self.canvas.connect('draw', self.draw)
        self.canvas.connect('button-press-event', self.press)
        self.canvas.connect('motion-notify-event', self.motion)
        self.canvas.connect('button-release-event', self.release)
        self.canvas.get_accessible().set_name('Display arrangement. Drag a screen or use the Position menu below.')
        content.pack_start(self.canvas, False, False, 0)
        self.selectors = box(False, 8)
        self.selectors.set_halign(Gtk.Align.CENTER)
        content.pack_start(self.selectors, False, False, 0)
        tip = label('Drag screens to match your desk. Select a display to adjust it.', 'muted')
        tip.set_halign(Gtk.Align.CENTER)
        content.pack_start(tip, False, False, 0)
        self.settings = styled(box(spacing=10), 'settings-card')
        content.pack_start(self.settings, True, True, 0)
        self.feedback = label('', 'muted')
        self.feedback.set_line_wrap(True)
        self.feedback.set_ellipsize(Pango.EllipsizeMode.NONE)
        content.pack_start(self.feedback, False, False, 0)
        self.footer = box(False, 8)
        self.cancel = Gtk.Button(label='Discard changes')
        self.cancel.connect('clicked', lambda *_: self.refresh())
        self.apply_button = styled(Gtk.Button(label='Apply changes'), 'primary')
        self.apply_button.connect('clicked', self.start_trial)
        self.footer.pack_end(self.apply_button, False, False, 0)
        self.footer.pack_end(self.cancel, False, False, 0)
        content.pack_start(self.footer, False, False, 0)
        self.confirm = box(False, 8)
        self.countdown = label('')
        self.confirm.pack_start(self.countdown, True, True, 0)
        self.revert = Gtk.Button(label='Revert')
        self.revert.connect('clicked', lambda *_: self.decision('revert'))
        self.keep = styled(Gtk.Button(label='Keep changes'), 'primary')
        self.keep.connect('clicked', lambda *_: self.decision('keep'))
        self.confirm.pack_end(self.keep, False, False, 0)
        self.confirm.pack_end(self.revert, False, False, 0)
        content.pack_start(self.confirm, False, False, 0)
        self.load_style()
        self.raw, self.draft, self.selected = [], [], ''
        self.refresh()
        self.window.show_all()
        self.confirm.hide()
        GLib.timeout_add(250, self.poll_job)
        GLib.timeout_add_seconds(4, self.detect)

    def load_style(self):
        self.colors = dict(bg='#191d1b', panel='#222824', selected='#303a33', border='#48554b',
                           fg='#e0e5dc', muted='#a6b2a7', accent='#b1c59e')
        try:
            text = (Path.home() / '.config/obsidian-ember/current/rofi.rasi').read_text()
            self.colors.update({k: v[:7] for k, v in re.findall(r'(\w+):\s*(#[0-9a-fA-F]{6,8})\s*;', text)})
        except OSError:
            pass
        css = (HERE / 'style.css').read_text()
        for k, v in self.colors.items():
            css = css.replace('{{' + k + '}}', v)
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def refresh(self, message=''):
        if self.job:
            return
        try:
            self.raw = backend.monitors()
            self.draft = backend.snapshot(self.raw)
            if self.selected not in {m['name'] for m in self.draft}:
                self.selected = self.draft[-1]['name'] if self.draft else ''
            self.baseline = copy.deepcopy(self.draft)
            self.dirty = False
            self.feedback.set_text(message)
            self.rebuild()
        except Exception as exc:
            self.feedback.set_text(str(exc))
            self.apply_button.set_sensitive(False)

    def rebuild(self):
        for child in self.selectors.get_children():
            self.selectors.remove(child)
        for m in self.draft:
            raw = next(r for r in self.raw if r['name'] == m['name'])
            button = Gtk.ToggleButton(label=title(raw))
            button.set_active(m['name'] == self.selected)
            button.connect('clicked', lambda _, name=m['name']: self.select(name))
            self.selectors.pack_start(button, False, False, 0)
        self.selectors.show_all()
        count = len(self.draft)
        self.summary.set_text(f'{count} display' + ('s' if count != 1 else '') + ' connected')
        self.build_settings()
        self.canvas.queue_draw()
        self.changed(False)

    def select(self, name):
        if self.job or self.selected == name:
            return
        self.selected = name
        self.rebuild()

    def row(self, heading, control):
        row = box(False, 20)
        row.pack_start(label(heading), True, True, 0)
        control.set_size_request(270, -1)
        control.get_accessible().set_name(heading)
        row.pack_end(control, False, False, 0)
        self.settings.pack_start(row, False, False, 0)
        return control

    def combo(self, heading, entries, active, callback):
        combo = Gtk.ComboBoxText()
        for key, text in entries:
            combo.append(str(key), text)
        combo.set_active_id(str(active))
        combo.connect('changed', lambda c: callback(c.get_active_id()) if c.get_active_id() is not None else None)
        return self.row(heading, combo)

    def build_settings(self):
        for child in self.settings.get_children():
            self.settings.remove(child)
        if not self.draft:
            self.settings.pack_start(label('No active display detected.'), False, False, 0)
            return
        m = next(m for m in self.draft if m['name'] == self.selected)
        raw = next(r for r in self.raw if r['name'] == self.selected)
        self.settings.pack_start(label(title(raw), 'screen-title'), False, False, 0)
        self.modes = {(int(p[1]), int(p[2]), float(p[3])) for mode in raw.get('availableModes', []) if (p := backend.MODE.fullmatch(mode))}
        self.modes.add((m['width'], m['height'], m['rate']))
        resolutions = sorted({(w, h) for w, h, r in self.modes}, reverse=True)
        self.combo('Resolution', [(f'{w}x{h}', f'{w} × {h}') for w, h in resolutions],
                   f"{m['width']}x{m['height']}", self.set_resolution)
        rates = sorted({round(r, 2) for w, h, r in self.modes if (w, h) == (m['width'], m['height'])}, reverse=True)
        self.combo('Refresh rate', [(r, f'{r:g} Hz') for r in rates], round(m['rate'], 2),
                   lambda v: self.update('rate', float(v)))
        scales = sorted({1, 1.25, 1.5, 1.6, 1.75, 2, 2.5, 3, m['scale']})
        self.combo('Text size', [(s, f'{s * 100:g}%' + (' · More space' if s == 1 else '')) for s in scales],
                   m['scale'], lambda v: self.update('scale', float(v), resize=True))
        others = [o for o in self.draft if o['name'] != self.selected and not o['mirror']]
        uses = [('', 'Extended display')] + [(o['name'], 'Mirror ' + title(next(r for r in self.raw if r['name'] == o['name']))) for o in others]
        self.combo('Use as', uses, m['mirror'], lambda v: self.update('mirror', v, rebuild=True))
        self.combo('Rotation', [(0, 'Standard'), (1, '90°'), (2, '180°'), (3, '270°')], m['transform'],
                   lambda v: self.update('transform', int(v), resize=True))
        if others and not m['mirror']:
            self.position_target = others[0]
            other_title = title(next(r for r in self.raw if r['name'] == others[0]['name']))
            self.combo('Position', [('current', 'Custom · drag above')] + [(p, p.title() + ' of ' + other_title) for p in ['left', 'right', 'above', 'below']], 'current', self.position)
        if self.selected.startswith('eDP'):
            try:
                current = int(subprocess.check_output(['brightnessctl', 'get'], text=True, timeout=2))
                maximum = int(subprocess.check_output(['brightnessctl', 'max'], text=True, timeout=2))
                slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 5, 100, 1)
                slider.set_value(current / maximum * 100)
                slider.set_digits(0)
                slider.connect('value-changed', self.brightness)
                self.row('Brightness', slider)
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        else:
            self.row('Brightness', label('Use the monitor’s buttons', 'muted'))
        self.settings.show_all()

    def brightness(self, slider):
        if getattr(self, 'brightness_timer', None):
            GLib.source_remove(self.brightness_timer)
        value = round(slider.get_value())
        def apply_brightness():
            self.brightness_timer = None
            helper = Path.home() / '.local/bin/obsidian-auto-brightness'
            if helper.exists():
                subprocess.run([str(helper), 'pause', '120'], timeout=3, check=False)
            subprocess.Popen(['brightnessctl', 'set', f'{value}%'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return False
        self.brightness_timer = GLib.timeout_add(120, apply_brightness)

    def update(self, key, value, resize=False, rebuild=False):
        m = next(m for m in self.draft if m['name'] == self.selected)
        old_w, old_h = backend.dimensions(m)
        m[key] = value
        if resize:
            new_w, new_h = backend.dimensions(m)
            for other in self.draft:
                if other is m or other['mirror']:
                    continue
                if abs(other['x'] - (m['x'] + old_w)) <= 2:
                    other['x'] = round(m['x'] + new_w)
                if abs(other['y'] - (m['y'] + old_h)) <= 2:
                    other['y'] = round(m['y'] + new_h)
        self.changed()
        if rebuild:
            self.build_settings()

    def set_resolution(self, value):
        w, h = map(int, value.split('x'))
        m = next(m for m in self.draft if m['name'] == self.selected)
        rates = [r for mw, mh, r in self.modes if (mw, mh) == (w, h)]
        self.update('width', w, resize=True)
        self.update('height', h, resize=True)
        self.update('rate', min(rates, key=lambda r: abs(r - m['rate'])))
        self.build_settings()

    def position(self, value):
        if value == 'current':
            return
        m = next(m for m in self.draft if m['name'] == self.selected)
        t = self.position_target
        w, h = backend.dimensions(m)
        tw, th = backend.dimensions(t)
        m['x'], m['y'] = round(t['x']), round(t['y'])
        if value == 'left': m['x'] -= round(w)
        if value == 'right': m['x'] += round(tw)
        if value == 'above': m['y'] -= round(h)
        if value == 'below': m['y'] += round(th)
        self.changed()

    def changed(self, clear=True):
        self.dirty = self.draft != self.baseline
        self.apply_button.set_sensitive(self.dirty and not self.job)
        self.cancel.set_sensitive(self.dirty and not self.job)
        if clear:
            self.feedback.set_text('Changes are not applied yet.' if self.dirty else '')
        self.canvas.queue_draw()

    def rgb(self, key):
        color = self.colors[key].lstrip('#')
        return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def draw(self, area, cr):
        self.rects = {}
        if not self.draft:
            return
        positions = copy.deepcopy(self.draft)
        for m in positions:
            if m['mirror']:
                source = next(o for o in positions if o['name'] == m['mirror'])
                m['x'], m['y'] = source['x'] + 180, source['y'] + 100
        x0 = min(m['x'] for m in positions)
        y0 = min(m['y'] for m in positions)
        x1 = max(m['x'] + backend.dimensions(m)[0] for m in positions)
        y1 = max(m['y'] + backend.dimensions(m)[1] for m in positions)
        factor = min((area.get_allocated_width() - 50) / max(x1 - x0, 1), (area.get_allocated_height() - 35) / max(y1 - y0, 1))
        ox = (area.get_allocated_width() - (x1 - x0) * factor) / 2
        oy = (area.get_allocated_height() - (y1 - y0) * factor) / 2
        self.factor = factor
        for i, m in enumerate(positions):
            w, h = backend.dimensions(m)
            x, y, w, h = ox + (m['x'] - x0) * factor, oy + (m['y'] - y0) * factor, w * factor, h * factor
            self.rects[m['name']] = (x, y, w, h)
            cr.set_source_rgb(*self.rgb('selected' if m['name'] == self.selected else 'panel'))
            cr.rectangle(x, y, w, h)
            cr.fill_preserve()
            cr.set_source_rgb(*self.rgb('accent' if m['name'] == self.selected else 'border'))
            cr.set_line_width(3 if m['name'] == self.selected else 1)
            cr.stroke()
            if m['name'].startswith('eDP'):
                cr.rectangle(x + w / 2 - 13, y, 26, 5)
                cr.fill()
            cr.select_font_face('sans-serif', 0, 0)
            cr.set_font_size(22)
            text = str(i + 1)
            ext = cr.text_extents(text)
            cr.move_to(x + (w - ext.width) / 2, y + h / 2)
            cr.show_text(text)
            cr.set_font_size(11)
            text = 'Built-in' if m['name'].startswith('eDP') else m['name']
            ext = cr.text_extents(text)
            cr.move_to(x + (w - ext.width) / 2, y + h / 2 + 21)
            cr.show_text(text)

    def press(self, widget, event):
        if self.job or event.button != 1:
            return
        for name, (x, y, w, h) in reversed(list(self.rects.items())):
            if x <= event.x <= x + w and y <= event.y <= y + h:
                self.select(name)
                m = next(m for m in self.draft if m['name'] == name)
                if not m['mirror']:
                    self.dragging = (m, event.x, event.y, m['x'], m['y'], self.factor)
                break

    def motion(self, widget, event):
        if self.dragging:
            m, ex, ey, x, y, factor = self.dragging
            m['x'], m['y'] = round(x + (event.x - ex) / factor), round(y + (event.y - ey) / factor)
            self.changed()

    def release(self, widget, event):
        if self.dragging:
            m = self.dragging[0]
            w, h = backend.dimensions(m)
            for o in self.draft:
                if o is m or o['mirror']:
                    continue
                ow, oh = backend.dimensions(o)
                xs = [o['x'], o['x'] + ow, o['x'] - w]
                ys = [o['y'], o['y'] + oh, o['y'] - h]
                nx, ny = min(xs, key=lambda v: abs(v - m['x'])), min(ys, key=lambda v: abs(v - m['y']))
                if abs(nx - m['x']) * self.factor < 18: m['x'] = round(nx)
                if abs(ny - m['y']) * self.factor < 18: m['y'] = round(ny)
            self.dragging = None
            self.changed()

    def start_trial(self, *_):
        try:
            backend.validate(self.draft, backend.monitors())
            runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / f'obsidian-displays-{os.getuid()}'
            runtime.mkdir(mode=0o700, exist_ok=True)
            self.job = Path(tempfile.mkdtemp(prefix='trial-', dir=runtime))
            (self.job / 'request.json').write_text(json.dumps(self.draft))
            self.worker = subprocess.Popen(['/usr/bin/python3', str(HERE / 'backend.py'), str(self.job)], start_new_session=True)
            self.settings.set_sensitive(False)
            self.selectors.set_sensitive(False)
            self.refresh_button.set_sensitive(False)
            self.footer.hide()
            self.confirm.show_all()
            self.keep.set_sensitive(False)
            self.revert.set_sensitive(True)
            self.feedback.set_text('Applying display settings…')
        except Exception as exc:
            self.feedback.set_text(str(exc))

    def decision(self, action):
        if self.job:
            (self.job / action).touch()
            self.keep.set_sensitive(False)
            self.revert.set_sensitive(False)
            self.countdown.set_text('Saving…' if action == 'keep' else 'Restoring…')

    def poll_job(self):
        if not self.job:
            return True
        try:
            status = json.loads((self.job / 'status.json').read_text())
        except (OSError, ValueError):
            status = {'state': 'applying'}
        state = status['state']
        if state == 'confirm':
            seconds = max(0, math.ceil(status['deadline'] - time.time()))
            if not (self.job / 'keep').exists() and not (self.job / 'revert').exists():
                self.keep.set_sensitive(True)
                self.countdown.set_text(f'Keep these settings? Reverting in {seconds}s')
        if state in ('kept', 'reverted', 'error') or self.worker.poll() is not None:
            message = status.get('message', 'Display change ended. Saved settings remain available.')
            self.job = None
            self.confirm.hide()
            self.footer.show_all()
            self.settings.set_sensitive(True)
            self.selectors.set_sensitive(True)
            self.refresh_button.set_sensitive(True)
            self.refresh(message)
        return True

    def detect(self):
        if self.job:
            return True
        try:
            names = {m['name'] for m in backend.snapshot(backend.monitors())}
            if names != {m['name'] for m in self.draft}:
                self.refresh('Connected displays changed; the list has been refreshed.')
        except Exception:
            pass
        return True

    def keypress(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            if self.job:
                self.decision('revert')
            else:
                self.window.close()
            return True
        return False

    def closing(self, *_):
        if self.job:
            self.decision('revert')
        self.quit()
        return False


if __name__ == '__main__':
    GLib.set_prgname('obsidian-displays')
    GLib.set_application_name('Displays')
    Displays().run()
