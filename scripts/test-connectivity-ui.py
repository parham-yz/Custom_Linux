#!/usr/bin/env python3
"""Opt-in live Rofi mouse/keyboard regression checks with mocked radio commands.

Uses the compositor's virtual-pointer protocol; no packages or input daemon needed.
Only example panels open. Network, Bluetooth, and settings actions are mocked.
"""
import argparse
import json
from pathlib import Path
import shutil
import signal
import subprocess as sp
import tempfile
import os, socket, struct, time
class Pointer:
    def __init__(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.connect(os.path.join(os.environ['XDG_RUNTIME_DIR'],os.environ['WAYLAND_DISPLAY']))
        self.sock.settimeout(2);self.buffer=b''
        self.send(1,1,struct.pack('=I',2))
        self.send(1,0,struct.pack('=I',3))
        name=None
        while True:
            while len(self.buffer)<8:self.buffer+=self.sock.recv(65536)
            obj,word=struct.unpack('=II',self.buffer[:8]);length=word>>16;op=word&65535
            while len(self.buffer)<length:self.buffer+=self.sock.recv(65536)
            data=self.buffer[8:length];self.buffer=self.buffer[length:]
            if obj==2 and op==0:
                ident,n=struct.unpack('=II',data[:8]);interface=data[8:8+n-1].decode()
                if interface=='zwlr_virtual_pointer_manager_v1':name=ident
            if obj==3:break
        if name is None:raise RuntimeError('Compositor has no virtual pointer protocol')
        interface=b'zwlr_virtual_pointer_manager_v1\0'
        wire=struct.pack('=II',name,len(interface))+interface+b'\0'*((-len(interface))%4)+struct.pack('=II',1,4)
        self.send(2,0,wire);self.send(4,0,struct.pack('=II',0,5));time.sleep(.1)
    def send(self,obj,opcode,data=b''):
        self.sock.sendall(struct.pack('=II',obj,((len(data)+8)<<16)|opcode)+data)
    def click(self):
        for state in (1,0):
            self.send(5,2,struct.pack('=III',int(time.monotonic()*1000)&0xffffffff,272,state))
            self.send(5,4);time.sleep(.05)
    def close(self):self.sock.close()

ROOT = Path(__file__).resolve().parents[1]
MOCK = r"""#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
name=Path(sys.argv[0]).name; args=sys.argv[1:]
with open(os.environ['PANEL_CALLS'],'a') as f:f.write(json.dumps([name,*args])+'\n')
if name=='bluetoothctl' and '--timeout' in args:
    time.sleep(float(args[args.index('--timeout')+1]))
    args=args[2:]
if name=='nmcli':
    if 'DEVICE,TYPE' in args:print('wlan0:wifi')
    elif args==['networking'] or 'WIFI-HW' in args:print('enabled')
    elif 'WIFI' in args:print('disabled')
elif name=='bluetoothctl':
    if args==['list']:print('Controller 11:22:33:44:55:66 Example adapter')
    elif args==['show']:print('Controller 11:22:33:44:55:66\nPowered: no')
"""

def layers():
    return [x for m in json.loads(sp.check_output(['hyprctl','layers','-j'])).values()
            for group in m['levels'].values() for x in group if x.get('namespace')=='rofi']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-desktop',action='store_true',help='Allow temporary example menus and pointer movement')
    parser.add_argument('--theme',type=Path,help='Alternate theme for reproducing the old bug')
    args=parser.parse_args()
    if not args.live_desktop:parser.error('Use --live-desktop in an idle Hyprland session')
    if layers():parser.error('An existing Rofi menu is open; close it before testing')
    monitor=next(m for m in json.loads(sp.check_output(['hyprctl','monitors','-j'])) if m['focused'])
    width=round(monitor['width']/monitor['scale']);height=round(monitor['height']/monitor['scale'])
    if width<1000 or height<700:parser.error('This layout check needs at least 1000x700 logical pixels')
    cursor=json.loads(sp.check_output(['hyprctl','cursorpos','-j']))
    pointer=Pointer()
    def move(x,y):
        sp.run(['hyprctl','dispatch','movecursor',f'{monitor["x"]+x} {monitor["y"]+y}'],check=True,stdout=sp.DEVNULL)
        time.sleep(.08)
    def click(x,y):move(x,y);pointer.click();time.sleep(.15)
    def key(name):sp.run(['wtype','-k',name],check=True);time.sleep(.15)
    try:
        with tempfile.TemporaryDirectory(prefix='obsidian-connectivity-ui-') as tmp:
            home=Path(tmp);mock=home/'bin';mock.mkdir();runtime=home/'runtime';runtime.mkdir()
            cfg=home/'.config';shutil.copytree(ROOT/'dotfiles/.config/rofi',cfg/'rofi')
            shutil.copytree(ROOT/'dotfiles/.config/obsidian-ember/current',cfg/'obsidian-ember/current')
            if args.theme:shutil.copy2(args.theme,cfg/'rofi/network.rasi')
            for name in ('nmcli','bluetoothctl','systemctl','notify-send','nm-connection-editor','pavucontrol'):
                p=mock/name;p.write_text(MOCK);p.chmod(0o755)
            calls=home/'calls'
            env=os.environ|{'HOME':tmp,'XDG_CONFIG_HOME':str(cfg),'XDG_RUNTIME_DIR':str(runtime),
                'WAYLAND_DISPLAY':os.path.join(os.environ['XDG_RUNTIME_DIR'],os.environ['WAYLAND_DISPLAY']),
                'PATH':f'{mock}:{ROOT}/dotfiles/.local/bin:'+os.environ['PATH'],'PANEL_CALLS':str(calls)}
            for name,query,settings in (('obsidian-network','Network Settings','nm-connection-editor'),
                                         ('obsidian-bluetooth','Audio Settings','pavucontrol')):
                for action in ('outside-top','outside-left','outside-right','outside-bottom','escape','search-click','keyboard','repeat-icon'):
                    calls.write_text('')
                    p=sp.Popen([str(ROOT/'dotfiles/.local/bin'/name)],env=env,start_new_session=True,stdout=sp.DEVNULL,stderr=sp.DEVNULL)
                    try:
                        deadline=time.monotonic()+3
                        while not layers() and p.poll() is None and time.monotonic()<deadline:time.sleep(.05)
                        assert layers(),f'{name}: panel failed to open within 3 seconds'
                        time.sleep(.35)
                        if action.startswith('outside'):
                            point={'outside-top':(width/2,16),'outside-left':(20,height/2),
                                   'outside-right':(width-3,100),'outside-bottom':(width-200,height-20)}[action]
                            click(*map(round,point))
                        elif action=='escape':key('Escape')
                        elif action in ('search-click','keyboard'):
                            # Clicking the search entry must not dismiss the panel.
                            click(width-300,80)
                            assert layers(),f'{name}: clicking inside dismissed the panel'
                            sp.run(['wtype',query],check=True);time.sleep(.15)
                            if action=='keyboard':key('Return')
                            else:click(width-300,174)
                        else:
                            sp.run([str(ROOT/'dotfiles/.local/bin'/name)],env=env,check=True,timeout=3)
                        try:p.wait(timeout=2)
                        except sp.TimeoutExpired:raise AssertionError(f'{name}: {action} did not close the menu')
                        assert not layers(),f'{name}: {action} left a menu open'
                        log=[json.loads(line) for line in calls.read_text().splitlines()]
                        selected=any(c[0]==settings for c in log)
                        assert selected==(action in ('search-click','keyboard')),(name,action,'wrong selected action')
                        assert not any(c[0]=='nmcli' and ('on' in c or 'off' in c) for c in log),'Unexpected Wi-Fi toggle'
                        assert not any(c[0]=='bluetoothctl' and 'power' in c for c in log),'Unexpected Bluetooth toggle'
                        assert not (runtime/'obsidian-network-rofi.pid').exists() and not list(runtime.glob('obsidian-bluetooth-*/rofi.pid')),f'{name}: stale panel PID after {action}'
                        print(f'PASS {name}: {action}',flush=True)
                    finally:
                        if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
                        p.wait();time.sleep(.15)
    finally:
        pointer.close()
        sp.run(['hyprctl','dispatch','movecursor',f'{cursor["x"]} {cursor["y"]}'],stdout=sp.DEVNULL)
    print('Native connectivity UI checks passed; all radio actions were mocked.')

if __name__=='__main__':main()
