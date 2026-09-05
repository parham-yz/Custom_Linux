#!/usr/bin/env python3
"""Local desktop companion for Hermes's native gateway, memory, and cron."""
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import html
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

HOME = Path.home()
ROOT = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share')) / 'obsidian-hermes'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config')) / 'obsidian-hermes/config.json'
STATE_FILE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) / 'obsidian-hermes/desktop.json'
DATA = ROOT / 'hermes'
CONTAINER = 'obsidian-hermes'
PORT = 8765
API = 'http://127.0.0.1:8766'
IMAGE = 'docker.io/nousresearch/hermes-agent@sha256:ef58f7f6906a19ca4d7d77bb35711f3a9740c83c8eac692b9c038e13f27e09d5'
LOCK = threading.RLock()
CHAT_LOCK = threading.Lock()
MODEL_LOCK = threading.Lock()
CONFIG_DATA = {}
STATE = {}
ACTIVE = None


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + '.tmp-' + secrets.token_hex(4))
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(value, out, ensure_ascii=False)
    os.replace(temp, path)


def save():
    with LOCK:
        write_json(STATE_FILE, STATE)


def command(args, timeout=10, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)


def api(path, method='GET', body=None, timeout=12, stream=False):
    req = urllib.request.Request(API + path, method=method,
        headers={'Authorization': 'Bearer ' + CONFIG_DATA['gateway_key'], 'Content-Type': 'application/json'},
        data=None if body is None else json.dumps(body).encode())
    response = urllib.request.urlopen(req, timeout=timeout)
    if stream:
        return response
    with response:
        return json.load(response)


def quiet(now=None):
    now = now or datetime.now(ZoneInfo('Europe/Berlin'))
    return now.hour >= 22 or now.hour < 8


def notify(title, body):
    result = command(['notify-send', '-a', 'Hermes', '--', html.escape(title), html.escape(body[:600])])
    return result.returncode == 0


def output_message(text):
    if '\n## Response\n' in text:
        return text.split('\n## Response\n', 1)[1].strip()
    if '\n---\n' in text:
        return text.split('\n---\n', 1)[1].strip()
    if '**Status:** script failed' in text:
        return 'A scheduled task failed. Open Hermes to review it.'
    return ''


def collect_outputs():
    with LOCK:
        seen = set(STATE.get('seen_outputs', []))
        items = STATE.setdefault('updates', [])
        for path in sorted((DATA / 'cron/output').glob('*/*.md')):
            key = str(path.relative_to(DATA))
            if key in seen:
                continue
            text = path.read_text(errors='replace')
            body = output_message(text)
            seen.add(key)
            if not body or body in ('[SILENT]', '(No response generated)'):
                continue
            title = text.splitlines()[0].removeprefix('# Cron Job: ').strip()
            items.append({'id': hashlib.sha256(key.encode()).hexdigest()[:20], 'title': title,
                          'body': body, 'time': path.stat().st_mtime, 'read': False, 'notified': False})
        STATE['seen_outputs'] = sorted(seen)
        STATE['updates'] = items[-200:]
        save()


def deliver_updates():
    with LOCK:
        if STATE.get('paused') or quiet():
            return
        try:
            if 'do-not-disturb' in command(['makoctl', 'mode'], timeout=2).stdout:
                return
        except (OSError, subprocess.TimeoutExpired):
            return
        pending = [i for i in STATE.get('updates', []) if not i['read'] and not i.get('notified')
                   and i.get('snoozed_until', 0) <= time.time()]
        if not pending:
            return
        title = pending[0]['title'] if len(pending) == 1 else f'{len(pending)} reminders ready'
        body = pending[0]['body'] if len(pending) == 1 else 'Open Hermes to review your reminders and follow-ups.'
        if notify(title, body):
            for item in pending:
                item['notified'] = True
            save()


def watcher():
    while True:
        try:
            collect_outputs()
            deliver_updates()
        except Exception as exc:
            print('Notification check:', type(exc).__name__, flush=True)
        time.sleep(10)


