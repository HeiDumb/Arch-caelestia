#!/usr/bin/env bash

set -euo pipefail

ENGINE="$HOME/linux-wallpaperengine/build/output/linux-wallpaperengine"
ROFI_BIN="${ROFI_BIN:-rofi}"
STEAM_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/Steam"
WORKSHOP="$STEAM_ROOT/steamapps/workshop/content/431960"
ASSETS_CANDIDATES=(
    "$STEAM_ROOT/steamapps/common/wallpaper_engine/assets"
    "$HOME/.steam/steam/steamapps/common/wallpaper_engine/assets"
)
STATE="$HOME/.cache/current-wallpaper"
PREVIEW_CACHE="$HOME/.cache/wallpaper-previews"
COMPAT_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/we-wallpaper-compat.tsv"
COMPAT_CACHE_VERSION="2"
VALIDATION_TIMEOUT="2"

COMPAT_PATTERNS=(
    "Unsupported project type"
    "filesystem error:"
    "Cannot load video"
    "Cannot load video texture"
)

mkdir -p "$HOME/.cache" "$PREVIEW_CACHE" "$(dirname "$COMPAT_CACHE")"

declare -A COMPAT_MTIME=()
declare -A COMPAT_STATUS=()
declare -A COMPAT_ISSUES=()
compat_cache_dirty=0

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

get_monitor_info() {
    python3 - <<'PY'
import json
import subprocess

default = ("eDP-1", 1920, 1080, 1.0)

try:
    output = subprocess.check_output(["hyprctl", "-j", "monitors"], text=True)
    monitors = json.loads(output)
except Exception:
    print(*default)
    raise SystemExit

if not monitors:
    print(*default)
    raise SystemExit

focused = next((m for m in monitors if m.get("focused")), monitors[0])
print(
    focused.get("name", default[0]),
    int(focused.get("width", default[1])),
    int(focused.get("height", default[2])),
    float(focused.get("scale", default[3])),
)
PY
}

build_theme_override() {
    python3 - "$1" "$2" "$3" <<'PY'
import sys

width = int(sys.argv[1])
height = int(sys.argv[2])
scale = float(sys.argv[3]) or 1.0

logical_width = max(1024, int(width / scale))
logical_height = max(720, int(height / scale))

icon_size = max(230, min(320, int(min(logical_width * 0.17, logical_height * 0.40))))
columns = max(5, min(9, int((logical_width * 0.92) / max(icon_size * 0.82, 1))))
pad_x = max(40, int(logical_width * 0.035))
pad_top = max(110, int(logical_height * 0.18))
pad_bottom = max(56, int(logical_height * 0.10))
spacing = -max(20, int(icon_size * 0.12))

print(f"""
configuration {{
    show-icons: true;
    hover-select: true;
    me-select-entry: "";
    me-accept-entry: "MousePrimary";
    kb-accept-entry: "Return,KP_Enter,space";
    kb-cancel: "Escape";
}}

* {{
    bg:              rgba (0, 0, 0, 0%);
    fg:              rgba (245, 238, 232, 95%);
}}

window {{
    transparency:     "real";
    fullscreen:       true;
    location:         center;
    anchor:           center;
    width:            100%;
    height:           100%;
    x-offset:         0px;
    y-offset:         0px;
    padding:          0px;
    margin:           0px;
    border:           0px;
    border-radius:    0px;
    background-color: transparent;
}}

mainbox {{
    orientation:      vertical;
    children:         [ "listview" ];
    spacing:          0px;
    padding:          {pad_top}px {pad_x}px {pad_bottom}px {pad_x}px;
    margin:           0px;
    border:           0px;
    background-color: transparent;
}}

listview {{
    flow:             horizontal;
    layout:           vertical;
    columns:          {columns};
    lines:            1;
    cycle:            true;
    dynamic:          false;
    fixed-height:     true;
    fixed-columns:    true;
    scrollbar:        false;
    spacing:          {spacing}px;
    margin:           0px;
    padding:          0px;
    border:           0px;
    background-color: transparent;
}}

element {{
    orientation:      vertical;
    margin:           0px;
    padding:          0px;
    border:           0px;
    background-color: transparent;
}}

element normal.normal,
element alternate.normal,
element selected.normal {{
    background-color: transparent;
    text-color: @fg;
}}

element-icon {{
    size:             {icon_size}px;
    margin:           0px;
    padding:          0px;
    border:           0px;
    background-color: transparent;
}}

element-text {{
    enabled:          false;
}}
""")
PY
}

render_card_preview() {
    local source="$1"
    local target="$2"

    python3 - "$source" "$target" <<'PY'
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageOps

source, target = sys.argv[1:3]

card_w = 500
card_h = 720
slant = 104
pad_left = 84
pad_right = 84
pad_top = 42
pad_bottom = 42

with Image.open(source) as img:
    if getattr(img, "is_animated", False):
        img.seek(0)
    img = img.convert("RGBA")
    card = ImageOps.fit(
        img,
        (card_w, card_h),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

mask = Image.new("L", (card_w, card_h), 0)
draw = ImageDraw.Draw(mask)
polygon = [(slant, 0), (card_w, 0), (card_w - slant, card_h), (0, card_h)]
draw.polygon(polygon, fill=255)

card.putalpha(mask)

canvas = Image.new(
    "RGBA",
    (card_w + pad_left + pad_right, card_h + pad_top + pad_bottom),
    (0, 0, 0, 0),
)

shadow_mask = mask.filter(ImageFilter.GaussianBlur(28))
shadow = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 190))
shadow.putalpha(shadow_mask)
canvas.alpha_composite(shadow, (pad_left + 18, pad_top + 24))

