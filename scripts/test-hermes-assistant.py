#!/usr/bin/env python3
"""Test desktop delivery, recovery state, and local HTTP boundaries in isolation."""
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import types
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('companion',ROOT/'dotfiles/.local/share/obsidian-hermes/app.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


def main():
    zone=ZoneInfo('Europe/Berlin')
    assert a.quiet(datetime(2026,10,25,7,59,tzinfo=zone))
    assert not a.quiet(datetime(2026,10,25,8,tzinfo=zone))
    assert a.quiet(datetime(2026,10,25,22,tzinfo=zone))
    assert a.output_message('# Cron Job: Test\n\n## Prompt\n\nPrivate prompt\n\n## Response\n\nOnly reminder')=='Only reminder'
    assert a.output_message('# Cron Job: Test\n\n---\n\nNo model required')=='No model required'
    print('PASS quiet-hour boundaries and native cron output extraction')
    with tempfile.TemporaryDirectory(prefix='hermes-desktop-test-') as directory:
        base=Path(directory);a.DATA=base/'hermes';a.STATE_FILE=base/'state.json';a.STATE={}
        output=a.DATA/'cron/output/example/run.md';output.parent.mkdir(parents=True)
        output.write_text('# Cron Job: Reminder\n\n---\n\nDo the thing')
        a.collect_outputs();a.collect_outputs()
        assert len(a.STATE['updates'])==1
        a.STATE=a.read_json(a.STATE_FILE,{})
        a.collect_outputs();assert len(a.STATE['updates'])==1
        a.quiet=lambda:False
        a.command=lambda *args,**kwargs:types.SimpleNamespace(stdout='default',returncode=0)
        sent=[];a.notify=lambda title,body:sent.append((title,body)) or True
        a.STATE['paused']=True;a.deliver_updates();assert not sent
        a.STATE['paused']=False
        a.command=lambda *args,**kwargs:types.SimpleNamespace(stdout='do-not-disturb',returncode=0)
        a.deliver_updates();assert not sent
        a.command=lambda *args,**kwargs:types.SimpleNamespace(stdout='default',returncode=0)
        a.deliver_updates();a.deliver_updates();assert len(sent)==1
        a.STATE=a.read_json(a.STATE_FILE,{});a.deliver_updates();assert len(sent)==1
        print('PASS notification deduplication across restart, pause, and Do Not Disturb')
        a.CONFIG_DATA={'desktop_key':'fixture-desktop-key','gateway_key':'fixture-gateway-key'}
        server=a.ThreadingHTTPServer(('127.0.0.1',0),a.Handler);a.PORT=server.server_port
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def post(body,*,origin=True,cookie=True,host=None):
            headers={'Content-Type':'application/json'}
            if origin:headers['Origin']=f'http://127.0.0.1:{a.PORT}'
            if cookie:headers['Cookie']='hermes_desktop=fixture-desktop-key'
            if host:headers['Host']=host
            req=urllib.request.Request(f'http://127.0.0.1:{a.PORT}/api/pause',headers=headers,data=json.dumps(body).encode())
            try:
                with urllib.request.urlopen(req) as r:return r.status,json.load(r)
            except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
        try:
            assert post({'paused':True},origin=False)[0]==403
            assert post({'paused':True},cookie=False)[0]==403
            assert post({'paused':True},host='attacker.example')[0]==403
            status,body=post({'paused':True});assert status==200 and body['paused'] is True
            assert a.read_json(a.STATE_FILE,{})['paused'] is True
        finally:server.shutdown();server.server_close()
        print('PASS local-only host/origin/session checks and persisted alert controls')
        manifest=(ROOT/'scripts/install-hermes-assistant.py').read_text()
        assert 'source_home/\'auth.json\'' in manifest
        gateway_source=(ROOT/'dotfiles/.local/share/obsidian-hermes/app.py').read_text()
        assert '127.0.0.1:8766:8642' in gateway_source
        assert 'EMAIL_ENABLED=false' in manifest and 'WHATSAPP_ENABLED=false' in manifest
        assert 'no_agent=True' in (ROOT/'dotfiles/.local/share/obsidian-hermes/cron_bridge.py').read_text()
        print('PASS container ports, disabled messaging gateways, deterministic reminder configuration')
        import yaml
        a.ROOT=ROOT/'dotfiles/.local/share/obsidian-hermes'
        (a.DATA/'config.yaml').write_text(yaml.safe_dump({'model':{'provider':'openai-codex','default':'fixture-a'},'agent':{'max_turns':30}}))
        calls=[]
        def catalog(*args,**kwargs):
            calls.append(True)
            return types.SimpleNamespace(returncode=0,stdout=json.dumps({'models':['fixture-a','fixture-b'],'live':True}))
        a.command=catalog
        assert a.models()['models']==['fixture-a','fixture-b']
        a.models();assert len(calls)==1
        assert a.set_model('fixture-b')['selected']=='fixture-b'
        assert yaml.safe_load((a.DATA/'config.yaml').read_text())['agent']['max_turns']==30
        assert (a.DATA/'config.yaml').stat().st_mode & 0o777 == 0o600
        try:a.set_model('unlisted-model')
        except ValueError:pass
        else:raise AssertionError('Unlisted model was accepted')
        a.command=lambda *args,**kwargs:types.SimpleNamespace(returncode=0,stdout=json.dumps({'models':['old-fallback'],'live':False}))
        assert a.models(force=True)['models']==['fixture-a','fixture-b']
        assert a.models()['source']=='cached'
        print('PASS model discovery cache, offline fallback, validated selection, and private atomic config')
        a.ACTIVE={'id':'lost-run','status':'running','text':'','disconnected':True,'approval':None}
        a.palette=lambda:{}
        def recovered(path,*args,**kwargs):
            if path.startswith('/api/jobs'):return {'jobs':[]}
            raise urllib.error.HTTPError(path,404,'Not found',{},None)
        a.api=recovered
        state=a.snapshot()
        assert state['online'] and state['active']['status']=='failed'
        assert a.read_json(a.STATE_FILE,{})['active']['status']=='failed'
        print('PASS gateway restart clears a lost run so a new message can be sent')
        sys.modules['app']=a
        health_spec=importlib.util.spec_from_file_location('health',a.ROOT/'health.py')
        health=importlib.util.module_from_spec(health_spec);health_spec.loader.exec_module(health)
        ready={'status':'ready','units':{'daemon':{'NRestarts':'0'}}}
        down={'status':'offline','units':{'daemon':{'NRestarts':'0'}}}
        assert health.transition({},down) is None
        assert health.transition(ready,down)[0]=='Hermes needs attention'
        assert health.transition(down,down)[0]=='Hermes needs attention'
        assert health.transition({**down,'down_alerted':True},down) is None
        assert health.transition(down,ready)[0]=='Hermes is back'
        assert health.transition(ready,ready) is None
        assert health.transition(ready,{'status':'ready','units':{'daemon':{'NRestarts':'1'}}})[0]=='Hermes restarted'
        print('PASS independent health monitor detects stops, startup failure, recovery, and automatic restarts without duplicate alerts')
    print('Hermes desktop checks passed without contacting a model or any account.')

if __name__=='__main__':main()
