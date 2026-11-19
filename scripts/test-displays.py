#!/usr/bin/python3
"""Test display transactions against a stateful simulated compositor."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'dotfiles/.local/share/obsidian-displays'))
import backend as b

RAW = [dict(id=0, name='eDP-1', width=2560, height=1664, refreshRate=60., scale=1.6,
            x=0, y=0, transform=0, mirrorOf='none', availableModes=['2560x1664@60.00Hz']),
       dict(id=1, name='DP-1', width=2560, height=1440, refreshRate=60., scale=1.,
            x=1600, y=0, transform=0, mirrorOf='none', availableModes=['2560x1440@60.00Hz', '1920x1080@60.00Hz'])]


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.job = self.root / 'trial'
        self.job.mkdir()
        self.config = self.root / 'displays.conf'
        self.old = b.render(b.snapshot(RAW))
        self.config.write_text(self.old)
        self.state = copy.deepcopy(RAW)
        self.wanted = b.snapshot(RAW)
        self.wanted[1]['x'] += 100
        (self.job / 'request.json').write_text(json.dumps(self.wanted))
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def command(self, *args):
        self.calls.append(args)
        if args[0] == 'reload':
            return 'ok'
        name, mode, position, scale, _, transform, *tail = args[2].split(',')
        m = next(m for m in self.state if m['name'] == name)
        p = b.MODE.fullmatch(mode)
        x, y = position.split('x')
        m.update(width=int(p[1]), height=int(p[2]), refreshRate=float(p[3]), scale=float(scale),
                 x=int(x), y=int(y), transform=int(transform), mirrorOf=tail[1] if tail else 'none')
        return 'ok'

    def run_trial(self):
        with patch.object(b, 'monitors', side_effect=lambda: copy.deepcopy(self.state)), patch.object(b, 'hypr', side_effect=self.command):
            b.transaction(self.job, config=self.config, duration=0.01)
        return json.loads((self.job / 'status.json').read_text())

    def test_timeout_restores_live_state_without_writing_settings(self):
        result = self.run_trial()
        self.assertEqual(result['state'], 'reverted')
        self.assertTrue(b.matches(b.snapshot(RAW), self.state))
        self.assertEqual(self.config.read_text(), self.old)
        self.assertTrue(any('1700x0' in args[-1] for args in self.calls))

    def test_keep_persists_only_after_live_verification_and_preserves_backup(self):
        (self.job / 'keep').touch()
        result = self.run_trial()
        self.assertEqual(result['state'], 'kept')
        self.assertTrue(b.matches(self.wanted, self.state))
        self.assertIn('1700x0', self.config.read_text())
        self.assertEqual(self.config.with_suffix('.conf.previous').read_text(), self.old)

    def test_explicit_revert_wins_over_keep(self):
        (self.job / 'keep').touch()
        (self.job / 'revert').touch()
        self.assertEqual(self.run_trial()['state'], 'reverted')
        self.assertTrue(b.matches(b.snapshot(RAW), self.state))

    def test_failed_commit_reload_restores_file_and_live_state(self):
        (self.job / 'keep').touch()
        real = self.command
        failures = [True]
        def fail_once(*args):
            if args[0] == 'reload' and failures:
                failures.pop()
                raise RuntimeError('simulated reload failure')
            return real(*args)
        self.command = fail_once
        result = self.run_trial()
        self.assertEqual(result['state'], 'reverted')
        self.assertEqual(self.config.read_text(), self.old)
        self.assertTrue(b.matches(b.snapshot(RAW), self.state))

    def test_hotplug_change_rejects_stale_request(self):
        with self.assertRaisesRegex(ValueError, 'connected displays changed'):
            b.validate(self.wanted, RAW[:1])

    def test_overlapping_layout_is_rejected(self):
        self.wanted[1]['x'] = 100
        with self.assertRaisesRegex(ValueError, 'overlap'):
            b.validate(self.wanted, RAW)

    def test_mirror_cycles_and_unadvertised_modes_are_rejected(self):
        self.wanted[0]['mirror'], self.wanted[1]['mirror'] = 'DP-1', 'eDP-1'
        with self.assertRaisesRegex(ValueError, 'mirror source'):
            b.validate(self.wanted, RAW)
        self.wanted = b.snapshot(RAW)
        self.wanted[1]['width'] = 99999
        with self.assertRaisesRegex(ValueError, 'not advertised'):
            b.validate(self.wanted, RAW)

    def test_disconnected_screen_preferences_survive_saving(self):
        old = self.old + 'monitor = HDMI-A-1,1920x1080@60,4160x0,1\n'
        self.assertIn('HDMI-A-1', b.render(self.wanted, old))
        self.assertEqual(b.render(self.wanted, old).count('monitor = DP-1,'), 1)

    def test_rotated_dimensions_and_mirror_ids(self):
        m = b.snapshot(RAW)[1]
        m['transform'] = 1
        self.assertEqual(b.dimensions(m), (1440, 2560))
        raw = copy.deepcopy(RAW)
        raw[1]['mirrorOf'] = 0
        self.assertEqual(b.snapshot(raw)[1]['mirror'], 'eDP-1')


if __name__ == '__main__':
    unittest.main()