card_overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
card_draw = ImageDraw.Draw(card_overlay)
card_draw.polygon(polygon, fill=(255, 255, 255, 8))
card_draw.line((slant + 18, 18, card_w - 34, 18), fill=(255, 248, 240, 48), width=2)
card_draw.polygon(polygon, outline=(255, 244, 234, 144), width=3)

canvas.alpha_composite(card, (pad_left, pad_top))
canvas.alpha_composite(card_overlay, (pad_left, pad_top))
canvas.save(target)
PY
}

find_preview() {
    local dir="$1"
    local id="$2"
    local preview=""
    local candidate

    for candidate in preview.jpg preview.png thumbnail.jpg thumbnail.png preview.gif; do
        if [[ -f "$dir/$candidate" ]]; then
            preview="$dir/$candidate"
            break
        fi
    done

    if [[ "$preview" == *.gif ]]; then
        local png="$PREVIEW_CACHE/${id}.png"
        if [[ ! -f "$png" || "$preview" -nt "$png" ]]; then
            ffmpeg -y -i "$preview" -vframes 1 "$png" >/dev/null 2>&1 || true
        fi
        [[ -f "$png" ]] && preview="$png"
    fi

    if [[ -n "$preview" ]]; then
        local card="$PREVIEW_CACHE/${id}-card.png"
        if [[ ! -f "$card" || "$preview" -nt "$card" ]]; then
            render_card_preview "$preview" "$card" || true
        fi
        [[ -f "$card" ]] && preview="$card"
    fi

    printf '%s\n' "$preview"
}

load_compat_cache() {
    [[ -f "$COMPAT_CACHE" ]] || return 0

    while IFS=$'\t' read -r version id mtime status issues; do
        [[ "$version" == "$COMPAT_CACHE_VERSION" ]] || continue
        [[ -n "$id" ]] || continue
        COMPAT_MTIME["$id"]="$mtime"
        COMPAT_STATUS["$id"]="$status"
        COMPAT_ISSUES["$id"]="$issues"
    done < "$COMPAT_CACHE"
}

save_compat_cache() {
    local tmp
    tmp="$(mktemp)"

    for id in "${!COMPAT_STATUS[@]}"; do
        printf '%s\t%s\t%s\t%s\t%s\n' \
            "$COMPAT_CACHE_VERSION" \
            "$id" \
            "${COMPAT_MTIME[$id]}" \
            "${COMPAT_STATUS[$id]}" \
            "${COMPAT_ISSUES[$id]}"
    done | sort -n > "$tmp"

    mv "$tmp" "$COMPAT_CACHE"
}

