#!/usr/bin/python3
"""Bluetooth presentation tests; --live-desktop also tests real GTK pointer input.

Live tests use example devices and an inert command runner. They never change radios.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bluetooth_panel', ROOT / 'dotfiles/.local/share/obsidian-bluetooth/panel.py')
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)
ADAPTER = '/org/bluez/hci0'
SAVED = ADAPTER + '/dev_AA_BB_CC_DD_EE_02'
CONNECTED = ADAPTER + '/dev_AA_BB_CC_DD_EE_01'
NEARBY = ADAPTER + '/dev_AA_BB_CC_DD_EE_03'
FIXTURE = {
    ADAPTER: {'org.bluez.Adapter1': {'Powered': True}},
    CONNECTED: {'org.bluez.Device1': {'Address': 'AA:BB:CC:DD:EE:01', 'Name': 'Studio Headphones',
        'Alias': 'Studio Headphones', 'Icon': 'audio-headphones', 'Paired': True, 'Connected': True},
        'org.bluez.Battery1': {'Percentage': 76}},
    SAVED: {'org.bluez.Device1': {'Address': 'AA:BB:CC:DD:EE:02', 'Name': 'Café Buds',
        'Alias': 'Café Buds', 'Paired': True, 'Connected': False}},
    NEARBY: {'org.bluez.Device1': {'Address': 'AA:BB:CC:DD:EE:03', 'Name': 'Keyboard',
        'Alias': 'Keyboard', 'Paired': False, 'Connected': True}},
    ADAPTER + '/noise': {'org.bluez.Device1': {'Address': 'AA:BB:CC:DD:EE:04'}},
}


class PresentationTests(unittest.TestCase):
    def test_temporary_pairing_link_is_not_presented_as_connected(self):
        groups = panel.device_groups(FIXTURE)
        self.assertEqual([d['name'] for d in groups['Connected']], ['Studio Headphones'])
        self.assertEqual([d['name'] for d in groups['Nearby Devices']], ['Keyboard'])

    def test_search_preserves_unicode_names(self):
        groups = panel.device_groups(FIXTURE, 'CAFÉ')
        self.assertEqual([d['name'] for d in groups['Saved Devices']], ['Café Buds'])
        self.assertFalse(groups['Connected'])

    def test_battery_and_unnamed_advertisements(self):
        groups = panel.device_groups(FIXTURE)
        self.assertEqual(groups['Connected'][0]['battery'], 76)
        self.assertEqual(sum(map(len, groups.values())), 3)

    def test_errors_describe_recovery_without_internal_error_codes(self):
        text = panel.friendly_error('org.bluez.Error.AuthenticationFailed', 'pair')
        self.assertIn('pairing mode', text)
        self.assertNotIn('org.bluez', text)


def live_tests():
    # Reuse the desktop's existing Wayland pointer test helper.
    spec = importlib.util.spec_from_file_location('connectivity_ui', ROOT / 'scripts/test-connectivity-ui.py')
    controls = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controls)
    monitor = next(m for m in json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j'])) if m['focused'])
    cursor = json.loads(subprocess.check_output(['hyprctl', 'cursorpos', '-j']))
    pointer = controls.Pointer()
    failures = []

    class ExamplePanel(panel.Panel):
        def __init__(self, scenario):
            super().__init__()
            self.set_application_id('org.obsidian.BluetoothPanelUITest.' + scenario.replace('-', ''))
            self.scenario = scenario
            self.example = copy.deepcopy(FIXTURE)
            self.actions = []
            self.timers = set()

        def refresh(self):
            self.objects = self.example
            self.render_state()
            return False

        def command_for(self, action, device):
            self.actions.append((action, device))
            return ['/usr/bin/sleep', '0.35']

        def finished(self, action, success, error):
            if action == 'connect':
                self.example[SAVED]['org.bluez.Device1']['Connected'] = True
            return super().finished(action, success, error)

        def do_activate(self):
            super().do_activate()
            panel.GLib.timeout_add(350, self.start_test)

        def step(self, function, delay=150):
            def guarded():
                self.timers.discard(source)
                try:
                    function()
                except Exception as exc:
                    failures.append((self.scenario, str(exc)))
                    self.busy = False
                    self.close()
                return False
            source = panel.GLib.timeout_add(delay, guarded)
            self.timers.add(source)

        def close(self):
            for source in self.timers:
                panel.GLib.source_remove(source)
            self.timers.clear()
            super().close()

        def click(self, widget):
            x, y = widget.translate_coordinates(self.window, 0, 0)
            self.click_at(x + widget.get_allocated_width() / 2, y + widget.get_allocated_height() / 2)

        def click_at(self, x, y):
            subprocess.run(['hyprctl', 'dispatch', 'movecursor',
                            f'{monitor["x"]+round(x)} {monitor["y"]+round(y)}'],
                           check=True, stdout=subprocess.DEVNULL)
            pointer.click()

        def find(self, predicate, root=None):
            root = root or self.window
            if predicate(root):
                return root
            if isinstance(root, panel.Gtk.Container):
                for child in root.get_children():
                    result = self.find(predicate, child)
                    if result is not None:
                        return result
            return None

        def named(self, name):
            result = self.find(lambda w: isinstance(w, panel.Gtk.Button) and w.get_label() == name)
            assert result is not None, f'button missing: {name}'
            return result

        def start_test(self):
            self.step(self.perform, 1)
            return False

        def perform(self):
            if self.scenario == 'outside-click':
                self.click_at(20, 500)
            elif self.scenario == 'escape':
                subprocess.run(['wtype', '-k', 'Escape'], check=True)
            elif self.scenario == 'details-and-back':
                target = self.find(lambda w: w.get_tooltip_text() == 'Details for Café Buds')
                assert target is not None
                self.click(target)
                def check():
                    assert self.detail_path == SAVED, 'mouse click did not open device details'
                    self.click(self.named('‹  All Devices'))
                    self.step(self.check_back)
                self.step(check)
            elif self.scenario == 'search':
                self.click(self.search)
                subprocess.run(['wtype', 'Café'], check=True)
                def check():
                    assert self.search.get_text() == 'Café'
                    names = []
                    def collect(widget):
                        if isinstance(widget, panel.Gtk.Label): names.append(widget.get_text())
                        if isinstance(widget, panel.Gtk.Container):
                            for child in widget.get_children(): collect(child)
                    collect(self.devices)
                    assert 'Café Buds' in names and 'Studio Headphones' not in names, names
                    self.close()
                self.step(check, 300)
            elif self.scenario == 'connect-and-progress':
                self.click(self.named('Connect'))
                def check_busy():
                    assert self.busy and not self.switch.get_sensitive(), 'operation did not show busy state'
                    assert self.feedback.get_reveal_child(), 'progress is hidden'
                    self.step(self.check_connected, 600)
                self.step(check_busy, 100)
            elif self.scenario == 'forget-confirmation':
                self.show_details(CONNECTED)
                self.step(lambda: self.click(self.named('Forget This Device…')))
                def check():
                    assert self.feedback.get_reveal_child(), 'confirmation was not shown'
                    assert not self.actions, 'device was removed before confirmation'
                    self.click(self.named('Cancel'))
                    self.step(self.check_cancel)
                self.step(check, 350)
            else:
                raise AssertionError(self.scenario)
            if self.scenario in ('outside-click', 'escape'):
                self.step(lambda: (_ for _ in ()).throw(AssertionError('panel did not dismiss')), 600)

        def check_back(self):
            assert self.detail_path is None and self.stack.get_visible_child_name() == 'devices'
            self.close()

        def check_connected(self):
            assert not self.busy
            assert self.actions[0][0] == 'connect'
            assert len(panel.device_groups(self.objects)['Connected']) == 2
            self.close()

        def check_cancel(self):
            assert not self.actions and not self.feedback.get_reveal_child()
            self.close()

    try:
        for scenario in ('outside-click', 'escape', 'details-and-back', 'search',
                         'connect-and-progress', 'forget-confirmation'):
            application = ExamplePanel(scenario)
            application.run(['test-bluetooth-panel'])
            if failures:
                raise AssertionError(failures)
            print('PASS native pointer/keyboard:', scenario, flush=True)
    finally:
        pointer.close()
        subprocess.run(['hyprctl', 'dispatch', 'movecursor', f'{cursor["x"]} {cursor["y"]}'], stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    if '--live-desktop' in sys.argv:
        live_tests()
    else:
        unittest.main()
