# Custom Linux — Hyprland/Waybar State Snapshot

A portable, sanitized snapshot of the current desktop configuration on a Fedora Asahi Remix system. It captures the **configuration and reproducibility metadata**, not the base operating-system files.

Snapshot created: `2026-08-13T09:36:52+02:00`

## Current appearance settings

| Setting | Value |
|---|---:|
| Desktop compositor | Hyprland 0.56.0 |
| Bar | Waybar 0.15.0 |
| Waybar rendered height | **30 px** (about 80% of the original 38 px) |
| Waybar top/side margins | 8 px / 10 px |
| Text size | 12 px |
| Network icon/text size | 14 px |
| Tray icon size | 16 px |
| Hyprland inner gap | **4 px** |
| Hyprland outer gap | **8 px** |
| Display | 2560×1664 @ 60 Hz, scale 1.6 |
| Active theme | `obsidian-ember` |

The bar retains its readable text/icon sizes and horizontal widths. Only its vertical geometry was compacted. The window gaps were scaled to 80% of their previous values (5→4 px and 10→8 px).

## Repository contents

```text
dotfiles/
  .config/
    hypr/             Hyprland configuration
    waybar/           Waybar configuration and CSS
    kitty/            Terminal configuration
    btop/             System monitor theme/configuration
    rofi/              Menus and flyouts
    mako/              Notification styling
    obsidian-ember/    Theme palettes, templates, and wallpapers
    systemd/user/      Custom desktop-related user units
  .local/bin/          Custom `obsidian-*` desktop utilities
  .local/state/        Whitelisted theme selection only
manifests/
  rpm-installed.tsv             Exact installed RPM inventory
  dnf-userinstalled.txt         DNF user-installed package inventory
  flatpak-installed.tsv         Flatpak inventory
  font-families.txt             Available font families
  *-services-enabled.txt        Enabled unit names
  wallpapers.sha256             Wallpaper integrity checksums
  system-summary.txt            Sanitized system summary
scripts/
  restore-config.sh             Safe configuration restore helper
  verify-snapshot.sh            Integrity and secret-pattern checks
```

## Restore the configuration

Review the files first, then run:

```bash
git clone https://github.com/parham-yz/Custom_Linux.git
cd Custom_Linux
./scripts/restore-config.sh --apply
```

The restore script:

1. creates timestamped backups for overwritten files;
2. copies only the tracked configuration files into `$HOME`;
3. restores the selected wallpaper path portably;
4. reloads systemd user units and the running Hyprland/Waybar session when available.

It does **not** install packages or enable services automatically. Use the manifests to compare the target machine before installing anything:

```bash
comm -23   <(cut -f1 manifests/rpm-installed.tsv | sort -u)   <(rpm -qa --qf '%{NAME}\n' | sort -u)
```

Flatpak applications can be reviewed with:

```bash
cat manifests/flatpak-installed.tsv
```

## Privacy and scope

The snapshot intentionally excludes:

- `/usr`, `/bin`, system libraries, kernels, firmware, and other base OS files;
- browser profiles, SSH/GPG keys, Git credentials, API keys, and environment files;
- network profiles and saved Wi-Fi passwords;
- clipboard history, logs, caches, PIDs, and personal documents;
- unrelated application/service configuration.

Only the whitelisted `current-theme` state is included from local state. Absolute home paths in the wallpaper selection are converted to a portable relative path.

## Compatibility

The configuration is tailored to Fedora Asahi Remix on Apple Silicon and a 2560×1664 internal display. Most dotfiles can be reused on other Hyprland systems, but package names, monitor scaling, power controls, brightness controls, and Apple-specific key bindings may require adjustment.

## Verify

```bash
./scripts/verify-snapshot.sh
```

This checks file hashes and scans tracked text for common secret patterns. The authoritative integrity list is `SHA256SUMS`.