def palette():
    slug = (Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) /
            'obsidian-ember/current-theme')
    name = slug.read_text().strip() if slug.exists() else 'moss-stone'
    if not re.fullmatch('[a-z0-9-]+', name):
        name = 'moss-stone'
    path = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config')) / 'obsidian-ember/themes' / name / 'palette'
    values = dict(re.findall(r'^(\w+)="([^"]+)"', path.read_text() if path.exists() else '', re.M))
    return {key.lower(): '#' + value for key, value in values.items()
            if key in ('BG','PANEL','HOVER','BORDER','TEXT','MUTED','ACCENT','ACCENT2','DANGER','CONTRAST')
            and re.fullmatch('[0-9a-fA-F]{6}', value)}


def history():
    session = STATE.get('session_id')
    if not session:
        return []
    return [m for m in api('/api/sessions/' + session + '/messages').get('data', [])
            if m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str) and m['content'].strip()]


def model_info():
    import yaml
    config = yaml.safe_load((DATA/'config.yaml').read_text())
    model = config.get('model', {})
    return {'provider': model.get('provider', ''), 'selected': model.get('default', '')}


def models(force=False):
    with MODEL_LOCK:
        info = model_info()
        cache_path = STATE_FILE.with_name('models.json')
        cached = read_json(cache_path, {})
        matching = cached.get('provider') == info['provider']
        if not force and matching and time.time() - cached.get('checked_at', 0) < 21600:
            return {**cached, **info}
        result = command(['podman', 'exec', '-i', CONTAINER, '/opt/hermes/.venv/bin/python', '-'],
                         timeout=35, input=(ROOT/'model_catalog.py').read_text())
        if result.returncode:
            if matching:
                return {**cached, **info, 'source': 'cached'}
            raise ValueError('Could not load models. Please refresh after Hermes reconnects.')
        catalog = json.loads(result.stdout)
        ids = [m for m in catalog.get('models', []) if isinstance(m, str)
               and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,199}', m)]
        source = 'live' if catalog.get('live') else 'bundled'
        if not catalog.get('live') and matching:
            ids = cached.get('models', [])
            source = 'cached'
        if info['selected'] not in ids:
            ids.insert(0, info['selected'])
        value = {**info, 'models': list(dict.fromkeys(ids)), 'source': source,
                 'checked_at': time.time(), 'updated_at': time.time() if catalog.get('live') else cached.get('updated_at')}
        write_json(cache_path, value)
        return value


def set_model(selected):
    import yaml
    catalog = models()
    if selected not in catalog['models']:
        raise ValueError('Choose a model from the available list.')
    with MODEL_LOCK, CHAT_LOCK:
        path = DATA/'config.yaml'
        config = yaml.safe_load(path.read_text())
        config['model']['default'] = selected
        temp = path.with_name('config.yaml.desktop-' + secrets.token_hex(4))
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as out:
            yaml.safe_dump(config, out, sort_keys=False)
        os.replace(temp, path)
    return model_info()


def consume_run(run_id):
    global ACTIVE
    try:
        with api('/v1/runs/' + run_id + '/events', stream=True, timeout=600) as response:
            for line in response:
                if not line.startswith(b'data:'):
                    continue
                event = json.loads(line[5:])
                kind = event.get('event')
                with LOCK:
                    if ACTIVE is None or ACTIVE['id'] != run_id:
                        return
                    if kind == 'message.delta':
                        ACTIVE['text'] += event.get('delta', '')
                    elif kind == 'tool.started':
                        ACTIVE['tool'] = event.get('tool', 'Working')
                    elif kind == 'approval.request':
                        ACTIVE['approval'] = event
                        ACTIVE['status'] = 'waiting_for_approval'
                    elif kind == 'run.completed':
                        ACTIVE.update(status='completed', text=event.get('output', ACTIVE['text']), tool='', approval=None)
                    elif kind in ('run.failed', 'run.cancelled'):
                        ACTIVE.update(status='failed' if kind == 'run.failed' else 'cancelled',
                                      error=str(event.get('error', 'Stopped')), tool='', approval=None)
                    STATE['active'] = ACTIVE
                    save()
    except Exception:
        pass
    finally:
        with LOCK:
            if ACTIVE and ACTIVE['id'] == run_id and ACTIVE['status'] not in ('completed','failed','cancelled'):
                ACTIVE['disconnected'] = True
                save()


