#!/usr/bin/python3
"""Compact weather panel using the shared Obsidian desktop style."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import threading

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell, Pango
import weather

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))


def style(widget, name):
    widget.get_style_context().add_class(name)
    return widget


def column(spacing=8):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)


def label(text='', css=None):
    widget = Gtk.Label(label=text, xalign=0)
    widget.set_ellipsize(Pango.EllipsizeMode.END)
    widget.set_max_width_chars(30)
    return style(widget, css) if css else widget


class Panel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.obsidian.WeatherPanel',
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.loading = False
        self.location = weather.read_location()
        self.result = None

    def do_command_line(self, command):
        if self.window:
            self.close()
        else:
            self.activate()
        return 0

    def button(self, icon, title, callback):
        button = style(Gtk.Button(), 'icon-button')
        button.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
        button.set_tooltip_text(title)
        button.get_accessible().set_name(title)
        button.connect('clicked', callback)
        return button

    def do_activate(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title('Weather')
        self.window.set_name('weather-backdrop')
        self.window.set_app_paintable(True)
        visual = self.window.get_screen().get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        GtkLayerShell.init_for_window(self.window)
        GtkLayerShell.set_namespace(self.window, 'obsidian-weather-panel')
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        GtkLayerShell.set_exclusive_zone(self.window, -1)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.window, edge, True)
        # Weather belongs to the built-in bar, including when another monitor is focused.
        display = self.window.get_display()
        try:
            monitors = json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j'], timeout=2))
            built_in = next(m for m in monitors if m['name'] == 'eDP-1')
            for i in range(display.get_n_monitors()):
                monitor = display.get_monitor(i)
                geometry = monitor.get_geometry()
                if (geometry.x, geometry.y) == (built_in['x'], built_in['y']):
                    GtkLayerShell.set_monitor(self.window, monitor)
                    break
        except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
            pass
        self.window.connect('key-press-event', self.keypress)
        overlay = Gtk.Overlay()
        self.window.add(overlay)
        backdrop = Gtk.EventBox()
        backdrop.set_visible_window(False)
        backdrop.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        backdrop.connect('button-press-event', lambda *_: self.close() or True)
        overlay.add(backdrop)
        surface = Gtk.EventBox()
        surface.set_name('weather-panel')
        style(surface, 'obsidian-panel')
        surface.set_halign(Gtk.Align.START)
        surface.set_valign(Gtk.Align.START)
        surface.set_margin_top(44)
        surface.set_margin_start(12)
        surface.set_size_request(320, -1)
        surface.connect('button-press-event', lambda *_: True)
        overlay.add_overlay(surface)
        layout = column(8)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(layout, 'set_margin_' + side)(10)
        surface.add(layout)


        header = Gtk.Box(spacing=8)
        header.pack_start(label('Weather', 'title'), True, True, 0)
        self.refresh_button = self.button('view-refresh-symbolic', 'Refresh weather', lambda *_: self.refresh(True))
        header.pack_end(self.button('window-close-symbolic', 'Close · Escape', lambda *_: self.close()), False, False, 0)
        header.pack_end(self.refresh_button, False, False, 0)
        layout.pack_start(header, False, False, 0)

        self.city = label('Local weather', 'city')
        self.city.set_tooltip_text('Automatic location uses your network address.')
        layout.pack_start(self.city, False, False, 0)
        self.summary = Gtk.Box(spacing=14)
        self.condition_icon = style(Gtk.Image(), 'weather-icon')
        self.condition_icon.set_pixel_size(36)
        self.summary.pack_start(self.condition_icon, False, False, 0)
        self.temperature = label('—', 'temperature')
        self.summary.pack_start(self.temperature, False, False, 0)
        detail = column(3)
        detail.set_valign(Gtk.Align.CENTER)
        self.condition = label('Loading…')
        self.feels = label('', 'muted')
        detail.pack_start(self.condition, False, False, 0)
        detail.pack_start(self.feels, False, False, 0)
        self.summary.pack_start(detail, True, True, 0)
        layout.pack_start(self.summary, False, False, 0)
        self.metrics = label('', 'muted')
        layout.pack_start(self.metrics, False, False, 0)
        layout.pack_start(Gtk.Separator(), False, False, 0)
        self.forecast = column(0)
        layout.pack_start(self.forecast, False, False, 0)

        footer = Gtk.Box(spacing=8)
        self.status = label('Updating…', 'muted')
        footer.pack_start(self.status, True, True, 0)
        self.location_button = self.button('mark-location-symbolic', 'Change location', self.toggle_location)
        footer.pack_end(self.location_button, False, False, 0)
        layout.pack_start(footer, False, False, 0)
        self.editor = Gtk.Revealer()
        self.editor.set_transition_type(Gtk.RevealerTransitionType.NONE)
        editor_box = column(6)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text('City, country · blank for automatic')
        self.entry.set_max_length(120)
        self.entry.set_text(self.location)
        self.entry.get_accessible().set_name('Weather location')
        self.entry.connect('activate', self.apply_location)
        editor_box.pack_start(self.entry, False, False, 0)
        self.apply_button = style(Gtk.Button(label='Apply location'), 'primary')
        self.apply_button.connect('clicked', self.apply_location)
        editor_box.pack_start(self.apply_button, False, False, 0)
        self.editor.add(editor_box)
        layout.pack_start(self.editor, False, False, 0)
        self.load_style()
        self.window.show_all()
        self.window.set_focus(None)
        self.result = weather.cached(self.location)
        if self.result:
            self.render(self.result)
        self.refresh()

    def toggle_location(self, *_):
        show = not self.editor.get_reveal_child()
        self.editor.set_reveal_child(show)
        if show:
            self.entry.grab_focus()

    def apply_location(self, *_):
        if self.loading:
            return
        location = self.entry.get_text().strip()
        try:
            weather.save_location(location)
        except OSError:
            self.status.set_text('Could not save location')
            return
        self.location = location
        self.result = weather.cached(location)
        self.render(self.result)
        self.editor.set_reveal_child(False)
        self.refresh(True)

    def refresh(self, force=False):
        if self.loading or not self.window:
            return
        self.loading = True
        self.refresh_button.set_sensitive(False)
        self.apply_button.set_sensitive(False)
        self.status.set_text('Updating…')
        location = self.location
        def work():
            result = weather.fetch(location, force)
            GLib.idle_add(self.refreshed, result)
        threading.Thread(target=work, daemon=True).start()

    def refreshed(self, result):
        if not self.window:
            return False
        self.loading = False
        self.refresh_button.set_sensitive(True)
        self.apply_button.set_sensitive(True)
        self.result = result
        self.render(result)
        # Signal only the weather module; do not reload the desktop bar.
        subprocess.run(['pkill', '-RTMIN+9', '-x', 'waybar'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return False

    def render(self, result):
        for child in self.forecast.get_children():
            child.destroy()
        if result is None:
            self.city.set_text(self.location or 'Automatic location')
            self.temperature.set_text('—')
            self.condition.set_text('Unavailable')
            self.condition_icon.set_from_icon_name('weather-overcast-symbolic', Gtk.IconSize.DIALOG)
            self.feels.set_text('Try refresh')
            self.metrics.set_text('Check your connection or choose a city.')
            self.status.set_text('Could not update')
            return
        data = result['data']
        self.city.set_text(data['city'])
        self.city.set_tooltip_text(', '.join(filter(None, [data['city'], data['country']])) +
                                   ('\nAutomatic · based on your network address' if not self.location else ''))
        self.temperature.set_text(f"{data['temperature']}°")
        self.condition.set_text(data['description'])
        self.condition.set_tooltip_text(data['description'])
        self.feels.set_text('Feels ' + weather.display_number(data['feels'], '°'))
        self.condition_icon.set_from_icon_name(weather.icon(data['description']), Gtk.IconSize.DIALOG)
        self.metrics.set_text(f"Wind {weather.display_number(data['wind'], ' km/h')}  ·  Humidity {weather.display_number(data['humidity'], '%')}")
        self.metrics.set_tooltip_text(f"Wind direction: {data['direction'] or '—'}")
        fetched_date = datetime.now().date()
        for day in data['days']:
            row = style(Gtk.Box(spacing=10), 'forecast-row')
            date = datetime.fromisoformat(day['date']).date()
            title = 'Today' if date == fetched_date else date.strftime('%a %d')
            name = label(title)
            name.set_width_chars(7)
            row.pack_start(name, False, False, 0)
            picture = Gtk.Image.new_from_icon_name(weather.icon(day['description']), Gtk.IconSize.BUTTON)
            picture.set_tooltip_text('Midday · ' + (day['description'] or 'Forecast unavailable'))
            row.pack_start(picture, False, False, 0)
            rain = label(weather.display_number(day['rain'], '%'), 'muted')
            rain.set_tooltip_text('Highest forecast rain chance during the day')
            row.pack_start(rain, True, True, 0)
            temperatures = label(f"{weather.display_number(day['low'], '°')} / {weather.display_number(day['high'], '°')}")
            temperatures.set_tooltip_text('Daily low / high · Celsius')
            row.pack_end(temperatures, False, False, 0)
            self.forecast.pack_start(row, False, False, 0)
        if not data['days']:
            self.forecast.pack_start(label('Forecast unavailable', 'muted'), False, False, 0)
        self.forecast.show_all()
        stamp = datetime.fromtimestamp(result['fetched']).strftime('%H:%M')
        self.status.set_text(('Offline · saved ' if result['stale'] else 'Updated ') + stamp)
        self.status.set_tooltip_text('wttr.in · Celsius\nRetrieved ' + datetime.fromtimestamp(result['fetched']).strftime('%d %b %H:%M') +
                                     (f"\nObservation {data['observed']} UTC" if data['observed'] else ''))

    def keypress(self, window, event):
        if event.keyval == Gdk.KEY_Escape:
            if self.editor.get_reveal_child():
                self.editor.set_reveal_child(False)
            else:
                self.close()
            return True
        return False

    def close(self):
        if self.window:
            self.window.destroy()
            self.window = None
        self.quit()

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

if __name__ == '__main__':
    raise SystemExit(Panel().run())
