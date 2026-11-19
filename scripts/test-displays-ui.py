#!/usr/bin/python3
"""Exercise real GTK controls with a fixture backend; never changes real displays."""
import copy
import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dotfiles/.local/share/obsidian-displays'))
import app
spec=importlib.util.spec_from_file_location('cases',Path(__file__).with_name('test-displays.py'))
cases=importlib.util.module_from_spec(spec); spec.loader.exec_module(cases)
raw=copy.deepcopy(cases.RAW)
raw[1]['model']='InnoView'
with patch.object(app.backend,'monitors',return_value=raw):
    ui=app.Displays()
    ui.set_application_id('org.obsidian.DisplaysValidation')
    ui.register(None)
    ui.activate()
    ui.window.hide()
    assert not ui.dirty
    assert not ui.apply_button.get_sensitive()
    assert ui.selected=='DP-1'
    def controls():
        return {row.get_children()[-1].get_accessible().get_name():row.get_children()[-1]
                for row in ui.settings.get_children() if isinstance(row,app.Gtk.Box)}
    controls()['Resolution'].set_active_id('1920x1080')
    changed=next(m for m in ui.draft if m['name']=='DP-1')
    assert (changed['width'],changed['height'])==(1920,1080)
    assert ui.dirty and ui.apply_button.get_sensitive()
    ui.refresh()
    controls()['Text size'].set_active_id('1.25')
    assert next(m for m in ui.draft if m['name']=='DP-1')['scale']==1.25
    ui.refresh()
    controls()['Rotation'].set_active_id('1')
    assert next(m for m in ui.draft if m['name']=='DP-1')['transform']==1
    ui.refresh()
    controls()['Use as'].set_active_id('eDP-1')
    assert next(m for m in ui.draft if m['name']=='DP-1')['mirror']=='eDP-1'
    app.backend.validate(ui.draft,raw)
    ui.refresh()
    controls()['Position'].set_active_id('left')
    assert next(m for m in ui.draft if m['name']=='DP-1')['x']==-2560
    app.backend.validate(ui.draft,raw)
    ui.refresh()
    ui.select('eDP-1')
    assert ui.selected=='eDP-1' and not ui.dirty
    ui.window.destroy()
    ui.quit()
print('GTK PASS: initial clean state; resolution, scaling, rotation, mirror, position, discard and display selection.')