def start_chat(message):
    global ACTIVE
    message = message.strip()
    if not message or len(message) > 20000:
        raise ValueError('Write a message of up to 20,000 characters.')
    with CHAT_LOCK:
        with LOCK:
            if ACTIVE and ACTIVE['status'] not in ('completed','failed','cancelled'):
                raise ValueError('Hermes is still working. Wait or stop the current response.')
        if not STATE.get('session_id'):
            session = api('/api/sessions', 'POST', {'title': 'Personal assistant'})['session']['id']
            STATE['session_id'] = session
            save()
        messages = [{'role':m['role'],'content':m['content']} for m in history()]
        result = api('/v1/runs', 'POST', {'input':message, 'session_id':STATE['session_id'],
                     'conversation_history':messages, 'instructions':(ROOT/'templates/ASSISTANT.md').read_text()})
        with LOCK:
            ACTIVE = {'id':result['run_id'],'status':'running','text':'','message':message,'approval':None,'tool':''}
            STATE['active'] = ACTIVE
            STATE['introduced'] = True
            save()
        threading.Thread(target=consume_run,args=(result['run_id'],),daemon=True).start()
        return ACTIVE.copy()


def snapshot():
    global ACTIVE
    connected = True
    try:
        jobs = api('/api/jobs?include_disabled=true', timeout=3).get('jobs', [])
        if ACTIVE and ACTIVE.get('disconnected') and ACTIVE['status'] not in ('completed','failed','cancelled'):
            try:
                run = api('/v1/runs/' + ACTIVE['id'], timeout=3)
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                run = {'status':'failed', 'error':'Hermes restarted before finishing. Please send your message again.'}
            with LOCK:
                ACTIVE.update(status=run.get('status',ACTIVE['status']), text=run.get('output') or ACTIVE['text'])
                if ACTIVE['status'] in ('completed','failed','cancelled'):
                    ACTIVE.update(approval=None, tool='', error=run.get('error',''))
                elif ACTIVE['status'] == 'waiting_for_approval' and not ACTIVE.get('approval'):
                    # This Hermes release cannot replay a lost approval detail. Never
                    # display an approval button without the action it would authorize.
                    api('/v1/runs/' + ACTIVE['id'] + '/stop', 'POST', {})
                    ACTIVE.update(status='failed', error='The connection interrupted an approval. Please send your request again to review it.', tool='')
                STATE['active'] = ACTIVE
                save()
    except Exception:
        jobs = []
        connected = False
    with LOCK:
        return {'online':connected,'introduced':STATE.get('introduced',False), 'paused':STATE.get('paused',False),
                'quiet':quiet(), 'palette':palette(), 'active':ACTIVE, 'jobs':jobs,
                'updates':list(reversed(STATE.get('updates',[]))), 'accounts':{'email':False,'calendar':False},
                'model':model_info(), 'monitored':time.time() - read_json(STATE_FILE.with_name('health.json'),{}).get('time',0) < 90}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Conversation bodies and gateway credentials never go into access logs.

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{PORT}',f'localhost:{PORT}')

    def authorized(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie',''))
            supplied = cookie['hermes_desktop'].value
            return hmac.compare_digest(supplied, CONFIG_DATA['desktop_key'])
        except (KeyError, ValueError):
            return False

    def json(self, value, status=200):
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(json.dumps(value,ensure_ascii=False).encode())

    def do_GET(self):
        if not self.valid_host():
            return self.json({'error':'Invalid host'},403)
        try:
            if self.path.startswith('/api/'):
                if not self.authorized():
                    return self.json({'error':'Open Hermes from the desktop icon first.'},403)
                if self.path == '/api/state':
                    return self.json(snapshot())
                if self.path == '/api/messages':
                    return self.json({'messages':history()})
                if self.path == '/api/models':
                    return self.json(models())
                if self.path == '/api/memory':
                    return self.json({name: (DATA/'memories'/name).read_text() if (DATA/'memories'/name).exists() else ''
                                      for name in ('USER.md','MEMORY.md')})
                return self.json({'error':'Not found'},404)
            allowed = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if self.path not in allowed:
                return self.json({'error':'Not found'},404)
            path = ROOT/'ui'/allowed[self.path]
            self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'text/plain')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if self.path == '/':
                self.send_header('Set-Cookie',f"hermes_desktop={CONFIG_DATA['desktop_key']}; HttpOnly; SameSite=Strict; Path=/")
            self.end_headers()
            self.wfile.write(path.read_bytes())
        except Exception:
            self.json({'error':'Hermes is not ready. Check its connection or try again shortly.'},503)

    def do_POST(self):
        if not self.valid_host() or not self.authorized() or self.headers.get('Origin') not in (
                f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'):
            return self.json({'error':'Open this action from Hermes.'},403)
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 65536:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(length))
            if self.path == '/api/models/refresh':
                return self.json(models(force=True))
            if self.path == '/api/model':
                return self.json(set_model(body.get('model')))
            if self.path == '/api/chat':
                return self.json(start_chat(body.get('message','')))
            if self.path == '/api/stop':
                if ACTIVE:
                    return self.json(api('/v1/runs/' + ACTIVE['id'] + '/stop','POST',{}))
                return self.json({})
            if self.path == '/api/approval':
                if not ACTIVE or not ACTIVE.get('approval'):
                    raise ValueError('There is no pending approval.')
                choice = body.get('choice')
                if choice not in ACTIVE['approval'].get('choices',[]):
                    raise ValueError('Unsupported approval choice')
                result = api('/v1/runs/' + ACTIVE['id'] + '/approval','POST',{'choice':choice})
                with LOCK:
                    ACTIVE.update(approval=None,status='running')
                    save()
                return self.json(result)
            if self.path == '/api/pause':
                with LOCK:
                    STATE['paused'] = bool(body.get('paused'))
                    save()
                return self.json({'paused':STATE['paused']})
            if self.path == '/api/reminders':
                text = body.get('text','').strip()
                when = datetime.fromisoformat(body.get('when',''))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=ZoneInfo('Europe/Berlin'))
                if not text or len(text)>500 or when.timestamp()<=time.time():
                    raise ValueError('Enter a reminder and a future time.')
                result = command(['podman','exec','-i',CONTAINER,'/opt/hermes/.venv/bin/python',
                                  '/desktop/cron_bridge.py'],timeout=30,
                                 input=json.dumps({'text':text,'schedule':when.isoformat()}))
                if result.returncode:
                    raise ValueError('Hermes could not schedule this reminder. Try again.')
                return self.json(json.loads(result.stdout))
            if self.path == '/api/job':
                job = body.get('id','')
                action = body.get('action')
                if not re.fullmatch('[a-zA-Z0-9_-]+',job) or action not in ('pause','resume','delete'):
                    raise ValueError('Invalid task action')
                return self.json(api('/api/jobs/'+job+('' if action=='delete' else '/'+action),
                                     'DELETE' if action=='delete' else 'POST',{}))
            if self.path == '/api/update':
                with LOCK:
                    item = next((i for i in STATE.get('updates',[]) if i['id']==body.get('id')),None)
                    if item is None:
                        raise ValueError('Reminder not found')
                    if body.get('action') == 'snooze':
                        item.update(snoozed_until=time.time()+86400,notified=False)
                    else:
                        item['read'] = True
                    save()
                return self.json({})
            return self.json({'error':'Not found'},404)
        except (ValueError, TypeError, KeyError) as exc:
            self.json({'error':str(exc)},400)
        except Exception:
            self.json({'error':'Hermes could not complete this action. Check its connection and try again.'},503)


