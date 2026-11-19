# Automatic monitor audio

Installed on 2026-11-19 for the M2 MacBook Air running
`7.1.13-fairydust-usbc+`. The connected XGIMI TV appeared as `DP-1`, but ALSA
and PipeWire exposed no display audio device. The running kernel's
`/sys/module/appledrm/parameters/hdmi_audio` value was `N`.

The pinned kernel source checks this flag both when starting the audio endpoint
and when creating the ALSA card. Its description calls this support unstable:
[driver source](https://github.com/AsahiLinux/linux/blob/ce9f2eba72c061a50b2d790450e90af3439d8c24/drivers/gpu/drm/apple/dcp.c#L49).

## Installed changes

- The ALSA HiFi profile in `/usr/share/alsa/ucm2/conf.d/apple_dcp/` reads the
  driver's `HDMI/DP Jack` control. Its two source files are in
  `/home/parham/Dev/asahi-usbc-setup/ucm2/apple_dcp/`.
- The user service `obsidian-monitor-audio` checks the DRM connector and audio
  jack. On connection it sends two seconds of silent stereo audio through
  PipeWire and checks that the display hardware consumes at least 12,000 frames.
  The playback test has a five-second deadline.
  It turns off the display card if the link disappears, the playback test fails, or
  an active playback clock stops progressing. Startup failures trigger up to
  three retries after 2, 6, and 15 seconds. A new connection resets the retries.
  If the audio server is unavailable during fallback, the service retries the
  pending profile change before it tests the display again. If ALSA started
  with no monitor and omitted the HiFi profile, the service uses the card's
  Pro Audio profile with the same stereo format.
- The WirePlumber rule in `~/.config/wireplumber/wireplumber.conf.d/60-monitor-audio.conf`
  matches the display controller's output name. Its priority of 950 places it
  above the speaker DSP (850) and below wired and Bluetooth headphones (1009
  and 1010). Applications following the default output can move automatically.
- `/home/parham/Dev/asahi-usbc-setup/enable-monitor-audio.sh` added
  `appledrm.hdmi_audio=1` only to the existing custom kernel's boot entry.
  Boot entries and before/after kernel information were backed up under
  `/var/lib/obsidian-monitor-audio-ASu6Nmb8`.

## Validation

After reboot the custom kernel exposed the Apple DisplayPort card. The original
rule left Firefox linked to an unplugged display whose generic analog route
reported unknown availability. PipeWire logged repeated ALSA errors. Taking
that card offline restored the speaker route. Firefox advanced from 34 to 37
seconds with both speaker channels active. A timed video and silent audio test
also finished on the laptop speakers.

The service was active after restarting WirePlumber with the cable out. Simulated
checks covered unplug, failed playback, a stopped hardware clock, and retry on
reconnect. On the subsequent XGIMI connection, PipeWire logged an ALSA startup allocation
error and the earlier service disabled display audio until unplug. Five seconds
of direct 48 kHz stereo playback then completed on the same connection.
With the updated service and a four-period audio buffer, the automatic test
passed and WirePlumber selected the HiFi display output. The user confirmed
audible playback. After the startup and fallback fixes, the monitor stayed
selected across a restart of the helper, its stereo check passed, and the
hardware clock advanced. The service is enabled with WirePlumber.

Run `python3 scripts/test-monitor-audio.py` from this repository to exercise
late device detection, temporary sound server failure, idle playback, clock
stalls, and retry exhaustion followed by reconnection. These tests simulate
cable events. A physical unplug and reconnect with this revision is still
unverified. For live results, run
`journalctl --user -u obsidian-monitor-audio -b`.

## Rollback

Disable display audio for the custom kernel and reboot:

```bash
pkexec /usr/bin/bash /home/parham/Dev/asahi-usbc-setup/enable-monitor-audio.sh disable
```

To remove the user routing policy:

```bash
systemctl --user disable --now obsidian-monitor-audio.service
rm ~/.config/wireplumber/wireplumber.conf.d/60-monitor-audio.conf
systemctl --user restart wireplumber
```

For manual output selections, sound settings work as usual. `wpctl clear-default`
clears all saved default device choices and resumes priority selection, including
for input devices.

To remove the custom ALSA profile, remove `HiFi.conf` and `apple_dcp.conf` from
`/usr/share/alsa/ucm2/conf.d/apple_dcp/` and restart WirePlumber.
