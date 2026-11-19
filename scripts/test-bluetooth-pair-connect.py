#!/usr/bin/env python3
"""Exercise menu pairing and reconnect commands with persistent fake BlueZ state."""
import os
from pathlib import Path
import subprocess
import tempfile
import time

SCRIPT = Path(__file__).resolve().parents[1] / 'dotfiles/.local/bin/obsidian-bluetooth'
MAC = 'AA:BB:CC:DD:EE:01'


def run_case(paired=False, pair_ok=True, connect_ok=True, menu=False, action='connect'):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / 'bin').mkdir()
        (root / 'runtime').mkdir()
        (root / 'paired').write_text('yes' if paired else 'no')
        (root / 'connected').write_text('no')
        mocks = {
            'systemctl': '#!/bin/sh\nexit 0\n',
            'notify-send': '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE/notices"\n',
            'rofi': '''#!/usr/bin/env python3
import os, pathlib, sys
p = pathlib.Path(os.environ['FIXTURE']) / 'menus'
count = int(p.read_text()) if p.exists() else 0
p.write_text(str(count + 1))
sys.stdin.read()
if count == 0: print('0')
elif count == 1: print('Pair, Trust and Connect')
else: print('Cancel')
''',
            'bluetoothctl': '''#!/usr/bin/env python3
import os, pathlib, sys
p = pathlib.Path(os.environ['FIXTURE'])
a = sys.argv[1:]
with (p/'commands').open('a') as f: f.write(' '.join(a)+'\\n')
cmd = next((x for x in a if x in ('list','show','devices','info','pair','trust','connect')), '')
if cmd == 'list': print('Controller 11:22:33:44:55:66 fixture')
elif cmd == 'show': print('Controller 11:22:33:44:55:66 fixture\\nPowered: yes')
elif cmd == 'devices': print('Device AA:BB:CC:DD:EE:01 Fixture Headphones')
elif cmd == 'info':
    print('Device AA:BB:CC:DD:EE:01\\nName: Fixture Headphones\\nAlias: Fixture Headphones\\nIcon: audio-headset\\nTrusted: yes')
    print('Paired: '+(p/'paired').read_text()+'\\nConnected: '+(p/'connected').read_text())
elif cmd == 'pair' and os.environ['PAIR_OK'] == '1':
    (p/'paired').write_text('yes')
    (p/'connected').write_text('yes')  # Temporary pairing link is not audio.
elif cmd == 'connect' and os.environ['CONNECT_OK'] == '1':
    (p/'connected').write_text('yes')
''',
        }
        for name, body in mocks.items():
            path = root / 'bin' / name
            path.write_text(body)
            path.chmod(0o755)
        env = dict(os.environ, FIXTURE=str(root), PAIR_OK=str(int(pair_ok)),
                   CONNECT_OK=str(int(connect_ok)), XDG_RUNTIME_DIR=str(root/'runtime'),
                   XDG_DATA_HOME=str(root/'data'),
                   PATH=str(root/'bin')+':/usr/bin:/bin')
        start = time.monotonic()
        result = subprocess.run(['bash', str(SCRIPT)] + ([] if menu else ['--' + action, MAC]),
                                env=env, capture_output=True, text=True, timeout=5)
        commands = (root/'commands').read_text() if (root/'commands').exists() else ''
        notices = (root/'notices').read_text() if (root/'notices').exists() else ''
        assert '--timeout' not in commands, commands
        assert time.monotonic() - start < 5
        return result, commands, notices


result, commands, notices = run_case(menu=True)
assert result.returncode == 0, result.stderr
assert 'pair '+MAC in commands and 'connect '+MAC in commands, commands
assert 'Bluetooth connected' in notices, notices
print('PASS: pairing explicitly connects profiles even when the temporary link is already connected')

result, commands, notices = run_case(menu=True, pair_ok=False)
assert 'connect '+MAC not in commands and 'trust '+MAC not in commands, commands
assert 'Bluetooth connected' not in notices, notices
print('PASS: successful command exit without a pairing bond is rejected')

result, commands, notices = run_case(paired=True)
assert result.returncode == 0 and 'connect '+MAC in commands, (result, commands)
assert 'pair '+MAC not in commands, commands
print('PASS: a paired headset reconnects without deleting its pairing')

result, commands, notices = run_case(paired=True, connect_ok=False)
assert result.returncode != 0 and 'Could not connect' in notices, (result, notices)
assert 'Bluetooth connected' not in notices, notices
print('PASS: successful command exit while disconnected is reported as failure')

result, commands, notices = run_case(action='pair')
assert result.returncode == 0 and 'pair '+MAC in commands and 'connect '+MAC in commands, (result, commands)
print('PASS: native panel pairing uses the verified pair-and-connect path')

result, commands, notices = run_case(action='pair', pair_ok=False)
assert result.returncode != 0 and 'connect '+MAC not in commands, (result, commands)
assert 'rejected pairing' in result.stderr
print('PASS: native panel receives a pairing error without opening a second menu')
