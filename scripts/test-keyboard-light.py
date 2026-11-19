#!/usr/bin/env python3
"""Verify ambient keyboard light, manual overrides, idle, and screen-hold isolation."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
loader=importlib.machinery.SourceFileLoader('keyboard_light',str(ROOT/'dotfiles/.local/bin/obsidian-keyboard-light'))
spec=importlib.util.spec_from_loader(loader.name,loader)
k=importlib.util.module_from_spec(spec);loader.exec_module(k)


def main():
    assert [k.target_for_lux(n) for n in (0,5,20,60,120,1000)]==[60,50,30,12,0,0]
    assert all(k.target_for_lux(n)>=k.target_for_lux(n+1) for n in range(150))
    for bad in (-1,float('nan'),float('inf')):
        try:k.target_for_lux(bad)
        except ValueError:pass
        else:raise AssertionError('Invalid sensor reading accepted')
    with tempfile.TemporaryDirectory(prefix='keyboard-light-test-') as directory:
        base=Path(directory);k.STATE=base/'state';k.RUNTIME=base/'runtime/obsidian-keyboard-light'
        k.LED=base/'led';k.LED.mkdir();(k.LED/'brightness').write_text('0');(k.LED/'max_brightness').write_text('100')
        sensor=base/'iio/iio:device0';sensor.mkdir(parents=True)
        (sensor/'name').write_text('aop-sensors-als');(sensor/'in_illuminance_input').write_text('20')
        display=base/'runtime/obsidian-ember-auto-brightness';display.mkdir(parents=True)
        (display/'hold-until').write_text('9999999999')
        with patch.dict(os.environ,{'OBSIDIAN_IIO_ROOT':str(base/'iio'),'XDG_RUNTIME_DIR':str(base/'runtime')}):
            assert k.ambient_lux()==20, 'Screen hold blocked the shared light sensor'
        changes=[]
        def write(value):
            changes.append(value);(k.LED/'brightness').write_text(str(value))
        lux=[0]
        k.write_brightness=write;k.ambient_lux=lambda:lux[0]
        controller=k.Controller()
        for _ in range(10):controller.tick(now=1000)
        assert k.brightness()==60
        assert all(abs(b-a)<=8 for a,b in zip([0]+changes,changes))
        lux[0]=1000
        for _ in range(30):controller.tick(now=1000)
        assert k.brightness()==0
        print('PASS dark-to-bright transitions, smooth steps, and independence from the display hold')
        with patch.object(k.time,'time',return_value=1000), patch.object(k.subprocess,'run'):
            k.control('up')
            assert k.brightness()==10
            k.Controller().tick(now=1119)
            assert k.brightness()==10, 'Daemon restart overwrote the manual adjustment'
            k.control('idle');assert k.brightness()==0
            k.control('active');assert k.brightness()==10
            k.Controller().tick(now=1120)
            assert k.brightness()<10, 'Automatic light did not resume after the manual pause'
            lux[0]=0
            k.control('enable');assert k.brightness()==60
            k.control('idle');assert k.brightness()==0
            k.control('active');assert k.brightness()==60
            k.control('disable');lux[0]=1000;k.Controller().tick(now=2000)
            assert k.brightness()==60, 'Disabled automation changed the keyboard light'
        print('PASS manual override expiry, persistence across restart, idle off/resume, and disable control')
    print('Keyboard light tests passed without changing the real keyboard.')


if __name__=='__main__':main()
