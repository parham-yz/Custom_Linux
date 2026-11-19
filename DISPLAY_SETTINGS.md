# Displays for Hyprland

Open **Displays** from the application launcher, **OMA → Displays**, or run
`obsidian-display-settings`. This is a native standalone app for the current
Hyprland session. KDE's built-in Display Configuration module remains a Plasma
controller; embedding these controls there would require a separate KCM plugin.

## Controls

- Click a display card or screen name to select it.
- Drag screens to match your desk, or use the Position presets.
- Choose a resolution and refresh rate advertised by that display.
- Adjust text size, rotation, and extended/mirrored operation.
- Adjust built-in brightness. This applies immediately and pauses automatic
  brightness for two minutes using the desktop's existing brightness helper.
  Use the InnoView's own buttons for its brightness.
- Click **Apply changes**, then **Keep changes** within 20 seconds to save.
  **Revert**, Escape during a trial, closing the app, or leaving the countdown
  unanswered restores the previous arrangement. A separate worker performs the
  timeout recovery, so it continues if the settings window crashes.

The app does not disable screens. It rejects unsupported modes, stale requests
after a connection change, mirror cycles, and overlapping extended screens.
These checks do not guarantee that an experimental display driver accepts every
advertised mode. If a mode fails, the trial is reverted.

## Configuration and recovery

Confirmed layouts are stored in `~/.config/hypr/obsidian-displays.conf`, included
by `hyprland.conf`. The previous saved layout is kept beside it as
`obsidian-displays.conf.previous`. Disconnected external-display preferences
are retained when another connected screen is adjusted. Unknown screens use
the existing preferred-mode fallback; the built-in default is scale 1.6.

If an application or compositor failure prevents automatic recovery, restore
the previous layout from a terminal and reload:

```bash
cp ~/.config/hypr/obsidian-displays.conf.previous ~/.config/hypr/obsidian-displays.conf
hyprctl reload
```

The original files from installation are under
`~/.local/state/obsidian-ember/backups/displays-<timestamp>/`. This app changes
user-level desktop configuration only; it does not change the kernel, EFI,
Apple startup selection, or macOS.

## Install and verify

```bash
/usr/bin/python3 scripts/install-displays.py
/usr/bin/python3 scripts/test-displays.py
/usr/bin/python3 scripts/test-displays-ui.py
```

Installation preserves the current live arrangement and independently edits the
repository and live config copies. Re-running it does not replace a saved layout.
Requires the existing GTK 3 / PyGObject / Cairo stack and Hyprland's `hyprctl`.
The UI test requires a graphical session; it uses simulated monitors and does
not change real output settings.

Validation on 2026-10-15:

- Nine transaction tests: timeout, Keep, explicit Revert, failed-save recovery,
  hotplug validation, overlap, mirror/mode validation, disconnected preferences,
  and rotated dimensions.
- Real GTK control callbacks against simulated displays passed.
- A detached live worker applied the current geometry, timed out, and verified
  restoration with the persistent config unchanged. This test deliberately did
  not switch resolution or refresh rate on the experimental USB-C driver.
- Hyprland reported no configuration errors; desktop entry validation passed.
- The visible app was inspected through system AT-SPI and a window-only capture.
  Orca's computer-use bridge could not locate its Python accessibility dependency,
  so system GTK accessibility was used directly.

Source reference: [Hyprland monitor configuration](https://wiki.hypr.land/0.54.0/Configuring/Monitors/).
The installed compositor still accepts this monitor-rule syntax.
