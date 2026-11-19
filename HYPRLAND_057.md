# Hyprland 0.57 recovery — 2026-11-01

The installed Hyprland 0.57.0 generated `~/.config/hypr/hyprland.lua` and loaded its stock configuration. The former `hyprland.conf` and custom desktop files remained intact. The stock session had 48 binds, no Waybar or wallpaper surfaces, and an inactive graphical-session target that prevented desktop portals from starting.

## Active configuration

`~/.config/hypr/hyprland.lua` now contains the native configuration and all 140 former shortcuts, including personal Hermes and speech controls. The old `.conf` files remain recovery references; edit the Lua file for future keybinding or compositor changes.

The Lua configuration reads only two managed data files in their existing format:

- `~/.config/obsidian-ember/current/hyprland.conf`: theme color assignments; the theme helper explicitly reloads after rendering.
- `~/.config/hypr/obsidian-displays.conf`: saved display rules; Displays retains its confirmation and rollback workflow.

`obsidian-session-start` imports the desktop environment into systemd/D-Bus, activates `obsidian-hyprland-session.target`, starts portals, and restores the existing theme/bar, notification, clipboard, power and idle tools. It runs on login; it was invoked manually once for the current session. A compositor shutdown hook stops the custom session target.

`obsidian-hyprctl` is a scoped adapter used only by the existing Obsidian helpers. It translates their supported monitor, gap, effect, launch, DPMS, close-window and logout commands into the new Lua IPC. System `hyprctl` is unchanged. It checks error replies, preserves integer types, and translates four-sided gap values into native tables. The gap reader also handles the new `css` response field.

Waybar remains restricted to `eDP-1`. The confirmed display layout, theme, and Network/Bluetooth notification placement are preserved. No kernel, bootloader, partitions, or Asahi recovery files were changed.

## Validation

- `Hyprland --verify-config -c ~/.config/hypr/hyprland.lua`: config ok.
- `python scripts/check-hyprland-desktop.py`: 140 active shortcuts; wallpaper on both outputs; one visible bar on built-in only; no config errors; desktop, portal, power and idle units active.
- `python scripts/test-displays.py`: 9 transaction tests passed.
- A live no-change display transaction applied and timed out correctly, restoring live settings without writing the saved layout.
- The live gap toggle disabled gaps/rounding and restored the exact prior values.
- The current session was repaired without logout. A fresh login has not been exercised.

## Recovery copy

Before changes, configuration, local helpers and display app files were backed up to:

`~/.local/state/obsidian-ember/backups/hyprland-057-20261101-091411`

This contains the pre-repair generated default Lua file as well as the intact legacy configuration. Restoring that Lua file returns to the default desktop, not the old customized desktop. Keep the new native config for Hyprland 0.57; restoring only `hyprland.conf` cannot make 0.57 read it.

The portable copies in this repository were patched separately to preserve unrelated existing changes. No commit was made.

## Companion packages

The requested package transaction contains only `hyprlauncher`, `hyprshutdown` and `hyprland-qt-support` (about 1 MiB installed). Installation uses the normal system authentication dialog. The existing Rofi, Swaybg, Swaylock, Swayidle, Mako and KDE authentication agent remain the configured desktop tools.
