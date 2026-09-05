#!/usr/bin/env python3
"""Live Wayland input regression test with fixture models and no account access."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-desktop', action='store_true')
    parser.add_argument('--panel-source', type=Path,
                        default=ROOT/'dotfiles/.local/share/obsidian-hermes/panel.py')
    args = parser.parse_args()
    if not args.live_desktop:
        parser.error('Use --live-desktop in an idle Hyprland session; the test moves the pointer.')
    sys.path.insert(0, str(ROOT/'dotfiles/.local/share/obsidian-hermes'))
    panel = module('model_panel_fixture', args.panel_source)
    from gi.repository import GLib
    Pointer = module('connectivity_fixture', ROOT/'scripts/test-connectivity-ui.py').Pointer
    selected = ['fixture-c']
    models = ['fixture-' + chr(97 + n) for n in range(10)]

    def request(path, body=None):
        if path == 'state':
            return {'online': True, 'monitored': True, 'active': None,
                    'palette': {}, 'jobs': [], 'updates': []}
        if path == 'messages':
            return {'messages': []}
        if path == 'models':
            return {'provider': 'fixture', 'models': models, 'selected': selected[0], 'source': 'live'}
        if path == 'model':
            assert body['model'] in models
            selected[0] = body['model']
            return {'selected': selected[0]}
        raise AssertionError('Unexpected request: ' + path)

    panel.request = request
    app = panel.Panel()
    app.set_application_id('org.obsidian.HermesModelRegression')
    pointer = Pointer()
    cursor = json.loads(subprocess.check_output(['hyprctl', 'cursorpos', '-j']))
    failures = []
    finished = []

    def fail(error):
        failures.append(str(error))
        app.close()
        return False

    def click(x, y):
        subprocess.run(['hyprctl', 'dispatch', 'movecursor', str(x), str(y)],
                       check=True, stdout=subprocess.DEVNULL)
        pointer.click()

    def background(operation, callback):
        def drive():
            try:
                operation()
                GLib.idle_add(callback)
            except Exception as exc:
                GLib.idle_add(fail, str(exc))
        threading.Thread(target=drive, daemon=True).start()

    def setup():
        app.stack.set_visible_child_name('settings')
        GLib.timeout_add(100, open_menu)
        return False

    def open_menu():
        if app.loading_models:
            return True
        position = app.model_picker.translate_coordinates(app.window, 40, 18)
        def choose():
            click(*position)
            time.sleep(.3)
            # With row C initially selected, row A is two menu rows above it.
            click(position[0], position[1] - 60)
            time.sleep(.2)
        background(choose, check_choice)
        return False

    def check_choice():
        actual = app.model_picker.get_active_id()
        if actual != 'fixture-a':
            return fail('Mouse selection was lost: expected fixture-a, got ' + str(actual))
        position = app.model_apply.translate_coordinates(app.window, 20, 15)
        background(lambda: (click(*position), time.sleep(.2)), check_saved)
        return False

    def check_saved():
        if not app.model_apply.get_sensitive():
            GLib.timeout_add(100, check_saved)
            return False
        if selected[0] != 'fixture-a':
            return fail('Use model did not save the new selection')
        if panel.GtkLayerShell.get_keyboard_mode(app.window) != panel.GtkLayerShell.KeyboardMode.EXCLUSIVE:
            return fail('Panel keyboard focus was not restored after choosing a model')
        print('PASS mouse model selection and Apply; exclusive panel focus restored', flush=True)
        # Reopening settings must show the saved model rather than the original.
        app.load_models()
        GLib.timeout_add(100, check_reload)
        return False

    def check_reload():
        if app.loading_models:
            return True
        if app.model_picker.get_active_id() != 'fixture-a':
            return fail('Reload reverted the saved model')
        print('PASS settings reload retains the new model', flush=True)
        finished.append(True)
        background(lambda: subprocess.run(['wtype', '-k', 'Escape'], check=True), lambda: False)
        GLib.timeout_add(1000, lambda: fail('Escape did not dismiss the panel'))
        return False

    GLib.timeout_add(250, setup)
    GLib.timeout_add_seconds(15, lambda: fail('Timed out waiting for model selection'))
    try:
        app.run(None)
    finally:
        pointer.close()
        subprocess.run(['hyprctl', 'dispatch', 'movecursor', str(cursor['x']), str(cursor['y'])],
                       stdout=subprocess.DEVNULL)
    if failures or not finished:
        raise SystemExit('; '.join(failures) or 'Panel closed before completing the test')
    print('PASS Escape after model selection; no provider or user configuration was accessed')


if __name__ == '__main__':
    main()
