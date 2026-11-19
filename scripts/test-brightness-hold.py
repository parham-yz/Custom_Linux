#!/usr/bin/env python3
"""Verify the real brightness daemon with a simulated clock and backlight."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'dotfiles/.local/bin/obsidian-auto-brightness'
MOCK='''#!/usr/bin/python3
import os,sys
from pathlib import Path
root=Path(os.environ['HOLD_FIXTURE'])
name=Path(sys.argv[0]).name
if name=='date':print((root/'clock').read_text().strip())
elif name=='brightnessctl':
 if 'set' in sys.argv:
  with (root/'changes').open('a') as f:f.write(sys.argv[-1]+'\\n')
 else:print('apple-panel-bl,backlight,400,40%,1000')
'''


def main():
    with tempfile.TemporaryDirectory(prefix='brightness-hold-test-') as directory:
        base=Path(directory);mock=base/'bin';mock.mkdir()
        for name in ('date','brightnessctl','notify-send'):
            file=mock/name;file.write_text(MOCK);file.chmod(0o755)
        sensor=base/'iio/iio:device0';sensor.mkdir(parents=True)
        (sensor/'name').write_text('aop-sensors-als')
        (sensor/'in_illuminance_input').write_text('1000')
        (base/'ac').write_text('1');(base/'clock').write_text('10000')
        env=os.environ | {'PATH':str(mock)+':'+os.environ['PATH'],'HOLD_FIXTURE':str(base),
                          'XDG_STATE_HOME':str(base/'state'),'XDG_RUNTIME_DIR':str(base/'runtime'),
                          'OBSIDIAN_IIO_ROOT':str(base/'iio'),'OBSIDIAN_AC_ONLINE_PATH':str(base/'ac'),
                          'OBSIDIAN_AUTO_BRIGHTNESS_POLL_SECONDS':'0.05'}
        def run(*args):
            return subprocess.run([str(SCRIPT),*args],env=env,check=True,capture_output=True,text=True,timeout=5).stdout
        run('hold-toggle')
        deadline=base/'runtime/obsidian-ember-auto-brightness/hold-until'
        assert deadline.read_text().strip()=='13600'
        assert json.loads(run('bar'))['class']=='held'
        assert '60m' in json.loads(run('bar'))['text']
        assert not (base/'changes').exists(), 'Starting a hold changed the current brightness'
        run('pause','120')
        run('once')
        assert not (base/'changes').exists(), 'Manual-key pause shortened the hour hold'
        daemon=subprocess.Popen([str(SCRIPT),'daemon'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            time.sleep(.25)
            assert daemon.poll() is None
            assert not (base/'changes').exists(), 'Daemon adjusted brightness during the hold'
            (base/'clock').write_text('13599')
            assert '1m' in json.loads(run('bar'))['text']
            (base/'clock').write_text('13600')
            for _ in range(50):
                if (base/'changes').exists():break
                time.sleep(.05)
            assert (base/'changes').exists(), 'Daemon did not resume when the hour expired'
            assert json.loads(run('bar'))['class']=='automatic'
        finally:
            daemon.terminate();daemon.communicate(timeout=3)
        print('PASS one-hour deadline, unchanged brightness while held, countdown, and automatic daemon resumption')
        run('hold-toggle');assert json.loads(run('bar'))['class']=='held'
        run('hold-toggle');assert json.loads(run('bar'))['class']=='automatic'
        run('disable');run('hold-toggle')
        assert json.loads(run('bar'))['class']=='disabled'
        assert not deadline.exists(), 'Hold enabled an explicitly disabled brightness controller'
        print('PASS early resume, manual-key pause isolation, and disabled-mode preservation')


if __name__=='__main__':main()
