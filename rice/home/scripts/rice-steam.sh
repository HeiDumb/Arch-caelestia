#!/usr/bin/env bash

set -euo pipefail

THEME_DIR="$HOME/.local/share/steam-rice/Adwaita-for-Steam"
STEAM_DIR="$HOME/.local/share/Steam"

cd "$THEME_DIR"

python3 install.py \
  --target "$STEAM_DIR" \
  --color-theme adwaita-gray \
  --windowcontrols-layout ':' \
  --custom-css \
  --extras library/hide_whats_new general/cursor_pointer

printf 'Steam theme reapplied to %s\n' "$STEAM_DIR"
