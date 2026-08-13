#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--apply" ]]; then
  cat <<'EOF'
Dry run only: no files were changed.
Review dotfiles/ and rerun with:
  ./scripts/restore-config.sh --apply
EOF
  exit 0
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
snapshot="$repo_root/dotfiles"
stamp="$(date +%Y%m%d_%H%M%S)"
backup="$HOME/.local/state/custom-linux-backups/$stamp"
mkdir -p "$backup"

if ! command -v rsync >/dev/null 2>&1; then
  echo "Error: rsync is required." >&2
  exit 1
fi

# --backup-dir retains every destination file replaced by this restore.
rsync -a \
  --exclude='.local/state/obsidian-ember/current-wallpaper.relative' \
  --backup --backup-dir="$backup" \
  "$snapshot/" "$HOME/"

relative_file="$snapshot/.local/state/obsidian-ember/current-wallpaper.relative"
if [[ -f "$relative_file" ]]; then
  relative_wallpaper="$(cat "$relative_file")"
  mkdir -p "$HOME/.local/state/obsidian-ember"
  printf '%s\n' "$HOME/.config/obsidian-ember/$relative_wallpaper" \
    > "$HOME/.local/state/obsidian-ember/current-wallpaper"
fi

systemctl --user daemon-reload 2>/dev/null || true
if command -v hyprctl >/dev/null 2>&1 && hyprctl instances -j >/dev/null 2>&1; then
  hyprctl reload >/dev/null
fi
if pgrep -x waybar >/dev/null 2>&1; then
  pkill -SIGUSR2 waybar
fi

echo "Configuration restored. Replaced-file backups: $backup"
echo "Services were not enabled and packages were not installed."