def gateway():
    args = ['podman','run','--rm','--name',CONTAINER,'--pull=never','--network=hermes-firecrawl',
            '--read-only','--userns=keep-id:uid=10000,gid=10000','--user=10000:10000',
            '--cap-drop=all','--security-opt=no-new-privileges','--pids-limit=256','--memory=2g',
            '--cpus=2','--ipc=private','--uts=private','--stop-timeout=15',
            '--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=256m','--tmpfs=/run:rw,noexec,nosuid,nodev,size=64m',
            '--publish=127.0.0.1:8766:8642','--env-file='+str(CONFIG.parent/'gateway.env'),
            '--env=HOME=/opt/data/home','--env=HERMES_HOME=/opt/data','--env=TZ=Europe/Berlin',
            '--env=HERMES_WRITE_SAFE_ROOT=/workspace','--env=PYTHONDONTWRITEBYTECODE=1',
            '--env=PYTHONPATH=/opt/hermes','--env=FIRECRAWL_API_URL=http://api:3002',
            '--volume='+str(DATA)+':/opt/data:Z','--volume='+str(ROOT/'workspace')+':/workspace:Z',
            '--volume='+str(ROOT/'cron_bridge.py')+':/desktop/cron_bridge.py:ro,Z',
            '--workdir=/workspace','--entrypoint=/opt/hermes/.venv/bin/hermes',IMAGE,'gateway','run']
    os.execvp(args[0],args)


