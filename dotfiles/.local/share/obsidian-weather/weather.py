"""Weather data shared by the bar and native panel; no GTK dependency."""
from datetime import datetime
import hashlib
import html
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.parse import quote

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'obsidian-ember/weather.json'
CACHE = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'obsidian-weather'
FRESH = 1800
MAX_AGE = 21600


def read_location():
    try:
        value = json.loads(CONFIG.read_text()).get('location', '')
        return value.strip()[:120] if isinstance(value, str) else ''
    except (OSError, ValueError, AttributeError):
        return ''


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            name = stream.name
            json.dump(data, stream, ensure_ascii=False)
            stream.write('\n')
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def save_location(location):
    write_json(CONFIG, {'location': location.strip()[:120]})


def number(value):
    try:
        result = float(value)
        return round(result) if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def display_number(value, suffix=''):
    return '—' if value is None else f'{value}{suffix}'


def words(value, fallback=''):
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return ' '.join(str(value[0].get('value', fallback)).split())[:100]
    return fallback


def icon(description):
    text = description.lower()
    if any(w in text for w in ('thunder', 'storm')): return 'weather-storm-symbolic'
    if any(w in text for w in ('snow', 'sleet', 'ice', 'blizzard')): return 'weather-snow-symbolic'
    if any(w in text for w in ('rain', 'drizzle')): return 'weather-showers-symbolic'
    if any(w in text for w in ('fog', 'mist')): return 'weather-fog-symbolic'
    if 'partly' in text: return 'weather-few-clouds-symbolic'
    if any(w in text for w in ('cloud', 'overcast')): return 'weather-overcast-symbolic'
    if 'clear' in text: return 'weather-clear-night-symbolic'
    return 'weather-clear-symbolic' if 'sun' in text else 'weather-overcast-symbolic'


def parse(payload):
    current = payload['current_condition'][0]
    temperature = number(current.get('temp_C'))
    if temperature is None or not -100 <= temperature <= 70:
        raise ValueError('Missing current temperature')
    area = (payload.get('nearest_area') or [{}])[0]
    days = []
    for day in payload.get('weather', [])[:3]:
        date = datetime.strptime(day['date'], '%Y-%m-%d').date()
        hourly = day.get('hourly', [])
        midday = min(hourly, key=lambda h: abs((number(h.get('time')) or 0) - 1200)) if hourly else {}
        rain = [number(h.get('chanceofrain')) for h in hourly]
        days.append({'date': date.isoformat(), 'low': number(day.get('mintempC')),
                     'high': number(day.get('maxtempC')), 'description': words(midday.get('weatherDesc')),
                     'rain': max((n for n in rain if n is not None), default=None)})
    return {'city': words(area.get('areaName'), 'Local weather'),
            'country': words(area.get('country')), 'temperature': temperature,
            'feels': number(current.get('FeelsLikeC')), 'humidity': number(current.get('humidity')),
            'wind': number(current.get('windspeedKmph')), 'direction': str(current.get('winddir16Point', ''))[:4],
            'description': words(current.get('weatherDesc'), 'Current conditions'),
            'observed': str(current.get('observation_time', ''))[:20], 'days': days}


def cached(location, now=None):
    now = time.time() if now is None else now
    path = CACHE / (hashlib.sha256(location.encode()).hexdigest()[:16] + '.json')
    try:
        entry = json.loads(path.read_text())
        age = now - float(entry['fetched'])
        if entry['location'] != location or not 0 <= age < MAX_AGE:
            return None
        return {'data': parse(entry['payload']), 'fetched': entry['fetched'], 'stale': age >= FRESH}
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        return None


def fetch(location, force=False):
    previous = cached(location)
    if previous and not previous['stale'] and not force:
        return previous
    try:
        result = subprocess.run(['curl', '-fsS', '--max-time', '10', '--max-filesize', '1048576',
                                 'https://wttr.in/' + quote(location, safe='') + '?format=j1&lang=en'],
                                capture_output=True, text=True, timeout=12, check=True)
        payload = json.loads(result.stdout)
        data = parse(payload)
        fetched = time.time()
        path = CACHE / (hashlib.sha256(location.encode()).hexdigest()[:16] + '.json')
        try:
            write_json(path, {'location': location, 'fetched': fetched, 'payload': payload})
        except OSError:
            pass  # A read-only cache must not hide valid weather.
        return {'data': data, 'fetched': fetched, 'stale': False}
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, subprocess.SubprocessError):
        if previous:
            return previous | {'stale': True}
        return None


def bar(result):
    if not result:
        # Keep the click target available for retry and location selection.
        return {'text': '󰖐  —', 'class': 'empty', 'tooltip': 'Weather unavailable · Click to retry'}
    data = result['data']
    glyphs = {'weather-clear-symbolic': '󰖙', 'weather-clear-night-symbolic': '󰖔',
              'weather-showers-symbolic': '󰖗', 'weather-snow-symbolic': '󰖘',
              'weather-storm-symbolic': '󰖓', 'weather-fog-symbolic': '󰖑'}
    glyph = glyphs.get(icon(data['description']), '󰖐')
    tooltip = f"{data['city']} · {data['description']}\nFeels {display_number(data['feels'], '°')} · Wind {display_number(data['wind'], ' km/h')}"
    if result['stale']: tooltip += '\nOffline · saved weather'
    return {'text': f"{glyph}  {data['temperature']}°", 'class': 'stale' if result['stale'] else 'available',
            'tooltip': html.escape(tooltip + '\nClick for forecast')}
