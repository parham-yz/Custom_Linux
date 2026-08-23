#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/runtime" "$TMP/config/rofi"
export PATH="$TMP/bin:$ROOT/dotfiles/.local/bin:/usr/bin:/bin"
export XDG_RUNTIME_DIR="$TMP/runtime"
export XDG_CONFIG_HOME="$TMP/config"
export BT_POWERED=no
export BT_LOG="$TMP/bluetooth.log"
export NOTIFY_LOG="$TMP/notify.log"
export ROFI_CAPTURE="$TMP/rofi-input"
: >"$BT_LOG"
: >"$NOTIFY_LOG"
cp "$ROOT/dotfiles/.config/rofi/network.rasi" "$TMP/config/rofi/network.rasi"

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1" >&2; exit 1; }
assert_eq() { [[ "$1" == "$2" ]] || fail "$3 (expected '$2', got '$1')"; pass "$3"; }
assert_has() { grep -F -- "$2" <<<"$1" >/dev/null || fail "$3"; pass "$3"; }

cat >"$TMP/bin/systemctl" <<'MOCK'
#!/usr/bin/env bash
if [[ ${1:-} == is-active ]]; then [[ ${BT_SERVICE_ACTIVE:-1} == 1 ]]; exit; fi
exit 0
MOCK
cat >"$TMP/bin/notify-send" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$NOTIFY_LOG"
MOCK
cat >"$TMP/bin/rfkill" <<'MOCK'
#!/usr/bin/env bash
printf 'rfkill %s\n' "$*" >>"$BT_LOG"
MOCK
cat >"$TMP/bin/rofi" <<'MOCK'
#!/usr/bin/env bash
cat >"$ROFI_CAPTURE"
exit 1
MOCK
cat >"$TMP/bin/bluetoothctl" <<'MOCK'
#!/usr/bin/env bash
printf 'bluetoothctl %s\n' "$*" >>"$BT_LOG"
case " $* " in
  *' list ')
    [[ ${BT_CONTROLLERS:-1} != 0 ]] && printf '%s\n' 'Controller 1C:57:DC:58:D4:F1 fixture-controller'
    [[ ${BT_CONTROLLERS:-1} == 2 ]] && printf '%s\n' 'Controller 11:22:33:44:55:66 fixture-controller-2'
    ;;
  *' show ')
    cat <<EOF
Controller 1C:57:DC:58:D4:F1 (public)
	Name: fixture-controller
	Powered: ${BT_POWERED:-no}
	Pairable: yes
EOF
    ;;
  *' devices Connected ')
    [[ ${BT_CONNECTED:-0} == 1 ]] && printf '%s\n' 'Device AA:BB:CC:DD:EE:01 Studio Headphones'
    ;;
  *' devices ')
    printf '%s\n' 'Device AA:BB:CC:DD:EE:01 Studio Headphones'
    ;;
  *' info AA:BB:CC:DD:EE:01 ')
    cat <<EOF
Device AA:BB:CC:DD:EE:01 (public)
	Name: Studio Headphones
	Alias: ${BT_ALIAS:-Studio Headphones}
	Icon: audio-headset
	Paired: yes
	Trusted: yes
	Connected: no
	Battery Percentage: 0x55 (85)
	RSSI: -42
EOF
    ;;
  *' power on ') [[ ${BT_POWER_ON_FAIL:-0} == 0 ]] ;;
  *' --timeout 10 scan on ') exit 0 ;;
  *) exit 0 ;;
esac
MOCK
chmod +x "$TMP/bin/"*