def open_space():
    command(['systemctl','--user','start','obsidian-hermes.service'])
    subprocess.Popen(['/usr/bin/python3',str(ROOT/'panel.py')],
                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)


def open_dashboard():
    command(['systemctl','--user','start','obsidian-hermes.service'])
    clients = json.loads(command(['hyprctl','clients','-j']).stdout or '[]')
    if not any(c.get('class')=='org.obsidian.hermes' for c in clients):
        browser = ROOT/'browser'
        browser.mkdir(parents=True,exist_ok=True,mode=0o700)
        subprocess.Popen(['firefox','--no-remote','--profile',str(browser),'--class','org.obsidian.hermes',
                          '--name','org.obsidian.hermes','--new-window',f'http://127.0.0.1:{PORT}'],
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    command(['hyprctl','dispatch','togglespecialworkspace','hermes'])


def main():
    global CONFIG_DATA, STATE, ACTIVE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('serve','gateway','open','dashboard','bar','menu','doctor','health'),nargs='?',default='open')
    args = parser.parse_args()
    CONFIG_DATA = read_json(CONFIG,{})
    STATE = read_json(STATE_FILE,{})
    ACTIVE = STATE.get('active')
    if args.action == 'gateway':
        gateway()
    elif args.action == 'serve':
        if not CONFIG_DATA.get('gateway_key') or not CONFIG_DATA.get('desktop_key'):
            parser.error('Run the desktop Hermes installer first.')
        if ACTIVE and ACTIVE['status'] not in ('completed','failed','cancelled'):
            ACTIVE['disconnected'] = True
        server = ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
        threading.Thread(target=watcher,daemon=True).start()
        server.serve_forever()
    elif args.action == 'open':
        open_space()
    elif args.action == 'dashboard':
        open_dashboard()
    elif args.action == 'health':
        from health import check
        check()
    elif args.action == 'bar':
        from health import inspect
        health = inspect()
        online = health['status'] == 'ready'
        count = sum(not i['read'] and i.get('snoozed_until',0)<=time.time() for i in STATE.get('updates',[]))
        label = '󱚣 ' + ('•' if online else '○') + (f' {count}' if count else '')
        status = ('Running · Alerts paused' if STATE.get('paused') else 'Running') if online else 'Stopped / reconnecting'
        print(json.dumps({'text':label,'class':'offline' if not online else 'attention' if count else 'ready',
                          'tooltip':f'Hermes · {status}\nClick: assistant · Right click: controls\nSuper+Ctrl+Shift+H'}))
    elif args.action == 'menu':
        rows=['Open assistant','Resume alerts' if STATE.get('paused') else 'Pause alerts','Open full view','Coding agents']
        result = command(['rofi','-dmenu','-no-custom','-no-sort','-p','Hermes','-mesg','Your personal assistant'],input='\n'.join(rows))
        choice = result.stdout.strip()
        if result.returncode == 0 and choice == rows[0]:open_space()
        elif result.returncode == 0 and choice == rows[1]:
            # Let the running server own state writes.
            req=urllib.request.Request(f'http://127.0.0.1:{PORT}/api/pause',method='POST',
                headers={'Origin':f'http://127.0.0.1:{PORT}','Cookie':'hermes_desktop='+CONFIG_DATA['desktop_key']},
                data=json.dumps({'paused':not STATE.get('paused')}).encode())
            urllib.request.urlopen(req,timeout=3).close()
        elif result.returncode == 0 and choice == rows[2]:open_dashboard()
        elif result.returncode == 0 and choice == rows[3]:command(['obsidian-menu','agents'],timeout=3600)
    else:
        print('Desktop:', command(['systemctl','--user','is-active','obsidian-hermes.service']).stdout.strip())
        print('Gateway:', command(['systemctl','--user','is-active','obsidian-hermes-gateway.service']).stdout.strip())
        try:
            api('/v1/models',timeout=3)
            print('Authenticated API: ready')
        except Exception:
            print('Authenticated API: unavailable')
        print('Accounts: connection setup deferred')
        print('URL:',f'http://127.0.0.1:{PORT}')


if __name__ == '__main__':
    main()
