#!/usr/bin/python3
"""Transient Bluetooth controls backed by BlueZ state and the desktop CLI."""
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

BACKEND = Path.home() / '.local/bin/obsidian-bluetooth'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))


def style(widget, name):
    widget.get_style_context().add_class(name)
    return widget


def column(spacing=8):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)


def label(text, css=None):
    item = Gtk.Label(label=text, xalign=0)
    item.set_ellipsize(Pango.EllipsizeMode.END)
    if css:
        style(item, css)
    return item


def button(text, callback, css=None):
    item = Gtk.Button(label=text)
    item.connect('clicked', lambda *_: callback())
    if css:
        style(item, css)
    return item


def icon_button(icon, tooltip, callback):
    item = Gtk.Button()
    item.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
    item.set_tooltip_text(tooltip)
    item.get_accessible().set_name(tooltip)
    item.connect('clicked', lambda *_: callback())
    return style(item, 'icon-button')


def clear(box):
    for child in box.get_children():
        child.destroy()


def device_groups(objects, query=''):
    groups = {'Connected': [], 'Saved Devices': [], 'Nearby Devices': []}
    for path, interfaces in objects.items():
        properties = interfaces.get('org.bluez.Device1')
        if not properties:
            continue
        device = dict(properties, path=path)
        device['name'] = properties.get('Alias') or properties.get('Name') or properties.get('Address', 'Device')
        if not properties.get('Paired') and not properties.get('Name'):
            continue  # Unnamed BLE advertisements do not belong in a device picker.
        if query.casefold() not in device['name'].casefold():
            continue
        device['battery'] = interfaces.get('org.bluez.Battery1', {}).get('Percentage')
        group = ('Connected' if properties.get('Paired') and properties.get('Connected')
                 else 'Saved Devices' if properties.get('Paired') else 'Nearby Devices')
        groups[group].append(device)
    for devices in groups.values():
        devices.sort(key=lambda d: (d['name'].casefold(), d.get('Address', '')))
    return groups


def friendly_error(text, action):
    if 'Authentication' in text:
        return 'Pairing was rejected. Put the device in pairing mode and try again.'
    if 'NotReady' in text or 'not powered' in text:
        return 'Bluetooth is not ready. Turn it on and try again.'
    if 'InProgress' in text:
        return 'Another Bluetooth action is still finishing. Please try again.'
    if action == 'pair':
        return 'Could not pair. Keep the device nearby and in pairing mode, then try again.'
    return 'Could not connect. Check that the device is on and available, then try again.'


