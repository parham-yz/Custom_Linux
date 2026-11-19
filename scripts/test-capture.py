#!/usr/bin/env python3
"""Exercise screenshot commands without capturing the desktop or clipboard."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MOCK = '''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
name=Path(sys.argv[0]).name
root=Path(os.environ['CAPTURE_FIXTURE'])
with (root/'calls').open('a') as out:out.write(json.dumps([name,*sys.argv[1:]])+'\\n')
if name=='grim':
 if os.environ.get('FAIL_CAPTURE'):sys.exit(1)
 Path(sys.argv[-1]).write_bytes(b'fixture image')
elif name=='wl-copy':(root/'clipboard').write_bytes(sys.stdin.buffer.read())
elif name=='slurp':
 if os.environ.get('CANCEL_SELECTION'):sys.exit(1)
 print('12,34 100x80')
elif name=='hyprctl':print('{}' if os.environ.get('NO_WINDOW') else json.dumps({'at':[20,30],'size':[200,100]}))
elif name=='obsidian-theme':print('191d1b' if sys.argv[-1]=='BG' else 'b1c59e')
'''


def main():
    with tempfile.TemporaryDirectory(prefix='obsidian-capture-test-') as directory:
        base=Path(directory);mock=base/'bin';mock.mkdir()
        for name in ('grim','wl-copy','slurp','hyprctl','notify-send','obsidian-theme','xdg-open'):
            path=mock/name;path.write_text(MOCK);path.chmod(0o755)
        env=os.environ | {'PATH':str(mock)+':'+os.environ['PATH'],
                          'XDG_PICTURES_DIR':str(base/'pictures'), 'CAPTURE_FIXTURE':str(base)}
        for kind, extra, geometry in [('screen',{},None),('region',{},'12,34 100x80'),
                                      ('window',{},'20,30 200x100'),
                                      ('region',{'CANCEL_SELECTION':'1'},None),
                                      ('window',{'NO_WINDOW':'1'},None)]:
            (base/'calls').unlink(missing_ok=True)
            before=set((base/'pictures/Screenshots').glob('*.png'))
            result=subprocess.run([str(ROOT/'dotfiles/.local/bin/obsidian-capture'),kind],
                                  env=env | extra,capture_output=True,text=True,timeout=5)
            assert result.returncode==0,(kind,result.stderr)
            after=set((base/'pictures/Screenshots').glob('*.png'))
            calls=[json.loads(line) for line in (base/'calls').read_text().splitlines()]
            if extra:
                assert after==before and not any(c[0]=='grim' for c in calls)
            else:
                assert len(after-before)==1
                assert next(iter(after-before)).read_bytes()==(base/'clipboard').read_bytes()
                capture=next(c for c in calls if c[0]=='grim')
                if geometry:assert capture[1:3]==['-g',geometry]
                assert any(c[0]=='notify-send' and 'Screenshot captured' in c for c in calls)
        print('PASS screen, region, and window captures save and copy; cancellation and missing windows do not capture')


if __name__=='__main__':main()