assert_eq "$(obsidian-bluetooth --status)" off 'reports a powered-off controller'
if BT_SERVICE_ACTIVE=0 obsidian-bluetooth --status >/dev/null 2>&1; then fail 'accepted an inactive Bluetooth service'; fi
pass 'reports an inactive system Bluetooth service'
if BT_CONTROLLERS=0 obsidian-bluetooth --status >/dev/null 2>&1; then fail 'accepted a missing controller'; fi
pass 'reports a missing Bluetooth controller'
obsidian-bluetooth --toggle
log="$(cat "$BT_LOG")"
assert_has "$log" 'rfkill unblock bluetooth' 'unblocks a soft-blocked controller before power-on'
assert_has "$log" 'power on' 'turns Bluetooth on'
if grep -F 'pairable on' <<<"$log" >/dev/null; then fail 'enabled inbound pairing unnecessarily'; fi
pass 'does not expose the adapter for unsolicited inbound pairing'

if BT_POWER_ON_FAIL=1 obsidian-bluetooth --toggle >/dev/null 2>&1; then fail 'reported success after a power-on failure'; fi
pass 'propagates controller power-on failures'

: >"$BT_LOG"
BT_POWERED=yes obsidian-bluetooth --toggle
assert_has "$(cat "$BT_LOG")" 'power off' 'turns Bluetooth off'


: >"$BT_LOG"
BT_POWERED=yes BT_CONNECTED=1 obsidian-bluetooth --toggle || true
if grep -F 'power off' "$BT_LOG" >/dev/null; then fail 'powered off with a connected device without confirmation'; fi
pass 'requires confirmation before disconnecting active devices'

if BT_CONTROLLERS=2 obsidian-bluetooth --status >/dev/null 2>&1; then fail 'silently selected one of multiple controllers'; fi
pass 'refuses ambiguous multi-controller selection'

: >"$BT_LOG"
BT_POWERED=yes obsidian-bluetooth --scan
assert_has "$(cat "$BT_LOG")" 'bluetoothctl --timeout 10 scan on' 'runs a bounded nearby-device scan'
assert_has "$(cat "$BT_LOG")" 'scan off' 'stops discovery after a scan'

BT_POWERED=yes obsidian-bluetooth || true
menu="$(cat "$ROFI_CAPTURE")"
assert_has "$menu" 'Studio Headphones' 'lists known headphones'
assert_has "$menu" '…EE:01' 'distinguishes duplicate aliases with a MAC suffix'
BT_ALIAS='Café Buds' BT_POWERED=yes obsidian-bluetooth || true
assert_has "$(cat "$ROFI_CAPTURE")" 'Café Buds' 'preserves UTF-8 device aliases'
assert_has "$menu" '• 85%' 'shows headset battery when BlueZ provides it'
assert_has "$menu" 'paired' 'shows device pairing state'
assert_has "$menu" 'Scan for Nearby Devices' 'offers device scanning'
assert_has "$menu" 'Turn Bluetooth Off' 'offers radio power control'

if obsidian-bluetooth --invalid >/dev/null 2>&1; then fail 'accepted an invalid command'; fi
pass 'rejects invalid commands'

jq -e '."modules-right" | index("bluetooth")' "$ROOT/dotfiles/.config/waybar/config" >/dev/null
jq -e '.bluetooth["on-click"] == "obsidian-bluetooth" and .bluetooth["on-click-middle"] == "obsidian-bluetooth --refresh" and .bluetooth["on-click-right"] == "obsidian-bluetooth --toggle"' "$ROOT/dotfiles/.config/waybar/config" >/dev/null
pass 'registers native Waybar click, scan, and toggle actions'
grep -F '#bluetooth.connected' "$ROOT/dotfiles/.config/waybar/style.css" >/dev/null
pass 'styles connected and powered-off Bluetooth states'
grep -F '*Bluetooth*) obsidian-bluetooth' "$ROOT/dotfiles/.local/bin/obsidian-menu" >/dev/null
pass 'routes OMA Bluetooth controls to the native manager'
grep -F 'audio-headset' "$ROOT/dotfiles/.local/bin/obsidian-bluetooth" >/dev/null
grep -F 'systemsettings kcm_pulseaudio' "$ROOT/dotfiles/.local/bin/obsidian-bluetooth" >/dev/null
pass 'supports headset icons and PipeWire audio settings'

printf '\nAll Bluetooth integration tests passed.\n'