class Panel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.obsidian.BluetoothPanel',
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.objects = {}
        self.bus = None
        self.busy = False
        self.loading = False
        self.pending_refresh = False
        self.requested = None
        self.detail_path = None
        self.cancel = Gio.Cancellable()
        self.fingerprint = None
        self.refresh_again = False
        self.dismiss_source = None

    def do_command_line(self, command):
        args = command.get_arguments()[1:]
        if self.window:
            if '--scan' in args:
                self.run_action('scan')
            elif '--toggle' in args:
                self.request_power(not self.powered())
            elif not self.window.get_visible():
                if self.dismiss_source is not None:
                    GLib.source_remove(self.dismiss_source)
                    self.dismiss_source = None
                self.window.show()
            else:
                self.close()
        else:
            self.requested = 'scan' if '--scan' in args else 'toggle' if '--toggle' in args else None
            self.activate()
        return 0

    def do_activate(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title('Bluetooth')
        self.window.set_name('bluetooth-backdrop')
        self.window.set_app_paintable(True)
        visual = self.window.get_screen().get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        GtkLayerShell.init_for_window(self.window)
        GtkLayerShell.set_namespace(self.window, 'obsidian-bluetooth-panel')
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
        surface.set_name('bluetooth-panel')
        style(surface, 'obsidian-panel')
        surface.set_halign(Gtk.Align.END)
        surface.set_valign(Gtk.Align.START)
        surface.set_margin_top(44)
        surface.set_margin_end(12)
        surface.set_size_request(360, -1)
        surface.connect('button-press-event', lambda *_: True)
        overlay.add_overlay(surface)
        layout = column(10)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(layout, 'set_margin_' + side)(10)
        surface.add(layout)

        header = Gtk.Box(spacing=12)
        badge = Gtk.Image.new_from_icon_name('bluetooth-symbolic', Gtk.IconSize.LARGE_TOOLBAR)
        style(badge, 'bluetooth-badge')
        heading = column(3)
        heading.pack_start(label('Bluetooth', 'title'), False, False, 0)
        self.subtitle = label('Loading devices…', 'muted')
        header.pack_start(heading, True, True, 0)
        self.switch = Gtk.Switch()
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.get_accessible().set_name('Bluetooth power')
        self.switch.connect('state-set', self.switch_changed)
        header.pack_start(self.switch, False, False, 0)
        header.pack_start(icon_button('window-close-symbolic', 'Close Bluetooth · Escape', self.close), False, False, 0)
        layout.pack_start(header, False, False, 0)

        self.feedback = Gtk.Revealer()
        self.feedback.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.feedback_box = column(8)
        style(self.feedback_box, 'feedback')
        self.feedback.add(self.feedback_box)
        layout.pack_start(self.feedback, False, False, 0)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(100)
        layout.pack_start(self.stack, False, False, 0)
        main = column(8)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text('Find a device')
        self.search.get_accessible().set_name('Find a Bluetooth device')
        self.search.connect('search-changed', lambda *_: self.render_devices())
        main.pack_start(self.search, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)
        scroll.set_max_content_height(340)
        self.devices = column(8)
        scroll.add(self.devices)
        main.pack_start(scroll, False, False, 0)
        self.stack.add_named(main, 'devices')
        self.details = column(12)
        self.stack.add_named(self.details, 'details')
        footer = Gtk.Box(spacing=8)
        self.scan = button('Scan', lambda: self.run_action('scan'))
        self.scan.set_image(Gtk.Image.new_from_icon_name('view-refresh-symbolic', Gtk.IconSize.BUTTON))
        self.scan.set_always_show_image(True)
        footer.pack_start(self.scan, True, True, 0)
        footer.pack_start(icon_button('audio-volume-high-symbolic', 'Audio settings', self.audio_settings), False, False, 0)
        layout.pack_start(Gtk.Separator(), False, False, 0)
        layout.pack_start(footer, False, False, 0)
        self.load_style()
        self.window.show_all()
        self.window.set_focus(None)
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self.subscription = self.bus.signal_subscribe('org.bluez', None, None, None, None,
                Gio.DBusSignalFlags.NONE, self.on_signal)
            self.refresh()
        except GLib.Error:
            self.message('Bluetooth is unavailable. Check that the Bluetooth service is running.', error=True)
            self.switch.set_sensitive(False)
            self.scan.set_sensitive(False)

    def load_style(self):
        defaults = {'bg': '#191d1b', 'panel': '#222824', 'selected': '#303a33',
                    'border': '#48554b', 'fg': '#e0e5dc', 'muted': '#a6b2a7', 'accent': '#b1c59e'}
        try:
            data = (CONFIG / 'obsidian-ember/current/rofi.rasi').read_text()
            defaults.update({key: color[:7] for key, color in
                             re.findall(r'(\w+):\s*(#[0-9a-fA-F]{6,8})\s*;', data)})
        except OSError:
            pass
        css = (CONFIG / 'obsidian-ember/panel.css').read_text() + '\n'
        css += (Path(__file__).parent / 'panel.css').read_text()
        for key, color in defaults.items():
            css = css.replace('{{' + key + '}}', color)
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def adapters(self):
        return [interfaces['org.bluez.Adapter1'] for interfaces in self.objects.values()
                if 'org.bluez.Adapter1' in interfaces]

    def powered(self):
        return any(adapter.get('Powered') for adapter in self.adapters())

    def on_signal(self, *_):
        if not self.pending_refresh and self.window:
            self.pending_refresh = True
            GLib.timeout_add(100, self.refresh)

    def refresh(self):
        self.pending_refresh = False
        if self.loading:
            self.refresh_again = True
            return False
        if not self.window or not self.bus:
            return False
        self.loading = True
        self.bus.call('org.bluez', '/', 'org.freedesktop.DBus.ObjectManager',
            'GetManagedObjects', None, None, Gio.DBusCallFlags.NONE, 4000,
            self.cancel, self.refreshed)
        return False

    def refreshed(self, bus, result):
        self.loading = False
        if not self.window:
            return
        try:
            self.objects = bus.call_finish(result).unpack()[0]
        except GLib.Error:
            self.objects = {}
            self.message('Bluetooth is reconnecting. Try again in a moment.', error=True)
        self.render_state()

    def render_state(self):
        adapters = self.adapters()
        self.updating = True
        self.switch.set_active(self.powered())
        self.switch.set_state(self.powered())
        self.updating = False
        self.switch.set_sensitive(len(adapters) == 1 and not self.busy)
        self.scan.set_sensitive(self.powered() and len(adapters) == 1 and not self.busy)
        groups = device_groups(self.objects)
        count = len(groups['Connected'])
        self.subtitle.set_text(('No adapter available' if not adapters else
            'Select an adapter in Bluetooth settings' if len(adapters) > 1 else
            'Off' if not self.powered() else f'{count} connected' if count else 'On · Ready to connect'))
        self.render_devices()
        if self.detail_path:
            self.show_details(self.detail_path)
        if self.requested:
            requested, self.requested = self.requested, None
            if requested == 'scan' and self.powered():
                self.run_action('scan')
            elif requested == 'toggle' and len(adapters) == 1:
                self.request_power(not self.powered())
        if self.refresh_again:
            self.refresh_again = False
            self.refresh()

    def render_devices(self):
        if not self.window:
            return
        groups = device_groups(self.objects, self.search.get_text())
        fingerprint = repr((groups, self.powered(), self.busy))
        if fingerprint == self.fingerprint:
            return
        self.fingerprint = fingerprint
        clear(self.devices)
        if not self.powered():
            self.devices.pack_start(label('Turn on Bluetooth to connect your devices.', 'empty'), False, False, 0)
        else:
            total = sum(map(len, groups.values()))
            for title, devices in groups.items():
                if not devices:
                    continue
                group = column(5)
                group.pack_start(label({'Saved Devices': 'Saved', 'Nearby Devices': 'Nearby'}.get(title, title), 'section-title'), False, False, 0)
                rows = column(3)
                style(rows, 'device-group')
                for device in devices:
                    rows.pack_start(self.device_row(device), False, False, 0)
                group.pack_start(rows, False, False, 0)
                self.devices.pack_start(group, False, False, 0)
            if not total:
                text = 'No matching devices.' if self.search.get_text() else 'No devices yet. Put your device in pairing mode, then scan.'
                empty = label(text, 'empty')
                empty.set_line_wrap(True)
                empty.set_max_width_chars(36)
                self.devices.pack_start(empty, False, False, 0)
        self.devices.show_all()

    def device_row(self, device):
        row = Gtk.Box(spacing=10)
        style(row, 'device-row')
        paired, connected = device.get('Paired'), device.get('Connected') and device.get('Paired')
        icon = device.get('Icon', 'bluetooth')
        if icon in ('bluetooth', 'audio-card') and any(uuid.startswith('0000110b-') for uuid in device.get('UUIDs', [])):
            icon = 'audio-headphones'
        image = Gtk.Image.new_from_icon_name(icon + '-symbolic', Gtk.IconSize.BUTTON)
        style(image, 'device-icon-active' if connected else 'device-icon')
        row.pack_start(image, False, False, 0)
        text = column(3)
        name = label(device['name'], 'device-name')
        name.set_max_width_chars(18)
        name.set_tooltip_text(device['name'])
        text.pack_start(name, False, False, 0)
        state = 'Connected' if connected else 'Not connected' if paired else 'Ready to pair'
        if device['battery'] is not None:
            state += f' · {device["battery"]}% battery'
        row.set_tooltip_text(state)
        if device['battery'] is not None:
            text.pack_start(label(f'{device["battery"]}% battery', 'muted'), False, False, 0)
        row.pack_start(text, True, True, 0)
        action = 'disconnect' if connected else 'connect' if paired else 'pair'
        control = button({'disconnect': 'Disconnect', 'connect': 'Connect', 'pair': 'Pair'}[action],
                         lambda: self.run_action(action, device), 'quiet' if connected else 'primary')
        control.set_sensitive(not self.busy)
        row.pack_start(control, False, False, 0)
        row.pack_start(icon_button('view-more-symbolic', f'Details for {device["name"]}',
                                   lambda: self.show_details(device['path'])), False, False, 0)
        return row

    def show_details(self, path):
        interfaces = self.objects.get(path, {})
        device = interfaces.get('org.bluez.Device1')
        if not device:
            self.back()
            return
        self.detail_path = path
        clear(self.details)
        self.details.pack_start(button('‹  All Devices', self.back, 'quiet'), False, False, 0)
        self.details.pack_start(label(device.get('Alias', 'Device'), 'title'), False, False, 0)
        self.details.pack_start(label(device.get('Address', ''), 'muted'), False, False, 0)
        text = label('Saved pairing' if device.get('Paired') else 'Pairing required', 'muted')
        self.details.pack_start(text, False, False, 0)
        full = dict(device, path=path, name=device.get('Alias', 'Device'))
        action = 'disconnect' if device.get('Paired') and device.get('Connected') else 'connect' if device.get('Paired') else 'pair'
        self.details.pack_start(button({'disconnect': 'Disconnect', 'connect': 'Connect', 'pair': 'Pair and Connect'}[action],
                                       lambda: self.run_action(action, full), 'primary'), False, False, 0)
        if device.get('Paired'):
            self.details.pack_start(button('Forget This Device…', lambda: self.confirm_forget(full), 'quiet'), False, False, 0)
        else:
            self.details.pack_start(button('Pair Using PIN…', lambda: self.pair_with_pin(full), 'quiet'), False, False, 0)
        self.details.set_sensitive(not self.busy)
        self.details.show_all()
        self.stack.set_visible_child_name('details')

    def back(self):
        self.detail_path = None
        self.stack.set_visible_child_name('devices')
        self.search.grab_focus()

    def message(self, text, error=False, confirm=None):
        clear(self.feedback_box)
        row = Gtk.Box(spacing=8)
        if self.busy:
            spinner = Gtk.Spinner()
            spinner.start()
            row.pack_start(spinner, False, False, 0)
        content = label(text, 'error' if error else 'muted')
        content.set_line_wrap(True)
        content.set_ellipsize(Pango.EllipsizeMode.NONE)
        content.set_max_width_chars(34)
        row.pack_start(content, True, True, 0)
        if not self.busy:
            row.pack_start(icon_button('window-close-symbolic', 'Dismiss message',
                                       lambda: self.feedback.set_reveal_child(False)), False, False, 0)
        self.feedback_box.pack_start(row, False, False, 0)
        if confirm:
            actions = Gtk.Box(spacing=8)
            actions.pack_start(button('Cancel', lambda: self.feedback.set_reveal_child(False)), True, True, 0)
            actions.pack_start(button(confirm[0], confirm[1], 'primary'), True, True, 0)
            self.feedback_box.pack_start(actions, False, False, 0)
        self.feedback_box.show_all()
        self.feedback.set_reveal_child(True)

    def confirm_forget(self, device):
        self.message(f'Forget {device["name"]}? You will need to pair it again.',
                     confirm=('Forget Device', lambda: self.run_action('forget', device)))

    def switch_changed(self, switch, desired):
        if not getattr(self, 'updating', False):
            self.request_power(desired)
        return True

    def request_power(self, desired):
        if self.busy:
            return
        connected = len(device_groups(self.objects)['Connected'])
        if not desired and connected:
            self.message('Turning off Bluetooth will disconnect your devices.',
                         confirm=('Turn Off', lambda: self.run_action('power-off')))
        else:
            self.run_action('power-on' if desired else 'power-off')

    def run_action(self, action, device=None):
        if self.busy or not self.window:
            return
        self.busy = True
        name = device['name'] if device else ''
        verb = {'pair': f'Pairing and connecting {name}…', 'connect': f'Connecting {name}…',
                'disconnect': f'Disconnecting {name}…', 'forget': f'Forgetting {name}…',
                'scan': 'Looking for nearby devices…', 'power-on': 'Turning Bluetooth on…',
                'power-off': 'Turning Bluetooth off…'}[action]
        self.message(verb)
        self.switch.set_sensitive(False)
        self.scan.set_sensitive(False)
        self.render_devices()
        self.details.set_sensitive(False)
        command = self.command_for(action, device)

        def work():
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=55)
                success, error = result.returncode == 0, result.stderr + result.stdout
            except (OSError, subprocess.TimeoutExpired) as exc:
                success, error = False, str(exc)
            GLib.idle_add(self.finished, action, success, error)
        threading.Thread(target=work, daemon=True).start()

    def command_for(self, action, device):
        if device and action in ('pair', 'connect'):
            command = [str(BACKEND), '--' + action, device['Address']]
        elif action == 'scan':
            command = [str(BACKEND), '--scan']
        elif action.startswith('power-'):
            command = [str(BACKEND), '--power', action[6:]]
        else:
            command = ['timeout', '15', 'bluetoothctl', 'remove' if action == 'forget' else action, device['Address']]
        return command

    def finished(self, action, success, error):
        if not self.window:
            return False
        self.busy = False
        if success:
            self.feedback.set_reveal_child(False)
            if action == 'forget':
                self.back()
        else:
            self.message(friendly_error(error, action), error=True)
        self.refresh()
        return False

    def audio_settings(self):
        subprocess.Popen(['sh', '-c', 'command -v pavucontrol >/dev/null && exec pavucontrol || exec systemsettings kcm_pulseaudio'],
                         start_new_session=True)
        self.close()

    def pair_with_pin(self, device):
        subprocess.Popen([str(BACKEND), '--pair-pin', device['Address']], start_new_session=True)
        self.close()

    def keypress(self, window, event):
        if event.keyval == Gdk.KEY_Escape:
            if self.detail_path:
                self.back()
            else:
                self.close()
            return True
        return False

    def close(self):
        if not self.window:
            return
        # Finish a requested pairing/connect even if the panel is dismissed.
        if self.busy:
            self.window.hide()
            if self.dismiss_source is None:
                self.dismiss_source = GLib.timeout_add(100, self.close_when_idle)
        else:
            self.cancel.cancel()
            self.window.destroy()
            self.window = None
            self.quit()

    def close_when_idle(self):
        if self.busy:
            return True
        self.dismiss_source = None
        self.close()
        return False


if __name__ == '__main__':
    raise SystemExit(Panel().run())
