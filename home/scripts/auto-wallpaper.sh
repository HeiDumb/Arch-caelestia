#!/usr/bin/env bash

set -euo pipefail

ENGINE="$HOME/linux-wallpaperengine/build/output/linux-wallpaperengine"
STEAM_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/Steam"
WORKSHOP="$STEAM_ROOT/steamapps/workshop/content/431960"
ASSETS_CANDIDATES=(
    "$STEAM_ROOT/steamapps/common/wallpaper_engine/assets"
    "$HOME/.steam/steam/steamapps/common/wallpaper_engine/assets"
)
STATE="$HOME/.cache/current-wallpaper"
VALIDATION_TIMEOUT="2"
COMPAT_PATTERNS=(
    "Unsupported project type"
    "filesystem error:"
    "Text objects are not supported yet"
    "Unknown object type found:"
    "ReferenceError:"
    "Cannot load video"
    "Cannot load video texture"
    "json.exception."
)

find_assets_dir() {
    local dir
    for dir in "${ASSETS_CANDIDATES[@]}"; do
        if [[ -d "$dir" ]]; then
            printf '%s\n' "$dir"
            return 0
        fi
    done

    return 1
}

validate_wallpaper() {
    local id="$1"
    local output=""
    local pattern
    local issues=()

    output="$(
        timeout "$VALIDATION_TIMEOUT" \
            "$ENGINE" \
            --assets-dir "$ASSETS" \
            --silent \
            --dump-structure \
            "$id" 2>&1 || true
    )"

    for pattern in "${COMPAT_PATTERNS[@]}"; do
        if [[ "$output" == *"$pattern"* ]]; then
            issues+=("$pattern")
        fi
    done

    if ((${#issues[@]})); then
        local joined
        joined="$(IFS=' | '; printf '%s' "${issues[*]}")"
        printf '%s\n' "$joined"
        return 1
    fi

    return 0
}

get_monitor_name() {
    python3 - <<'PY'
import json
import subprocess

default = "eDP-1"

try:
    output = subprocess.check_output(["hyprctl", "-j", "monitors"], text=True)
    monitors = json.loads(output)
except Exception:
    print(default)
    raise SystemExit

if not monitors:
    print(default)
    raise SystemExit

focused = next((m for m in monitors if m.get("focused")), monitors[0])
print(focused.get("name", default))
PY
}

wait_for_wallpaper_engine_target() {
    local output=""
    local attempt

    for attempt in $(seq 1 60); do
        if output="$(qs ipc -c caelestia show 2>/dev/null)" && grep -q '^target wallpaperEngine$' <<< "$output"; then
            return 0
        fi
        sleep 0.2
    done

    return 1
}

apply_wallpaper_engine() {
    local project_path="$1"

    if ! wait_for_wallpaper_engine_target; then
        notify-send -u critical "Wallpaper Engine" "Caelestia's wallpaper engine target did not become ready."
        return 1
    fi

    if qs ipc -c caelestia call wallpaperEngine set "$project_path" >/dev/null 2>&1; then
        return 0
    fi

    sleep 0.4
    qs ipc -c caelestia call wallpaperEngine set "$project_path" >/dev/null 2>&1
}

select_compatible_wallpaper() {
    local dir
    local id

    for dir in "$WORKSHOP"/*; do
        [[ -d "$dir" ]] || continue

        id="$(basename "$dir")"
        if validate_wallpaper "$id" >/dev/null; then
            printf '%s\n' "$id"
            return 0
        fi
    done

    return 1
}

ASSETS="$(find_assets_dir)" || exit 1

[[ -x "$ENGINE" ]] || exit 1
[[ -d "$WORKSHOP" ]] || exit 1

while ! hyprctl monitors >/dev/null 2>&1; do
    sleep 1
done

sleep 2

if [[ ! -f "$STATE" ]]; then
    id="$(select_compatible_wallpaper)" || {
        notify-send -u critical "Wallpaper Engine" "No compatible wallpapers found."
        exit 1
    }
    printf '%s\n' "$id" > "$STATE"
fi

id="$(cat "$STATE")"

if [[ ! -d "$WORKSHOP/$id" ]]; then
    id="$(select_compatible_wallpaper)" || {
        notify-send -u critical "Wallpaper Engine" "Saved wallpaper was missing, and no compatible fallback was found."
        exit 1
    }
    printf '%s\n' "$id" > "$STATE"
elif ! issues="$(validate_wallpaper "$id")"; then
    previous_id="$id"
    id="$(select_compatible_wallpaper)" || {
        notify-send -u critical "Wallpaper Engine" "Saved wallpaper $previous_id is incompatible: $issues"
        exit 1
    }
    printf '%s\n' "$id" > "$STATE"
    notify-send -u normal "Wallpaper Engine" "Skipped incompatible wallpaper $previous_id and switched to $id."
fi

for _ in $(seq 1 30); do
    if qs ipc -c caelestia show >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

if ! apply_wallpaper_engine "$WORKSHOP/$id"; then
    notify-send -u critical "Wallpaper Engine" "Failed to restore wallpaper through Caelestia."
    exit 1
fi
