#!/usr/bin/env python3

import argparse
import configparser
import json
import re
import shutil
import subprocess
import time
from pathlib import Path


HOME = Path.home()
SCHEME_PATH = HOME / ".local/state/caelestia/scheme.json"

HYPR_BORDER_PATH = HOME / ".config/hypr/dynamic-border.conf"
HYPRLOCK_CONFIG_PATH = HOME / ".config/quickshell/caelestia/assets/hyprlock.conf"
HYPRLOCK_MARKER_BEGIN = "# Begin wallpaper-synced colours"
HYPRLOCK_MARKER_END = "# End wallpaper-synced colours"
GTK3_DYNAMIC_PATH = HOME / ".config/gtk-3.0/caelestia-dynamic.css"
GTK4_DYNAMIC_PATH = HOME / ".config/gtk-4.0/caelestia-dynamic.css"
GTK3_THUNAR_PATH = HOME / ".config/gtk-3.0/thunar.css"
GTK4_THUNAR_PATH = HOME / ".config/gtk-4.0/thunar.css"
ROFI_DYNAMIC_PATH = HOME / ".config/rofi/caelestia-dynamic.rasi"
FOOT_DYNAMIC_PATH = HOME / ".config/foot/colors.ini"
ZSH_THEME_PATH = HOME / ".config/zsh/wallpaper-theme.zsh"
CODE_SETTINGS_PATH = HOME / ".config/Code - OSS/User/settings.json"
KDE_GLOBALS_PATH = HOME / ".config/kdeglobals"
SPICETIFY_CONFIG_PATH = HOME / ".config/spicetify/config-xpui.ini"
SPICETIFY_THEME_PATH = HOME / ".config/spicetify/Themes/caelestia/color.ini"
ZED_THEME_PATH = HOME / ".config/zed/themes/caelestia.json"
STEAM_LIBRARYROOT_CUSTOM_CSS_PATH = HOME / ".local/share/Steam/steamui/libraryroot.custom.css"
STEAM_DYNAMIC_CSS_PATH = HOME / ".local/share/Steam/steamui/caelestia-dynamic.css"
STEAM_DYNAMIC_IMPORT = '@import url("https://steamloopback.host/caelestia-dynamic.css");'
DISCORD_THEME_PATHS = [
    HOME / ".config/Vencord/themes/caelestia.theme.css",
    HOME / ".config/vesktop/themes/caelestia.theme.css",
    HOME / ".config/BetterDiscord/themes/caelestia.theme.css",
    HOME / ".config/legcord/themes/caelestia.theme.css",
    HOME / ".config/equibop/themes/caelestia.theme.css",
    HOME / ".config/Equicord/themes/caelestia.theme.css",
]
ZEN_MARKER_BEGIN = "/* Begin Caelestia Dynamic */"
ZEN_MARKER_END = "/* End Caelestia Dynamic */"


def hex_rgb(value: str | None, fallback: str) -> str:
    value = (value or "").strip().lower().lstrip("#")
    if len(value) >= 6:
        return value[:6]
    return fallback


def hex_rgba(value: str | None, alpha: str = "ff", fallback: str = "ffffff") -> str:
    value = (value or "").strip().lower().lstrip("#")
    if len(value) == 8:
        return value
    if len(value) == 6:
        return f"{value}{alpha}"
    return f"{fallback}{alpha}"


def rgb_tuple(value: str | None, fallback: str) -> tuple[int, int, int]:
    rgb = hex_rgb(value, fallback)
    return tuple(int(rgb[i : i + 2], 16) for i in (0, 2, 4))


def clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def blend(rgb_a: tuple[int, int, int], rgb_b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(
        clamp_channel(a + (b - a) * amount)
        for a, b in zip(rgb_a, rgb_b)
    )


def rgba_css(value: str | None, alpha: float, fallback: str) -> str:
    r, g, b = rgb_tuple(value, fallback)
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def hex_css(value: str | None, fallback: str) -> str:
    return f"#{hex_rgb(value, fallback)}"


def hex_with_alpha(value: str | None, alpha: str, fallback: str) -> str:
    return f"#{hex_rgba(value, alpha=alpha, fallback=fallback)}"


def rgb_css(value: str | None, fallback: str) -> str:
    r, g, b = rgb_tuple(value, fallback)
    return f"rgb({r}, {g}, {b})"


def rgb_csv(value: str | None, fallback: str) -> str:
    r, g, b = rgb_tuple(value, fallback)
    return f"{r},{g},{b}"


def hex_from_rgb(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def sgr_truecolor(value: str | None, fallback: str) -> str:
    r, g, b = rgb_tuple(value, fallback)
    return f"38;2;{r};{g};{b}"


def mixed_rgb_css(value: str | None, fallback: str, mix_with: str, amount: float) -> str:
    base = rgb_tuple(value, fallback)
    other = rgb_tuple(mix_with, mix_with)
    mixed = blend(base, other, amount)
    return f"rgb({mixed[0]}, {mixed[1]}, {mixed[2]})"


def write_file(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == content:
                return False
        except OSError:
            pass
    path.write_text(content, encoding="utf-8")
    return True


def new_config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    return parser


def ensure_import_line(path: Path, line: str) -> None:
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    stripped = line.strip()
    if any(existing.strip() == stripped for existing in text.splitlines()):
        return

    path.write_text(f"{line}\n{text}", encoding="utf-8")


def ensure_line_after(path: Path, anchor: str, line: str) -> None:
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    stripped = line.strip()
    if any(existing.strip() == stripped for existing in text.splitlines()):
        return

    if anchor in text:
        updated = text.replace(anchor, f"{anchor}\n{line}", 1)
    elif "\n:root" in text:
        updated = text.replace("\n:root", f"\n{line}\n\n:root", 1)
    else:
        updated = f"{line}\n{text}"

    path.write_text(updated, encoding="utf-8")


def ensure_discord_theme_targets() -> None:
    template = next((path for path in DISCORD_THEME_PATHS if path.exists()), None)
    if template is None:
        return

    try:
        content = template.read_text(encoding="utf-8")
    except OSError:
        return

    for path in DISCORD_THEME_PATHS:
        if path.exists():
            continue
        write_file(path, content)


def first_existing_paths(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.glob(pattern) if path.is_file())


def theme_exists(name: str) -> bool:
    if not name:
        return False

    roots = (
        HOME / ".themes" / name,
        HOME / ".local/share/themes" / name,
        Path("/usr/share/themes") / name,
    )
    return any(root.exists() for root in roots)


def pick_theme_toggle(current: str | None) -> tuple[str, str] | None:
    if not current:
        return None

    current = current.strip()
    if not current:
        return None

    candidates: list[str]
    if current.endswith("-dark"):
        candidates = [current[:-5], "adw-gtk3", "Adwaita"]
    else:
        candidates = [f"{current}-dark", "adw-gtk3-dark", "Adwaita-dark"]

    for candidate in candidates:
        if candidate and candidate != current and theme_exists(candidate):
            return current, candidate

    return None


def read_command_text(args: list[str]) -> str | None:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def refresh_gtk_theme() -> None:
    if shutil.which("xfconf-query"):
        current = read_command_text(["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName"])
        toggle = pick_theme_toggle(current)
        if toggle:
            original, alternate = toggle
            for prop in ("/Net/ThemeName", "/Gtk/ThemeName"):
                subprocess.run(
                    ["xfconf-query", "-c", "xsettings", "-p", prop, "-s", alternate],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            time.sleep(0.12)
            for prop in ("/Net/ThemeName", "/Gtk/ThemeName"):
                subprocess.run(
                    ["xfconf-query", "-c", "xsettings", "-p", prop, "-s", original],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )

    if shutil.which("gsettings"):
        current = read_command_text(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"])
        if current:
            current = current.strip().strip("'")
        toggle = pick_theme_toggle(current)
        if toggle:
            original, alternate = toggle
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", alternate],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            time.sleep(0.12)
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", original],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def load_scheme() -> dict | None:
    try:
        return json.loads(SCHEME_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def build_border_values(colours: dict[str, str]) -> tuple[str, str]:
    active_primary = hex_rgba(colours.get("primary") or colours.get("surfaceTint"), fallback="ffffff")
    active_secondary = hex_rgba(colours.get("secondary") or colours.get("secondaryFixedDim"), fallback="d3c876")
    active_tertiary = hex_rgba(colours.get("tertiary") or colours.get("primaryFixedDim"), fallback="ffd27a")
    inactive = hex_rgba(colours.get("outlineVariant") or colours.get("outline"), alpha="aa", fallback="595959")
    active_value = f"rgba({active_primary}) rgba({active_secondary}) rgba({active_tertiary}) 45deg"
    inactive_value = f"rgba({inactive})"
    return active_value, inactive_value


def render_hyprland(colours: dict[str, str]) -> None:
    active_value, inactive_value = build_border_values(colours)
    shadow_active = f"rgba({hex_rgba(colours.get('secondaryContainer') or colours.get('primaryContainer') or colours.get('secondary'), alpha='96', fallback='3f3a1e')})"
    shadow_inactive = f"rgba({hex_rgba(colours.get('surfaceContainerHigh') or colours.get('surfaceContainer') or colours.get('outlineVariant'), alpha='78', fallback='222014')})"
    write_file(
        HYPR_BORDER_PATH,
        (
            "# Generated by ~/scripts/system-theme-sync.py\n"
            "general {\n"
            f"    col.active_border = {active_value}\n"
            f"    col.inactive_border = {inactive_value}\n"
            f"    col.nogroup_border = {inactive_value}\n"
            f"    col.nogroup_border_active = {active_value}\n"
            "}\n"
            "decoration {\n"
            "    shadow {\n"
            f"        color = {shadow_active}\n"
            f"        color_inactive = {shadow_inactive}\n"
            "    }\n"
            "}\n"
            "group {\n"
            f"    col.border_active = {active_value}\n"
            f"    col.border_inactive = {inactive_value}\n"
            f"    col.border_locked_active = {active_value}\n"
            f"    col.border_locked_inactive = {inactive_value}\n"
            "}\n"
        ),
    )
    live_keywords = {
        "general:col.active_border": active_value,
        "general:col.inactive_border": inactive_value,
        "general:col.nogroup_border": inactive_value,
        "general:col.nogroup_border_active": active_value,
        "decoration:shadow:color": shadow_active,
        "decoration:shadow:color_inactive": shadow_inactive,
        "group:col.border_active": active_value,
        "group:col.border_inactive": inactive_value,
        "group:col.border_locked_active": active_value,
        "group:col.border_locked_inactive": inactive_value,
    }
    for keyword, value in live_keywords.items():
        subprocess.run(
            ["hyprctl", "keyword", keyword, value],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def render_hyprlock(colours: dict[str, str]) -> None:
    if not HYPRLOCK_CONFIG_PATH.exists():
        return

    values = {
        "hl_clock_text": rgba_css(colours.get("onSurface") or colours.get("onBackground"), 0.98, "f2f6fc"),
        "hl_date_text": rgba_css(colours.get("onSurfaceVariant") or colours.get("outline"), 0.82, "bcc9dc"),
        "hl_divider": rgba_css(colours.get("primary") or colours.get("secondary"), 0.56, "94cdff"),
        "hl_avatar_bg": rgba_css(colours.get("surfaceContainerLow") or colours.get("surface"), 0.16, "0e121a"),
        "hl_avatar_ring": rgba_css(colours.get("outlineVariant") or colours.get("outline"), 0.28, "ccdcf5"),
        "hl_avatar_shadow": rgba_css(colours.get("scrim") or colours.get("shadow"), 0.12, "000000"),
        "hl_avatar_border": rgba_css(colours.get("primaryFixed") or colours.get("onSurface"), 0.30, "e4eefc"),
        "hl_user_text": rgba_css(colours.get("onSurface") or colours.get("onBackground"), 0.92, "e0e8f4"),
        "hl_input_text": rgba_css(colours.get("onSurface") or colours.get("onBackground"), 1.0, "f4f7fc"),
        "hl_input_inner": rgba_css(colours.get("surfaceContainerLowest") or colours.get("surface"), 0.22, "0c1018"),
        "hl_input_outer": rgba_css(colours.get("outline") or colours.get("secondary"), 0.30, "aebfd9"),
        "hl_input_check": rgba_css(colours.get("primary") or colours.get("secondary"), 0.96, "84bfff"),
        "hl_input_fail": rgba_css(colours.get("error"), 0.96, "ff8694"),
        "hl_input_caps": rgba_css(colours.get("tertiary"), 0.96, "ffab7f"),
        "hl_input_num": rgba_css(colours.get("success") or colours.get("green"), 0.96, "7ad5bf"),
        "hl_hint_text": rgba_css(colours.get("outline"), 0.74, "aebacb"),
        "hl_panel_bg": rgba_css(colours.get("surfaceContainerLowest") or colours.get("surface"), 0.12, "0b0f16"),
        "hl_panel_border": rgba_css(colours.get("outlineVariant") or colours.get("outline"), 0.22, "ccdcf5"),
        "hl_panel_shadow": rgba_css(colours.get("scrim") or colours.get("shadow"), 0.10, "000000"),
        "hl_chip_bg": rgba_css(colours.get("surfaceContainerHigh") or colours.get("surfaceContainer"), 0.34, "0e131b"),
        "hl_chip_border": rgba_css(colours.get("secondary") or colours.get("primary"), 0.28, "9aceff"),
        "hl_chip_text": rgba_css(colours.get("secondary") or colours.get("primary"), 1.0, "b0dcff"),
        "hl_panel_text": rgba_css(colours.get("onSurface") or colours.get("onBackground"), 0.98, "f1f5fb"),
    }

    block = (
        "# Generated by ~/scripts/system-theme-sync.py\n"
        f"{HYPRLOCK_MARKER_BEGIN}\n"
        + "".join(f"${name} = {value}\n" for name, value in values.items())
        + f"{HYPRLOCK_MARKER_END}\n"
    )

    text = HYPRLOCK_CONFIG_PATH.read_text(encoding="utf-8")
    pattern = (
        r"# Generated by ~/scripts/system-theme-sync.py\n"
        + re.escape(HYPRLOCK_MARKER_BEGIN)
        + r".*?"
        + re.escape(HYPRLOCK_MARKER_END)
        + r"\n?"
    )

    if re.search(pattern, text, flags=re.S):
        updated = re.sub(pattern, block, text, count=1, flags=re.S)
    else:
        anchor = "$font_mono = CaskaydiaCove NF\n"
        if anchor in text:
            updated = text.replace(anchor, anchor + "\n" + block, 1)
        else:
            updated = block + "\n" + text

    if updated != text:
        write_file(HYPRLOCK_CONFIG_PATH, updated)


def render_gtk(colours: dict[str, str]) -> None:
    accent = hex_css(colours.get("secondary") or colours.get("primary"), "d3c876")
    accent_fg = hex_css(colours.get("onSecondary") or colours.get("onPrimary"), "1d1b14")
    window_bg = hex_css(colours.get("surface") or colours.get("background"), "151409")
    window_fg = hex_css(colours.get("onSurface") or colours.get("onBackground"), "e8e2cf")
    card_bg = hex_css(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), "222014")
    card_fg = window_fg
    selected_bg = rgba_css(colours.get("secondary") or colours.get("primary"), 0.18, "d3c876")
    selected_fg = window_fg

    css = (
        "/* Generated by ~/scripts/system-theme-sync.py */\n"
        f"@define-color accent_color {accent};\n"
        f"@define-color accent_fg_color {accent_fg};\n"
        f"@define-color accent_bg_color {accent};\n"
        f"@define-color window_bg_color {window_bg};\n"
        f"@define-color window_fg_color {window_fg};\n"
        f"@define-color headerbar_bg_color {window_bg};\n"
        f"@define-color headerbar_fg_color {window_fg};\n"
        f"@define-color popover_bg_color {card_bg};\n"
        f"@define-color popover_fg_color {window_fg};\n"
        f"@define-color view_bg_color {window_bg};\n"
        f"@define-color view_fg_color {window_fg};\n"
        f"@define-color card_bg_color {card_bg};\n"
        f"@define-color card_fg_color {card_fg};\n"
        "@define-color sidebar_bg_color @window_bg_color;\n"
        "@define-color sidebar_fg_color @window_fg_color;\n"
        "@define-color sidebar_border_color @window_bg_color;\n"
        "@define-color sidebar_backdrop_color @window_bg_color;\n"
        f"@define-color theme_selected_bg_color {selected_bg};\n"
        f"@define-color theme_selected_fg_color {selected_fg};\n"
    )
    changed = write_file(GTK3_DYNAMIC_PATH, css)
    changed = write_file(GTK4_DYNAMIC_PATH, css) or changed
    changed = render_thunar(colours) or changed
    if changed:
        refresh_gtk_theme()


def render_thunar(colours: dict[str, str]) -> bool:
    window_bg = hex_css(colours.get("surface") or colours.get("background"), "121415")
    window_fg = hex_css(colours.get("onSurface") or colours.get("onBackground"), "e2e2e5")
    panel_bg = hex_css(colours.get("surfaceContainerLow") or colours.get("surfaceContainer"), "1a1c1e")
    panel_strong = hex_css(colours.get("surfaceContainer") or colours.get("surfaceContainerHigh"), "1e2022")
    accent = hex_css(colours.get("secondary") or colours.get("primary"), "bac8d6")
    accent_soft = rgba_css(colours.get("secondary") or colours.get("primary"), 0.15, "bac8d6")
    accent_hover = rgba_css(colours.get("secondary") or colours.get("primary"), 0.08, "bac8d6")
    hover = rgba_css(colours.get("onSurface") or colours.get("onBackground"), 0.10, "e2e2e5")

    css = (
        "/* Generated by ~/scripts/system-theme-sync.py */\n"
        ".thunar * {\n"
        "    outline: none;\n"
        "    border: none;\n"
        "}\n\n"
        ".thunar.background {\n"
        f"    background: {window_bg};\n"
        f"    color: {window_fg};\n"
        "}\n\n"
        ".thunar .titlebar {\n"
        "    background: inherit;\n"
        "    color: inherit;\n"
        "    padding: 15px 0 5px 0;\n"
        "}\n\n"
        ".thunar .titlebutton.close {\n"
        "    margin: 0 15px 0 0;\n"
        "}\n\n"
        ".thunar paned > separator {\n"
        "    min-width: 4px;\n"
        "    margin-right: -7px;\n"
        "    margin-left: -7px;\n"
        "    background: none;\n"
        "    background-image: none;\n"
        "    box-shadow: none;\n"
        "}\n\n"
        ".thunar .frame.standard-view {\n"
        "    padding: 10px;\n"
        "    margin: 10px 15px 0 0;\n"
        "    border-radius: 15px;\n"
        f"    background-color: {panel_bg};\n"
        "    animation: fading 400ms ease forwards;\n"
        "    opacity: 0;\n"
        "    animation-delay: 250ms;\n"
        "}\n\n"
        ".thunar .frame.standard-view .view:not(.rubberband),\n"
        ".thunar .frame.standard-view .view *:not(.rubberband) {\n"
        "    background-color: transparent;\n"
        "}\n\n"
        ".thunar .frame.standard-view .view *:selected {\n"
        f"    color: {accent};\n"
        "}\n\n"
        ".thunar .rubberband {\n"
        f"    background-color: {accent_soft};\n"
        f"    border: 1px solid {accent_soft};\n"
        "}\n\n"
        ".thunar header.top {\n"
        "    background: none;\n"
        "    padding: 0 10px 0 0;\n"
        "    margin: 3px 0 -3px -2px;\n"
        "}\n\n"
        ".thunar header.top tabs .reorderable-page {\n"
        "    margin: 0;\n"
        "    transition: all ease 300ms;\n"
        "}\n\n"
        ".thunar header.top tabs .reorderable-page + .reorderable-page {\n"
        "    margin: 0 0 0 10px;\n"
        "}\n\n"
        ".thunar header.top tabs .reorderable-page:hover {\n"
        f"    background-color: {accent_hover};\n"
        "}\n\n"
        ".thunar header.top tabs .reorderable-page:checked {\n"
        f"    color: {accent};\n"
        f"    background-color: {accent_soft};\n"
        "}\n\n"
        ".thunar .sidebar {\n"
        "    padding: 0 20px;\n"
        "    background: none;\n"
        "    animation: fading 600ms ease forwards;\n"
        "    animation-delay: 100ms;\n"
        "    opacity: 0;\n"
        "}\n\n"
        ".thunar .sidebar .view {\n"
        "    padding: 8px 4px;\n"
        "    border-radius: 10px;\n"
        "    background: none;\n"
        "    transition: all ease 300ms;\n"
        "}\n\n"
        ".thunar .sidebar .view:hover {\n"
        f"    background: {hover};\n"
        "}\n\n"
        ".thunar .sidebar .view:selected {\n"
        f"    background: {accent_soft};\n"
        f"    color: {accent};\n"
        "}\n\n"
        ".thunar .path-bar-button {\n"
        "    margin: 0;\n"
        "    padding: 8px 5px;\n"
        "    transition: all ease 0.4s;\n"
        "}\n\n"
        ".thunar .location-button.toggle:checked,\n"
        ".thunar .path-bar-button.toggle:checked {\n"
        "    padding: 8px 25px;\n"
        f"    background: {accent_soft};\n"
        f"    color: {accent};\n"
        "    box-shadow: none;\n"
        "}\n\n"
        ".thunar .location-button.path-bar-button:not(:checked) {\n"
        f"    background-color: {panel_strong};\n"
        f"    color: {window_fg};\n"
        "}\n\n"
        ".thunar .location-button.path-bar-button:not(:checked):hover {\n"
        f"    background: {accent_hover};\n"
        f"    color: {accent};\n"
        "}\n\n"
        ".thunar .location-button.toggle + .location-button.toggle:checked {\n"
        "    margin-left: 0;\n"
        "    padding: 0 25px;\n"
        "}\n\n"
        ".thunar button.toggle:checked {\n"
        f"    color: {accent};\n"
        "}\n\n"
        ".thunar .image-button {\n"
        "    padding: 8px;\n"
        "    margin: 0 0 0 8px;\n"
        "    transition: all ease 0.4s;\n"
        "}\n\n"
        ".thunar statusbar {\n"
        f"    background-color: {panel_bg};\n"
        "    border-radius: 15px;\n"
        "    padding: 10px 10px;\n"
        "    margin: 15px 5px 15px -10px;\n"
        f"    color: {window_fg};\n"
        "}\n\n"
        ".thunar box.vertical .image {\n"
        "    margin: 15px;\n"
        "}\n\n"
        "@keyframes fading {\n"
        "    to {\n"
        "        opacity: 1;\n"
        "    }\n"
        "}\n"
    )

    changed = write_file(GTK3_THUNAR_PATH, css)
    changed = write_file(GTK4_THUNAR_PATH, css) or changed
    return changed


def render_rofi(colours: dict[str, str]) -> None:
    bg = rgba_css(colours.get("surfaceContainerLowest") or colours.get("surface"), 0.78, "000000")
    bg_alt = rgba_css(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), 0.90, "222014")
    fg = rgba_css(colours.get("onSurface") or colours.get("onBackground"), 0.95, "e8e2cf")
    accent = rgba_css(colours.get("secondary") or colours.get("primary"), 0.96, "d3c876")
    stroke = rgba_css(colours.get("outline") or colours.get("outlineVariant"), 0.18, "969178")
    accent_dim = rgba_css(colours.get("secondary") or colours.get("primary"), 0.16, "d3c876")
    accent_soft = rgba_css(colours.get("secondaryContainer") or colours.get("secondary"), 0.06, "3f3a1e")

    content = (
        "/* Generated by ~/scripts/system-theme-sync.py */\n"
        "* {\n"
        f"    bg: {bg};\n"
        f"    bg-alt: {bg_alt};\n"
        f"    fg: {fg};\n"
        f"    accent: {accent};\n"
        f"    accent-dim: {accent_dim};\n"
        f"    accent-soft: {accent_soft};\n"
        f"    stroke: {stroke};\n"
        "}\n"
    )
    write_file(ROFI_DYNAMIC_PATH, content)


def find_tmux_bin() -> str | None:
    bundled = HOME / ".local/bin/tmux"
    if bundled.exists():
        return str(bundled)
    return shutil.which("tmux")


def render_shell_theme(colours: dict[str, str]) -> None:
    prompt_primary = hex_css(colours.get("secondary") or colours.get("primary"), "d3c876")
    prompt_mid = hex_css(colours.get("primary") or colours.get("onSurface"), "ffffff")
    prompt_tail = hex_css(colours.get("tertiary") or colours.get("secondaryFixed"), "cbce78")
    prompt_arrow = hex_css(colours.get("onSurface") or colours.get("primaryFixed"), "e8e2cf")
    prompt_path = hex_css(colours.get("outline") or colours.get("outlineVariant"), "969178")
    prompt_time = hex_css(colours.get("outlineVariant") or colours.get("outline"), "4a4732")

    ls_colors = ":".join(
        [
            f"di={sgr_truecolor(colours.get('secondary') or colours.get('primary'), 'd3c876')}",
            f"ln={sgr_truecolor(colours.get('primary') or colours.get('secondary'), 'ffffff')}",
            f"so={sgr_truecolor(colours.get('tertiary') or colours.get('term6'), 'cbce78')}",
            f"pi={sgr_truecolor(colours.get('term3') or colours.get('tertiary'), 'ffe66f')}",
            f"ex={sgr_truecolor(colours.get('term2') or colours.get('secondaryFixed'), 'dbcf4d')}",
            f"bd={sgr_truecolor(colours.get('term4') or colours.get('primaryFixed'), 'a2b174')}",
            f"cd={sgr_truecolor(colours.get('term5') or colours.get('secondaryFixed'), 'd3a343')}",
            f"*.zip={sgr_truecolor(colours.get('term9') or colours.get('error'), 'd1a200')}",
            f"*.tar={sgr_truecolor(colours.get('term9') or colours.get('error'), 'd1a200')}",
            f"*.gz={sgr_truecolor(colours.get('term9') or colours.get('error'), 'd1a200')}",
            f"*.jpg={sgr_truecolor(colours.get('primaryFixed') or colours.get('primary'), 'ffffff')}",
            f"*.png={sgr_truecolor(colours.get('primaryFixed') or colours.get('primary'), 'ffffff')}",
            f"*.mp3={sgr_truecolor(colours.get('term4') or colours.get('primaryFixed'), 'a2b174')}",
            f"*.mp4={sgr_truecolor(colours.get('term4') or colours.get('primaryFixed'), 'a2b174')}",
            f"*.py={sgr_truecolor(colours.get('term3') or colours.get('tertiary'), 'ffe66f')}",
            f"*.sh={sgr_truecolor(colours.get('term2') or colours.get('secondaryFixed'), 'dbcf4d')}",
            f"*.js={sgr_truecolor(colours.get('term3') or colours.get('tertiary'), 'ffe66f')}",
            f"*.md={sgr_truecolor(colours.get('outline') or colours.get('outlineVariant'), '969178')}",
        ]
    )

    active_border = hex_css(colours.get("secondary") or colours.get("primary"), "d3c876")
    inactive_border = hex_css(colours.get("outlineVariant") or colours.get("outline"), "4a4732")

    content = (
        "# Generated by ~/scripts/system-theme-sync.py\n"
        f"PROMPT='%F{{{prompt_primary}}}Archlinux%f%F{{{prompt_mid}}}_%f%F{{{prompt_tail}}}Itachi%f %F{{{prompt_arrow}}}❯%f '\n"
        f"RPROMPT='%F{{{prompt_path}}}%~%f %F{{{prompt_time}}}%*%f'\n"
        f"export LESS_TERMCAP_mb=$'\\e[{sgr_truecolor(colours.get('secondary') or colours.get('primary'), 'd3c876')}m'\n"
        f"export LESS_TERMCAP_md=$'\\e[{sgr_truecolor(colours.get('primary') or colours.get('onSurface'), 'ffffff')}m'\n"
        "export LESS_TERMCAP_me=$'\\e[0m'\n"
        "export LESS_TERMCAP_se=$'\\e[0m'\n"
        f"export LESS_TERMCAP_so=$'\\e[{sgr_truecolor(colours.get('term3') or colours.get('tertiary'), 'ffe66f')};48;2;49;43;6m'\n"
        "export LESS_TERMCAP_ue=$'\\e[0m'\n"
        f"export LESS_TERMCAP_us=$'\\e[{sgr_truecolor(colours.get('tertiary') or colours.get('secondaryFixed'), 'cbce78')}m'\n"
        f"export LS_COLORS='{ls_colors}'\n"
        f"export CAELESTIA_TMUX_ACTIVE_BORDER='{active_border}'\n"
        f"export CAELESTIA_TMUX_INACTIVE_BORDER='{inactive_border}'\n"
    )
    write_file(ZSH_THEME_PATH, content)

    tmux_bin = find_tmux_bin()
    if not tmux_bin:
        return

    options = {
        "pane-active-border-style": f"fg={active_border}",
        "pane-border-style": f"fg={inactive_border}",
    }
    for option, value in options.items():
        subprocess.run(
            [tmux_bin, "set-window-option", "-g", option, value],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    windows = subprocess.run(
        [tmux_bin, "list-windows", "-a", "-F", "#{session_name}:#{window_index}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if windows.returncode != 0:
        return

    for target in {line.strip() for line in windows.stdout.splitlines() if line.strip()}:
        for option, value in options.items():
            subprocess.run(
                [tmux_bin, "set-window-option", "-t", target, option, value],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def render_foot(colours: dict[str, str]) -> None:
    surface_low = rgb_tuple(colours.get("surfaceContainerLow") or colours.get("surfaceContainer") or colours.get("surface"), "1d1c10")
    accent_tint = rgb_tuple(colours.get("secondaryContainer") or colours.get("secondary") or colours.get("primary"), "514a01")
    bg = hex_from_rgb(blend(surface_low, accent_tint, 0.18))
    fg = hex_css(colours.get("onSurface") or colours.get("onBackground"), "e8e2cf")
    selection_fg = hex_css(colours.get("onSecondaryContainer") or colours.get("onSecondary"), "151409")
    selection_base = rgb_tuple(colours.get("secondaryContainer") or colours.get("secondary"), "3f3a1e")
    selection_bg = hex_from_rgb(blend(selection_base, surface_low, 0.12))
    url = hex_css(colours.get("primary") or colours.get("secondary"), "d3c876")
    cursor = hex_css(colours.get("primary") or colours.get("onSurface"), "ffffff")
    cursor_text = bg

    colors = {
        "regular0": colours.get("term0") or colours.get("surfaceContainerLowest") or "000000",
        "regular1": colours.get("term1") or colours.get("error") or colours.get("red") or "ffb4ab",
        "regular2": colours.get("term2") or colours.get("success") or colours.get("green") or "b5ccba",
        "regular3": colours.get("term3") or colours.get("tertiary") or colours.get("yellow") or "ffd27a",
        "regular4": colours.get("term4") or colours.get("primary") or colours.get("blue") or "ffffff",
        "regular5": colours.get("term5") or colours.get("secondary") or colours.get("purple") or "d3c876",
        "regular6": colours.get("term6") or colours.get("surfaceTint") or colours.get("sky") or "c8c1ff",
        "regular7": colours.get("onSurface") or "e8e2cf",
        "bright0": colours.get("term8") or colours.get("outline") or "969178",
        "bright1": colours.get("term9") or colours.get("errorContainer") or colours.get("maroon") or "ff8f86",
        "bright2": colours.get("term10") or colours.get("successContainer") or colours.get("teal") or "d1e9d6",
        "bright3": colours.get("term11") or colours.get("tertiaryContainer") or "f2d58d",
        "bright4": colours.get("term12") or colours.get("primaryFixed") or colours.get("lavender") or "ffffff",
        "bright5": colours.get("term13") or colours.get("secondaryFixed") or colours.get("pink") or "f1e28a",
        "bright6": colours.get("term14") or colours.get("secondaryFixedDim") or colours.get("sapphire") or "ddd3ff",
        "bright7": colours.get("term15") or colours.get("inverseSurface") or "fff8e8",
    }

    def render_section(name: str) -> list[str]:
        lines = [
            f"[{name}]",
            "alpha=0.92",
            "alpha-mode=matching",
            "blur=yes",
            f"foreground={fg}",
            f"background={bg}",
            f"selection-foreground={selection_fg}",
            f"selection-background={selection_bg}",
            f"urls={url}",
            f"cursor={cursor}",
            f"cursor-text={cursor_text}",
        ]
        for color_name, value in colors.items():
            lines.append(f"{color_name}={hex_css(value, 'ffffff')}")
        return lines

    content = "\n".join(
        ["# Generated by ~/scripts/system-theme-sync.py"]
        + render_section("colors")
        + [""]
        + render_section("colors-dark")
        + [""]
        + render_section("colors-light")
    ) + "\n"
    write_file(FOOT_DYNAMIC_PATH, content)

    # Existing foot windows can live-switch by jumping to the dark theme section.
    for proc in ("foot", "footclient"):
        subprocess.run(
            ["pkill", "-USR1", "-x", proc],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def patch_discord_theme(path: Path, colours: dict[str, str]) -> None:
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")

    text0 = hex_css(colours.get("onSecondary") or colours.get("onPrimary"), "1d1b14")
    text1 = rgb_css(colours.get("onPrimaryContainer") or colours.get("onSurface"), "e8e2cf")
    text2 = rgb_css(colours.get("onSurface") or colours.get("onBackground"), "e8e2cf")
    text3 = hex_css(colours.get("onSurface") or colours.get("onBackground"), "e8e2cf")
    text4 = hex_css(colours.get("outline") or colours.get("outlineVariant"), "969178")
    text5 = text4
    bg1 = hex_css(colours.get("surfaceContainerHigh") or colours.get("surfaceContainer"), "2c2a1e")
    bg2 = hex_css(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), "222014")
    bg3 = hex_css(colours.get("surface") or colours.get("background"), "151409")
    bg4 = hex_css(colours.get("surfaceContainerLow") or colours.get("surfaceContainer"), "1d1b11")
    hover = rgba_css(colours.get("onSurface"), 0.08, "e8e2cf")
    active = rgba_css(colours.get("secondary") or colours.get("primary"), 0.10, "d3c876")
    active2 = rgba_css(colours.get("secondary") or colours.get("primary"), 0.20, "d3c876")
    message_hover = hover
    border = rgba_css(colours.get("outline"), 0.20, "969178")
    border_light = rgba_css(colours.get("outline"), 0.0, "969178")
    button_border = border_light

    reds = [hex_css(colours.get("error"), "ffb4ab")]
    greens = [hex_css(colours.get("success"), "b5ccba")]
    blues = [hex_css(colours.get("primary"), "ffffff")]
    yellows = [hex_css(colours.get("tertiary"), "ffd27a")]
    purples = [hex_css(colours.get("secondary"), "d3c876")]

    for arr, source, fallback in (
        (reds, colours.get("errorContainer"), "d8655d"),
        (greens, colours.get("successContainer"), "9db7a3"),
        (blues, colours.get("primaryContainer"), "d8d2a6"),
        (yellows, colours.get("tertiaryContainer"), "f2d58d"),
        (purples, colours.get("secondaryContainer"), "a79f5d"),
    ):
        base = arr[0]
        base_rgb = rgb_tuple(base, fallback)
        mix_rgb = rgb_tuple(source, fallback)
        arr.extend(
            [
                f"rgb({blend(base_rgb, mix_rgb, 0.22)[0]}, {blend(base_rgb, mix_rgb, 0.22)[1]}, {blend(base_rgb, mix_rgb, 0.22)[2]})",
                f"rgb({blend(base_rgb, mix_rgb, 0.42)[0]}, {blend(base_rgb, mix_rgb, 0.42)[1]}, {blend(base_rgb, mix_rgb, 0.42)[2]})",
                f"rgb({blend(base_rgb, mix_rgb, 0.62)[0]}, {blend(base_rgb, mix_rgb, 0.62)[1]}, {blend(base_rgb, mix_rgb, 0.62)[2]})",
                f"rgb({blend(base_rgb, mix_rgb, 0.82)[0]}, {blend(base_rgb, mix_rgb, 0.82)[1]}, {blend(base_rgb, mix_rgb, 0.82)[2]})",
            ]
        )

    replacement = f""":root {{
  --colors: on; /* turn off to use discord default colors */
  /* text colors */
  --text-0: {text0}; /* text on colored elements */
  --text-1: {text1}; /* bright text on colored elements */
  --text-2: {text2}; /* headings and important text */
  --text-3: {text3}; /* normal text */
  --text-4: {text4}; /* icon buttons and channels */
  --text-5: {text5}; /* muted channels/chats and timestamps */
  /* background and dark colors */
  --bg-1: {bg1}; /* dark buttons when clicked */
  --bg-2: {bg2}; /* dark buttons */
  --bg-3: {bg3}; /* spacing, secondary elements */
  --bg-4: {bg4}; /* main background color */
  --hover: {hover}; /* channels and buttons when hovered */
  --active: {active}; /* channels and buttons when clicked or selected */
  --active-2: {active2}; /* extra state for transparent buttons */
  --message-hover: {message_hover}; /* messages when hovered */
  /* accent colors */
  --accent-1: var(--blue-1); /* links and other accent text */
  --accent-2: var(--blue-2); /* small accent elements */
  --accent-3: var(--blue-3); /* accent buttons */
  --accent-4: var(--blue-4); /* accent buttons when hovered */
  --accent-5: var(--blue-5); /* accent buttons when clicked */
  --accent-new: {hex_css(colours.get("error"), "ffb4ab")}; /* stuff that's normally red like mute/deafen buttons */
  --mention: linear-gradient(
      to right,
      color-mix(in hsl, var(--blue-2), transparent 90%) 40%,
      transparent
  ); /* background of messages that mention you */
  --mention-hover: linear-gradient(
      to right,
      color-mix(in hsl, var(--blue-2), transparent 95%) 40%,
      transparent
  ); /* background of messages that mention you when hovered */
  --reply: linear-gradient(
      to right,
      color-mix(in hsl, var(--text-3), transparent 90%) 40%,
      transparent
  ); /* background of messages that reply to you */
  --reply-hover: linear-gradient(
      to right,
      color-mix(in hsl, var(--text-3), transparent 95%) 40%,
      transparent
  ); /* background of messages that reply to you when hovered */
  /* status indicator colors */
  --online: var(--green-2); /* change to #43a25a for default */
  --dnd: var(--red-2); /* change to #d83a42 for default */
  --idle: var(--yellow-2); /* change to #ca9654 for default */
  --streaming: var(--purple-2); /* change to #593695 for default */
  --offline: var(--text-4); /* change to #83838b for default offline color */
  /* border colors */
  --border-light: {border_light}; /* light border color */
  --border: {border}; /* normal border color */
  --button-border: {button_border}; /* neutral border color of buttons */
  /* base colors */
  --red-1: {reds[0]};
  --red-2: {reds[1]};
  --red-3: {reds[2]};
  --red-4: {reds[3]};
  --red-5: {reds[4]};
  --green-1: {greens[0]};
  --green-2: {greens[1]};
  --green-3: {greens[2]};
  --green-4: {greens[3]};
  --green-5: {greens[4]};
  --blue-1: {blues[0]};
  --blue-2: {blues[1]};
  --blue-3: {blues[2]};
  --blue-4: {blues[3]};
  --blue-5: {blues[4]};
  --yellow-1: {yellows[0]};
  --yellow-2: {yellows[1]};
  --yellow-3: {yellows[2]};
  --yellow-4: {yellows[3]};
  --yellow-5: {yellows[4]};
  --purple-1: {purples[0]};
  --purple-2: {purples[1]};
  --purple-3: {purples[2]};
  --purple-4: {purples[3]};
  --purple-5: {purples[4]};
}}"""

    updated = re.sub(r":root\s*\{.*?\n\}", replacement, text, count=1, flags=re.S)
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def render_zen(colours: dict[str, str]) -> None:
    surface = rgba_css(colours.get("surface"), 0.82, "151409")
    surface_strong = rgba_css(colours.get("surfaceContainer"), 0.90, "222014")
    accent = hex_css(colours.get("secondary") or colours.get("primary"), "d3c876")
    fg = hex_css(colours.get("onSurface") or colours.get("onBackground"), "e8e2cf")
    panel = hex_css(colours.get("surfaceContainerLow") or colours.get("surface"), "1d1c10")
    border = hex_with_alpha(colours.get("outline") or colours.get("outlineVariant"), "66", "969178")

    dynamic_css = (
        ":root {\n"
        f"  --caelestia-surface: {surface} !important;\n"
        f"  --caelestia-surface-strong: {surface_strong} !important;\n"
        f"  --caelestia-accent: {accent} !important;\n"
        f"  --toolbar-bgcolor: {surface} !important;\n"
        f"  --toolbar-color: {fg} !important;\n"
        f"  --toolbarbutton-icon-fill: {fg} !important;\n"
        f"  --lwt-accent-color: {panel} !important;\n"
        f"  --lwt-text-color: {fg} !important;\n"
        f"  --tab-selected-bgcolor: {surface_strong} !important;\n"
        f"  --arrowpanel-background: {surface_strong} !important;\n"
        f"  --arrowpanel-color: {fg} !important;\n"
        f"  --newtab-background-color: {panel} !important;\n"
        f"  --newtab-text-primary-color: {fg} !important;\n"
        f"  --chrome-content-separator-color: {border} !important;\n"
        "}\n"
    )
    dynamic_block = (
        "/* Generated by ~/scripts/system-theme-sync.py */\n"
        f"{ZEN_MARKER_BEGIN}\n"
        + dynamic_css
        + f"{ZEN_MARKER_END}\n"
    )

    for chrome_css in first_existing_paths(HOME / ".config/zen", "*/chrome/userChrome.css"):
        text = chrome_css.read_text(encoding="utf-8")
        updated = re.sub(
            r'(?m)^@import url\("caelestia-dynamic\.css"\);\n?',
            "",
            text,
        )
        updated = re.sub(
            re.escape(ZEN_MARKER_BEGIN) + r".*?" + re.escape(ZEN_MARKER_END) + r"\n?",
            "",
            updated,
            flags=re.S,
        )
        updated = re.sub(
            r"(?m)^/\* Generated by ~/scripts/system-theme-sync\.py \*/\n?",
            "",
            updated,
        )
        updated = re.sub(
            r"(?s)\n*:root\s*\{\s*--caelestia-surface:.*?--caelestia-surface-strong:.*?\}\s*\n*",
            "\n",
            updated,
            count=1,
        ).lstrip("\n")
        updated = f"{dynamic_block}\n{updated}" if updated else dynamic_block
        if updated != text:
            chrome_css.write_text(updated, encoding="utf-8")
        write_file(
            chrome_css.parent / "caelestia-dynamic.css",
            "/* Generated by ~/scripts/system-theme-sync.py */\n" + dynamic_css,
        )


def render_kde(colours: dict[str, str]) -> None:
    config = new_config()
    if KDE_GLOBALS_PATH.exists():
        config.read(KDE_GLOBALS_PATH, encoding="utf-8")

    general_section = dict(config["General"]) if config.has_section("General") else {}
    general_section.update(
        {
            "ColorScheme": "CaelestiaDynamic",
            "Name": "CaelestiaDynamic",
            "shadeSortColumn": "true",
        }
    )
    config["General"] = general_section

    window_bg = colours.get("surface") or colours.get("background") or "151409"
    window_alt = colours.get("surfaceContainerLow") or colours.get("surfaceContainer") or "1d1c10"
    button_bg = colours.get("surfaceContainer") or colours.get("surfaceContainerLow") or "222014"
    panel_bg = colours.get("surfaceContainerHigh") or colours.get("surfaceContainer") or "2c2a1e"
    view_bg = colours.get("surfaceContainerLowest") or colours.get("surface") or "100e05"
    fg = colours.get("onSurface") or colours.get("onBackground") or "e8e2cf"
    fg_muted = colours.get("outline") or colours.get("outlineVariant") or "969178"
    accent = colours.get("secondary") or colours.get("primary") or "d3c876"
    accent_fg = colours.get("onSecondary") or colours.get("onPrimary") or "1d1b14"

    section_values = {
        "Colors:Window": {
            "BackgroundNormal": rgb_csv(window_bg, "151409"),
            "BackgroundAlternate": rgb_csv(window_alt, "1d1c10"),
            "ForegroundNormal": rgb_csv(fg, "e8e2cf"),
            "ForegroundActive": rgb_csv(fg, "e8e2cf"),
            "ForegroundInactive": rgb_csv(fg_muted, "969178"),
            "DecorationFocus": rgb_csv(accent, "d3c876"),
            "DecorationHover": rgb_csv(accent, "d3c876"),
        },
        "Colors:View": {
            "BackgroundNormal": rgb_csv(view_bg, "100e05"),
            "BackgroundAlternate": rgb_csv(window_alt, "1d1c10"),
            "ForegroundNormal": rgb_csv(fg, "e8e2cf"),
            "ForegroundInactive": rgb_csv(fg_muted, "969178"),
            "DecorationFocus": rgb_csv(accent, "d3c876"),
            "DecorationHover": rgb_csv(accent, "d3c876"),
        },
        "Colors:Button": {
            "BackgroundNormal": rgb_csv(button_bg, "222014"),
            "BackgroundAlternate": rgb_csv(window_alt, "1d1c10"),
            "ForegroundNormal": rgb_csv(fg, "e8e2cf"),
            "ForegroundInactive": rgb_csv(fg_muted, "969178"),
            "DecorationFocus": rgb_csv(accent, "d3c876"),
            "DecorationHover": rgb_csv(accent, "d3c876"),
        },
        "Colors:Selection": {
            "BackgroundNormal": rgb_csv(accent, "d3c876"),
            "BackgroundAlternate": rgb_csv(colours.get("secondaryContainer") or accent, "514a01"),
            "ForegroundNormal": rgb_csv(accent_fg, "1d1b14"),
            "ForegroundInactive": rgb_csv(accent_fg, "1d1b14"),
            "DecorationFocus": rgb_csv(accent, "d3c876"),
            "DecorationHover": rgb_csv(accent, "d3c876"),
        },
        "Colors:Tooltip": {
            "BackgroundNormal": rgb_csv(panel_bg, "2c2a1e"),
            "BackgroundAlternate": rgb_csv(button_bg, "222014"),
            "ForegroundNormal": rgb_csv(fg, "e8e2cf"),
            "ForegroundInactive": rgb_csv(fg_muted, "969178"),
            "DecorationFocus": rgb_csv(accent, "d3c876"),
            "DecorationHover": rgb_csv(accent, "d3c876"),
        },
        "Colors:Complementary": {
            "BackgroundNormal": rgb_csv(panel_bg, "2c2a1e"),
            "BackgroundAlternate": rgb_csv(button_bg, "222014"),
            "ForegroundNormal": rgb_csv(fg, "e8e2cf"),
            "ForegroundInactive": rgb_csv(fg_muted, "969178"),
            "DecorationFocus": rgb_csv(accent, "d3c876"),
            "DecorationHover": rgb_csv(accent, "d3c876"),
        },
        "WM": {
            "activeBackground": rgb_csv(panel_bg, "2c2a1e"),
            "activeForeground": rgb_csv(fg, "e8e2cf"),
            "inactiveBackground": rgb_csv(window_bg, "151409"),
            "inactiveForeground": rgb_csv(fg_muted, "969178"),
        },
    }

    for section, mapping in section_values.items():
        if not config.has_section(section):
            config.add_section(section)
        for key, value in mapping.items():
            config.set(section, key, value)

    with KDE_GLOBALS_PATH.open("w", encoding="utf-8") as handle:
        config.write(handle)


def render_spicetify(colours: dict[str, str]) -> None:
    theme = new_config()
    theme["caelestia"] = {
        "text": hex_rgb(colours.get("onSurface"), "e8e2cf"),
        "subtext": hex_rgb(colours.get("outline"), "969178"),
        "main": hex_rgb(colours.get("surfaceContainerLow") or colours.get("surface"), "1d1c10"),
        "highlight": hex_rgb(colours.get("secondary") or colours.get("primary"), "d3c876"),
        "misc": hex_rgb(colours.get("secondary") or colours.get("primary"), "d3c876"),
        "notification": hex_rgb(colours.get("outline"), "969178"),
        "notification-error": hex_rgb(colours.get("error"), "ffb4ab"),
        "shadow": "000000",
        "card": hex_rgb(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), "222014"),
        "player": hex_rgb(colours.get("surfaceContainerHigh") or colours.get("surfaceContainer"), "2c2a1e"),
        "sidebar": hex_rgb(colours.get("surface"), "151409"),
        "main-elevated": hex_rgb(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), "222014"),
        "highlight-elevated": hex_rgb(colours.get("surfaceContainerHigh") or colours.get("surfaceContainer"), "2c2a1e"),
        "selected-row": hex_rgb(colours.get("onSurface"), "e8e2cf"),
        "button": hex_rgb(colours.get("secondary") or colours.get("primary"), "d3c876"),
        "button-active": hex_rgb(colours.get("secondaryContainer") or colours.get("secondary"), "514a01"),
        "button-disabled": hex_rgb(colours.get("outline"), "969178"),
        "tab-active": hex_rgb(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), "222014"),
    }
    with SPICETIFY_THEME_PATH.open("w", encoding="utf-8") as handle:
        theme.write(handle)

    if SPICETIFY_CONFIG_PATH.exists():
        config = new_config()
        config.read(SPICETIFY_CONFIG_PATH, encoding="utf-8")
        if not config.has_section("Setting"):
            config.add_section("Setting")
        config.set("Setting", "current_theme", "caelestia")
        config.set("Setting", "color_scheme", "")
        with SPICETIFY_CONFIG_PATH.open("w", encoding="utf-8") as handle:
            config.write(handle)


def render_zed(colours: dict[str, str]) -> None:
    if ZED_THEME_PATH.exists():
        try:
            data = json.loads(ZED_THEME_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    themes = data.setdefault("themes", [{}])
    if not themes:
        themes.append({})

    theme = themes[0]
    theme["name"] = "Caelestia"
    theme["appearance"] = "dark"
    theme.setdefault("author", "Caelestia")
    data["$schema"] = "https://zed.dev/schema/themes/v0.2.0.json"
    data["name"] = "Caelestia"
    data["author"] = "Caelestia"

    style = theme.setdefault("style", {})
    accent = colours.get("secondary") or colours.get("primary") or "d3c876"
    bg = colours.get("surface") or colours.get("background") or "151409"
    bg_alt = colours.get("surfaceContainerLow") or colours.get("surfaceContainer") or "1d1c10"
    bg_card = colours.get("surfaceContainer") or colours.get("surfaceContainerLow") or "222014"
    bg_high = colours.get("surfaceContainerHigh") or colours.get("surfaceContainer") or "2c2a1e"
    fg = colours.get("onSurface") or colours.get("onBackground") or "e8e2cf"
    muted = colours.get("outline") or colours.get("outlineVariant") or "969178"
    muted_soft = colours.get("outlineVariant") or colours.get("outline") or "4a4732"

    style.update(
        {
            "background": hex_css(bg, "151409"),
            "border": hex_with_alpha(muted_soft, "40", "54453c"),
            "border.variant": hex_with_alpha(muted_soft, "60", "54453c"),
            "border.focused": hex_css(accent, "d3c876"),
            "border.selected": hex_with_alpha(accent, "80", "d3c876"),
            "border.transparent": "#00000000",
            "border.disabled": hex_with_alpha(muted_soft, "30", "54453c"),
            "elevated_surface.background": hex_css(bg_card, "222014"),
            "surface.background": hex_css(bg, "151409"),
            "element.background": hex_with_alpha(muted_soft, "40", "54453c"),
            "element.hover": hex_with_alpha(muted_soft, "60", "54453c"),
            "element.active": hex_with_alpha(accent, "30", "d3c876"),
            "element.selected": hex_with_alpha(accent, "20", "d3c876"),
            "element.disabled": hex_with_alpha(muted_soft, "20", "54453c"),
            "drop_target.background": hex_with_alpha(accent, "20", "d3c876"),
            "ghost_element.background": "#00000000",
            "ghost_element.hover": hex_with_alpha(muted_soft, "40", "54453c"),
            "ghost_element.active": hex_with_alpha(accent, "30", "d3c876"),
            "ghost_element.selected": hex_with_alpha(accent, "20", "d3c876"),
            "ghost_element.disabled": hex_with_alpha(muted_soft, "20", "54453c"),
            "text": hex_css(fg, "e8e2cf"),
            "text.muted": hex_css(muted, "969178"),
            "text.placeholder": hex_css(muted_soft, "4a4732"),
            "text.disabled": hex_with_alpha(muted_soft, "80", "4a4732"),
            "text.accent": hex_css(accent, "d3c876"),
            "icon": hex_css(fg, "e8e2cf"),
            "icon.muted": hex_css(muted, "969178"),
            "icon.disabled": hex_with_alpha(muted_soft, "60", "4a4732"),
            "icon.placeholder": hex_css(muted, "969178"),
            "icon.accent": hex_css(accent, "d3c876"),
            "status_bar.background": hex_css(bg, "151409"),
            "title_bar.background": hex_css(bg, "151409"),
            "title_bar.inactive_background": hex_css(bg, "151409"),
            "toolbar.background": hex_css(bg, "151409"),
            "tab_bar.background": hex_css(bg, "151409"),
            "tab.inactive_background": hex_css(bg, "151409"),
            "tab.active_background": hex_css(bg_card, "222014"),
            "search.match_background": hex_with_alpha(accent, "40", "d3c876"),
            "panel.background": hex_css(bg, "151409"),
            "panel.focused_border": hex_css(accent, "d3c876"),
            "pane.focused_border": hex_css(accent, "d3c876"),
            "scrollbar.thumb.background": hex_with_alpha(muted_soft, "30", "54453c"),
            "scrollbar.thumb.hover_background": hex_with_alpha(muted_soft, "60", "54453c"),
            "scrollbar.thumb.border": hex_with_alpha(muted_soft, "20", "54453c"),
            "scrollbar.track.background": "#00000000",
            "scrollbar.track.border": "#00000000",
            "editor.foreground": hex_css(fg, "e8e2cf"),
            "editor.background": hex_css(bg, "151409"),
            "editor.gutter.background": hex_css(bg, "151409"),
            "editor.subheader.background": hex_css(bg_alt, "1d1c10"),
            "editor.active_line.background": hex_with_alpha(bg_high, "60", "2c2a1e"),
            "editor.highlighted_line.background": hex_with_alpha(accent, "15", "d3c876"),
            "editor.line_number": hex_css(muted, "969178"),
            "editor.active_line_number": hex_css(fg, "e8e2cf"),
            "editor.invisible": hex_with_alpha(muted_soft, "40", "54453c"),
            "editor.wrap_guide": hex_with_alpha(muted_soft, "30", "54453c"),
            "editor.active_wrap_guide": hex_with_alpha(muted_soft, "60", "54453c"),
            "editor.document_highlight.read_background": hex_with_alpha(accent, "20", "d3c876"),
            "editor.document_highlight.write_background": hex_with_alpha(accent, "30", "d3c876"),
            "terminal.background": hex_css(bg, "151409"),
            "terminal.foreground": hex_css(fg, "e8e2cf"),
            "terminal.bright_foreground": hex_css(colours.get("term15") or fg, "ffffff"),
            "terminal.dim_foreground": hex_css(muted, "969178"),
            "terminal.ansi.black": hex_css(colours.get("term0") or bg_alt, "353433"),
            "terminal.ansi.bright_black": hex_css(colours.get("term8") or muted, "a9a290"),
            "terminal.ansi.dim_black": hex_with_alpha(colours.get("term0") or bg_alt, "80", "353433"),
            "terminal.ansi.red": hex_css(colours.get("term1") or colours.get("error"), "b48b00"),
            "terminal.ansi.bright_red": hex_css(colours.get("term9") or colours.get("errorContainer"), "d1a200"),
            "terminal.ansi.dim_red": hex_with_alpha(colours.get("term1") or colours.get("error"), "80", "b48b00"),
            "terminal.ansi.green": hex_css(colours.get("term2") or colours.get("success"), "dbcf4d"),
            "terminal.ansi.bright_green": hex_css(colours.get("term10") or colours.get("successContainer"), "eee145"),
            "terminal.ansi.dim_green": hex_with_alpha(colours.get("term2") or colours.get("success"), "80", "dbcf4d"),
            "terminal.ansi.yellow": hex_css(colours.get("term3") or colours.get("tertiary"), "ffe66f"),
            "terminal.ansi.bright_yellow": hex_css(colours.get("term11") or colours.get("tertiaryContainer"), "fff4cb"),
            "terminal.ansi.dim_yellow": hex_with_alpha(colours.get("term3") or colours.get("tertiary"), "80", "ffe66f"),
            "terminal.ansi.blue": hex_css(colours.get("term4") or colours.get("primary"), "a2b174"),
            "terminal.ansi.bright_blue": hex_css(colours.get("term12") or colours.get("primaryFixed"), "c0c49a"),
            "terminal.ansi.dim_blue": hex_with_alpha(colours.get("term4") or colours.get("primary"), "80", "a2b174"),
            "terminal.ansi.magenta": hex_css(colours.get("term5") or colours.get("secondary"), "d3a343"),
            "terminal.ansi.bright_magenta": hex_css(colours.get("term13") or colours.get("secondaryFixed"), "e2b967"),
            "terminal.ansi.dim_magenta": hex_with_alpha(colours.get("term5") or colours.get("secondary"), "80", "d3a343"),
            "terminal.ansi.cyan": hex_css(colours.get("term6") or colours.get("surfaceTint"), "cbce78"),
            "terminal.ansi.bright_cyan": hex_css(colours.get("term14") or colours.get("secondaryFixedDim"), "e0e07e"),
            "terminal.ansi.dim_cyan": hex_with_alpha(colours.get("term6") or colours.get("surfaceTint"), "80", "cbce78"),
            "terminal.ansi.white": hex_css(colours.get("term7") or fg, "e0d8bf"),
            "terminal.ansi.bright_white": hex_css(colours.get("term15") or fg, "ffffff"),
            "terminal.ansi.dim_white": hex_with_alpha(colours.get("term7") or fg, "80", "e0d8bf"),
            "link_text.hover": hex_css(accent, "d3c876"),
            "conflict": hex_css(colours.get("tertiary") or colours.get("term3"), "ffe66f"),
            "conflict.background": hex_with_alpha(colours.get("tertiary") or colours.get("term3"), "15", "ffe66f"),
            "conflict.border": hex_css(colours.get("tertiary") or colours.get("term3"), "ffe66f"),
            "created": hex_css(colours.get("success") or colours.get("term2"), "dbcf4d"),
            "created.background": hex_with_alpha(colours.get("success") or colours.get("term2"), "15", "dbcf4d"),
            "created.border": hex_css(colours.get("success") or colours.get("term2"), "dbcf4d"),
            "deleted": hex_css(colours.get("error") or colours.get("term1"), "b48b00"),
            "deleted.background": hex_with_alpha(colours.get("error") or colours.get("term1"), "15", "b48b00"),
            "deleted.border": hex_css(colours.get("error") or colours.get("term1"), "b48b00"),
            "error": hex_css(colours.get("error"), "ffb4ab"),
            "error.background": hex_with_alpha(colours.get("error"), "15", "ffb4ab"),
            "error.border": hex_css(colours.get("error"), "ffb4ab"),
            "hidden": hex_css(muted, "969178"),
            "hidden.background": hex_with_alpha(muted, "15", "969178"),
            "hidden.border": hex_css(muted, "969178"),
            "hint": hex_css(colours.get("success"), "B5CCBA"),
            "hint.background": hex_with_alpha(colours.get("success"), "15", "B5CCBA"),
            "hint.border": hex_css(colours.get("success"), "B5CCBA"),
            "ignored": hex_css(muted, "969178"),
            "ignored.background": hex_with_alpha(muted, "15", "969178"),
            "ignored.border": hex_css(muted, "969178"),
            "info": hex_css(colours.get("primary") or accent, "ffffff"),
            "info.background": hex_with_alpha(colours.get("primary") or accent, "15", "ffffff"),
            "info.border": hex_css(colours.get("primary") or accent, "ffffff"),
            "modified": hex_css(colours.get("secondary") or accent, "d3c876"),
            "modified.background": hex_with_alpha(colours.get("secondary") or accent, "15", "d3c876"),
            "modified.border": hex_css(colours.get("secondary") or accent, "d3c876"),
            "predictive": hex_css(muted, "969178"),
            "predictive.background": hex_with_alpha(muted, "15", "969178"),
            "predictive.border": hex_with_alpha(muted_soft, "40", "54453c"),
            "renamed": hex_css(colours.get("term6") or colours.get("surfaceTint"), "cbce78"),
            "renamed.background": hex_with_alpha(colours.get("term6") or colours.get("surfaceTint"), "15", "cbce78"),
            "renamed.border": hex_css(colours.get("term6") or colours.get("surfaceTint"), "cbce78"),
            "success": hex_css(colours.get("success"), "B5CCBA"),
            "success.background": hex_with_alpha(colours.get("success"), "15", "B5CCBA"),
            "success.border": hex_css(colours.get("success"), "B5CCBA"),
            "unreachable": hex_css(muted, "969178"),
            "unreachable.background": hex_with_alpha(muted, "15", "969178"),
            "unreachable.border": hex_css(muted, "969178"),
            "warning": hex_css(colours.get("tertiary") or colours.get("term3"), "ffe66f"),
            "warning.background": hex_with_alpha(colours.get("tertiary") or colours.get("term3"), "15", "ffe66f"),
            "warning.border": hex_css(colours.get("tertiary") or colours.get("term3"), "ffe66f"),
        }
    )

    style["players"] = [
        {"cursor": hex_css(colours.get("term15") or fg, "ffffff"), "selection": hex_with_alpha(colours.get("term15") or fg, "60", "ffffff"), "background": hex_css(colours.get("term4"), "a2b174")},
        {"cursor": hex_css(colours.get("term10"), "eee145"), "selection": hex_with_alpha(colours.get("term10"), "40", "eee145"), "background": hex_css(colours.get("term10"), "eee145")},
        {"cursor": hex_css(colours.get("term13"), "e2b967"), "selection": hex_with_alpha(colours.get("term13"), "40", "e2b967"), "background": hex_css(colours.get("term13"), "e2b967")},
        {"cursor": hex_css(colours.get("term11"), "fff4cb"), "selection": hex_with_alpha(colours.get("term11"), "40", "fff4cb"), "background": hex_css(colours.get("term11"), "fff4cb")},
        {"cursor": hex_css(colours.get("term2"), "dbcf4d"), "selection": hex_with_alpha(colours.get("term2"), "40", "dbcf4d"), "background": hex_css(colours.get("term2"), "dbcf4d")},
        {"cursor": hex_css(colours.get("term1"), "b48b00"), "selection": hex_with_alpha(colours.get("term1"), "40", "b48b00"), "background": hex_css(colours.get("term1"), "b48b00")},
        {"cursor": hex_css(colours.get("term6"), "cbce78"), "selection": hex_with_alpha(colours.get("term6"), "40", "cbce78"), "background": hex_css(colours.get("term6"), "cbce78")},
        {"cursor": hex_css(colours.get("term9"), "d1a200"), "selection": hex_with_alpha(colours.get("term9"), "40", "d1a200"), "background": hex_css(colours.get("term9"), "d1a200")},
    ]

    syntax = style.setdefault("syntax", {})
    syntax_updates = {
        "attribute": hex_css(colours.get("term11") or colours.get("tertiary"), "fff4cb"),
        "boolean": hex_css(colours.get("term13") or colours.get("secondary"), "e2b967"),
        "comment": hex_css(muted, "969178"),
        "comment.doc": hex_css(muted, "969178"),
        "constant": hex_css(colours.get("term13") or colours.get("secondary"), "e2b967"),
        "constructor": hex_css(colours.get("term11") or colours.get("tertiary"), "fff4cb"),
        "embedded": hex_css(colours.get("term15") or fg, "ffffff"),
        "emphasis": hex_css(accent, "d3c876"),
        "enum": hex_css(colours.get("term4") or colours.get("primary"), "a2b174"),
        "function": hex_css(colours.get("term4") or colours.get("primary"), "a2b174"),
        "hint": hex_css(colours.get("success"), "B5CCBA"),
        "keyword": hex_css(accent, "d3c876"),
        "label": hex_css(colours.get("term6") or colours.get("surfaceTint"), "cbce78"),
        "link_text": hex_css(accent, "d3c876"),
        "number": hex_css(colours.get("term1") or colours.get("error"), "b48b00"),
        "operator": hex_css(colours.get("term14") or colours.get("secondaryFixedDim"), "e0e07e"),
        "predictive": hex_css(muted, "969178"),
        "preproc": hex_css(colours.get("term6") or colours.get("surfaceTint"), "cbce78"),
        "primary": hex_css(fg, "e8e2cf"),
        "property": hex_css(colours.get("term12") or colours.get("primaryFixed"), "c0c49a"),
        "punctuation": hex_css(muted, "969178"),
        "punctuation.bracket": hex_css(muted, "969178"),
        "punctuation.delimiter": hex_css(muted, "969178"),
        "punctuation.list_marker": hex_css(accent, "d3c876"),
        "string": hex_css(colours.get("term3") or colours.get("tertiary"), "ffe66f"),
        "string.escape": hex_css(colours.get("term6") or colours.get("surfaceTint"), "cbce78"),
        "string.regex": hex_css(colours.get("term10") or colours.get("success"), "eee145"),
        "tag": hex_css(colours.get("term4") or colours.get("primary"), "a2b174"),
        "text.literal": hex_css(fg, "e8e2cf"),
        "title": hex_css(accent, "d3c876"),
        "type": hex_css(colours.get("term12") or colours.get("primaryFixed"), "c0c49a"),
        "variable": hex_css(fg, "e8e2cf"),
        "variable.special": hex_css(colours.get("term1") or colours.get("error"), "b48b00"),
        "variant": hex_css(colours.get("term13") or colours.get("secondary"), "e2b967"),
    }
    for token, color in syntax_updates.items():
        entry = syntax.get(token)
        if not isinstance(entry, dict):
            entry = {}
        entry["color"] = color
        syntax[token] = entry

    write_file(ZED_THEME_PATH, json.dumps(data, indent=2) + "\n")


def render_steam(colours: dict[str, str]) -> None:
    if not STEAM_LIBRARYROOT_CUSTOM_CSS_PATH.exists():
        return

    ensure_line_after(
        STEAM_LIBRARYROOT_CUSTOM_CSS_PATH,
        '@import url("https://steamloopback.host/adwaita/custom/custom.css");',
        STEAM_DYNAMIC_IMPORT,
    )

    accent_bg = rgb_csv(colours.get("secondary") or colours.get("primary"), "d3c876")
    accent_fg = rgb_csv(colours.get("onSecondary") or colours.get("onPrimary"), "1d1b14")
    accent = rgb_csv(colours.get("secondaryFixed") or colours.get("primaryFixed") or colours.get("secondary"), "f0e58f")
    success_bg = rgb_csv(colours.get("success") or colours.get("term2"), "26a269")
    success_fg = rgb_csv(colours.get("onSuccess") or colours.get("onPrimary"), "213528")
    success = rgb_csv(colours.get("successContainer") or colours.get("term10") or colours.get("success"), "8ff0a4")
    warning_bg = rgb_csv(colours.get("tertiary") or colours.get("term3"), "cd9309")
    warning_fg = rgb_csv(colours.get("onTertiary") or colours.get("onPrimary"), "263500")
    warning = rgb_csv(colours.get("tertiaryContainer") or colours.get("term11") or colours.get("tertiary"), "f8e45c")
    error_bg = rgb_csv(colours.get("error"), "c01c28")
    error_fg = rgb_csv(colours.get("onError"), "690005")
    error = rgb_csv(colours.get("errorContainer") or colours.get("term9") or colours.get("error"), "ff7b63")
    window_bg = rgb_csv(colours.get("surface") or colours.get("background"), "151409")
    window_fg = rgb_csv(colours.get("onSurface") or colours.get("onBackground"), "e8e2cf")
    view_bg = rgb_csv(colours.get("surfaceContainerLow") or colours.get("surface"), "1d1c10")
    view_fg = window_fg
    headerbar_bg = rgb_csv(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), "222014")
    headerbar_fg = window_fg
    headerbar_border = rgb_csv(colours.get("outlineVariant") or colours.get("outline"), "4a4732")
    headerbar_backdrop = rgb_csv(colours.get("surfaceContainerLow") or colours.get("surface"), "1d1c10")
    sidebar_bg = rgb_csv(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), "222014")
    sidebar_fg = window_fg
    sidebar_backdrop = rgb_csv(colours.get("surfaceContainerLow") or colours.get("surface"), "1d1c10")
    secondary_sidebar_bg = rgb_csv(colours.get("surfaceContainerLow") or colours.get("surface"), "1d1c10")
    secondary_sidebar_fg = window_fg
    secondary_sidebar_backdrop = rgb_csv(colours.get("surfaceContainerLowest") or colours.get("surface"), "100e05")
    card_bg = rgb_csv(colours.get("surfaceContainerHighest") or colours.get("surfaceContainerHigh"), "373528")
    card_fg = window_fg
    dialog_bg = rgb_csv(colours.get("surfaceContainerHigh") or colours.get("surfaceContainer"), "2c2a1e")
    dialog_fg = window_fg
    popover_bg = rgb_csv(colours.get("surfaceContainerHigh") or colours.get("surfaceContainer"), "2c2a1e")
    popover_fg = window_fg
    thumbnail_bg = rgb_csv(colours.get("surfaceContainerHigh") or colours.get("surfaceContainer"), "2c2a1e")
    thumbnail_fg = window_fg

    write_file(
        STEAM_DYNAMIC_CSS_PATH,
        (
            "/* Generated by ~/scripts/system-theme-sync.py */\n"
            ":root {\n"
            f"    --adw-accent-bg-rgb: {accent_bg} !important;\n"
            f"    --adw-accent-fg-rgb: {accent_fg} !important;\n"
            f"    --adw-accent-rgb: {accent} !important;\n"
            f"    --adw-destructive-bg-rgb: {error_bg} !important;\n"
            f"    --adw-destructive-fg-rgb: {error_fg} !important;\n"
            f"    --adw-destructive-rgb: {error} !important;\n"
            f"    --adw-success-bg-rgb: {success_bg} !important;\n"
            f"    --adw-success-fg-rgb: {success_fg} !important;\n"
            f"    --adw-success-rgb: {success} !important;\n"
            f"    --adw-warning-bg-rgb: {warning_bg} !important;\n"
            f"    --adw-warning-fg-rgb: {warning_fg} !important;\n"
            "    --adw-warning-fg-a: 0.92 !important;\n"
            f"    --adw-warning-rgb: {warning} !important;\n"
            f"    --adw-error-bg-rgb: {error_bg} !important;\n"
            f"    --adw-error-fg-rgb: {error_fg} !important;\n"
            f"    --adw-error-rgb: {error} !important;\n"
            f"    --adw-window-bg-rgb: {window_bg} !important;\n"
            f"    --adw-window-fg-rgb: {window_fg} !important;\n"
            f"    --adw-view-bg-rgb: {view_bg} !important;\n"
            f"    --adw-view-fg-rgb: {view_fg} !important;\n"
            f"    --adw-headerbar-bg-rgb: {headerbar_bg} !important;\n"
            f"    --adw-headerbar-fg-rgb: {headerbar_fg} !important;\n"
            f"    --adw-headerbar-border-rgb: {headerbar_border} !important;\n"
            f"    --adw-headerbar-backdrop-rgb: {headerbar_backdrop} !important;\n"
            f"    --adw-sidebar-bg-rgb: {sidebar_bg} !important;\n"
            f"    --adw-sidebar-fg-rgb: {sidebar_fg} !important;\n"
            f"    --adw-sidebar-backdrop-rgb: {sidebar_backdrop} !important;\n"
            f"    --adw-secondary-sidebar-bg-rgb: {secondary_sidebar_bg} !important;\n"
            f"    --adw-secondary-sidebar-fg-rgb: {secondary_sidebar_fg} !important;\n"
            f"    --adw-secondary-sidebar-backdrop-rgb: {secondary_sidebar_backdrop} !important;\n"
            f"    --adw-card-bg-rgb: {card_bg} !important;\n"
            f"    --adw-card-fg-rgb: {card_fg} !important;\n"
            f"    --adw-dialog-bg-rgb: {dialog_bg} !important;\n"
            f"    --adw-dialog-fg-rgb: {dialog_fg} !important;\n"
            f"    --adw-popover-bg-rgb: {popover_bg} !important;\n"
            f"    --adw-popover-fg-rgb: {popover_fg} !important;\n"
            f"    --adw-thumbnail-bg-rgb: {thumbnail_bg} !important;\n"
            f"    --adw-thumbnail-fg-rgb: {thumbnail_fg} !important;\n"
            "    --adw-card-bg-a: 0.10 !important;\n"
            "    --adw-banner-bg-a: 0.22 !important;\n"
            "    --adw-shade-a: 0.24 !important;\n"
            "    --adw-sidebar-shade-a: 0.18 !important;\n"
            "    --adw-popover-shade-a: 0.20 !important;\n"
            "}\n"
        ),
    )


def render_vscode(colours: dict[str, str]) -> None:
    if not CODE_SETTINGS_PATH.exists():
        return

    settings = json.loads(CODE_SETTINGS_PATH.read_text(encoding="utf-8"))
    bg = hex_css(colours.get("surface") or colours.get("background"), "151409")
    bg_alt = hex_css(colours.get("surfaceContainer") or colours.get("surfaceContainerLow"), "222014")
    bg_soft = hex_css(colours.get("surfaceContainerHigh") or colours.get("surfaceContainer"), "2c2a1e")
    fg = hex_css(colours.get("onSurface") or colours.get("onBackground"), "e8e2cf")
    muted = hex_css(colours.get("outline") or colours.get("outlineVariant"), "969178")
    accent = hex_css(colours.get("secondary") or colours.get("primary"), "d3c876")
    accent_soft = rgba_css(colours.get("secondary") or colours.get("primary"), 0.16, "d3c876")
    error = hex_css(colours.get("error"), "ffb4ab")

    settings["workbench.colorCustomizations"] = {
        "editor.background": bg,
        "editor.foreground": fg,
        "sideBar.background": bg_alt,
        "sideBar.foreground": fg,
        "activityBar.background": bg,
        "activityBar.foreground": fg,
        "activityBarBadge.background": accent,
        "activityBarBadge.foreground": bg,
        "titleBar.activeBackground": bg,
        "titleBar.activeForeground": fg,
        "statusBar.background": bg_alt,
        "statusBar.foreground": fg,
        "statusBar.debuggingBackground": accent,
        "statusBar.debuggingForeground": bg,
        "list.activeSelectionBackground": accent_soft,
        "list.inactiveSelectionBackground": accent_soft,
        "list.hoverBackground": rgba_css(colours.get("onSurface"), 0.08, "e8e2cf"),
        "editorGroupHeader.tabsBackground": bg,
        "tab.activeBackground": bg_alt,
        "tab.inactiveBackground": bg,
        "tab.activeForeground": fg,
        "tab.inactiveForeground": muted,
        "panel.background": bg,
        "panel.border": muted,
        "input.background": bg_soft,
        "input.foreground": fg,
        "input.border": muted,
        "button.background": accent,
        "button.foreground": bg,
        "button.hoverBackground": hex_css(colours.get("secondaryContainer") or colours.get("secondary"), "a79f5d"),
        "focusBorder": accent,
        "textLink.foreground": accent,
        "terminal.foreground": fg,
        "terminal.background": bg,
        "terminalCursor.foreground": accent,
        "terminal.ansiBlack": hex_css(colours.get("term0") or bg_soft, "353433"),
        "terminal.ansiRed": hex_css(colours.get("term1") or colours.get("error"), "b48b00"),
        "terminal.ansiGreen": hex_css(colours.get("term2") or colours.get("success"), "dbcf4d"),
        "terminal.ansiYellow": hex_css(colours.get("term3") or colours.get("tertiary"), "ffe66f"),
        "terminal.ansiBlue": hex_css(colours.get("term4") or colours.get("primary"), "a2b174"),
        "terminal.ansiMagenta": hex_css(colours.get("term5") or colours.get("secondary"), "d3a343"),
        "terminal.ansiCyan": hex_css(colours.get("term6") or colours.get("surfaceTint") or colours.get("secondaryFixedDim"), "cbce78"),
        "terminal.ansiWhite": hex_css(colours.get("term7") or fg, "e0d8bf"),
        "terminal.ansiBrightBlack": hex_css(colours.get("term8") or muted, "a9a290"),
        "terminal.ansiBrightRed": hex_css(colours.get("term9") or colours.get("errorContainer"), "d1a200"),
        "terminal.ansiBrightGreen": hex_css(colours.get("term10") or colours.get("successContainer"), "eee145"),
        "terminal.ansiBrightYellow": hex_css(colours.get("term11") or colours.get("tertiaryContainer"), "fff4cb"),
        "terminal.ansiBrightBlue": hex_css(colours.get("term12") or colours.get("primaryFixed"), "c0c49a"),
        "terminal.ansiBrightMagenta": hex_css(colours.get("term13") or colours.get("secondaryFixed"), "e2b967"),
        "terminal.ansiBrightCyan": hex_css(colours.get("term14") or colours.get("secondaryFixedDim"), "e0e07e"),
        "terminal.ansiBrightWhite": hex_css(colours.get("term15") or colours.get("inverseSurface"), "ffffff"),
        "errorForeground": error,
    }
    settings["editor.tokenColorCustomizations"] = {
        "comments": muted,
        "textMateRules": [
            {
                "scope": ["keyword", "storage.type", "storage.modifier"],
                "settings": {"foreground": accent},
            },
            {
                "scope": ["string", "string.quoted"],
                "settings": {"foreground": hex_css(colours.get("tertiary"), "ffd27a")},
            },
            {
                "scope": ["entity.name.function", "support.function"],
                "settings": {"foreground": hex_css(colours.get("primary"), "ffffff")},
            },
            {
                "scope": ["constant.numeric", "constant.language"],
                "settings": {"foreground": hex_css(colours.get("error"), "ffb4ab")},
            },
        ],
    }
    write_file(CODE_SETTINGS_PATH, json.dumps(settings, indent=4) + "\n")


def sync_once() -> bool:
    data = load_scheme()
    if not data:
        return False

    colours = data.get("colours")
    if not isinstance(colours, dict):
        return False

    render_hyprland(colours)
    render_hyprlock(colours)
    render_gtk(colours)
    render_rofi(colours)
    render_shell_theme(colours)
    render_foot(colours)
    render_zen(colours)
    render_kde(colours)
    render_spicetify(colours)
    render_steam(colours)
    render_zed(colours)
    ensure_discord_theme_targets()
    for path in DISCORD_THEME_PATHS:
        patch_discord_theme(path, colours)
    render_vscode(colours)
    return True


def watch(interval: float) -> int:
    last_mtime_ns = None
    while True:
        try:
            mtime_ns = SCHEME_PATH.stat().st_mtime_ns
        except FileNotFoundError:
            mtime_ns = None

        if mtime_ns != last_mtime_ns:
            sync_once()
            last_mtime_ns = mtime_ns

        time.sleep(max(interval, 0.2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync system theme files to the current Caelestia wallpaper palette.")
    parser.add_argument("--watch", action="store_true", help="watch the scheme file and keep syncing on changes")
    parser.add_argument("--interval", type=float, default=1.0, help="poll interval in seconds when watching")
    args = parser.parse_args()

    sync_once()
    if args.watch:
        return watch(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
