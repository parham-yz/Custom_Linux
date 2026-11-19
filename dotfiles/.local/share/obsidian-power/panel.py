#!/usr/bin/python3
"""Theme-matched, transient power controls for the Obsidian desktop."""
import os
from pathlib import Path
import re
import shlex
import subprocess
import threading

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell, Pango

BACKEND = Path.home() / '.local/bin/obsidian-power'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
BATTERY = Path('/sys/class/power_supply/macsmc-battery')
MODES = (
    ('power-saver', 'low', 'Low power', 'Longer battery life · limited CPU speed', 'power-profile-power-saver-symbolic'),
    ('balanced', 'balanced', 'Balanced', 'Speed when you need it', 'power-profile-balanced-symbolic'),
    ('performance', 'high', 'High performance', 'Maximum speed · more energy', 'power-profile-performance-symbolic'),
)


def style(widget, name):
    widget.get_style_context().add_class(name)
    return widget


def column(spacing=8):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)


def label(text='', css=None):
    widget = Gtk.Label(label=text, xalign=0)
    widget.set_ellipsize(Pango.EllipsizeMode.END)
    return style(widget, css) if css else widget


def number(path):
    try:
        return float(path.read_text().strip())
    except (OSError, ValueError):
        return None


def battery_snapshot(root=BATTERY):
    try:
        status = (root / 'status').read_text().strip()
    except OSError:
        status = 'Unavailable'
    full, design = number(root / 'energy_full'), number(root / 'energy_full_design')
    watts = number(root / 'power_now')
    return {
        'percent': number(root / 'capacity'), 'status': status,
        'health': 100 * full / design if full is not None and design else None,
        'watts': abs(watts) / 1e6 if watts is not None else None,
        'on_ac': number(root.parent / 'macsmc-ac/online') == 1,
    }


def read_profile():
    result = subprocess.run(['busctl', '--system', 'get-property',
        'net.hadess.PowerProfiles', '/net/hadess/PowerProfiles',
        'net.hadess.PowerProfiles', 'ActiveProfile'],
        check=True, capture_output=True, text=True, timeout=4)
    fields = shlex.split(result.stdout)
    if len(fields) != 2 or fields[1] not in {mode[0] for mode in MODES}:
        raise ValueError('Unknown power profile')
    return fields[1]


def read_state():
    state = battery_snapshot()
    state['profile'] = read_profile()
    state['limits'] = [number(Path(f'/sys/devices/system/cpu/cpufreq/policy{i}/scaling_max_freq'))
                       for i in (0, 4)]
    return state


