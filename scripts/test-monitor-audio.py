#!/usr/bin/python3
"""Exercise the installed service logic with a simulated display and sound server."""

from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import runpy
import subprocess
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "dotfiles/.local/bin/obsidian-monitor-audio"
MAIN = runpy.run_path(str(SCRIPT))["main"]


class Finished(BaseException):
    """End the simulated event loop."""


class MonitorAudioTests(unittest.TestCase):
    def simulate(self, ticks, *, enable=(), disable=(), progress=()):
        ticks = iter(ticks)
        current = next(ticks)
        clock = 0

        def poll(timeout):
            nonlocal current, clock
            clock += timeout
            current = next(ticks, None)
            if current is None:
                raise Finished

        events = Mock()
        events.poll.side_effect = poll
        self.open_sink = Mock(side_effect=enable)
        self.set_profile = Mock(side_effect=disable or None)
        pcm = Mock()
        pcm.exists.side_effect = lambda: current != "absent"
        timer = SimpleNamespace(monotonic=lambda: clock, sleep=lambda _: None)
        fake = dict(PCM=pcm, time=timer, connected=lambda: current == "plugged",
                    enable=self.open_sink, set_profile=self.set_profile,
                    playback_progress=Mock(side_effect=progress or None, return_value=None))
        with ExitStack() as stack:
            stack.enter_context(patch.dict(MAIN.__globals__, fake))
            stack.enter_context(patch("pyudev.Monitor.from_netlink", return_value=events))
            with self.assertRaises(Finished):
                MAIN()

    def test_late_card_while_unplugged(self):
        self.simulate(["absent", "unplugged", "unplugged"])
        self.set_profile.assert_called_once_with("off")

    def test_audio_server_returns_during_fallback(self):
        unavailable = subprocess.CalledProcessError(1, ["pactl"])
        self.simulate(["plugged"] * 7, enable=[RuntimeError("start failed"), 7],
                      disable=[unavailable, None])
        self.assertEqual(self.open_sink.call_count, 2)
        self.assertEqual(self.set_profile.call_count, 2)

    def test_idle_and_reconnect(self):
        self.simulate(["plugged"] * 5 + ["unplugged", "plugged"], enable=[7, 12],
                      progress=[100, 200, None, None, None, 8])
        self.set_profile.assert_called_once_with("off")
        self.assertEqual(self.open_sink.call_count, 2)

    def test_stalled_clock_recovers(self):
        self.simulate(["plugged"] * 7, enable=[7, 9], progress=[100, 100, 100, 1, 2, 3, 4])
        self.set_profile.assert_called_once_with("off")
        self.assertEqual(self.open_sink.call_count, 2)

    def test_persistent_failure_stops_retrying_until_reconnect(self):
        self.simulate(["plugged"] * 40 + ["unplugged", "plugged"],
                      enable=[RuntimeError("start failed")] * 4 + [12])
        self.assertEqual(self.open_sink.call_count, 5)


if __name__ == "__main__":
    unittest.main()
