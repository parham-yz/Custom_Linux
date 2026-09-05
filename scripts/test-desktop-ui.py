#!/usr/bin/env python3
"""Exercise menu, recording, reminder, clipboard and status behavior in isolation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'dotfiles/.local/bin'
MOCK = r'''#!/usr/bin/env python3
import json, os, sys, time, signal
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
base = Path(os.environ['UI_FIXTURE'])
with (base/'calls').open('a') as out: out.write(json.dumps([name,*args])+'\n')
if name == 'rofi':
    content=sys.stdin.read()
    with (base/'menus').open('a') as out: out.write(json.dumps({'args':args,'input':content})+'\n')
    counter=base/'counter'; i=int(counter.read_text()) if counter.exists() else 0; counter.write_text(str(i+1))
    replies=json.loads(os.environ.get('UI_REPLIES','[]'))
    if i >= len(replies) or replies[i] is None: sys.exit(1)
    print(replies[i])
elif name == 'systemctl':
    if 'stop' in args and os.environ.get('UI_STOP_FAIL') == '1': sys.exit(1)
    if 'list-units' in args: print('obsidian-reminder-123.timer loaded active waiting fixture')
    elif 'is-active' in args: print('active')
elif name == 'hyprctl':
    if args[0] == 'getoption': print(json.dumps({'int':10} if 'rounding' in args[1] else {'custom':'4 4 4 4'}))
    elif args[0] == 'activewindow': print('{}')
elif name == 'makoctl': print('default\ndo-not-disturb' if os.environ.get('UI_DND') == '1' else 'default')
elif name == 'busctl': print('s "balanced"')
elif name == 'wl-copy': (base/'copied').write_text(sys.stdin.read())
elif name == 'wpctl' and args[0] == 'get-volume': print('Volume: 0.40 [MUTED]')
elif name == 'wf-recorder':
    if os.environ.get('UI_RECORD_FAIL') == '1': sys.exit(3)
    Path(args[args.index('-f')+1]).write_bytes(b'fixture video')
    signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
    while True: time.sleep(.1)
elif name == 'curl': sys.exit(22)
'''


def main():
    with tempfile.TemporaryDirectory(prefix='obsidian-ui-tests-') as directory:
        fixture = Path(directory)
        home = fixture / 'home'
        home.mkdir()
        mock = fixture / 'bin'
        mock.mkdir()
        for name in ('rofi','systemctl','systemd-run','notify-send','hyprctl','makoctl','busctl','wl-copy','wtype','wpctl','wf-recorder','curl','pkill','pgrep','swaylock'):
            path = mock / name
            path.write_text(MOCK)
            path.chmod(0o755)
        shutil.copytree(ROOT / 'dotfiles/.config/obsidian-ember', home / '.config/obsidian-ember')
        state = home / '.local/state/obsidian-ember'
        state.mkdir(parents=True)
        (state / 'current-theme').write_text('moss-stone\n')
        env = os.environ | {'HOME':str(home),'XDG_STATE_HOME':str(home/'.local/state'),'XDG_CONFIG_HOME':str(home/'.config'),
                            'XDG_CACHE_HOME':str(home/'.cache'),'XDG_RUNTIME_DIR':str(fixture),
                            'PATH':f'{mock}:{BIN}:/usr/bin:/bin','UI_FIXTURE':str(fixture)}
        def run(name, *args, replies=(), extra=None, input=None, expected=0):
            for file in ('calls','menus','counter'):
                (fixture / file).unlink(missing_ok=True)
            result = subprocess.run([str(BIN/name),*args], env=env | {'UI_REPLIES':json.dumps(replies)} | (extra or {}),
                                    capture_output=True,text=True,input=input,timeout=20)
            assert result.returncode == expected, (name,args,result.returncode,result.stderr)
            calls = [json.loads(line) for line in (fixture/'calls').read_text().splitlines()] if (fixture/'calls').exists() else []
            menus = [json.loads(line) for line in (fixture/'menus').read_text().splitlines()] if (fixture/'menus').exists() else []
            return result, calls, menus
        _, calls, _ = run('obsidian-menu', replies=['unlisted Reboot'])
        assert not any(c[0] == 'systemctl' for c in calls)
        _, _, menus = run('obsidian-menu','style',replies=['󰁍  Back',None])
        assert len(menus) == 2 and ' OMA ' in menus[-1]['args']
        _, calls, _ = run('obsidian-menu','system',replies=['󰜉  Reboot','Cancel'])
        assert not any('reboot' in c for c in calls)
        print('PASS menu membership, Back, Escape and cancelled power action')

        run('obsidian-theme','switch')
        result, _, _ = run('obsidian-theme','color','BG')
        assert result.stdout.strip() == '191d1b'
        result, _, _ = run('obsidian-theme','name')
        assert result.stdout.strip() == 'Moss Stone'
        _, calls, _ = run('obsidian-lock')
        lock = next(c for c in calls if c[0] == 'swaylock')
        assert lock[lock.index('--color')+1] == '191d1b'
        assert '--ring-wrong-color' in lock and '--text-ver-color' in lock
        print('PASS theme cancellation and active palette lookup')

        _, calls, _ = run('obsidian-reminder','set',replies=['08','Stretch'])
        assert any('--on-active=8m' in c for c in calls)
        _, calls, _ = run('obsidian-reminder','clear',replies=['Clear reminders'])
        assert ['systemctl','--user','stop','obsidian-reminder-123.timer','obsidian-reminder-123.service'] in calls
        _, calls, _ = run('obsidian-reminder','clear',replies=['Clear reminders'],extra={'UI_STOP_FAIL':'1'},expected=1)
        assert not any('All reminders cleared' in c for c in calls)
        print('PASS decimal reminder duration and real timer cancellation')

        history = state / 'clipboard'
        history.mkdir()
        (history/'watch.pid').write_text('12345')
        (history/'1-test.txt').write_text('A useful note')
        _, _, menus = run('obsidian-clipboard','open')
        assert '12345' not in menus[0]['input'] and 'A useful note' in menus[0]['input']
        run('obsidian-clipboard','clear')
        assert (history/'watch.pid').exists() and not (history/'1-test.txt').exists()
        print('PASS clipboard excludes and preserves watcher state')

        run('obsidian-toggle','gaps')
        _, calls, _ = run('obsidian-toggle','gaps')
        assert ['hyprctl','keyword','general:gaps_in','4 4 4 4'] in calls
        assert ['hyprctl','keyword','general:gaps_out','4 4 4 4'] in calls
        print('PASS gap toggle restores observed dimensions')

        _, calls, _ = run('obsidian-osd','volume-mute')
        notices = [c for c in calls if c[0] == 'notify-send']
        assert notices and 'Obsidian OSD' in notices[0] and notices[0][-1] == 'Muted'
        result, _, _ = run('obsidian-weather','bar')
        assert json.loads(result.stdout)['class'] == 'empty'
        print('PASS readable mute OSD and valid offline weather state')

        _, calls, _ = run('obsidian-record','start-screen','silent',extra={'UI_RECORD_FAIL':'1'},expected=1)
        assert not any('Recording started' in c for c in calls)
        assert not (state/'recording/pid').exists()
        run('obsidian-record','start-screen','silent')
        try:
            result, _, _ = run('obsidian-record','status')
            assert result.stdout.strip() == 'recording'
            run('obsidian-record','menu')
            run('obsidian-record','status')
            result, _, _ = run('obsidian-status','bar',extra={'UI_DND':'1'})
            status = json.loads(result.stdout)
            assert status['class'] == 'recording' and 'REC' in status['text'] and 'disturb' in status['tooltip']
        finally:
            _, calls, _ = run('obsidian-record','stop')
        assert any('Recording saved' in c for c in calls)
        run('obsidian-record','status',expected=1)
        print('PASS recorder startup failure, menu cancellation, status indicator and verified stop')
        print('Desktop interaction checks passed without changing the live session.')


if __name__ == '__main__':
    main()
