---
name: obsidian-desktop
description: Manage this Fedora Asahi Remix Hyprland desktop. Use for requests about Hyprland, Waybar, Rofi, Mako, Kitty, themes, shortcuts, desktop services, display, power, network, capture, or Obsidian Ember commands.
---

# Obsidian Ember desktop

This machine uses Fedora Asahi Remix on Apple Silicon with Hyprland. The desktop
snapshot is restored from `~/Dev/Custom_Linux`; it is not Omarchy or Arch Linux.

## Read before changing

- User configuration: `~/.config/hypr`, `~/.config/waybar`, `~/.config/rofi`,
  `~/.config/mako`, `~/.config/kitty`, and `~/.config/obsidian-ember`.
- Desktop commands: `~/.local/bin/obsidian-*`.
- User services: `~/.config/systemd/user`.
- Source snapshot: `~/Dev/Custom_Linux/dotfiles`.

Prefer editing the source snapshot, validating it, then applying it with
`~/Dev/Custom_Linux/scripts/restore-config.sh --apply`. That command creates
backups. Do not put tokens, provider credentials, transcripts, or private files
in the snapshot.

## Safety

1. Inspect current state before edits. Preserve unrelated user changes.
2. Use Fedora commands and package names. Never assume `pacman` or Arch paths.
3. Do not use `sudo` unless necessary and the user approves the exact command.
4. Treat display, boot, power, and network changes as high impact. Explain the
   rollback before applying them.
5. Validate shell with `bash -n`, JSON with `jq`, services with
   `systemd-analyze --user verify`, and the snapshot with
   `scripts/verify-snapshot.sh`.
6. Never weaken agent approval, sandbox, or credential storage without explicit
   consent.

## Native agent integration

`obsidian-agent` selects and launches the default coding agent.
`obsidian-agent settings` controls the default and approval mode.
`obsidian-agent usage panel` shows local usage and subscription limits.
Desktop launches use the class `org.obsidian.agent`. The default approval mode
is `ask`; `auto` is opt-in and allows supported agents to act with fewer prompts.
