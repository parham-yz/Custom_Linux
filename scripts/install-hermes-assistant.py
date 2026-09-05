#!/usr/bin/env python3
"""Install the Hermes desktop integration; preserve the existing coding sandbox."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = ['.local/bin/obsidian-hermes','.config/hypr/hermes.conf',
         '.config/systemd/user/obsidian-hermes.service','.config/systemd/user/obsidian-hermes-gateway.service',
         '.config/systemd/user/obsidian-hermes-health.service','.config/systemd/user/obsidian-hermes-health.timer',
         '.config/hypr/hyprland.conf','.config/waybar/config','.config/waybar/style.css','.local/bin/obsidian-menu',
         '.local/bin/obsidian-keybindings']
FILES += [str(p.relative_to(ROOT/'dotfiles')) for p in (ROOT/'dotfiles/.local/share/obsidian-hermes').rglob('*') if p.is_file() and '__pycache__' not in p.parts]


def private_write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:f.write(data)
    path.chmod(0o600)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    home=Path.home()
    if any(os.environ.get(k) and Path(os.environ[k]) != home/v for k,v in (
        ('XDG_CONFIG_HOME','.config'),('XDG_DATA_HOME','.local/share'),('XDG_STATE_HOME','.local/state'))):
        parser.error('This installer targets the default home-directory layout.')
    source_home=home/'.local/share/hermes-safe/data'
    receipt_path=home/'.local/state/obsidian-hermes/installed-files.json'
    receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    if not (source_home/'auth.json').is_file():
        parser.error('The existing Hermes provider login was not found. Set up Hermes first.')
    for rel in FILES:
        target=home/rel
        if target.exists() and target.read_bytes()!=(ROOT/'dotfiles'/rel).read_bytes():
            if hashlib.sha256(target.read_bytes()).hexdigest()==receipt.get(rel):
                continue
            previous=subprocess.run(['git','show','HEAD:dotfiles/'+rel],cwd=ROOT,capture_output=True)
            if previous.returncode or target.read_bytes()!=previous.stdout:
                parser.error(f'Local edits need merging: {target}. No files changed.')
    print(f'{"Install" if args.apply else "Would install"} {len(FILES)} files; reuse provider login and profile; enable desktop startup.')
    if not args.apply:return
    import yaml
    source_config=yaml.safe_load((source_home/'config.yaml').read_text())
    backup=home/'.local/state/custom-linux-backups'/('hermes-assistant-'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir(parents=True,mode=0o700)
    for rel in FILES:
        target=home/rel
        if target.is_file():
            destination=backup/rel;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,destination)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'dotfiles'/rel,target)
    data_root=home/'.local/share/obsidian-hermes';data=data_root/'hermes';workspace=data_root/'workspace'
    for p in (data,workspace,data/'home',data/'memories',home/'.config/obsidian-hermes'):
        p.mkdir(parents=True,exist_ok=True,mode=0o700);p.chmod(0o700)
    config_path=home/'.config/obsidian-hermes/config.json'
    if not config_path.exists():
        config={'gateway_key':secrets.token_urlsafe(36),'desktop_key':secrets.token_urlsafe(36)}
        private_write(config_path,json.dumps(config))
    else:config=json.loads(config_path.read_text())
    private_write(config_path.parent/'gateway.env', 'API_SERVER_ENABLED=true\nAPI_SERVER_HOST=0.0.0.0\nAPI_SERVER_PORT=8642\nAPI_SERVER_KEY='+config['gateway_key']+'\nEMAIL_ENABLED=false\nWHATSAPP_ENABLED=false\n')
    if not (data/'auth.json').exists():
        shutil.copy2(source_home/'auth.json',data/'auth.json');(data/'auth.json').chmod(0o600)
    # Use a separate native Hermes home: no SMTP/IMAP secrets, messaging channels,
    # legacy cron jobs, or transcripts are imported into this new assistant.
    if not (data/'config.yaml').exists():
        cfg={'model':source_config['model'], 'agent':{'max_turns':30},
             'terminal':{'backend':'local','cwd':'/workspace'},
             'platform_toolsets':{'api_server':['memory','session_search','cronjob','file','todo','clarify','web'],
                                 'cron':['memory','session_search','file','todo']},
             'web':{'backend':'firecrawl','use_gateway':False},
             'security':{'redact_secrets':True},'display':{'tool_progress':True}}
        private_write(data/'config.yaml',yaml.safe_dump(cfg,sort_keys=False))
    for name in ('USER.md','MEMORY.md'):
        src=source_home/'memories'/name;dest=data/'memories'/name
        if src.is_file() and not dest.exists():shutil.copy2(src,dest);dest.chmod(0o600)
    src=home/'.local/share/hermes-safe/workspace/PARHAM_PROFILE.md'
    if src.is_file() and not (workspace/src.name).exists():
        shutil.copy2(src,workspace/src.name);(workspace/src.name).chmod(0o600)
    if not (workspace/'AGENTS.md').exists():
        private_write(workspace/'AGENTS.md',(data_root/'templates/ASSISTANT.md').read_text())
    private_write(receipt_path,json.dumps({rel:hashlib.sha256((ROOT/'dotfiles'/rel).read_bytes()).hexdigest() for rel in FILES},indent=2))
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable','--now','obsidian-hermes.service','obsidian-hermes-gateway.service'],check=True)
    subprocess.run(['systemctl','--user','restart','obsidian-hermes.service'],check=True)
    subprocess.run([str(home/'.local/bin/obsidian-hermes'),'health'],check=True)
    subprocess.run(['systemctl','--user','enable','--now','obsidian-hermes-health.timer'],check=True)
    subprocess.run(['hyprctl','reload'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['pkill','-SIGUSR2','waybar'],check=False)
    print('Backup:',backup)
    print('Hermes starts at login. Open it with Super+Ctrl+Shift+H.')


if __name__=='__main__':main()
