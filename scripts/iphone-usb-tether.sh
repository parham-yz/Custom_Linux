#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: iphone-usb-tether.sh [--keep-wifi | --wifi-on]

Connect an unlocked iPhone by USB, enable Personal Hotspot, and accept the
Trust prompt. By default this script disables Wi-Fi after USB internet works,
ensuring that traffic uses only the cable.

Options:
  --keep-wifi  Connect USB tethering without disabling Wi-Fi
  --wifi-on    Re-enable Wi-Fi and exit
  -h, --help   Show this help
EOF
}

keep_wifi=false
case "${1:-}" in
  "") ;;
  --keep-wifi) keep_wifi=true ;;
  --wifi-on) nmcli radio wifi on; echo "Wi-Fi enabled."; exit 0 ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

need=(nmcli ip lsusb)
for command_name in "${need[@]}"; do
  command -v "$command_name" >/dev/null || {
    echo "Error: required command not found: $command_name" >&2
    exit 1
  }
done

if ! command -v idevicepair >/dev/null; then
  if ! command -v dnf >/dev/null; then
    echo "Error: idevicepair is missing; install libimobiledevice-utils." >&2
    exit 1
  fi
  echo "Installing the iPhone pairing utility..."
  if [[ -t 0 ]]; then
    sudo dnf install -y libimobiledevice-utils
  elif command -v pkexec >/dev/null; then
    pkexec dnf install -y libimobiledevice-utils
  else
    echo "Error: run 'sudo dnf install libimobiledevice-utils' first." >&2
    exit 1
  fi
fi

if ! lsusb -d 05ac: >/dev/null 2>&1; then
  cat >&2 <<'EOF'
No Apple USB device detected.
Unlock the iPhone, enable Settings > Personal Hotspot > Allow Others to Join,
connect it directly with a data-capable cable, and retry.
EOF
  exit 1
fi

if ! lsmod | grep -q '^ipheth '; then
  echo "Loading the iPhone USB Ethernet driver..."
  if [[ -t 0 ]]; then
    sudo modprobe ipheth
  elif command -v pkexec >/dev/null; then
    pkexec modprobe ipheth
  else
    echo "Error: run 'sudo modprobe ipheth' first." >&2
    exit 1
  fi
fi

mapfile -t device_ids < <(idevice_id -l)
if ((${#device_ids[@]} == 0)); then
  echo "Error: usbmuxd cannot see the iPhone. Unlock and reconnect it." >&2
  exit 1
fi

udid="${device_ids[0]}"
echo "Pairing with iPhone $udid..."
if ! idevicepair -u "$udid" validate >/dev/null 2>&1; then
  if ! idevicepair -u "$udid" pair; then
    cat >&2 <<'EOF'
Pairing did not complete. Unlock the iPhone, tap Trust, enter its passcode,
and rerun this script.
EOF
    exit 1
  fi
fi
idevicepair -u "$udid" validate >/dev/null

interface=""
for _ in {1..15}; do
  for candidate in /sys/class/net/*; do
    [[ -e "$candidate/device/driver" ]] || continue
    [[ "$(basename "$(readlink -f "$candidate/device/driver")")" == ipheth ]] || continue
    interface="${candidate##*/}"
    break
  done
  [[ -n "$interface" ]] && break
  sleep 1
done

if [[ -z "$interface" ]]; then
  echo "Error: the ipheth Ethernet interface did not appear." >&2
  exit 1
fi

echo "Connecting NetworkManager interface $interface..."
nmcli device set "$interface" managed yes
nmcli device connect "$interface" >/dev/null 2>&1 || true

connected=false
for _ in {1..30}; do
  if [[ "$(nmcli -g GENERAL.STATE device show "$interface" | cut -d' ' -f1)" == 100 ]]      && ip -4 route show default dev "$interface" | grep -q .; then
    connected=true
    break
  fi
  sleep 1
done

if [[ "$connected" != true ]]; then
  echo "Error: USB tethering did not obtain an address/default route." >&2
  echo "Confirm that Personal Hotspot is enabled and allowed by your carrier." >&2
  exit 1
fi

if [[ "$keep_wifi" != true ]]; then
  nmcli radio wifi off
fi

if ! ping -I "$interface" -c 1 -W 5 1.1.1.1 >/dev/null 2>&1; then
  echo "Warning: USB connected, but the internet connectivity test failed." >&2
  exit 1
fi

address="$(ip -4 -o addr show dev "$interface" | awk '{print $4; exit}')"
echo "iPhone USB tethering is active on $interface (${address:-address unknown})."
if [[ "$keep_wifi" == true ]]; then
  echo "Wi-Fi was left enabled. USB normally has the lower route metric."
else
  echo "Wi-Fi is disabled; internet traffic is using only the USB cable."
  echo "Restore Wi-Fi with: $0 --wifi-on"
fi
