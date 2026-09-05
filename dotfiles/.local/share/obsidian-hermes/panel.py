#!/usr/bin/env python3
"""A transient Wayland panel for the persistent Hermes desktop companion."""
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell, Pango

from app import CONFIG, PORT, palette, read_json

URL = f'http://127.0.0.1:{PORT}'
TERMINAL = ('completed', 'failed', 'cancelled')
INTRO = ('Let’s get acquainted. Start from what you already know about me, then ask '
         'one useful question at a time about what I need help keeping track of.')


def request(path, body=None):
    key = read_json(CONFIG, {}).get('desktop_key', '')
    req = urllib.request.Request(URL + '/api/' + path,
        headers={'Cookie': 'hermes_desktop=' + key, 'Origin': URL,
                 'Content-Type': 'application/json'},
        data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=45 if path.startswith('model') else 12) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise ValueError(json.load(exc).get('error', 'Please try again.')) from None
    except (OSError, ValueError):
        raise ValueError('Hermes is reconnecting. Please try again shortly.') from None


def label(text, style=None):
    widget = Gtk.Label(label=text, xalign=0)
    widget.set_line_wrap(True)
    widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    widget.set_max_width_chars(44)
    if style:
        widget.get_style_context().add_class(style)
    return widget


def button(text, callback, tooltip=None):
    widget = Gtk.Button(label=text)
    widget.connect('clicked', lambda *_: callback())
    if tooltip:
        widget.set_tooltip_text(tooltip)
    return widget


def column(spacing=10):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)


def clear(box):
    for child in box.get_children():
        child.destroy()


