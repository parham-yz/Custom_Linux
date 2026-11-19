#!/usr/bin/python3
"""Opt-in live GTK weather checks; fixture data and isolated location settings."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dotfiles/.local/share/obsidian-weather'))
import panel
import weather


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-desktop',action='store_true')
    args=parser.parse_args()
    if not args.live_desktop:parser.error('Use --live-desktop to open temporary fixture panels')
    cases=load('weather_cases',ROOT/'scripts/test-weather.py')
    controls=load('pointer_controls',ROOT/'scripts/test-connectivity-ui.py')
    pointer=controls.Pointer()
    cursor=json.loads(subprocess.check_output(['hyprctl','cursorpos','-j']))
    monitor=next(m for m in json.loads(subprocess.check_output(['hyprctl','monitors','-j'])) if m['name']=='eDP-1')
    result={'data':weather.parse(cases.FIXTURE),'fetched':time.time(),'stale':False}
    failures=[]
    class Example(panel.Panel):
        def __init__(self,scenario):
            super().__init__();self.scenario=scenario;self.refreshes=0
            self.set_application_id('org.obsidian.WeatherUITest.'+scenario)
        def refresh(self,force=False):
            self.refreshes+=1
            self.result=result
            self.render(result)
        def do_activate(self):
            super().do_activate()
            panel.GLib.timeout_add(300,self.check)
        def check(self):
            try:
                assert self.city.get_text()=='Example City'
                assert self.temperature.get_text()=='12°'
                assert len(self.forecast.get_children())==1
                surface=self.summary.get_parent().get_parent()
                assert surface.get_allocated_width()<=340,surface.get_allocated_width()
                self.refresh_button.clicked();assert self.refreshes==2
                self.location_button.clicked();assert self.editor.get_reveal_child()
                self.entry.set_text('Example Town');self.apply_button.clicked()
                assert weather.read_location()=='Example Town'
                assert not self.editor.get_reveal_child()
                self.render(result|{'stale':True});assert self.status.get_text().startswith('Offline')
                self.render(None);assert self.temperature.get_text()=='—'
                assert not self.forecast.get_children()
                self.render(result)
                if self.scenario=='escape':
                    subprocess.run(['wtype','-k','Escape'],check=True)
                elif self.scenario=='outside':
                    subprocess.run(['hyprctl','dispatch','movecursor',f"{monitor['x']+700} {monitor['y']+600}"],check=True,stdout=subprocess.DEVNULL)
                    pointer.click()
                else:
                    self.do_command_line(None)
                panel.GLib.timeout_add(400,self.verify_closed)
            except Exception as exc:
                failures.append((self.scenario,str(exc)));self.close()
            return False
        def verify_closed(self):
            if self.window:
                failures.append((self.scenario,'dismissal did not close'));self.close()
            return False
    try:
        with tempfile.TemporaryDirectory() as tmp,patch.object(weather,'CONFIG',Path(tmp)/'weather.json'),patch.object(weather,'CACHE',Path(tmp)/'cache'):
            for scenario in ('escape','outside','toggle'):
                ui=Example(scenario)
                ui.run([])
                assert ui.window is None
                print('PASS GTK:',scenario,flush=True)
    finally:
        pointer.close()
        subprocess.run(['hyprctl','dispatch','movecursor',f"{cursor['x']} {cursor['y']}"],stdout=subprocess.DEVNULL)
    assert not failures,failures
    print('PASS refresh, location editor, offline/empty states, compact width, Escape, outside click, repeated activation')

if __name__=='__main__':main()
