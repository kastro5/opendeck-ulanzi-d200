#!/usr/bin/env bash
# Launcher for the Ulanzi D200X OpenDeck device plugin.
#
# OpenDeck invokes this with:
#   -port <N> -pluginUUID <UUID> -registerEvent registerPlugin -info <JSON>
#
# When OpenDeck runs as a Flatpak, native plugins are started *inside* the
# sandbox, where the host's python3/hidapi and /dev/hidraw* are not reachable.
# `flatpak-spawn --host` (OpenDeck holds org.freedesktop.Flatpak=talk) runs the
# plugin on the host instead.
set -euo pipefail

#
# Release zips carry a self-contained build (d200x_plugin-linux) that needs no
# Python packages; a source checkout (install.sh --link) runs the script with the
# system python3 and its hidapi/pillow/websockets.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="$SCRIPT_DIR/d200x_plugin-linux"

if [ -x "$BINARY" ]; then
	set -- "$BINARY" "$@"
else
	set -- python3 "$SCRIPT_DIR/d200x_plugin.py" "$@"
fi

if command -v flatpak-spawn >/dev/null 2>&1; then
	exec flatpak-spawn --host "$@"
else
	exec "$@"
fi
