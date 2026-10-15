#!/usr/bin/env bash
# Install the Ulanzi D200X device plugin into OpenDeck.
#
#   ./install.sh            install (auto-detects Flatpak vs native OpenDeck)
#   ./install.sh --link     symlink instead of copy (handy while developing)
#   ./install.sh --uninstall
set -euo pipefail

PLUGIN="dev.kastro5.ulanzi-d200.sdPlugin"
# Before 1.3.0 the plugin lived under the upstream bundle ID; both would claim the deck.
LEGACY_PLUGIN="com.ulanzi.d200x.sdPlugin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/$PLUGIN"
RULE_SRC="$HERE/60-ulanzi-d200x.rules"

FLATPAK_DIR="$HOME/.var/app/me.amankhanna.opendeck/config/opendeck/plugins"
NATIVE_DIR="$HOME/.config/opendeck/plugins"

# Both directories can exist (e.g. the Flatpak was tried first), so prefer the
# one belonging to the OpenDeck that is actually running.
DEST_DIR=""
if pgrep -f '^/usr/bin/opendeck' >/dev/null 2>&1 || pgrep -f 'bin/opendeck$' >/dev/null 2>&1; then
	DEST_DIR="$NATIVE_DIR"
elif pgrep -f 'me\.amankhanna\.opendeck' >/dev/null 2>&1; then
	DEST_DIR="$FLATPAK_DIR"
fi

if [[ -z "$DEST_DIR" ]]; then
	for candidate in "$NATIVE_DIR" "$FLATPAK_DIR"; do
		[[ -d "$candidate" ]] && DEST_DIR="$candidate" && break
	done
fi

if [[ -z "$DEST_DIR" ]]; then
	echo "Could not find an OpenDeck plugins directory." >&2
	echo "Looked in:  $NATIVE_DIR" >&2
	echo "            $FLATPAK_DIR" >&2
	echo "Start OpenDeck once so it creates its config, then re-run this script." >&2
	exit 1
fi
mkdir -p "$DEST_DIR"

DEST="$DEST_DIR/$PLUGIN"

if [[ "${1:-}" == "--uninstall" ]]; then
	rm -rf "$DEST" "$DEST_DIR/$LEGACY_PLUGIN"
	echo "Removed $DEST"
	echo "Restart OpenDeck to finish."
	exit 0
fi

# The plugin runs on the host (via flatpak-spawn), so check the host's Python.
missing=()
for mod in hid PIL websockets; do
	python3 -c "import $mod" 2>/dev/null || missing+=("$mod")
done
if (( ${#missing[@]} )); then
	echo "Missing Python modules on the host: ${missing[*]}" >&2
	echo "Arch/CachyOS:  sudo pacman -S python-hidapi python-pillow python-websockets" >&2
	echo "Debian/Ubuntu: sudo apt install python3-hid python3-pil python3-websockets" >&2
	exit 1
fi

# hidraw access. Don't guess from rule filenames -- just try the device nodes,
# which is the only thing that actually matters.
ACCESS="$(python3 - <<'PY'
import os
import hid
nodes = [d["path"].decode() for d in hid.enumerate(0x2207, 0x0019)]
if not nodes:
    print("absent")
elif all(os.access(n, os.R_OK | os.W_OK) for n in nodes):
    print("ok")
else:
    print("denied " + " ".join(n for n in nodes if not os.access(n, os.R_OK | os.W_OK)))
PY
)"

case "$ACCESS" in
ok)
	echo "Device found and accessible."
	;;
absent)
	echo "Note: no D200X currently plugged in, so device access could not be checked."
	echo "      If it is not detected later, install the udev rule:"
	echo "        sudo cp '$RULE_SRC' /etc/udev/rules.d/"
	echo "        sudo udevadm control --reload-rules && sudo udevadm trigger"
	;;
denied*)
	echo
	echo "The D200X is connected but not writable by this user: ${ACCESS#denied }" >&2
	echo "Install the udev rule, then unplug and replug the device:" >&2
	echo "  sudo cp '$RULE_SRC' /etc/udev/rules.d/" >&2
	echo "  sudo udevadm control --reload-rules && sudo udevadm trigger" >&2
	echo >&2
	echo "Continuing with the install; the plugin will not see the device until this is fixed." >&2
	;;
esac

rm -rf "$DEST"
if [[ -e "$DEST_DIR/$LEGACY_PLUGIN" ]]; then
	rm -rf "$DEST_DIR/$LEGACY_PLUGIN"
	echo "Removed the pre-1.3.0 copy ($LEGACY_PLUGIN); its settings carry over on first start."
fi
if [[ "${1:-}" == "--link" ]]; then
	ln -s "$SRC" "$DEST"
	echo "Linked $SRC -> $DEST"
else
	cp -r "$SRC" "$DEST"
	find "$DEST" -name __pycache__ -prune -exec rm -rf {} +
	echo "Installed to $DEST"
fi

chmod +x "$DEST/launch.sh" "$DEST/d200x_plugin.py" 2>/dev/null || true

# Another D200-family device plugin will fight over the same hidraw node.
CONFLICT="$DEST_DIR/com.glmagalhaes.ulanzi.d200.sdPlugin"
if [[ -e "$CONFLICT" ]]; then
	echo
	echo "WARNING: '$(basename "$CONFLICT")' is also installed and claims the same"
	echo "         hardware. Remove it (or disable it in OpenDeck's plugin manager)"
	echo "         before using this plugin, or the two will fight over the device."
fi

echo
echo "Restart OpenDeck. The D200X should appear in the device selector."