project_mtime() {
    local dir="$1"

    if [[ -f "$dir/project.json" ]]; then
        stat -c %Y "$dir/project.json"
        return 0
    fi

    printf '0\n'
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

refresh_compat_cache() {
    local dir
    local id
    local mtime
    local issues

    for dir in "$WORKSHOP"/*; do
        [[ -d "$dir" ]] || continue

        id="$(basename "$dir")"
        mtime="$(project_mtime "$dir")"

        if [[ ${COMPAT_MTIME[$id]+x} && "${COMPAT_MTIME[$id]}" == "$mtime" ]]; then
            continue
        fi

        if issues="$(validate_wallpaper "$id")"; then
            COMPAT_STATUS["$id"]="compatible"
            COMPAT_ISSUES["$id"]=""
        else
            COMPAT_STATUS["$id"]="incompatible"
            COMPAT_ISSUES["$id"]="$issues"
        fi

        COMPAT_MTIME["$id"]="$mtime"
        compat_cache_dirty=1
    done

    if ((compat_cache_dirty)); then
        save_compat_cache
    fi
}

cached_compatibility_status() {
    local dir="$1"
    local id="$2"
    local mtime

    mtime="$(project_mtime "$dir")"

    if [[ ${COMPAT_MTIME[$id]+x} && "${COMPAT_MTIME[$id]}" == "$mtime" ]]; then
        [[ "${COMPAT_STATUS[$id]}" == "compatible" ]]
        return
    fi

    return 2
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

select_wallpaper_rofi() {
    local items_file="$1"
    local theme_file="$2"
    local menu_file
    local current_id=""
    local current_index=0
    local selected_index=""
    local index=0
    local id preview title
    local -a ids=()

    [[ -f "$STATE" ]] && current_id="$(<"$STATE")"

    menu_file="$(mktemp)"
    trap 'rm -f "$menu_file"' RETURN

    while IFS=$'\t' read -r id preview title; do
        [[ -n "$id" ]] || continue
        [[ -f "$preview" ]] || continue

        ids+=("$id")
        if [[ -n "$current_id" && "$id" == "$current_id" ]]; then
            current_index="$index"
        fi

        printf '%s\0icon\x1f%s\n' "$title" "$preview" >> "$menu_file"
        ((index += 1))
    done < "$items_file"

    [[ ${#ids[@]} -gt 0 ]] || return 1

    selected_index="$(
        "$ROFI_BIN" -dmenu \
            -theme "$theme_file" \
            -show-icons \
            -format i \
            -no-custom \
            -selected-row "$current_index" \
            < "$menu_file" || true
    )"

    [[ -n "$selected_index" ]] || return 1
    [[ "$selected_index" =~ ^[0-9]+$ ]] || return 1
    (( selected_index >= 0 && selected_index < ${#ids[@]} )) || return 1

    printf '%s\n' "${ids[$selected_index]}"
}

ASSETS="$(find_assets_dir)" || {
    notify-send -u critical "Wallpaper Engine" "Could not find wallpaper_engine/assets."
    exit 1
}

if [[ ! -x "$ENGINE" ]]; then
    notify-send -u critical "Wallpaper Engine" "Engine binary not found at $ENGINE."
    exit 1
fi

if [[ ! -d "$WORKSHOP" ]]; then
    notify-send -u critical "Wallpaper Engine" "Workshop folder not found at $WORKSHOP."
    exit 1
fi

if ! command -v "$ROFI_BIN" >/dev/null 2>&1; then
    notify-send -u critical "Wallpaper Engine" "Rofi not found in PATH."
    exit 1
fi

load_compat_cache

if [[ "${1:-}" == "--refresh-cache" ]]; then
    refresh_compat_cache
    exit 0
fi

read -r MONITOR MONITOR_WIDTH MONITOR_HEIGHT MONITOR_SCALE < <(get_monitor_info)

items_file="$(mktemp)"
theme_file="$(mktemp --suffix=.rasi)"
trap 'rm -f "$items_file" "$theme_file"' EXIT

build_theme_override "$MONITOR_WIDTH" "$MONITOR_HEIGHT" "$MONITOR_SCALE" > "$theme_file"

for dir in "$WORKSHOP"/*; do
    [[ -d "$dir" ]] || continue

    id="$(basename "$dir")"
    title=""

    status=0
    cached_compatibility_status "$dir" "$id" || status=$?
    if [[ "$status" != "0" ]]; then
        if [[ "$status" == "2" ]]; then
            mtime="$(project_mtime "$dir")"
            if issues="$(validate_wallpaper "$id")"; then
                COMPAT_STATUS["$id"]="compatible"
                COMPAT_ISSUES["$id"]=""
            else
                COMPAT_STATUS["$id"]="incompatible"
                COMPAT_ISSUES["$id"]="$issues"
                COMPAT_MTIME["$id"]="$mtime"
                compat_cache_dirty=1
                continue
            fi

            COMPAT_MTIME["$id"]="$mtime"
            compat_cache_dirty=1
        else
            continue
        fi
    fi

    if [[ -f "$dir/project.json" ]]; then
        title="$(
            python3 - "$dir/project.json" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    print("")
    raise SystemExit

print(data.get("title", ""))
PY
)"
    fi

    [[ -n "$title" ]] || title="$id"
    title="${title//$'\t'/ }"
    title="${title//$'\n'/ }"
    title="${title//$'\r'/ }"

    preview="$(find_preview "$dir" "$id")"
    [[ -n "$preview" ]] || continue
    [[ -f "$preview" ]] || continue

    printf '%s\t%s\t%s\n' "$id" "$preview" "$title" >> "$items_file"
done

if ((compat_cache_dirty)); then
    save_compat_cache
fi

[[ -s "$items_file" ]] || {
    notify-send -u critical "Wallpaper Engine" "No compatible wallpapers found."
    exit 1
}

if ! id="$(select_wallpaper_rofi "$items_file" "$theme_file")"; then
    exit 0
fi

[[ -n "$id" ]] || exit 1
[[ -d "$WORKSHOP/$id" ]] || {
    notify-send -u critical "Wallpaper Engine" "Selected wallpaper directory is missing: $WORKSHOP/$id"
    exit 1
}

mtime="$(project_mtime "$WORKSHOP/$id")"
if issues="$(validate_wallpaper "$id")"; then
    COMPAT_STATUS["$id"]="compatible"
    COMPAT_ISSUES["$id"]=""
else
    COMPAT_STATUS["$id"]="incompatible"
    COMPAT_ISSUES["$id"]="$issues"
    COMPAT_MTIME["$id"]="$mtime"
    save_compat_cache
    notify-send -u critical "Wallpaper Engine" "Selected wallpaper is incompatible: $issues"
    exit 1
fi

COMPAT_MTIME["$id"]="$mtime"
save_compat_cache

printf '%s\n' "$id" > "$STATE"

if ! apply_wallpaper_engine "$WORKSHOP/$id"; then
    notify-send -u critical "Wallpaper Engine" "Failed to hand wallpaper change to Caelestia."
    exit 1
fi
