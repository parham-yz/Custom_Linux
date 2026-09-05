"""Independent service health checks; still works when the desktop bridge stops."""
import time
import urllib.request

from app import API, CONFIG, PORT, STATE_FILE, command, notify, read_json, write_json

PATH = STATE_FILE.with_name('health.json')
SERVICES = ('obsidian-hermes.service', 'obsidian-hermes-gateway.service')


def inspect():
    units = {}
    for name in SERVICES:
        result = command(['systemctl', '--user', 'show', name,
                          '--property=ActiveState,NRestarts,SubState'], timeout=3)
        units[name] = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    running = all(u.get('ActiveState') == 'active' for u in units.values())
    ready = False
    if running:
        try:
            key = read_json(CONFIG, {})['gateway_key']
            req = urllib.request.Request(API + '/v1/models', headers={'Authorization': 'Bearer ' + key})
            with urllib.request.urlopen(req, timeout=2) as response:
                ready = response.status == 200
            if ready:
                with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/', timeout=2) as response:
                    ready = response.status == 200
        except (OSError, KeyError):
            pass
    return {'status': 'ready' if ready else 'reconnecting' if running else 'offline',
            'time': time.time(), 'units': units}


def transition(previous, current):
    if not previous:
        return None
    before, after = previous.get('status'), current['status']
    if after != 'ready' and (before == 'ready' or not previous.get('down_alerted')):
        return ('Hermes needs attention', 'The assistant stopped or lost its connection. Open its bar icon to check it.')
    if after == 'ready' and before != 'ready':
        return ('Hermes is back', 'Your assistant is running again.')
    restarted = any(int(unit.get('NRestarts', 0)) > int(previous.get('units', {}).get(name, {}).get('NRestarts', 0))
                    for name, unit in current['units'].items())
    if restarted and after == 'ready':
        return ('Hermes restarted', 'The assistant stopped unexpectedly. It has restarted and is ready again.')
    return None


def check():
    previous = read_json(PATH, {})
    current = inspect()
    current['down_alerted'] = bool(previous.get('down_alerted')) if current['status'] != 'ready' else False
    alert = transition(previous, current)
    # Retry failed notification delivery at the next check, without duplicating successes.
    pending = alert or previous.get('pending')
    if pending:
        if not notify(*pending):
            current['pending'] = pending
        elif current['status'] != 'ready':
            current['down_alerted'] = True
    write_json(PATH, current)


if __name__ == '__main__':
    check()