class Panel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.obsidian.PowerPanel',
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.busy = False
        self.loading = False
        self.generation = 0
        self.active = None
        self.buttons = {}
        self.timer = None

    def do_command_line(self, command):
        if self.window:
            if self.window.get_visible():
                self.close()
            else:
                self.window.show()
        else:
            self.activate()
        return 0

    def do_activate(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title('Power & battery')
        self.window.set_name('power-backdrop')
        self.window.set_app_paintable(True)
        visual = self.window.get_screen().get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        GtkLayerShell.init_for_window(self.window)
        GtkLayerShell.set_namespace(self.window, 'obsidian-power-panel')
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        GtkLayerShell.set_exclusive_zone(self.window, -1)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.window, edge, True)
        self.window.connect('key-press-event', self.keypress)
        overlay = Gtk.Overlay()
        self.window.add(overlay)
        backdrop = Gtk.EventBox()
        backdrop.set_visible_window(False)
        backdrop.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        backdrop.connect('button-press-event', lambda *_: self.close() or True)
        overlay.add(backdrop)
        surface = Gtk.EventBox()
        surface.set_name('power-panel')
        style(surface, 'obsidian-panel')
        surface.set_halign(Gtk.Align.END)
        surface.set_valign(Gtk.Align.START)
        surface.set_margin_top(44)
        surface.set_margin_end(12)
        surface.set_size_request(280, -1)
        surface.connect('button-press-event', lambda *_: True)
        overlay.add_overlay(surface)
        layout = column(8)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(layout, 'set_margin_' + side)(10)
        surface.add(layout)

        header = Gtk.Box(spacing=12)
        icon = Gtk.Image.new_from_icon_name('battery-good-symbolic', Gtk.IconSize.LARGE_TOOLBAR)
        heading = column(3)
        heading.pack_start(label('Power', 'title'), False, False, 0)
        self.source = label('Reading battery…', 'muted')
        header.pack_start(heading, True, True, 0)
        close = style(Gtk.Button(), 'icon-button')
        close.set_image(Gtk.Image.new_from_icon_name('window-close-symbolic', Gtk.IconSize.BUTTON))
        close.set_tooltip_text('Close · Escape')
        close.get_accessible().set_name('Close power panel')
        close.connect('clicked', lambda *_: self.close())
        header.pack_end(close, False, False, 0)
        layout.pack_start(header, False, False, 0)

        battery = style(column(8), 'battery-card')
        self.battery_card = battery
        summary = Gtk.Box(spacing=12)
        self.percent = label('—', 'percentage')
        summary.pack_start(self.percent, False, False, 0)
        battery_state = column(3)
        battery_state.set_valign(Gtk.Align.CENTER)
        self.charge = label('Checking battery', 'strong')
        self.draw = label('', 'muted')
        battery_state.pack_start(self.charge, False, False, 0)
        summary.pack_end(battery_state, False, False, 0)
        battery.pack_start(summary, False, False, 0)
        self.level = Gtk.ProgressBar()
        self.level.get_accessible().set_name('Battery charge')
        battery.pack_start(self.level, False, False, 0)
        layout.pack_start(battery, False, False, 0)

        modes = column(0)
        group = style(column(0), 'mode-group')
        for profile, command, title, description, icon_name in MODES:
            item = style(Gtk.Button(), 'mode-row')
            item.get_accessible().set_name(title)
            item.set_tooltip_text(description)
            row = Gtk.Box(spacing=12)
            image = style(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON), 'mode-icon')
            row.pack_start(image, False, False, 0)
            text = column(4)
            text.pack_start(label(title, 'strong'), False, False, 0)
            row.pack_start(text, True, True, 0)
            check = Gtk.Image.new_from_icon_name('object-select-symbolic', Gtk.IconSize.BUTTON)
            check.set_opacity(0)
            row.pack_end(check, False, False, 0)
            item.add(row)
            item.connect('clicked', lambda _, c=command: self.select(c))
            group.pack_start(item, False, False, 0)
            self.buttons[profile] = (item, check)
        modes.pack_start(group, False, False, 0)
        layout.pack_start(Gtk.Separator(), False, False, 0)
        layout.pack_start(modes, False, False, 0)

        self.feedback = label('', 'feedback')
        self.feedback.set_line_wrap(True)
        self.feedback.set_ellipsize(Pango.EllipsizeMode.NONE)
        self.feedback.set_max_width_chars(44)
        self.feedback.set_no_show_all(True)
        layout.pack_start(self.feedback, False, False, 0)
        self.recommend = style(Gtk.Button(label='Automatic'), 'quiet')
        self.recommend.set_tooltip_text('Low power on battery; Balanced when plugged in.\nManual choices last until the power source changes.')
        self.recommend.connect('clicked', lambda *_: self.select('auto'))
        layout.pack_start(self.recommend, False, False, 0)
        self.load_style()
        self.window.show_all()
        self.window.set_focus(None)
        self.refresh()
        self.timer = GLib.timeout_add_seconds(5, self.refresh)

    def load_style(self):
        colors = {'bg': '#191d1b', 'panel': '#222824', 'selected': '#303a33',
                  'border': '#48554b', 'fg': '#e0e5dc', 'muted': '#a6b2a7', 'accent': '#b1c59e'}
        try:
            data = (CONFIG / 'obsidian-ember/current/rofi.rasi').read_text()
            colors.update({key: color[:7] for key, color in
                           re.findall(r'(\w+):\s*(#[0-9a-fA-F]{6,8})\s*;', data)})
        except OSError:
            pass
        css = (CONFIG / 'obsidian-ember/panel.css').read_text() + '\n'
        css += (Path(__file__).parent / 'panel.css').read_text()
        for key, value in colors.items():
            css = css.replace('{{' + key + '}}', value)
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_sensitive(self, sensitive):
        for item, _ in self.buttons.values():
            item.set_sensitive(sensitive)
        self.recommend.set_sensitive(sensitive)

    def refresh(self):
        if self.loading or self.busy or not self.window:
            return True
        self.loading = True
        generation = self.generation
        def work():
            try:
                state = read_state()
            except (OSError, ValueError, subprocess.SubprocessError):
                state = None
            GLib.idle_add(self.refreshed, generation, state)
        threading.Thread(target=work, daemon=True).start()
        return True

    def refreshed(self, generation, state):
        self.loading = False
        if not self.window or generation != self.generation:
            return False
        if state is None:
            self.message('Power controls are unavailable. Try opening this panel again.')
            self.set_sensitive(False)
        else:
            self.render(state)
            self.set_sensitive(True)
        return False

    def render(self, state):
        self.active = state['profile']
        self.source.set_text('Connected to power' if state['on_ac'] else 'Running on battery')
        percent = state['percent']
        self.percent.set_text(f'{percent:.0f}%' if percent is not None else '—')
        self.level.set_fraction(max(0, min(1, percent / 100)) if percent is not None else 0)
        status = state['status']
        self.charge.set_text({'Full': 'Charged', 'Discharging': 'On battery',
                              'Not charging': 'Not charging'}.get(status, status))
        watts = state['watts']
        self.draw.set_text(f'{watts:.1f} W battery draw' if status == 'Discharging' and watts is not None
                           else f'{watts:.1f} W charging' if status == 'Charging' and watts is not None
                           else 'Ready to unplug' if status == 'Full' else '')
        for profile, (item, check) in self.buttons.items():
            selected = profile == self.active
            context = item.get_style_context()
            (context.add_class if selected else context.remove_class)('selected')
            check.set_opacity(1 if selected else 0)
            item.get_accessible().set_description('Active mode' if selected else 'Select this mode')
        health = state['health']
        efficiency, performance = state['limits']
        details = [self.source.get_text()]
        if self.draw.get_text():
            details.append(self.draw.get_text())
        if health is not None:
            details.append(f'Battery health: {health:.0f}%')
        if efficiency is not None and performance is not None:
            details.append(f'CPU limits: {efficiency/1e6:.2f} / {performance/1e6:.2f} GHz')
        self.battery_card.set_tooltip_text('\n'.join(details))

    def message(self, text):
        self.feedback.set_text(text)
        self.feedback.show()

    def select(self, command):
        if self.busy:
            return
        self.busy = True
        self.generation += 1
        self.set_sensitive(False)
        self.message('Applying power mode…')
        def work():
            state = None
            try:
                subprocess.run([str(BACKEND), command], check=True, capture_output=True, text=True, timeout=20)
                state = read_state()
                expected = {'low': 'power-saver', 'balanced': 'balanced', 'high': 'performance'}
                target = expected.get(command, 'balanced' if state['on_ac'] else 'power-saver')
                if state['profile'] != target:
                    state = None
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
            GLib.idle_add(self.finished, state)
        threading.Thread(target=work, daemon=True).start()

    def finished(self, state):
        self.busy = False
        if not self.window:
            return False
        self.set_sensitive(True)
        if state is None:
            self.message('Could not change the mode. Try again.')
        else:
            self.render(state)
            self.feedback.hide()
        if not self.window.get_visible():
            self.close()
        return False

    def keypress(self, window, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def close(self):
        if not self.window:
            return
        if self.busy:
            self.window.hide()
            return
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        self.window.destroy()
        self.window = None
        self.quit()


if __name__ == '__main__':
    raise SystemExit(Panel().run())