class Panel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.obsidian.HermesPanel', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.state = {}
        self.messages = []
        self.history_version = None
        self.rendered = None
        self.rendered_reminders = None
        self.fetching = False
        self.sending = False
        self.loading_models = False
        self.poll_error = False
        self.alive = True

    def do_activate(self):
        if self.window:
            self.close()
            return
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title('Hermes')
        self.window.set_name('hermes-backdrop')
        self.window.set_app_paintable(True)
        visual = self.window.get_screen().get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        GtkLayerShell.init_for_window(self.window)
        GtkLayerShell.set_namespace(self.window, 'obsidian-hermes-panel')
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        GtkLayerShell.set_exclusive_zone(self.window, -1)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.window, edge, True)
        self.window.connect('key-press-event', self.keypress)
        self.window.connect('destroy', lambda *_: self.quit())

        overlay = Gtk.Overlay()
        self.window.add(overlay)
        backdrop = Gtk.EventBox()
        backdrop.set_visible_window(False)
        backdrop.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        backdrop.connect('button-press-event', lambda *_: self.close() or True)
        overlay.add(backdrop)
        surface = Gtk.EventBox()
        surface.set_name('hermes-panel')
        surface.set_halign(Gtk.Align.END)
        surface.set_valign(Gtk.Align.START)
        surface.set_margin_top(43)
        surface.set_margin_end(10)
        surface.set_size_request(420, 520)
        # Give the panel its own event window so clicks on its padding stay inside.
        surface.connect('button-press-event', lambda *_: True)
        overlay.add_overlay(surface)
        layout = column(12)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(layout, 'set_margin_' + side)(16)
        surface.add(layout)

        header = Gtk.Box(spacing=8)
        title = label('Hermes', 'title')
        header.pack_start(title, True, True, 0)
        self.health = label('Connecting…', 'muted')
        header.pack_start(self.health, False, False, 0)
        self.alerts = button('Alerts on', lambda: self.act('pause', {'paused': not self.state.get('paused')}))
        header.pack_start(self.alerts, False, False, 0)
        header.pack_start(button('×', self.close, 'Close · Escape'), False, False, 0)
        layout.pack_start(header, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        switcher = Gtk.StackSwitcher(stack=self.stack)
        switcher.set_halign(Gtk.Align.FILL)
        switcher.set_homogeneous(True)
        layout.pack_start(switcher, False, False, 0)
        layout.pack_start(self.stack, True, True, 0)
        self.chat = column(14)
        self.chat_scroll = self.scroll(self.chat)
        self.stack.add_titled(self.chat_scroll, 'chat', 'Assistant')
        self.reminders = column(12)
        self.stack.add_titled(self.scroll(self.reminders), 'reminders', 'Reminders')
        self.settings = column(10)
        self.stack.add_titled(self.scroll(self.settings), 'settings', 'Settings')
        self.settings.pack_start(label('Model', 'title'), False, False, 0)
        self.provider_name = label('Your connected provider', 'muted')
        self.settings.pack_start(self.provider_name, False, False, 0)
        self.model_picker = Gtk.ComboBoxText()
        self.model_picker.connect('notify::popup-shown', self.model_popup_changed)
        self.model_picker.set_hexpand(True)
        for cell in self.model_picker.get_cells():
            cell.set_property('ellipsize', Pango.EllipsizeMode.END)
            cell.set_property('max-width-chars', 32)
        self.settings.pack_start(self.model_picker, False, False, 0)
        model_actions = Gtk.Box(spacing=8)
        self.model_apply = button('Use model', self.select_model)
        self.model_apply.get_style_context().add_class('primary')
        self.model_refresh = button('Refresh list', lambda: self.load_models(force=True))
        model_actions.pack_start(self.model_apply, False, False, 0)
        model_actions.pack_start(self.model_refresh, False, False, 0)
        self.settings.pack_start(model_actions, False, False, 0)
        self.model_note = label('New models are checked automatically when you open settings.', 'muted')
        self.settings.pack_start(self.model_note, False, False, 0)
        self.settings.pack_start(label('Changes apply to the next reply and scheduled tasks.', 'muted'), False, False, 0)
        self.settings.pack_start(label('Background assistant', 'title'), False, False, 8)
        self.daemon_status = label('Checking…')
        self.settings.pack_start(self.daemon_status, False, False, 0)
        self.settings.pack_start(label('Starts at login. If it stops, a separate health check notifies you within about 30 seconds.', 'muted'), False, False, 0)
        self.settings.pack_start(label('Email and calendar are not connected yet.', 'muted'), False, False, 0)
        self.stack.connect('notify::visible-child-name', self.view_changed)

        self.approval = column(6)
        self.approval.set_no_show_all(True)
        layout.pack_start(self.approval, False, False, 0)
        self.error = label('', 'error')
        self.error.set_no_show_all(True)
        layout.pack_start(self.error, False, False, 0)
        composer = Gtk.Box(spacing=8)
        self.composer = composer
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text('Ask or remind me…')
        self.entry.set_max_length(20000)
        self.entry.connect('activate', lambda *_: self.send())
        composer.pack_start(self.entry, True, True, 0)
        self.send_button = button('Send', self.send)
        self.send_button.get_style_context().add_class('primary')
        composer.pack_start(self.send_button, False, False, 0)
        self.stop_button = button('Stop', lambda: self.act('stop', {}))
        self.stop_button.set_no_show_all(True)
        composer.pack_start(self.stop_button, False, False, 0)
        layout.pack_start(composer, False, False, 0)
        self.footer = label('Quiet hours 22:00–08:00', 'muted')
        layout.pack_start(self.footer, False, False, 0)
        self.provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), self.provider,
                                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.colors = None
        self.apply_palette(palette())
        self.render_chat()
        self.window.show_all()
        self.entry.grab_focus()
        self.refresh()
        GLib.timeout_add(1500, self.refresh)

    def scroll(self, child):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(295)
        scroll.set_max_content_height(295)
        scroll.set_propagate_natural_height(True)
        scroll.add(child)
        return scroll

    def apply_palette(self, colors):
        if colors == self.colors:
            return
        self.colors = colors.copy()
        c = dict(bg='#20231e', panel='#292d25', hover='#353c30', border='#4d5745',
                 text='#e0e4d9', muted='#a2ad98', accent='#b1c998', danger='#e69b91', contrast='#20231e')
        c.update(colors)
        css = '''
        #hermes-backdrop { background: transparent; }
        #hermes-panel { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s;
                        border-radius: 10px; font: 13px "Inter", "sans-serif"; }
        #hermes-panel label { color: %(text)s; }
        #hermes-panel .title { font-size: 17px; font-weight: 600; }
        #hermes-panel .muted { color: %(muted)s; font-size: 11px; }
        #hermes-panel .error { color: %(danger)s; }
        #hermes-panel .user { color: %(muted)s; }
        #hermes-panel button { background: transparent; background-image: none; color: %(muted)s;
            border: 1px solid transparent; border-radius: 6px; padding: 5px 9px;
            box-shadow: none; text-shadow: none; min-height: 22px; }
        #hermes-panel button:hover, #hermes-panel button:checked { background: %(hover)s; color: %(text)s; }
        #hermes-panel button:focus { border-color: %(accent)s; }
        #hermes-panel button.primary { background: %(accent)s; color: %(contrast)s; }
        #hermes-panel button.primary label { color: %(contrast)s; }
        #hermes-panel combobox button { background: %(bg)s; border-color: %(border)s; }
        #hermes-panel button:disabled { opacity: 0.45; }
        #hermes-panel entry { background: %(bg)s; color: %(text)s; caret-color: %(accent)s;
            border: 1px solid %(border)s; border-radius: 6px; padding: 7px; box-shadow: none; }
        #hermes-panel entry:focus { border-color: %(accent)s; }
        #hermes-panel scrolledwindow, #hermes-panel viewport { background: transparent; border: none; }
        #hermes-panel scrollbar { background: transparent; }
        #hermes-panel scrollbar slider { background: %(border)s; min-width: 3px; border: none; }
        ''' % c
        self.provider.load_from_data(css.encode())

    def keypress(self, _window, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def close(self):
        self.alive = False
        if self.window:
            self.window.destroy()
        self.quit()

    def show_error(self, message):
        if self.alive:
            self.error.set_text(message)
            self.error.set_visible(bool(message))

    def worker(self, operation, callback):
        def run():
            try:
                value, error = operation(), None
            except Exception as exc:
                value, error = None, str(exc)
            def done():
                if self.alive:
                    callback(value, error)
                return False
            GLib.idle_add(done)
        threading.Thread(target=run, daemon=True).start()

    def act(self, path, body, callback=None):
        self.show_error('')
        def done(value, error):
            if error:
                self.show_error(error)
            if callback:
                callback(value, error)
            self.refresh()
        self.worker(lambda: request(path, body), done)

    def send(self, text=None):
        text = (text if text is not None else self.entry.get_text()).strip()
        active = self.state.get('active') or {}
        if not text or self.sending or (active and active.get('status') not in TERMINAL):
            return
        self.sending = True
        self.send_button.set_sensitive(False)
        self.stack.set_visible_child_name('chat')
        def done(value, error):
            self.sending = False
            if not error:
                self.entry.set_text('')
                self.state['active'] = value
                self.render_chat()
            self.send_button.set_sensitive(True)
            self.entry.grab_focus()
        self.act('chat', {'message': text}, done)

    def view_changed(self, *_):
        settings = self.stack.get_visible_child_name() == 'settings'
        self.composer.set_visible(not settings)
        if settings:
            self.load_models()
        else:
            self.entry.grab_focus()

    def load_models(self, force=False):
        if self.loading_models:
            return
        self.loading_models = True
        self.model_refresh.set_sensitive(False)
        self.model_apply.set_sensitive(False)
        self.model_note.set_text('Checking available models…')
        def done(value, error):
            self.loading_models = False
            self.model_refresh.set_sensitive(True)
            if error:
                self.model_note.set_text(error)
                return
            self.provider_name.set_text(value['provider'])
            self.model_picker.remove_all()
            for model in value['models']:
                self.model_picker.append(model, model)
            self.model_picker.set_active_id(value['selected'])
            self.model_apply.set_sensitive(True)
            self.model_note.set_text('List is up to date · Checked with your provider' if value['source'] == 'live' else
                                     'Using the saved list · Refresh when connected')
        self.worker(lambda: request('models/refresh', {}) if force else request('models'), done)

    def select_model(self):
        selected = self.model_picker.get_active_id()
        if not selected:
            return
        self.model_apply.set_sensitive(False)
        def done(value, error):
            self.model_apply.set_sensitive(True)
            if not error:
                self.model_note.set_text('Using ' + value['selected'] + ' for the next reply.')
        self.act('model', {'model': selected}, done)

    def model_popup_changed(self, picker, _property):
        # An exclusive layer-shell keyboard grab prevents GTK's model menu from
        # receiving selection input on Hyprland. Let the popup own input while
        # it is open, then restore the panel's keyboard focus for Escape/typing.
        mode = (GtkLayerShell.KeyboardMode.ON_DEMAND if picker.get_property('popup-shown')
                else GtkLayerShell.KeyboardMode.EXCLUSIVE)
        GtkLayerShell.set_keyboard_mode(self.window, mode)

    def refresh(self):
        if not self.alive:
            return False
        if self.fetching:
            return True
        self.fetching = True
        def fetch():
            state = request('state')
            active = state.get('active') or {}
            version = (active.get('id'), active.get('status') in TERMINAL)
            history = request('messages')['messages'] if version != self.history_version else None
            return state, history, version
        def done(value, error):
            self.fetching = False
            if error:
                self.poll_error = True
                self.health.set_text('Reconnecting')
                self.send_button.set_sensitive(False)
                self.show_error(error)
                return
            if self.poll_error:
                self.poll_error = False
                self.show_error('')
            self.state, history, self.history_version = value
            if history is not None:
                self.messages = history
            self.render()
        self.worker(fetch, done)
        return True

    def render(self):
        self.apply_palette(self.state.get('palette', {}))
        active = self.state.get('active') or {}
        busy = bool(active) and active.get('status') not in TERMINAL
        self.health.set_text('Reconnecting' if not self.state.get('online') else
                             'Your decision' if active.get('approval') else 'Thinking…' if busy else 'Ready')
        self.daemon_status.set_text(('Running · Health monitoring on' if self.state.get('monitored') else
                                    'Running · Health check unavailable') if self.state.get('online') else 'Reconnecting…')
        self.alerts.set_label('Paused' if self.state.get('paused') else 'Alerts on')
        self.alerts.set_tooltip_text('Resume notifications' if self.state.get('paused') else 'Pause notifications')
        self.send_button.set_visible(not busy)
        self.send_button.set_sensitive(not self.sending and self.state.get('online', False))
        self.stop_button.set_visible(busy)
        self.footer.set_text('Alerts paused · Hermes is still running' if self.state.get('paused') else
                             'Quiet hours · Alerts resume at 08:00' if self.state.get('quiet') else
                             'Quiet hours 22:00–08:00')
        approval = active.get('approval')
        # Preserve focused controls during polling unless the approval changes.
        serialized = json.dumps(approval, sort_keys=True)
        if serialized != getattr(self, 'last_approval', None):
            self.last_approval = serialized
            clear(self.approval)
            if approval:
                detail = label(str(approval.get('command') or 'Hermes needs your decision.'))
                detail.set_selectable(True)
                scroll = Gtk.ScrolledWindow()
                scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scroll.set_size_request(-1, 65)
                scroll.add(detail)
                self.approval.pack_start(scroll, False, False, 0)
                actions = Gtk.Box(spacing=8)
                for choice, title in [('once', 'Allow once'), ('deny', 'Deny')]:
                    if choice in approval.get('choices', []):
                        actions.pack_start(button(title, lambda c=choice: self.act('approval', {'choice': c})), False, False, 0)
                self.approval.pack_start(actions, False, False, 0)
                self.approval.show_all()
            self.approval.set_visible(bool(approval))
        if active.get('status') == 'failed':
            self.show_error(active.get('error') or 'Hermes could not finish. Please try again.')
        self.render_chat()
        self.render_reminders()

    def render_chat(self):
        active = self.state.get('active') or {}
        rows = [{'role': m['role'], 'content': m['content']} for m in self.messages[-12:]]
        if active and active.get('status') not in TERMINAL:
            # Native history may already include the pending user message after reopening.
            if not rows or rows[-1] != {'role': 'user', 'content': active.get('message', '')}:
                rows.append({'role': 'user', 'content': active.get('message', '')})
            rows.append({'role': 'assistant', 'content': active.get('text') or 'Thinking…'})
        serialized = json.dumps(rows)
        if self.rendered == serialized:
            return
        self.rendered = serialized
        adjustment = self.chat_scroll.get_vadjustment()
        bottom = adjustment.get_upper() - adjustment.get_value() - adjustment.get_page_size() < 60
        clear(self.chat)
        if not rows:
            self.chat.pack_start(label('A little less to keep in your head.', 'title'), False, False, 12)
            self.chat.pack_start(label('Ask me to remember something, keep track of a task, or help plan your day.'), False, False, 0)
            intro = button('Meet Hermes', lambda: self.send(INTRO))
            intro.set_halign(Gtk.Align.START)
            intro.get_style_context().add_class('primary')
            self.chat.pack_start(intro, False, False, 0)
            self.chat.pack_start(label('Email and calendar can be connected later.', 'muted'), False, False, 0)
        for row in rows:
            block = column(4)
            block.pack_start(label('You' if row['role'] == 'user' else 'Hermes', 'muted'), False, False, 0)
            content = label(row['content'], 'user' if row['role'] == 'user' else None)
            content.set_selectable(True)
            block.pack_start(content, False, False, 0)
            self.chat.pack_start(block, False, False, 0)
        self.chat.show_all()
        if bottom:
            GLib.idle_add(lambda: adjustment.set_value(max(0, adjustment.get_upper() - adjustment.get_page_size())))

    def render_reminders(self):
        now = datetime.now().timestamp()
        updates = [i for i in self.state.get('updates', []) if not i['read'] and i.get('snoozed_until', 0) <= now]
        jobs = sorted([j for j in self.state.get('jobs', []) if j.get('enabled') or j.get('state') == 'paused'],
                      key=lambda j: j.get('next_run_at') or 'z')
        serialized = json.dumps([updates, jobs], sort_keys=True)
        if self.rendered_reminders == serialized:
            return
        self.rendered_reminders = serialized
        clear(self.reminders)
        if not updates and not jobs:
            self.reminders.pack_start(label('Nothing waiting.', 'title'), False, False, 12)
            self.reminders.pack_start(label('Try “Remind me tomorrow at 9 to book an appointment.”'), False, False, 0)
        for item in updates:
            block = column(5)
            block.pack_start(label(item['title']), False, False, 0)
            body = label(item['body'])
            body.set_selectable(True)
            block.pack_start(body, False, False, 0)
            actions = Gtk.Box(spacing=8)
            for action, title in [('read', 'Handled'), ('snooze', 'Tomorrow')]:
                actions.pack_start(button(title, lambda a=action, i=item['id']: self.act('update', {'id': i, 'action': a})), False, False, 0)
            block.pack_start(actions, False, False, 0)
            self.reminders.pack_start(block, False, False, 0)
        if jobs:
            self.reminders.pack_start(label('Upcoming', 'muted'), False, False, 0)
        for job in jobs:
            block = column(4)
            block.pack_start(label(job.get('name') or 'Reminder'), False, False, 0)
            when = job.get('next_run_at')
            try:
                when = datetime.fromisoformat(when).astimezone(ZoneInfo('Europe/Berlin')).strftime('%a %d %b · %H:%M')
            except (ValueError, TypeError):
                when = job.get('schedule_display') or 'Scheduled'
            block.pack_start(label('Paused' if job.get('state') == 'paused' else when, 'muted'), False, False, 0)
            action = 'resume' if job.get('state') == 'paused' else 'pause'
            control = button(action.capitalize(), lambda a=action, i=job['id']: self.act('job', {'id': i, 'action': a}))
            control.set_halign(Gtk.Align.START)
            block.pack_start(control, False, False, 0)
            self.reminders.pack_start(block, False, False, 0)
        self.reminders.show_all()


if __name__ == '__main__':
    Panel().run(None)
