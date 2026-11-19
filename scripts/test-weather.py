#!/usr/bin/python3
"""Weather parsing, cache isolation, offline recovery, and bar safety."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'dotfiles/.local/share/obsidian-weather'))
import weather
FIXTURE = {'nearest_area':[{'areaName':[{'value':'Example City'}], 'country':[{'value':'Germany'}]}],
 'current_condition':[{'temp_C':'12','FeelsLikeC':'10','humidity':'72','windspeedKmph':'14',
                       'weatherDesc':[{'value':'Partly cloudy'}]}],
 'weather':[{'date':'2026-10-16','mintempC':'7','maxtempC':'14','hourly':[
  {'time':'0','chanceofrain':'10','weatherDesc':[{'value':'Clear'}]},
  {'time':'1200','chanceofrain':'60','weatherDesc':[{'value':'Light rain'}]}]}]}

class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patcher=patch.multiple(weather,CACHE=Path(self.tmp.name)/'cache',CONFIG=Path(self.tmp.name)/'config/weather.json')
        self.patcher.start();self.addCleanup(self.patcher.stop)

    def download(self,payload=FIXTURE):
        return patch.object(weather.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(payload),''))

    def test_forecast_uses_midday_and_daily_max_rain(self):
        data=weather.parse(FIXTURE)
        self.assertEqual(data['days'][0]['description'],'Light rain')
        self.assertEqual(data['days'][0]['rain'],60)
        self.assertEqual((data['days'][0]['low'],data['days'][0]['high']),(7,14))

    def test_fresh_cache_avoids_network_and_keeps_locations_separate(self):
        with self.download() as run:
            weather.fetch('');weather.fetch('');self.assertEqual(run.call_count,1)
            weather.fetch('Berlin');self.assertEqual(run.call_count,2)
        self.assertIsNone(weather.cached('Paris'))

    def test_offline_fallback_is_marked_and_expires(self):
        with self.download():weather.fetch('')
        with patch.object(weather.subprocess,'run',side_effect=subprocess.TimeoutExpired('curl',12)):
            self.assertTrue(weather.fetch('',True)['stale'])
            with patch.object(weather.time,'time',return_value=time.time()+weather.MAX_AGE+1):
                self.assertIsNone(weather.fetch(''))

    def test_invalid_response_does_not_overwrite_good_cache(self):
        with self.download():weather.fetch('')
        with self.download({'error':'proxy unavailable'}):
            result=weather.fetch('',True)
        self.assertTrue(result['stale']);self.assertEqual(result['data']['temperature'],12)

    def test_bar_escapes_remote_markup_and_keeps_empty_click_target(self):
        data=weather.parse(FIXTURE);data['city']='<b>City</b>'
        result=weather.bar({'data':data,'stale':False})
        self.assertNotIn('<b>',result['tooltip'])
        self.assertTrue(weather.bar(None)['text'])
        self.assertEqual(weather.bar(None)['class'],'empty')

    def test_partial_conditions_and_missing_forecast(self):
        fixture={'current_condition':[{'temp_C':'0'}]}
        data=weather.parse(fixture)
        self.assertEqual(data['temperature'],0);self.assertIsNone(data['feels'])
        self.assertEqual(data['days'],[])
        self.assertEqual(weather.display_number(None,'%'),'—')

    def test_corrupt_cache_and_nonfinite_temperatures(self):
        with self.download():weather.fetch('')
        next(weather.CACHE.glob('*.json')).write_text('{broken')
        self.assertIsNone(weather.cached(''))
        for value in ('nan','inf','1000',None):
            fixture=copy.deepcopy(FIXTURE);fixture['current_condition'][0]['temp_C']=value
            with self.assertRaises(ValueError):weather.parse(fixture)

    def test_location_settings_roundtrip(self):
        weather.save_location('  München, Germany  ')
        self.assertEqual(weather.read_location(),'München, Germany')
        weather.save_location('');self.assertEqual(weather.read_location(),'')

if __name__=='__main__':unittest.main()
